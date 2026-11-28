"""四段式执行器（demo）：A 数据 → B 模型加载 → C 批处理/断点 → D 指数拟合。

- A：把合成 fixture 转成 ``Batch``，附 manifest（as_of/行数/哈希）。
- B：注册模块并做加载报告；demo 用内存注册表，不启真实 worker。
- C：按 chunk 执行图，原子落盘 + manifest；支持从已完成 chunk 恢复。
- D：按市值权重合成指数估值（demo 口径），输出覆盖与区间。

只依赖标准库；与 :mod:`valnet.graph` 的执行器解耦，生产版可替换为常驻 worker。
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from .graph import GraphResult, execute
from .modules import (
    ALL_MODULES,
    COMPARABLE,
    DCM,
    DCF,
    INDUSTRY_BASELINE,
    SENTIMENT,
)
from .pooling import linear_pool, pool_intervals
from .spec import Batch, EdgeSpec, GraphSpec, Interval, ModuleSpec, NodeSpec, PoolSpec

#: demo 版本；进入 manifest。
STAGE_VERSION = "0.1.0"


# ---------------------------------------------------------------------------
# A. 数据资料收集
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StageAOutput:
    """A 段产物：类型化 Batch + 可追溯 manifest。"""

    batch: Batch
    manifest: dict[str, object]


def _derive_features(features: Mapping[str, list[float | None]]) -> dict[str, list[float | None]]:
    """从现有 fixture 派生 DCM 输入（demo 口径；生产由 A 段源适配器提供）。"""
    out = {name: list(values) for name, values in features.items()}
    out["dcm_base"] = list(out.get("dcf_base", []))
    out["discount"] = list(out.get("wacc", []))
    return out


def stage_a(
    features: Mapping[str, list[float | None]],
    masks: Mapping[str, list[bool]],
    ids: Sequence[str],
    meta: Mapping[str, object] | None = None,
) -> StageAOutput:
    """构造 Batch 与 manifest；manifest 用 feature 名/行数/哈希做指纹。"""
    derived = _derive_features(features)
    derived_masks = {name: list(values) for name, values in masks.items()}
    derived_masks["has_dcm"] = list(derived_masks.get("has_dcf", [True] * len(ids)))
    batch = Batch(ids=list(ids), features=derived, masks=derived_masks, meta=dict(meta or {}))
    payload = json.dumps(
        {"ids": batch.ids, "features": derived, "masks": derived_masks, "meta": batch.meta},
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    manifest: dict[str, object] = {
        "stage": "A",
        "version": STAGE_VERSION,
        "rows": len(ids),
        "as_of": (meta or {}).get("as_of"),
        "feature_names": sorted(derived),
        "mask_names": sorted(derived_masks),
        "digest": hashlib.sha256(payload).hexdigest()[:16],
    }
    return StageAOutput(batch=batch, manifest=manifest)


# ---------------------------------------------------------------------------
# B. 模型层加载
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StageBOutput:
    """B 段产物：模块注册表 + 加载报告。"""

    modules: Mapping[str, ModuleSpec]
    loaded: tuple[str, ...]
    failed: tuple[str, ...]

    @property
    def count(self) -> int:
        return len(self.loaded)


def stage_b(modules: Iterable[ModuleSpec] = ALL_MODULES) -> StageBOutput:
    """加载模块；这里只做声明校验与注册（demo 不启 worker）。

    生产版在这里做参数包解析、依赖检查、预热与健康检查；加载失败只禁用该模块。
    """
    registry: dict[str, ModuleSpec] = {}
    loaded: list[str] = []
    failed: list[str] = []
    for module in modules:
        try:
            if not isinstance(module, ModuleSpec):
                raise TypeError("not a ModuleSpec")
            if module.name in registry:
                raise ValueError(f"duplicate module {module.name}")
            registry[module.name] = module
            loaded.append(module.name)
        except Exception:
            failed.append(getattr(module, "name", "<unknown>"))
    return StageBOutput(modules=registry, loaded=tuple(loaded), failed=tuple(failed))


# ---------------------------------------------------------------------------
# C. 批处理 + 断点恢复
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BatchReport:
    """C 段产物：合并后的逐券结果 + 断点统计。"""

    ids: tuple[str, ...]
    values: tuple[float | None, ...]
    intervals: tuple[Interval, ...]
    confidence: tuple[float | None, ...]
    chunks_total: int
    chunks_done: int
    executed_chunks: int
    trace_status: Mapping[str, str] = field(default_factory=dict)

    @property
    def covered(self) -> int:
        return sum(value is not None for value in self.values)


def _chunk_path(root: Path, chunk_id: int) -> Path:
    return root / f"chunk_{chunk_id:04d}.json"


def _atomic_write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _slice_batch(batch: Batch, positions: Sequence[int]) -> Batch:
    return Batch(
        ids=[batch.ids[position] for position in positions],
        features={
            name: [values[position] for position in positions]
            for name, values in batch.features.items()
        },
        masks={
            name: [values[position] for position in positions]
            for name, values in batch.masks.items()
        },
        meta=dict(batch.meta),
    )


def _chunk_payload(chunk_id: int, result: GraphResult, ids: Sequence[str]) -> dict[str, object]:
    return {
        "chunk": chunk_id,
        "ids": list(ids),
        "values": list(result.values),
        "intervals": [
            None if interval is None else [interval[0], interval[1]]
            for interval in result.intervals
        ],
        "confidence": list(result.confidence),
        "trace_status": result.trace.statuses(),
        "pool_weights": dict(result.pool_weights),
    }


def stage_c(
    graph: GraphSpec,
    batch: Batch,
    out_dir: str | Path,
    batch_id: str,
    chunk_size: int = 2,
    resume: bool = True,
) -> BatchReport:
    """按 chunk 执行；每个 chunk 原子落盘，manifest 记录状态；可恢复。

    - ``resume=True`` 时，manifest 中 ``done`` 且 chunk 文件存在的块跳过。
    - 返回的 ``executed_chunks`` 是本次实际执行的块数，便于测试恢复语义。
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size 必须为正")
    root = Path(out_dir) / batch_id
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = root / "manifest.json"
    total = (len(batch) + chunk_size - 1) // chunk_size
    status: dict[str, str] = {}
    if resume and manifest_path.exists():
        try:
            prior = _read_json(manifest_path)
            if isinstance(prior, dict) and isinstance(prior.get("status"), dict):
                status = {str(key): str(value) for key, value in prior["status"].items()}
        except Exception:
            status = {}

    executed = 0
    for chunk_id in range(total):
        key = str(chunk_id)
        chunk_file = _chunk_path(root, chunk_id)
        if resume and status.get(key) == "done" and chunk_file.exists():
            continue
        positions = list(range(chunk_id * chunk_size, min((chunk_id + 1) * chunk_size, len(batch))))
        sub_batch = _slice_batch(batch, positions)
        result = execute(graph, sub_batch)
        _atomic_write(chunk_file, _chunk_payload(chunk_id, result, sub_batch.ids))
        status[key] = "done"
        _atomic_write(
            manifest_path,
            {
                "stage": "C",
                "version": STAGE_VERSION,
                "batch_id": batch_id,
                "chunk_size": chunk_size,
                "total": total,
                "status": status,
            },
        )
        executed += 1

    ids: list[str] = []
    values: list[float | None] = []
    intervals: list[Interval] = []
    confidence: list[float | None] = []
    trace_status: dict[str, str] = {}
    for chunk_id in range(total):
        payload = _read_json(_chunk_path(root, chunk_id))
        if not isinstance(payload, dict):
            raise ValueError(f"chunk {chunk_id} 不是对象")
        ids.extend(str(item) for item in payload["ids"])
        values.extend(payload["values"])
        for interval in payload["intervals"]:
            intervals.append(None if interval is None else (float(interval[0]), float(interval[1])))
        confidence.extend(payload["confidence"])
        for node, state in (payload.get("trace_status") or {}).items():
            trace_status[str(node)] = str(state)

    return BatchReport(
        ids=tuple(ids),
        values=tuple(values),
        intervals=tuple(intervals),
        confidence=tuple(confidence),
        chunks_total=total,
        chunks_done=sum(1 for state in status.values() if state == "done"),
        executed_chunks=executed,
        trace_status=trace_status,
    )


# ---------------------------------------------------------------------------
# D. 指数选择与拟合
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IndexFit:
    """D 段产物：demo 口径的指数估值。"""

    value: float | None
    interval: Interval
    covered: int
    total: int
    weights: Mapping[str, float]


def stage_d(
    report: BatchReport,
    batch: Batch,
    weight_feature: str = "market_cap",
) -> IndexFit:
    """按权重合成指数估值（demo 口径：逐券估值加权平均）。"""
    caps = batch.features.get(weight_feature)
    if caps is None:
        raise ValueError(f"Batch 缺少权重 feature {weight_feature!r}")
    values: list[float] = []
    weights: list[float] = []
    intervals: list[Interval] = []
    weight_map: dict[str, float] = {}
    for position, security in enumerate(report.ids):
        cap = caps[position]
        value = report.values[position]
        if cap is None or value is None:
            continue
        values.append(value)
        weights.append(cap)
        intervals.append(report.intervals[position])
        weight_map[security] = cap
    total_weight = sum(weights)
    return IndexFit(
        value=linear_pool(values, weights),
        interval=pool_intervals(intervals, weights, "linear"),
        covered=len(values),
        total=len(report.ids),
        weights={key: (value / total_weight if total_weight else 0.0) for key, value in weight_map.items()},
    )


def demo_batch() -> Batch:
    """构造带 DCM 输入的 3 家合成公司 Batch（供 stages runner/tests 使用）。"""
    from .runner import DEMO_COMPANIES, FEATURE_NAMES, MASK_NAMES, build_batch

    batch = build_batch()
    features = {name: list(values) for name, values in batch.features.items()}
    features["dcm_base"] = list(features.get("dcf_base", []))
    features["discount"] = list(features.get("wacc", []))
    masks = {name: list(values) for name, values in batch.masks.items()}
    masks["has_dcm"] = [True] * len(batch)
    return Batch(ids=batch.ids, features=features, masks=masks, meta=batch.meta)


def demo_graph() -> GraphSpec:
    """带 DCF/DCM/可比/舆情残差的 demo 图（四路池化）。"""
    baseline = NodeSpec(id="industry_baseline", spec=INDUSTRY_BASELINE)
    dcf = NodeSpec(id="dcf", spec=DCF)
    dcm = NodeSpec(id="dcm", spec=DCM)
    comparable = NodeSpec(id="comparable", spec=COMPARABLE)
    sentiment = NodeSpec(
        id="sentiment", spec=SENTIMENT, deps=("industry_baseline",), residual_alpha=0.5
    )
    return GraphSpec(
        name="vcg-stages",
        nodes=(baseline, dcf, dcm, comparable, sentiment),
        edges=(EdgeSpec(src="industry_baseline", dst="sentiment"),),
        pool=PoolSpec(
            kind="linear",
            weights=(("dcf", 0.30), ("dcm", 0.20), ("comparable", 0.30), ("sentiment", 0.20)),
        ),
        output="fair_value",
        version="0.1.0",
    )
