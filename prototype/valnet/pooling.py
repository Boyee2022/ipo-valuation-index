"""池化语义：线性池 / 对数池 / 专家乘积，以及区间与置信度合成。

所有函数都是纯函数，输入是"逐成分券对齐"的序列：

- ``values`` / ``confidence`` 为标量序列，``weights`` 等长；
- ``intervals`` 为 ``(lo, hi) | None`` 序列；
- ``None`` 值（缺失 / 门控 / 失败）按对跳过，剩余权重按池化方式处理；
- ``log`` 与 ``product`` 要求非 ``None`` 值严格为正，否则抛 :class:`PoolingError`。

语义说明：

- **linear**：``Σ w_i v_i / Σ w_i``（逐券对有效权重再归一）。
- **log**：``exp(Σ w_i ln v_i / Σ w_i)``，即加权几何平均；权重整体缩放不改变结果。
- **product**：``exp(Σ w_i ln v_i)``，权重是证据/对数密度指数、**不归一**；
  若权重和恰为 1，则与 log 数值等价。这是对"专家乘积"的简化，见 README。

区间按端点用同一种池化方式独立合成；这忽略了模块间相关性，是原型的已知简化。
置信度始终用线性池（置信度本身不是可几何平均的估值量）。
"""

from __future__ import annotations

import math
from typing import Sequence

from .spec import Interval, PoolKind, Scalar

#: 置信度 / 权重的类型别名（允许 None 权重，表示该成员本次不参与）。
Weight = float | None


class PoolingError(ValueError):
    """池化输入非法：长度不一致、负权重、非正值参与 log/product 等。"""


def _validate_inputs(
    values: Sequence[Scalar], weights: Sequence[Weight]
) -> list[tuple[float, float]]:
    """校验输入并返回有效 ``(value, weight)`` 对；跳过含 None 的对。"""
    if len(values) != len(weights):
        raise PoolingError(
            f"values 长度 {len(values)} != weights 长度 {len(weights)}"
        )
    pairs: list[tuple[float, float]] = []
    for position, (value, weight) in enumerate(zip(values, weights)):
        if weight is not None:
            if isinstance(weight, bool) or not isinstance(weight, (int, float)):
                raise PoolingError(f"权重必须是数或 None，位置 {position} 收到 {weight!r}")
            if not math.isfinite(float(weight)) or float(weight) < 0.0:
                raise PoolingError(
                    f"权重必须是非负有限数，位置 {position} 收到 {weight!r}"
                )
        if value is None or weight is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise PoolingError(f"值必须是数或 None，位置 {position} 收到 {value!r}")
        if not math.isfinite(float(value)):
            raise PoolingError(f"值必须是有限数，位置 {position} 收到 {value!r}")
        pairs.append((float(value), float(weight)))
    return pairs


def _require_positive(pairs: Sequence[tuple[float, float]], operation: str) -> None:
    """log / product 池化要求所有有效值 > 0。"""
    for value, _ in pairs:
        if value <= 0.0:
            raise PoolingError(
                f"{operation} 池化要求所有值 > 0，收到 {value!r}"
            )


def linear_pool(values: Sequence[Scalar], weights: Sequence[Weight]) -> float | None:
    """线性池：``Σ w_i v_i / Σ w_i``；无有效成员或权重和为 0 时返回 ``None``。"""
    pairs = _validate_inputs(values, weights)
    total = sum(weight for _, weight in pairs)
    if not pairs or total <= 0.0:
        return None
    return math.fsum(value * weight for value, weight in pairs) / total


def log_pool(values: Sequence[Scalar], weights: Sequence[Weight]) -> float | None:
    """对数池：``exp(Σ w_i ln v_i / Σ w_i)``（加权几何平均）。

    要求所有有效值 > 0；无有效成员或权重和为 0 时返回 ``None``。
    """
    pairs = _validate_inputs(values, weights)
    total = sum(weight for _, weight in pairs)
    if not pairs or total <= 0.0:
        return None
    _require_positive(pairs, "log")
    log_sum = math.fsum(weight * math.log(value) for value, weight in pairs)
    return math.exp(log_sum / total)


def product_pool(
    values: Sequence[Scalar],
    weights: Sequence[Weight],
    *,
    normalize_weights: bool = False,
) -> float | None:
    """专家乘积：``exp(Σ w_i ln v_i)``；``normalize_weights=True`` 时除以权重和。

    权重是证据/对数密度指数，默认不归一，因此与 :func:`log_pool` 区分；
    当 ``normalize_weights=True`` 或权重和恰为 1 时两者数值等价。
    要求所有有效值 > 0；无有效成员或权重和为 0 时返回 ``None``。
    """
    pairs = _validate_inputs(values, weights)
    total = sum(weight for _, weight in pairs)
    if not pairs or total <= 0.0:
        return None
    _require_positive(pairs, "product")
    log_sum = math.fsum(weight * math.log(value) for value, weight in pairs)
    if normalize_weights:
        log_sum /= total
    return math.exp(log_sum)


def pool_values(
    kind: PoolKind, values: Sequence[Scalar], weights: Sequence[Weight]
) -> float | None:
    """按池化方式分派到线性池 / 对数池 / 专家乘积。"""
    if kind == "linear":
        return linear_pool(values, weights)
    if kind == "log":
        return log_pool(values, weights)
    if kind == "product":
        return product_pool(values, weights)
    raise PoolingError(f"未知池化方式 {kind!r}")


def pool_intervals(
    intervals: Sequence[Interval],
    weights: Sequence[Weight],
    kind: PoolKind = "linear",
) -> Interval:
    """区间传播：对下界、上界分别用同一池化方式合成，跳过 ``None`` 区间。

    线性池下等价于端点加权平均；对数池 / 专家乘积下等价于端点几何合成。
    若没有有效区间或权重和为 0 返回 ``None``；log/product 要求端点 > 0。
    """
    if len(intervals) != len(weights):
        raise PoolingError(
            f"intervals 长度 {len(intervals)} != weights 长度 {len(weights)}"
        )
    valid: list[tuple[float, float, float]] = []
    for position, (interval, weight) in enumerate(zip(intervals, weights)):
        if weight is not None:
            if isinstance(weight, bool) or not isinstance(weight, (int, float)):
                raise PoolingError(
                    f"权重必须是数或 None，位置 {position} 收到 {weight!r}"
                )
            if not math.isfinite(float(weight)) or float(weight) < 0.0:
                raise PoolingError(
                    f"权重必须是非负有限数，位置 {position} 收到 {weight!r}"
                )
        if interval is None or weight is None:
            continue
        if not isinstance(interval, (tuple, list)) or len(interval) != 2:
            raise PoolingError(f"区间必须是 (lo, hi) 二元组，位置 {position}")
        low, high = interval
        if not all(
            isinstance(item, (int, float))
            and not isinstance(item, bool)
            and math.isfinite(float(item))
            for item in (low, high)
        ):
            raise PoolingError(f"区间端点必须是有限数，位置 {position}")
        if float(low) > float(high):
            raise PoolingError(f"区间下界大于上界，位置 {position}")
        valid.append((float(low), float(high), float(weight)))
    total = sum(weight for _, _, weight in valid)
    if not valid or total <= 0.0:
        return None

    if kind == "linear":
        low = math.fsum(low * weight for low, _, weight in valid) / total
        high = math.fsum(high * weight for _, high, weight in valid) / total
        return (low, high)
    if kind in ("log", "product"):
        for low, high, _ in valid:
            if low <= 0.0 or high <= 0.0:
                raise PoolingError(
                    f"{kind} 区间传播要求端点 > 0，收到 ({low!r}, {high!r})"
                )
        if kind == "log":
            low = math.exp(
                math.fsum(weight * math.log(low) for low, _, weight in valid) / total
            )
            high = math.exp(
                math.fsum(weight * math.log(high) for _, high, weight in valid) / total
            )
        else:
            low = math.exp(
                math.fsum(weight * math.log(low) for low, _, weight in valid)
            )
            high = math.exp(
                math.fsum(weight * math.log(high) for _, high, weight in valid)
            )
        return (low, high)
    raise PoolingError(f"未知池化方式 {kind!r}")


def pool_confidence(
    confidence: Sequence[Scalar], weights: Sequence[Weight]
) -> float | None:
    """置信度合成：始终用线性池；无有效成员返回 ``None``。"""
    return linear_pool(confidence, weights)
