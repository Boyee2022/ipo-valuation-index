"""VCG 原型 DAG 执行器。

职责（与 ``docs/v2/02-architecture.md`` 的"图执行器"对应）：

1. **校验**：节点 id 唯一、依赖存在、``edges`` 与 ``deps`` 一致、池化成员合法；
2. **拓扑排序**：Kahn 算法，按节点声明顺序确定性地打破平局；有环报错；
3. **门控**：门控值逐券为 0 的券不进入模块（模块只在活跃子批上执行），
   节点级门控优先于模块默认门控；全部门控为 0 时节点跳过；
4. **残差**：``residual_alpha != 0`` 的节点按
   ``norm(base + α * module_output)`` 合成；``norm`` 是 winsorize stub；
5. **失败隔离**：单个节点（含门控函数）抛异常只把该节点输出置 ``None`` 并记
   trace，不中断整图；下游看到的是"依赖缺失"；
6. **池化**：按 :class:`~valnet.spec.PoolSpec` 对节点输出做线性/对数/专家乘积
   合成，同时合成区间与置信度；
7. **审计**：返回不可变的 :class:`ExecutionTrace`，逐节点记录状态、门控数、
   残差数与错误信息。

确定性：无随机、无时间戳、拓扑顺序固定；同输入同输出，可逐字段比较。
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass
from typing import Any, Mapping

from .pooling import (
    PoolingError,
    pool_confidence,
    pool_intervals,
    pool_values,
)
from .spec import (
    Batch,
    GraphSpec,
    Interval,
    ModuleOutput,
    NodeSpec,
    Scalar,
)

#: 残差归一化 stub 的 winsorize 比例：单步模块调整最多把基线拉动 ±50%。
RESIDUAL_CLIP = 0.5

#: trace 状态常量。
STATUS_OK = "ok"
STATUS_GATED = "gated"
STATUS_FAILED = "failed"


class GraphError(Exception):
    """执行器错误基类（图校验失败、池化失败等）。"""


class GraphValidationError(GraphError):
    """图结构非法：边不一致、池化成员不存在等。"""


class MissingDependencyError(GraphValidationError):
    """依赖或池化成员引用了不存在的节点。"""


class CycleError(GraphValidationError):
    """图中存在环，无法拓扑排序。"""


class DuplicateNodeError(GraphValidationError):
    """节点 id 重复。"""


@dataclass(frozen=True)
class TraceEntry:
    """单个节点的执行 trace。"""

    order: int
    node_id: str
    module_name: str
    module_version: str
    kind: str
    deps: tuple[str, ...]
    residual_alpha: float
    status: str
    gated_count: int = 0
    residual_count: int = 0
    residual_base_missing: int = 0
    value_count: int = 0
    error: str | None = None


@dataclass(frozen=True)
class ExecutionTrace:
    """整图执行 trace：拓扑顺序 + 逐节点条目 + 池化信息。"""

    graph_name: str
    graph_version: str
    topology: tuple[str, ...]
    pool_kind: str
    output: str
    entries: tuple[TraceEntry, ...]

    def entry(self, node_id: str) -> TraceEntry:
        """按节点 id 取 trace 条目；不存在时抛 ``KeyError``。"""
        for item in self.entries:
            if item.node_id == node_id:
                return item
        raise KeyError(f"trace 中没有节点 {node_id!r}")

    def statuses(self) -> dict[str, str]:
        """节点 id -> 状态（按拓扑顺序）。"""
        return {item.node_id: item.status for item in self.entries}

    @property
    def failed_nodes(self) -> tuple[str, ...]:
        """执行失败的节点 id。"""
        return tuple(item.node_id for item in self.entries if item.status == STATUS_FAILED)

    @property
    def gated_nodes(self) -> tuple[str, ...]:
        """因全部门控为 0 而整体跳过的节点 id。"""
        return tuple(item.node_id for item in self.entries if item.status == STATUS_GATED)


@dataclass(frozen=True)
class GraphResult:
    """图执行结果：合成值 + 逐节点输出 + 池化权重 + trace。"""

    output: str
    values: list[Scalar]
    intervals: list[Interval]
    confidence: list[Scalar]
    outputs: dict[str, ModuleOutput | None]
    pool_weights: dict[str, float]
    trace: ExecutionTrace

    def __len__(self) -> int:
        return len(self.values)

    @property
    def value_count(self) -> int:
        """有合成值的券数。"""
        return sum(value is not None for value in self.values)

    def node_output(self, node_id: str) -> ModuleOutput | None:
        """取某节点的输出；节点不存在时抛 ``KeyError``。"""
        try:
            return self.outputs[node_id]
        except KeyError:
            raise KeyError(f"结果中没有节点 {node_id!r}") from None


def _node_index(nodes: tuple[NodeSpec, ...]) -> dict[str, int]:
    """节点 id -> 声明下标；重复 id 报错。"""
    index: dict[str, int] = {}
    duplicates: list[str] = []
    for position, node in enumerate(nodes):
        if node.id in index:
            duplicates.append(node.id)
        index[node.id] = position
    if duplicates:
        raise DuplicateNodeError(f"节点 id 重复：{sorted(set(duplicates))}")
    return index


def topological_order(graph: GraphSpec) -> tuple[str, ...]:
    """返回确定性的拓扑顺序；依赖缺失报 ``MissingDependencyError``，有环报 ``CycleError``。"""
    if not isinstance(graph, GraphSpec):
        raise TypeError("topological_order 需要 GraphSpec")
    index = _node_index(graph.nodes)
    for node in graph.nodes:
        for dep in node.deps:
            if dep not in index:
                raise MissingDependencyError(
                    f"节点 {node.id!r} 依赖不存在的节点 {dep!r}"
                )

    indegree = {node.id: len(node.deps) for node in graph.nodes}
    children: dict[str, list[str]] = {node.id: [] for node in graph.nodes}
    for node in graph.nodes:
        for dep in node.deps:
            children[dep].append(node.id)

    # 就绪节点用声明下标做堆键，保证同层节点顺序完全确定。
    ready: list[int] = [
        index[node.id] for node in graph.nodes if indegree[node.id] == 0
    ]
    heapq.heapify(ready)
    order: list[str] = []
    while ready:
        node = graph.nodes[heapq.heappop(ready)]
        order.append(node.id)
        for child in children[node.id]:
            indegree[child] -= 1
            if indegree[child] == 0:
                heapq.heappush(ready, index[child])

    if len(order) != len(graph.nodes):
        cyclic = [node.id for node in graph.nodes if indegree[node.id] > 0]
        raise CycleError(f"检测到环，无法拓扑排序；涉及节点：{cyclic}")
    return tuple(order)


def validate_graph(graph: GraphSpec) -> tuple[str, ...]:
    """完整校验图结构并返回拓扑顺序。"""
    if not isinstance(graph, GraphSpec):
        raise TypeError("validate_graph 需要 GraphSpec")
    index = _node_index(graph.nodes)
    for node in graph.nodes:
        for dep in node.deps:
            if dep not in index:
                raise MissingDependencyError(
                    f"节点 {node.id!r} 依赖不存在的节点 {dep!r}"
                )

    declared = [(edge.src, edge.dst) for edge in graph.edges]
    if len(set(declared)) != len(declared):
        raise GraphValidationError("edges 含重复边")
    expected = {
        (dep, node.id) for node in graph.nodes for dep in node.deps
    }
    declared_set = set(declared)
    missing = expected - declared_set
    extra = declared_set - expected
    if missing or extra:
        raise GraphValidationError(
            f"edges 与节点 deps 不一致：缺少 {sorted(missing)}，多余 {sorted(extra)}"
        )

    for member in graph.pool.members:
        if member not in index:
            raise MissingDependencyError(
                f"池化成员 {member!r} 不是图节点"
            )

    return topological_order(graph)


def bounded_residual(
    upstream: float,
    module: float,
    alpha: float,
    *,
    clip: float = RESIDUAL_CLIP,
) -> float:
    """残差归一化 stub：``norm(upstream + alpha * (module - upstream))``。

    这里把 ``norm`` 实现为对"单步偏离"做 winsorize：

    - ``delta = module - upstream``；
    - ``delta`` 截断到 ``±clip * max(|upstream|, 1e-12)``；
    - 返回 ``upstream + alpha * delta``。

    目的：模块只应做有界调整，防止单个模块把估值整体翻转。生产版应替换为
    按行业/量纲定义的真实归一化算子，见 README 已知简化。
    """
    for label, value in (("upstream", upstream), ("module", module), ("alpha", alpha)):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TypeError(f"{label} 必须是数值")
        if not math.isfinite(float(value)):
            raise ValueError(f"{label} 必须是有限数")
    if not math.isfinite(float(clip)) or clip <= 0.0:
        raise ValueError("clip 必须是正的有限数")
    scale = abs(float(upstream))
    limit = clip * scale if scale > 1e-12 else clip
    delta = float(module) - float(upstream)
    clipped = max(-limit, min(limit, delta))
    return float(upstream) + float(alpha) * clipped


def _active_indices(raw_gate: Any, size: int) -> list[int]:
    """校验门控返回值并返回活跃下标（门控值 > 0）。"""
    if isinstance(raw_gate, (str, bytes)) or not isinstance(raw_gate, (list, tuple)):
        raise TypeError(
            f"门控必须返回 list[float]，收到 {type(raw_gate).__name__}"
        )
    values = list(raw_gate)
    if len(values) != size:
        raise ValueError(f"门控返回长度 {len(values)} != 批大小 {size}")
    active: list[int] = []
    for position, value in enumerate(values):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"门控值必须是数，位置 {position} 收到 {value!r}")
        number = float(value)
        if not math.isfinite(number) or not 0.0 <= number <= 1.0:
            raise ValueError(f"门控值必须在 [0, 1]，位置 {position} 收到 {number}")
        if number > 0.0:
            active.append(position)
    return active


def _error_text(error: BaseException) -> str:
    """统一的 trace 错误文本。"""
    return f"{type(error).__name__}: {error}"


def _entry(
    node: NodeSpec,
    order: int,
    status: str,
    *,
    gated_count: int = 0,
    residual_count: int = 0,
    residual_base_missing: int = 0,
    value_count: int = 0,
    error: str | None = None,
) -> TraceEntry:
    """构造 trace 条目。"""
    return TraceEntry(
        order=order,
        node_id=node.id,
        module_name=node.spec.name,
        module_version=node.spec.version,
        kind=node.spec.kind,
        deps=node.deps,
        residual_alpha=node.residual_alpha,
        status=status,
        gated_count=gated_count,
        residual_count=residual_count,
        residual_base_missing=residual_base_missing,
        value_count=value_count,
        error=error,
    )


def _inherit_output(base: ModuleOutput, node: NodeSpec) -> ModuleOutput:
    """全部门控为 0 时，残差节点继承基线输出。"""
    return ModuleOutput(
        values=list(base.values),
        intervals=list(base.intervals),
        confidence=list(base.confidence),
        evidence=list(base.evidence) + [
            f"gate: 节点 {node.id!r} 全部门控为 0，继承残差基线 "
            f"{node.deps[0]!r} 的输出"
        ],
        diagnostics=dict(base.diagnostics, gate_inherited=True, node=node.id),
    )


def _apply_residual(
    output: ModuleOutput,
    base: ModuleOutput | None,
    node: NodeSpec,
    active: list[int],
) -> tuple[ModuleOutput, int, int]:
    """对节点输出应用残差层，返回 ``(新输出, 残差生效数, 基线缺失数)``。

    规则：

    - 门控剔除的券：继承基线值/区间/置信度；
    - 活跃券：``norm(base + α * module)``，区间端点做同样变换；
    - 基线节点缺失或某券基线值为 ``None``：该券无法形成残差，输出 ``None``
      （严格语义：残差基数是必要条件）。
    """
    size = len(output)
    alpha = node.residual_alpha
    baseline_dep = node.deps[0]
    active_set = set(active)

    if base is None:
        evidence = list(output.evidence) + [
            f"residual: 基线 {baseline_dep!r} 无输出，节点 {node.id!r} 输出降级为空"
        ]
        diagnostics = dict(output.diagnostics)
        diagnostics.update(
            {"residual_skipped": True, "residual_alpha": alpha, "baseline": baseline_dep}
        )
        return (
            ModuleOutput(
                values=[None] * size,
                intervals=[None] * size,
                confidence=[None] * size,
                evidence=evidence,
                diagnostics=diagnostics,
            ),
            0,
            size,
        )

    values: list[Scalar] = [None] * size
    intervals: list[Interval] = [None] * size
    confidence: list[Scalar] = [None] * size
    residual_count = 0
    base_missing = 0

    for position in range(size):
        base_value = base.values[position]
        if position not in active_set:
            # 门控剔除：继承基线（有残差才有继承语义）。
            if base_value is None:
                base_missing += 1
                continue
            values[position] = base_value
            intervals[position] = base.intervals[position]
            confidence[position] = base.confidence[position]
            residual_count += 1
            continue

        module_value = output.values[position]
        if base_value is None:
            base_missing += 1
            continue
        if module_value is None:
            continue
        values[position] = bounded_residual(base_value, module_value, alpha)
        interval = output.intervals[position]
        if interval is not None:
            low = bounded_residual(base_value, interval[0], alpha)
            high = bounded_residual(base_value, interval[1], alpha)
            intervals[position] = (min(low, high), max(low, high))
        confidence[position] = output.confidence[position]
        residual_count += 1

    evidence = list(output.evidence) + [
        f"residual: α={alpha:g}，基线={baseline_dep!r}，"
        f"winsorize=±{RESIDUAL_CLIP:.0%}"
    ]
    diagnostics = dict(output.diagnostics)
    diagnostics.update(
        {
            "residual_alpha": alpha,
            "residual_count": residual_count,
            "residual_base_missing": base_missing,
        }
    )
    return (
        ModuleOutput(
            values=values,
            intervals=intervals,
            confidence=confidence,
            evidence=evidence,
            diagnostics=diagnostics,
        ),
        residual_count,
        base_missing,
    )


def _run_node(
    node: NodeSpec,
    batch: Batch,
    outputs: dict[str, ModuleOutput | None],
    order: int,
) -> tuple[ModuleOutput | None, TraceEntry]:
    """执行单个节点；任何异常都被隔离为该节点输出 ``None``。"""
    size = len(batch)
    gate = node.resolved_gate
    active = list(range(size))

    if gate is not None:
        try:
            active = _active_indices(gate(batch), size)
        except Exception as error:  # noqa: BLE001 - 失败隔离是执行器职责
            return None, _entry(
                node, order, STATUS_FAILED, error=_error_text(error)
            )

    upstream: dict[str, ModuleOutput] = {
        dep: outputs[dep]
        for dep in node.deps
        if outputs.get(dep) is not None
    }

    if not active:
        # 全部门控为 0：残差节点继承基线，其余节点跳过。
        if node.residual_alpha != 0.0:
            base = upstream.get(node.deps[0])
            if base is not None:
                inherited = _inherit_output(base, node)
                return inherited, _entry(
                    node,
                    order,
                    STATUS_GATED,
                    gated_count=size,
                    residual_count=inherited.value_count,
                    value_count=inherited.value_count,
                )
        return None, _entry(node, order, STATUS_GATED, gated_count=size)

    subset = len(active) != size
    try:
        if subset:
            sub_batch = batch.select(active)
            sub_upstream = {
                dep: output.select(active) for dep, output in upstream.items()
            }
            partial = node.spec.apply(sub_batch, sub_upstream)
            output = partial.expand(size, active)
        else:
            output = node.spec.apply(batch, upstream)
    except Exception as error:  # noqa: BLE001 - 失败隔离是执行器职责
        return None, _entry(
            node,
            order,
            STATUS_FAILED,
            gated_count=size - len(active),
            error=_error_text(error),
        )

    residual_count = 0
    base_missing = 0
    if node.residual_alpha != 0.0:
        base = upstream.get(node.deps[0])
        output, residual_count, base_missing = _apply_residual(
            output, base, node, active
        )

    return output, _entry(
        node,
        order,
        STATUS_OK,
        gated_count=size - len(active),
        residual_count=residual_count,
        residual_base_missing=base_missing,
        value_count=output.value_count,
    )


def _pool_outputs(
    graph: GraphSpec, outputs: Mapping[str, ModuleOutput | None], size: int
) -> tuple[list[Scalar], list[Interval], list[Scalar]]:
    """逐券合成 values / intervals / confidence；池化输入非法时抛 ``GraphError``。"""
    pool = graph.pool
    weights = [weight for _, weight in pool.weights]
    values: list[Scalar] = []
    intervals: list[Interval] = []
    confidence: list[Scalar] = []

    for position in range(size):
        member_values: list[Scalar] = []
        member_intervals: list[Interval] = []
        member_confidence: list[Scalar] = []
        for node_id, _ in pool.weights:
            output = outputs.get(node_id)
            if output is None:
                member_values.append(None)
                member_intervals.append(None)
                member_confidence.append(None)
            else:
                member_values.append(output.values[position])
                member_intervals.append(output.intervals[position])
                member_confidence.append(output.confidence[position])
        try:
            values.append(pool_values(pool.kind, member_values, weights))
            intervals.append(pool_intervals(member_intervals, weights, pool.kind))
            confidence.append(pool_confidence(member_confidence, weights))
        except PoolingError as error:
            raise GraphError(
                f"池化失败（security={position}，pool={pool.kind}）：{error}"
            ) from error
    return values, intervals, confidence


def execute(graph: GraphSpec, batch: Batch) -> GraphResult:
    """执行整图。

    步骤：校验结构 -> 拓扑排序 -> 按序执行（门控/残差/失败隔离）-> 池化 -> 返回
    :class:`GraphResult`。节点异常不阻断整图；池化输入非法会抛 :class:`GraphError`。

    参数：
        graph: 图声明。
        batch: 输入批；输出长度与 ``len(batch)`` 一致。

    返回：
        ``GraphResult``（逐券合成值、区间、置信度、逐节点输出、池化权重、trace）。
    """
    if not isinstance(graph, GraphSpec):
        raise TypeError("execute 需要 GraphSpec")
    if not isinstance(batch, Batch):
        raise TypeError("execute 需要 Batch")

    topology = validate_graph(graph)
    node_by_id = {node.id: node for node in graph.nodes}
    outputs: dict[str, ModuleOutput | None] = {}
    entries: list[TraceEntry] = []

    for order, node_id in enumerate(topology):
        node = node_by_id[node_id]
        output, entry = _run_node(node, batch, outputs, order)
        outputs[node_id] = output
        entries.append(entry)

    values, intervals, confidence = _pool_outputs(graph, outputs, len(batch))
    trace = ExecutionTrace(
        graph_name=graph.name,
        graph_version=graph.version,
        topology=topology,
        pool_kind=graph.pool.kind,
        output=graph.output,
        entries=tuple(entries),
    )
    return GraphResult(
        output=graph.output,
        values=values,
        intervals=intervals,
        confidence=confidence,
        outputs=outputs,
        pool_weights=graph.pool.normalized_weights(),
        trace=trace,
    )
