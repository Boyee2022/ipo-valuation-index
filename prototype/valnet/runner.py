"""示例 runner：3 家公司的 monitoring 图，打印逐券输出与指数合成。

运行（在 ``prototype/`` 目录下）::

    python3 -m valnet.runner

数据是**硬编码的合成 fixture**，公司名与数值均为演示虚构，不对应真实证券。
图结构::

    industry_baseline (encoder)          # 行业基准，残差基线
            │
            ▼
    sentiment (valuation, residual α=0.5)
    dcf (valuation)      comparable (valuation)
            └──────┬──────────┬───────────┘
                   ▼
              linear pool  -> fair_value（逐券合成）
                   ▼
        市值加权 -> 指数合成（演示口径）

其中 C003 无可比数据：``comparable`` 被 mask 门控跳过，``sentiment`` 回退行业
基准；池化按剩余权重再归一。这正是原型要演示的跳过/兜底路径。
"""

from __future__ import annotations

from dataclasses import dataclass

from .graph import GraphResult, execute
from .modules import COMPARABLE, DCF, INDUSTRY_BASELINE, SENTIMENT
from .pooling import linear_pool, pool_intervals
from .spec import Batch, EdgeSpec, GraphSpec, Interval, NodeSpec, PoolSpec

#: 硬编码的 3 家演示公司（合成数据，元/股；market_cap 为演示权重，单位任意）。
DEMO_COMPANIES: tuple[dict[str, object], ...] = (
    {
        "id": "C001",
        "name": "云岭酒业",
        "dcf_base": 78.0,
        "growth": 0.06,
        "wacc": 0.09,
        "earnings": 4.0,
        "peer_pe_1": 19.0,
        "peer_pe_2": 21.0,
        "peer_pe_3": 23.0,
        "sentiment_adj": 0.03,
        "industry_median": 82.0,
        "market_cap": 2000.0,
    },
    {
        "id": "C002",
        "name": "远星电池",
        "dcf_base": 45.0,
        "growth": 0.18,
        "wacc": 0.11,
        "earnings": 2.0,
        "peer_pe_1": 18.0,
        "peer_pe_2": 24.0,
        "peer_pe_3": 30.0,
        "sentiment_adj": 0.05,
        "industry_median": 46.0,
        "market_cap": 1200.0,
    },
    {
        "id": "C003",
        "name": "寂野科技",
        "dcf_base": 30.0,
        "growth": 0.25,
        "wacc": 0.12,
        "earnings": 1.0,
        # 关键演示点：无可比 → 无可比 PE，comparable 被门控跳过。
        "peer_pe_1": None,
        "peer_pe_2": None,
        "peer_pe_3": None,
        "sentiment_adj": -0.02,
        "industry_median": 36.0,
        "market_cap": 500.0,
        "has_comparable": False,
    },
)

#: Batch.features 中参与演示的通道（market_cap 只用于 runner 的指数合成）。
FEATURE_NAMES: tuple[str, ...] = (
    "dcf_base",
    "growth",
    "wacc",
    "earnings",
    "peer_pe_1",
    "peer_pe_2",
    "peer_pe_3",
    "sentiment_adj",
    "industry_median",
    "market_cap",
)

#: Batch.masks 中参与演示的通道（缺省 True）。
MASK_NAMES: tuple[str, ...] = (
    "has_dcf",
    "has_comparable",
    "has_sentiment",
    "has_industry_baseline",
)


@dataclass(frozen=True)
class IndexComposite:
    """指数合成结果（市值加权，演示口径）。"""

    value: float | None
    interval: Interval
    covered: int
    total: int


def _number(company: dict[str, object], key: str) -> float | None:
    """从 fixture 取数值字段；缺失/None 返回 ``None``。"""
    value = company.get(key)
    return None if value is None else float(value)


def build_batch() -> Batch:
    """把硬编码 fixture 转成 :class:`~valnet.spec.Batch`。"""
    ids = [str(company["id"]) for company in DEMO_COMPANIES]
    features = {
        name: [_number(company, name) for company in DEMO_COMPANIES]
        for name in FEATURE_NAMES
    }
    masks = {
        name: [
            bool(company.get(name, True)) for company in DEMO_COMPANIES
        ]
        for name in MASK_NAMES
    }
    return Batch(
        ids=ids,
        features=features,
        masks=masks,
        meta={
            "as_of": "2026-11-28",
            "universe": "DEMO-3",
            "currency": "CNY",
            "names": {
                str(company["id"]): str(company["name"])
                for company in DEMO_COMPANIES
            },
            "note": "合成 fixture，仅用于 VCG 原型演示",
        },
    )


def build_monitoring_graph() -> GraphSpec:
    """构建示例 monitoring 图（基线 + DCF + 可比 + 舆情残差 + 线性池）。"""
    baseline = NodeSpec(id="industry_baseline", spec=INDUSTRY_BASELINE)
    dcf = NodeSpec(id="dcf", spec=DCF)
    comparable = NodeSpec(id="comparable", spec=COMPARABLE)
    sentiment = NodeSpec(
        id="sentiment",
        spec=SENTIMENT,
        deps=("industry_baseline",),
        residual_alpha=0.5,
    )
    return GraphSpec(
        name="vcg-monitoring",
        nodes=(baseline, dcf, comparable, sentiment),
        edges=(EdgeSpec(src="industry_baseline", dst="sentiment"),),
        pool=PoolSpec(
            kind="linear",
            weights=(("dcf", 0.40), ("comparable", 0.35), ("sentiment", 0.25)),
        ),
        output="fair_value",
        version="0.1.0",
    )


def compose_index(
    result: GraphResult,
    batch: Batch,
    weight_feature: str = "market_cap",
) -> IndexComposite:
    """按市值权重合成"指数估值"（演示口径：逐券合成值的加权平均）。"""
    caps = batch.features.get(weight_feature)
    if caps is None:
        raise ValueError(f"Batch 缺少权重 feature {weight_feature!r}")
    values: list[float] = []
    weights: list[float] = []
    intervals: list[Interval] = []
    for position in range(len(batch)):
        cap = caps[position]
        value = result.values[position]
        if cap is None or value is None:
            continue
        values.append(value)
        weights.append(cap)
        intervals.append(result.intervals[position])
    return IndexComposite(
        value=linear_pool(values, weights),
        interval=pool_intervals(intervals, weights, "linear"),
        covered=len(values),
        total=len(batch),
    )


def _format_number(value: float | None, digits: int = 2) -> str:
    """数值格式化；``None`` 显示为 "—"。"""
    return "—" if value is None else f"{value:.{digits}f}"


def _format_interval(interval: Interval, digits: int = 2) -> str:
    """区间格式化。"""
    if interval is None:
        return "—"
    return f"[{interval[0]:.{digits}f}, {interval[1]:.{digits}f}]"


def _node_lines(
    result: GraphResult, node_id: str, label: str, position: int
) -> list[str]:
    """格式化一个节点的逐券输出行。"""
    output = result.node_output(node_id)
    if output is None:
        return [f"    {label:<8} = —（节点无输出）"]
    return [
        f"    {label:<8} = {_format_number(output.values[position])}"
        f"  区间 {_format_interval(output.intervals[position])}"
        f"  conf={_format_number(output.confidence[position])}"
    ]


def format_report(
    result: GraphResult, batch: Batch, composite: IndexComposite
) -> str:
    """生成可读的逐券 + 指数合成报告文本（确定性，不含时间戳）。"""
    lines: list[str] = [
        f"VCG prototype · {result.trace.graph_name} v{result.trace.graph_version}",
        f"as_of={batch.meta.get('as_of', '—')}  "
        f"universe={batch.meta.get('universe', '—')}  "
        f"pool={result.trace.pool_kind}  output={result.output}",
        "",
        "逐券输出（元/股，合成数据；区间与置信度为 stub）",
    ]
    names = batch.meta.get("names", {})
    for position, security_id in enumerate(batch.ids):
        name = names.get(security_id, "") if isinstance(names, dict) else ""
        lines.append(f"[{position + 1}] {security_id} {name}")
        lines.extend(_node_lines(result, "industry_baseline", "行业基准", position))
        lines.extend(_node_lines(result, "dcf", "DCF", position))
        lines.extend(_node_lines(result, "comparable", "可比", position))
        lines.extend(_node_lines(result, "sentiment", "舆情/残差", position))
        lines.append(
            f"    {result.output:<8} = {_format_number(result.values[position])}"
            f"  区间 {_format_interval(result.intervals[position])}"
            f"  conf={_format_number(result.confidence[position])}"
        )

    lines.append("")
    lines.append("执行 trace（拓扑顺序）")
    for entry in result.trace.entries:
        details = [f"values={entry.value_count}/{len(batch)}"]
        if entry.gated_count:
            details.append(f"gated={entry.gated_count}")
        if entry.residual_alpha:
            details.append(
                f"α={entry.residual_alpha:g} residual={entry.residual_count}"
            )
        if entry.residual_base_missing:
            details.append(f"base_missing={entry.residual_base_missing}")
        if entry.error is not None:
            details.append(f"error={entry.error}")
        lines.append(
            f"  {entry.order:02d} {entry.node_id:<18} {entry.kind:<10} "
            f"{entry.status:<6} " + " ".join(details)
        )
    gated = result.trace.gated_nodes
    lines.append(
        "  门控整体跳过的节点："
        + (", ".join(gated) if gated else "无")
    )

    lines.append("")
    lines.append("指数合成（市值加权平均，演示口径，非真实指数点位）")
    lines.append(
        f"  覆盖 {composite.covered}/{composite.total} 家；"
        f"指数值={_format_number(composite.value)}；"
        f"区间={_format_interval(composite.interval)}"
    )
    lines.append("")
    lines.append(
        "说明：合成 fixture；缺可比的公司由 mask 门控跳过可比法，"
        "舆情回退行业基准，池化按剩余权重再归一；无 LLM、无生产代码依赖。"
    )
    return "\n".join(lines)


def main() -> int:
    """构建并执行示例图，打印报告。"""
    batch = build_batch()
    graph = build_monitoring_graph()
    result = execute(graph, batch)
    composite = compose_index(result, batch)
    print(format_report(result, batch, composite))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
