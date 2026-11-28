"""四个 stub 估值模块：DCF / Comparable / Sentiment / IndustryBaseline。

**演示用，不做真实估值。** 公式故意极简，只为验证图执行器、门控、残差与池化：

- ``DCF``：``base * (1 + growth) / (1 + wacc)``，区间 ±20%；
- ``Comparable``：``median(peer_pe_1..3) * earnings``，区间 ±25%；
- ``Sentiment``：``peer_median * (1 + adjustment)``，区间 ±10%；
  缺失可比时回退 ``industry_median``（并在 evidence/diagnostics 标注）；
- ``IndustryBaseline``：``industry_median``，区间 ±15%，作为舆情模块的残差基线。

输入约定（由 ``Batch.features`` 提供，均按券排列）：

=====================  ====================================================
feature                含义
=====================  ====================================================
``dcf_base``           DCF 基期每股价值（元/股）
``growth``             显式期增长率（小数）
``wacc``               折现率（小数）
``earnings``           每股收益（元/股）
``peer_pe_1..3``       三家可比公司的 PE
``sentiment_adj``      舆情调整比例（小数）
``industry_median``    行业中位估值（元/股）
=====================  ====================================================

mask 约定：``has_dcf`` / ``has_comparable`` / ``has_sentiment`` /
``has_industry_baseline``；缺失 mask 视为全部可用。mask 同时作为模块默认门控：
不可用的券不进入模块执行。
"""

from __future__ import annotations

import math
from typing import Mapping, Sequence

from .spec import Batch, Interval, ModuleOutput, ModuleSpec, Scalar

#: 模块版本；进入 trace 用于审计。
VERSION = "0.1.0"

#: DCF 输入特征。
F_DCF_BASE = "dcf_base"
F_GROWTH = "growth"
F_WACC = "wacc"
#: 可比公司 PE 输入特征（取可用者的中位数）。
F_PEER_PE: tuple[str, ...] = ("peer_pe_1", "peer_pe_2", "peer_pe_3")
#: 每股收益。
F_EARNINGS = "earnings"
#: 舆情调整比例。
F_SENTIMENT_ADJ = "sentiment_adj"
#: 行业中位估值。
F_INDUSTRY_MEDIAN = "industry_median"

#: 数据可用性 mask。
M_HAS_DCF = "has_dcf"
M_HAS_COMPARABLE = "has_comparable"
M_HAS_SENTIMENT = "has_sentiment"
M_HAS_INDUSTRY_BASELINE = "has_industry_baseline"

#: 各模块区间半宽（相对值）。
DCF_INTERVAL_PCT = 0.20
COMPARABLE_INTERVAL_PCT = 0.25
SENTIMENT_INTERVAL_PCT = 0.10
BASELINE_INTERVAL_PCT = 0.15


def _size(batch: Batch) -> int:
    return len(batch)


def _feature(batch: Batch, name: str, position: int) -> Scalar:
    """取某券的 feature 值；feature 不存在时返回 ``None``。"""
    values = batch.features.get(name)
    if values is None:
        return None
    return values[position]


def _available(batch: Batch, mask_name: str, position: int) -> bool:
    """取某券 mask；mask 不存在视为可用。"""
    flags = batch.masks.get(mask_name)
    return True if flags is None else flags[position]


def _median(values: Sequence[float]) -> float | None:
    """中位数（偶数个取中间两数均值）；空序列返回 ``None``。"""
    ordered = sorted(values)
    count = len(ordered)
    if count == 0:
        return None
    middle = count // 2
    if count % 2 == 1:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def _interval(value: float, half_width: float) -> Interval:
    """按相对半宽构造区间；负数也能保证下界不大于上界。"""
    low, high = value * (1.0 - half_width), value * (1.0 + half_width)
    return (min(low, high), max(low, high))


def _mask_gate(mask_name: str):
    """由 mask 生成默认门控：可用返回 1.0，不可用返回 0.0。"""

    def gate(batch: Batch) -> list[float]:
        return [
            1.0 if _available(batch, mask_name, position) else 0.0
            for position in range(_size(batch))
        ]

    gate.__name__ = f"gate_{mask_name}"
    return gate


def run_dcf(
    batch: Batch, upstream: Mapping[str, ModuleOutput]
) -> ModuleOutput:
    """DCF stub：``base * (1 + growth) / (1 + wacc)``。"""
    values: list[Scalar] = []
    intervals: list[Interval] = []
    confidence: list[Scalar] = []
    computed = 0
    missing = 0
    invalid = 0

    for position in range(_size(batch)):
        base = _feature(batch, F_DCF_BASE, position)
        growth = _feature(batch, F_GROWTH, position)
        wacc = _feature(batch, F_WACC, position)
        if (
            base is None
            or growth is None
            or wacc is None
            or not _available(batch, M_HAS_DCF, position)
        ):
            missing += 1
            values.append(None)
            intervals.append(None)
            confidence.append(None)
            continue
        if wacc <= -1.0:
            invalid += 1
            values.append(None)
            intervals.append(None)
            confidence.append(None)
            continue
        value = base * (1.0 + growth) / (1.0 + wacc)
        if not math.isfinite(value) or value <= 0.0:
            invalid += 1
            values.append(None)
            intervals.append(None)
            confidence.append(None)
            continue
        computed += 1
        values.append(value)
        intervals.append(_interval(value, DCF_INTERVAL_PCT))
        confidence.append(0.75)

    return ModuleOutput(
        values=values,
        intervals=intervals,
        confidence=confidence,
        evidence=[
            f"DCF v{VERSION}: value = dcf_base*(1+growth)/(1+wacc)，"
            f"区间 ±{DCF_INTERVAL_PCT:.0%}，n={computed}/{_size(batch)}"
        ],
        diagnostics={
            "module": "dcf",
            "computed": computed,
            "missing": missing,
            "invalid": invalid,
            "interval_pct": DCF_INTERVAL_PCT,
        },
    )


def run_comparable(
    batch: Batch, upstream: Mapping[str, ModuleOutput]
) -> ModuleOutput:
    """可比公司 stub：``median(peer_pe_1..3) * earnings``。"""
    values: list[Scalar] = []
    intervals: list[Interval] = []
    confidence: list[Scalar] = []
    computed = 0
    missing = 0

    for position in range(_size(batch)):
        earnings = _feature(batch, F_EARNINGS, position)
        peers = [
            value
            for name in F_PEER_PE
            if (value := _feature(batch, name, position)) is not None
        ]
        if (
            not _available(batch, M_HAS_COMPARABLE, position)
            or earnings is None
            or not peers
        ):
            missing += 1
            values.append(None)
            intervals.append(None)
            confidence.append(None)
            continue
        peer_median = _median(peers)
        if peer_median is None:
            missing += 1
            values.append(None)
            intervals.append(None)
            confidence.append(None)
            continue
        value = peer_median * earnings
        if not math.isfinite(value) or value <= 0.0:
            missing += 1
            values.append(None)
            intervals.append(None)
            confidence.append(None)
            continue
        computed += 1
        values.append(value)
        intervals.append(_interval(value, COMPARABLE_INTERVAL_PCT))
        # 可比家数越多，置信度略高（stub 规则，非统计校准）。
        confidence.append(min(0.90, 0.50 + 0.10 * len(peers)))

    return ModuleOutput(
        values=values,
        intervals=intervals,
        confidence=confidence,
        evidence=[
            f"Comparable v{VERSION}: value = median(peer PE)*earnings，"
            f"区间 ±{COMPARABLE_INTERVAL_PCT:.0%}，n={computed}/{_size(batch)}"
        ],
        diagnostics={
            "module": "comparable",
            "computed": computed,
            "missing": missing,
            "interval_pct": COMPARABLE_INTERVAL_PCT,
        },
    )


def run_sentiment(
    batch: Batch, upstream: Mapping[str, ModuleOutput]
) -> ModuleOutput:
    """舆情 stub：``peer_implied_median * (1 + adjustment)``，缺失可比时回退行业中位。

    ``peer_implied_median = median(peer_pe_1..3) * earnings``（可比法隐含估值中枢）；
    没有可用可比时用 ``industry_median`` 作为兜底中枢。
    """
    values: list[Scalar] = []
    intervals: list[Interval] = []
    confidence: list[Scalar] = []
    computed = 0
    fallback = 0
    missing = 0

    for position in range(_size(batch)):
        adjustment = _feature(batch, F_SENTIMENT_ADJ, position)
        earnings = _feature(batch, F_EARNINGS, position)
        peers = [
            value
            for name in F_PEER_PE
            if (value := _feature(batch, name, position)) is not None
        ]
        if not _available(batch, M_HAS_SENTIMENT, position) or adjustment is None:
            missing += 1
            values.append(None)
            intervals.append(None)
            confidence.append(None)
            continue
        peer_pe_median = _median(peers)
        peer_implied = (
            peer_pe_median * earnings
            if peer_pe_median is not None and earnings is not None
            else None
        )
        used_fallback = peer_implied is None
        base = peer_implied
        if used_fallback:
            base = _feature(batch, F_INDUSTRY_MEDIAN, position)
            if base is not None and not _available(
                batch, M_HAS_INDUSTRY_BASELINE, position
            ):
                base = None
        if base is None:
            missing += 1
            values.append(None)
            intervals.append(None)
            confidence.append(None)
            continue
        value = base * (1.0 + adjustment)
        if not math.isfinite(value) or value <= 0.0:
            missing += 1
            values.append(None)
            intervals.append(None)
            confidence.append(None)
            continue
        computed += 1
        if used_fallback:
            fallback += 1
        values.append(value)
        intervals.append(_interval(value, SENTIMENT_INTERVAL_PCT))
        confidence.append(0.35 if used_fallback else 0.55)

    return ModuleOutput(
        values=values,
        intervals=intervals,
        confidence=confidence,
        evidence=[
            f"Sentiment v{VERSION}: value = peer_implied_median*(1+adj)，"
            f"区间 ±{SENTIMENT_INTERVAL_PCT:.0%}，"
            f"n={computed}/{_size(batch)}（其中 {fallback} 家回退行业基准）"
        ],
        diagnostics={
            "module": "sentiment",
            "computed": computed,
            "fallback_industry": fallback,
            "missing": missing,
            "interval_pct": SENTIMENT_INTERVAL_PCT,
        },
    )


def run_industry_baseline(
    batch: Batch, upstream: Mapping[str, ModuleOutput]
) -> ModuleOutput:
    """行业基准 stub：``industry_median``，作为舆情残差模块的基线。"""
    values: list[Scalar] = []
    intervals: list[Interval] = []
    confidence: list[Scalar] = []
    computed = 0
    missing = 0

    for position in range(_size(batch)):
        median = _feature(batch, F_INDUSTRY_MEDIAN, position)
        if median is None or not _available(
            batch, M_HAS_INDUSTRY_BASELINE, position
        ):
            missing += 1
            values.append(None)
            intervals.append(None)
            confidence.append(None)
            continue
        computed += 1
        values.append(median)
        intervals.append(_interval(median, BASELINE_INTERVAL_PCT))
        confidence.append(0.50)

    return ModuleOutput(
        values=values,
        intervals=intervals,
        confidence=confidence,
        evidence=[
            f"IndustryBaseline v{VERSION}: value = industry_median，"
            f"区间 ±{BASELINE_INTERVAL_PCT:.0%}，n={computed}/{_size(batch)}"
        ],
        diagnostics={
            "module": "industry_baseline",
            "computed": computed,
            "missing": missing,
            "interval_pct": BASELINE_INTERVAL_PCT,
        },
    )


#: 可直接挂到 :class:`~valnet.spec.NodeSpec` 的四个 stub 模块。
DCF = ModuleSpec(
    name="dcf",
    kind="valuation",
    version=VERSION,
    inputs=(F_DCF_BASE, F_GROWTH, F_WACC),
    outputs=("value", "interval", "confidence"),
    run=run_dcf,
    gate=_mask_gate(M_HAS_DCF),
)

COMPARABLE = ModuleSpec(
    name="comparable",
    kind="valuation",
    version=VERSION,
    inputs=(F_EARNINGS, *F_PEER_PE),
    outputs=("value", "interval", "confidence"),
    run=run_comparable,
    gate=_mask_gate(M_HAS_COMPARABLE),
)

SENTIMENT = ModuleSpec(
    name="sentiment",
    kind="valuation",
    version=VERSION,
    inputs=(F_SENTIMENT_ADJ, F_EARNINGS, *F_PEER_PE, F_INDUSTRY_MEDIAN),
    outputs=("value", "interval", "confidence"),
    run=run_sentiment,
    gate=_mask_gate(M_HAS_SENTIMENT),
)

INDUSTRY_BASELINE = ModuleSpec(
    name="industry_baseline",
    kind="encoder",
    version=VERSION,
    inputs=(F_INDUSTRY_MEDIAN,),
    outputs=("value", "interval", "confidence"),
    run=run_industry_baseline,
    gate=_mask_gate(M_HAS_INDUSTRY_BASELINE),
)

#: 四个 stub 模块的注册表（按声明顺序，便于审计打印）。
ALL_MODULES: tuple[ModuleSpec, ...] = (
    DCF,
    COMPARABLE,
    SENTIMENT,
    INDUSTRY_BASELINE,
)
