"""VCG（Valuation Computation Graph）原型的类型化数据契约。

本模块只定义数据结构，不含执行逻辑；执行器见 :mod:`valnet.graph`，池化见
:mod:`valnet.pooling`。

- :class:`Batch`：一批成分券的输入（``ids`` / ``features`` / ``masks`` / ``meta``）。
- :class:`ModuleOutput`：模块输出（值 / 区间 / 置信度 / 证据 / 诊断）。
- :class:`ModuleSpec`：模块协议（名称、类型、版本、输入输出声明、``run``、``gate``）。
- :class:`NodeSpec` / :class:`EdgeSpec`：图节点与边。
- :class:`PoolSpec` / :class:`GraphSpec`：池化声明与整图声明。

设计原则：frozen dataclass、无全局可变状态、无随机、只用标准库。
所有按券排列的字段（``values`` / ``intervals`` / ``confidence``）长度必须等于
``len(batch)``；构造时校验，执行器只消费这里声明的类型。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable, Literal, Mapping, Sequence

#: 逐券标量：估值、置信度等；``None`` 表示该券不可用（缺失 / 门控 / 失败）。
Scalar = float | None
#: 闭区间；``None`` 表示无区间。
Interval = tuple[float, float] | None
#: feature 名 -> 按券排列的标量列表。
FeatureMap = dict[str, list[Scalar]]
#: mask 名 -> 按券排列的布尔列表。
MaskMap = dict[str, list[bool]]

#: 模块类型。encoder 产表示/基线，valuation 产估值，gate 产路由信号，
#: pool 做合成，critic 是评审层（原型未实现）。
ModuleKind = Literal["encoder", "valuation", "gate", "pool", "critic"]
MODULE_KINDS: frozenset[str] = frozenset(
    {"encoder", "valuation", "gate", "pool", "critic"}
)

#: 池化方式：线性池 / 对数池 / 专家乘积。
PoolKind = Literal["linear", "log", "product"]
POOL_KINDS: frozenset[str] = frozenset({"linear", "log", "product"})

#: 模块执行函数签名：``run(batch, upstream) -> ModuleOutput``。
ModuleRun = Callable[["Batch", Mapping[str, "ModuleOutput"]], "ModuleOutput"]
#: 门控函数签名：``gate(batch) -> list[float]``，逐券返回 [0, 1] 权重，0 表示跳过。
ModuleGate = Callable[["Batch"], list[float]]


def _is_real(value: object) -> bool:
    """判断是否为有限的 ``int`` / ``float``（显式排除 ``bool``）。"""
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _check_indices(indices: Sequence[int], size: int, *, unique: bool = True) -> list[int]:
    """校验下标列表：整数、在 ``range(size)`` 内、可选去重。"""
    result = list(indices)
    for index in result:
        if not isinstance(index, int) or isinstance(index, bool):
            raise TypeError(f"下标必须是 int，收到 {type(index).__name__}")
        if index < 0 or index >= size:
            raise IndexError(f"下标越界：{index}，批大小 {size}")
    if unique and len(set(result)) != len(result):
        raise ValueError("下标列表不能有重复值")
    return result


@dataclass(frozen=True)
class Batch:
    """一批成分券的类型化输入。

    字段：
        ids: 成分券代码，顺序即输出顺序；不允许重复。
        features: ``feature 名 -> 按券排列的 float | None``；长度必须等于 ``len(ids)``。
        masks: ``mask 名 -> 按券排列的 bool``；用于"数据是否可用"门控；长度同上。
        meta: 任意元数据（as_of、名称、口径说明等），执行器不解释其内容。
    """

    ids: list[str]
    features: FeatureMap
    masks: MaskMap
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        ids = list(self.ids)
        if any(not isinstance(item, str) or not item for item in ids):
            raise ValueError("Batch.ids 必须是非空字符串列表")
        if len(set(ids)) != len(ids):
            raise ValueError("Batch.ids 不能重复")
        size = len(ids)

        features: FeatureMap = {}
        for name, values in self.features.items():
            if not isinstance(name, str) or not name:
                raise ValueError("feature 名必须是非空字符串")
            series = list(values)
            if len(series) != size:
                raise ValueError(
                    f"feature {name!r} 长度 {len(series)} != 批大小 {size}"
                )
            normalized: list[Scalar] = []
            for value in series:
                if value is None:
                    normalized.append(None)
                elif _is_real(value):
                    normalized.append(float(value))
                else:
                    raise ValueError(
                        f"feature {name!r} 含非法值 {value!r}（只允许有限 float 或 None）"
                    )
            features[name] = normalized

        masks: MaskMap = {}
        for name, flags in self.masks.items():
            if not isinstance(name, str) or not name:
                raise ValueError("mask 名必须是非空字符串")
            series = list(flags)
            if len(series) != size:
                raise ValueError(
                    f"mask {name!r} 长度 {len(series)} != 批大小 {size}"
                )
            if any(not isinstance(flag, bool) for flag in series):
                raise ValueError(f"mask {name!r} 必须只含 bool")
            masks[name] = series

        object.__setattr__(self, "ids", ids)
        object.__setattr__(self, "features", features)
        object.__setattr__(self, "masks", masks)
        object.__setattr__(self, "meta", dict(self.meta))

    def __len__(self) -> int:
        return len(self.ids)

    @property
    def size(self) -> int:
        """批大小（成分券数量）。"""
        return len(self.ids)

    def feature(self, name: str) -> list[Scalar]:
        """返回某个 feature 的逐券取值；不存在时抛 ``KeyError``。"""
        try:
            return self.features[name]
        except KeyError:
            raise KeyError(f"Batch 不含 feature {name!r}") from None

    def mask(self, name: str) -> list[bool]:
        """返回某个 mask 的逐券取值；不存在时抛 ``KeyError``。"""
        try:
            return self.masks[name]
        except KeyError:
            raise KeyError(f"Batch 不含 mask {name!r}") from None

    def select(self, indices: Sequence[int]) -> "Batch":
        """按下标取子批（保持给定顺序）；用于门控后只对活跃券执行模块。"""
        idx = _check_indices(indices, self.size)
        return Batch(
            ids=[self.ids[index] for index in idx],
            features={
                name: [values[index] for index in idx]
                for name, values in self.features.items()
            },
            masks={
                name: [flags[index] for index in idx]
                for name, flags in self.masks.items()
            },
            meta=dict(self.meta),
        )


@dataclass(frozen=True)
class ModuleOutput:
    """模块的逐券输出。

    字段：
        values: 逐券估值（``None`` 表示该券无输出）。
        intervals: 逐券闭区间 ``(lo, hi)``；``None`` 表示无区间。
        confidence: 逐券置信度，取值 [0, 1]；``None`` 表示不可用。
        evidence: 人类可读的证据/口径说明（整批共享，不是逐券）。
        diagnostics: 机读诊断信息（计数、参数、回退原因等）。
    """

    values: list[Scalar]
    intervals: list[Interval]
    confidence: list[Scalar]
    evidence: list[str] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        values = list(self.values)
        size = len(values)

        intervals: list[Interval] = []
        for value in self.intervals:
            if value is None:
                intervals.append(None)
                continue
            if (
                not isinstance(value, (tuple, list))
                or len(value) != 2
                or not _is_real(value[0])
                or not _is_real(value[1])
            ):
                raise ValueError(f"区间必须是 (float, float) 或 None，收到 {value!r}")
            low, high = float(value[0]), float(value[1])
            if low > high:
                raise ValueError(f"区间下界 {low} 大于上界 {high}")
            intervals.append((low, high))
        if len(intervals) != size:
            raise ValueError(
                f"intervals 长度 {len(intervals)} != values 长度 {size}"
            )

        confidence: list[Scalar] = []
        for value in self.confidence:
            if value is None:
                confidence.append(None)
                continue
            if not _is_real(value) or not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"confidence 必须在 [0, 1] 或为 None，收到 {value!r}")
            confidence.append(float(value))
        if len(confidence) != size:
            raise ValueError(
                f"confidence 长度 {len(confidence)} != values 长度 {size}"
            )

        evidence = list(self.evidence)
        if any(not isinstance(item, str) for item in evidence):
            raise ValueError("evidence 必须只含字符串")

        normalized_values: list[Scalar] = []
        for value in values:
            if value is None:
                normalized_values.append(None)
            elif _is_real(value):
                normalized_values.append(float(value))
            else:
                raise ValueError(f"values 含非法值 {value!r}")

        object.__setattr__(self, "values", normalized_values)
        object.__setattr__(self, "intervals", intervals)
        object.__setattr__(self, "confidence", confidence)
        object.__setattr__(self, "evidence", evidence)
        object.__setattr__(self, "diagnostics", dict(self.diagnostics))

    def __len__(self) -> int:
        return len(self.values)

    @property
    def size(self) -> int:
        """输出对应的券数。"""
        return len(self.values)

    @property
    def value_count(self) -> int:
        """非 ``None`` 值的数量。"""
        return sum(value is not None for value in self.values)

    @classmethod
    def empty(cls, size: int) -> "ModuleOutput":
        """构造长度为 ``size`` 的全空输出。"""
        if size < 0:
            raise ValueError("size 不能为负")
        return cls(
            values=[None] * size,
            intervals=[None] * size,
            confidence=[None] * size,
        )

    def select(self, indices: Sequence[int]) -> "ModuleOutput":
        """按下标取子输出；与 :meth:`Batch.select` 配套使用。"""
        idx = _check_indices(indices, self.size)
        return ModuleOutput(
            values=[self.values[index] for index in idx],
            intervals=[self.intervals[index] for index in idx],
            confidence=[self.confidence[index] for index in idx],
            evidence=list(self.evidence),
            diagnostics=dict(self.diagnostics),
        )

    def expand(self, size: int, indices: Sequence[int]) -> "ModuleOutput":
        """把子批输出散射回整批长度，未覆盖的下标填 ``None``。

        ``len(self)`` 必须等于 ``len(indices)``；用于门控后只对活跃券执行模块、
        再把结果放回原批次的场景。
        """
        idx = _check_indices(indices, size)
        if len(idx) != len(self):
            raise ValueError(
                f"子输出长度 {len(self)} != 目标下标数 {len(idx)}"
            )
        values: list[Scalar] = [None] * size
        intervals: list[Interval] = [None] * size
        confidence: list[Scalar] = [None] * size
        for position, target in enumerate(idx):
            values[target] = self.values[position]
            intervals[target] = self.intervals[position]
            confidence[target] = self.confidence[position]
        return ModuleOutput(
            values=values,
            intervals=intervals,
            confidence=confidence,
            evidence=list(self.evidence),
            diagnostics=dict(self.diagnostics),
        )


@dataclass(frozen=True, eq=False)
class ModuleSpec:
    """模块协议：一个可插拔的估值算子。

    字段：
        name: 模块名（图内唯一标识的一部分）。
        kind: 模块类型，见 :data:`ModuleKind`。
        version: 模块版本，进入 trace 用于审计。
        inputs: 声明的输入 feature / 上游信号名（文档 + 审计用途）。
        outputs: 声明的输出名；原型的图绑定主输出 ``values``，区间与置信度是
            :class:`ModuleOutput` 的标准副通道。
        run: ``run(batch, upstream) -> ModuleOutput``；``upstream`` 只含成功产出的
            依赖节点输出。
        gate: 可选默认门控；节点级门控优先于它。
    """

    name: str
    kind: ModuleKind
    version: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    run: ModuleRun
    gate: ModuleGate | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("ModuleSpec.name 必须是非空字符串")
        if not isinstance(self.version, str) or not self.version:
            raise ValueError("ModuleSpec.version 必须是非空字符串")
        if self.kind not in MODULE_KINDS:
            raise ValueError(
                f"未知模块类型 {self.kind!r}，允许值：{sorted(MODULE_KINDS)}"
            )
        inputs = tuple(self.inputs)
        outputs = tuple(self.outputs)
        if not outputs:
            raise ValueError("ModuleSpec.outputs 不能为空")
        if any(not isinstance(item, str) or not item for item in inputs + outputs):
            raise ValueError("ModuleSpec.inputs / outputs 必须是非空字符串元组")
        if len(set(outputs)) != len(outputs):
            raise ValueError("ModuleSpec.outputs 不能重复")
        if not callable(self.run):
            raise TypeError("ModuleSpec.run 必须可调用")
        if self.gate is not None and not callable(self.gate):
            raise TypeError("ModuleSpec.gate 必须是可调用对象或 None")
        object.__setattr__(self, "inputs", inputs)
        object.__setattr__(self, "outputs", outputs)

    def apply(
        self, batch: Batch, upstream: Mapping[str, ModuleOutput]
    ) -> ModuleOutput:
        """调用 ``run`` 并校验输出契约；模块内部异常向上抛出，由执行器隔离。"""
        frozen_upstream: Mapping[str, ModuleOutput] = MappingProxyType(dict(upstream))
        output = self.run(batch, frozen_upstream)
        if not isinstance(output, ModuleOutput):
            raise TypeError(
                f"模块 {self.name!r} 返回 {type(output).__name__}，应为 ModuleOutput"
            )
        if len(output) != len(batch):
            raise ValueError(
                f"模块 {self.name!r} 输出长度 {len(output)} != 批大小 {len(batch)}"
            )
        return output


@dataclass(frozen=True, eq=False)
class NodeSpec:
    """图节点：绑定一个模块，声明依赖、残差缩放与节点级门控。

    字段：
        id: 节点 id（图内唯一）。
        spec: 节点执行的模块。
        deps: 上游节点 id；执行器按拓扑序先算依赖。
        residual_alpha: 残差缩放 ``α``；非 0 时要求恰好一个依赖作残差基线，
            输出按 ``norm(base + α * 模块输出)`` 合成。
        gate: 节点级门控，优先于 ``spec.gate``。
    """

    id: str
    spec: ModuleSpec
    deps: tuple[str, ...] = ()
    residual_alpha: float = 0.0
    gate: ModuleGate | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise ValueError("NodeSpec.id 必须是非空字符串")
        if not isinstance(self.spec, ModuleSpec):
            raise TypeError("NodeSpec.spec 必须是 ModuleSpec")
        deps = tuple(self.deps)
        if any(not isinstance(dep, str) or not dep for dep in deps):
            raise ValueError("NodeSpec.deps 必须是非空字符串元组")
        if len(set(deps)) != len(deps):
            raise ValueError(f"节点 {self.id!r} 的 deps 不能重复")
        if self.id in deps:
            raise ValueError(f"节点 {self.id!r} 不能依赖自身")
        if not _is_real(self.residual_alpha):
            raise ValueError(f"节点 {self.id!r} 的 residual_alpha 必须是有限数")
        if float(self.residual_alpha) != 0.0 and len(deps) != 1:
            raise ValueError(
                f"残差节点 {self.id!r} 必须恰好有一个依赖作为基线，收到 {len(deps)} 个"
            )
        if self.gate is not None and not callable(self.gate):
            raise TypeError("NodeSpec.gate 必须是可调用对象或 None")
        object.__setattr__(self, "deps", deps)
        object.__setattr__(self, "residual_alpha", float(self.residual_alpha))

    @property
    def resolved_gate(self) -> ModuleGate | None:
        """生效门控：节点级优先，其次模块默认门控。"""
        return self.gate if self.gate is not None else self.spec.gate


@dataclass(frozen=True, order=True)
class EdgeSpec:
    """有向边 ``src -> dst``；必须与节点 ``deps`` 声明一致（执行器校验）。"""

    src: str
    dst: str

    def __post_init__(self) -> None:
        if not isinstance(self.src, str) or not self.src:
            raise ValueError("EdgeSpec.src 必须是非空字符串")
        if not isinstance(self.dst, str) or not self.dst:
            raise ValueError("EdgeSpec.dst 必须是非空字符串")
        if self.src == self.dst:
            raise ValueError("EdgeSpec 不允许自环")


@dataclass(frozen=True)
class PoolSpec:
    """池化声明：池化方式 + 参与节点及其权重。

    ``weights`` 为 ``(node_id, weight)`` 的有序元组；权重必须非负，总权重 > 0。
    执行器按券跳过无值节点并对剩余权重再归一，因此这里的权重是"相对权重"。

    - ``linear``：加权平均，逐券权重再归一。
    - ``log``：加权几何平均（权重和归一），要求值 > 0。
    - ``product``：专家乘积 ``exp(Σ w_i ln v_i)``，权重是证据指数、不归一；
      若权重和恰为 1 则与 ``log`` 等价，见 README。
    """

    kind: PoolKind
    weights: tuple[tuple[str, float], ...]

    def __post_init__(self) -> None:
        if self.kind not in POOL_KINDS:
            raise ValueError(
                f"未知池化方式 {self.kind!r}，允许值：{sorted(POOL_KINDS)}"
            )
        weights = tuple(self.weights)
        if not weights:
            raise ValueError("PoolSpec.weights 不能为空")
        seen: set[str] = set()
        normalized: list[tuple[str, float]] = []
        for member, weight in weights:
            if not isinstance(member, str) or not member:
                raise ValueError("PoolSpec 成员必须是非空节点 id")
            if member in seen:
                raise ValueError(f"PoolSpec 成员 {member!r} 重复")
            if not _is_real(weight) or float(weight) < 0.0:
                raise ValueError(
                    f"PoolSpec 权重必须是非负有限数，节点 {member!r} 收到 {weight!r}"
                )
            seen.add(member)
            normalized.append((member, float(weight)))
        if sum(weight for _, weight in normalized) <= 0.0:
            raise ValueError("PoolSpec 权重总和必须 > 0")
        object.__setattr__(self, "weights", tuple(normalized))

    @property
    def members(self) -> tuple[str, ...]:
        """参与池化的节点 id（按声明顺序）。"""
        return tuple(member for member, _ in self.weights)

    @property
    def total_weight(self) -> float:
        """声明权重总和。"""
        return sum(weight for _, weight in self.weights)

    def normalized_weights(self) -> dict[str, float]:
        """声明权重的静态归一化结果（按声明顺序）。"""
        total = self.total_weight
        return {member: weight / total for member, weight in self.weights}


@dataclass(frozen=True, eq=False)
class GraphSpec:
    """整图声明：节点、边、池化、输出名与版本。

    ``edges`` 与节点 ``deps`` 是同一事实的两种表达，执行器会校验二者一致；
    ``output`` 是合成输出的语义标签（如 ``fair_value``），供报告/trace 引用。
    """

    name: str
    nodes: tuple[NodeSpec, ...]
    edges: tuple[EdgeSpec, ...]
    pool: PoolSpec
    output: str = "fair_value"
    version: str = "0.1.0"

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("GraphSpec.name 必须是非空字符串")
        nodes = tuple(self.nodes)
        if not nodes:
            raise ValueError("GraphSpec.nodes 不能为空")
        edges = tuple(self.edges)
        if any(not isinstance(edge, EdgeSpec) for edge in edges):
            raise TypeError("GraphSpec.edges 必须只含 EdgeSpec")
        if not isinstance(self.pool, PoolSpec):
            raise TypeError("GraphSpec.pool 必须是 PoolSpec")
        if not isinstance(self.output, str) or not self.output:
            raise ValueError("GraphSpec.output 必须是非空字符串")
        if not isinstance(self.version, str) or not self.version:
            raise ValueError("GraphSpec.version 必须是非空字符串")
        object.__setattr__(self, "nodes", nodes)
        object.__setattr__(self, "edges", edges)

    @property
    def node_by_id(self) -> dict[str, NodeSpec]:
        """节点 id -> 节点；重复 id 时后者覆盖前者（执行器会先报重复错误）。"""
        return {node.id: node for node in self.nodes}
