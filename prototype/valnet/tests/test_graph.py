"""图执行器测试：拓扑、环检测、门控、残差、失败隔离、池化、确定性与 trace。"""

import unittest
from typing import Callable, Mapping

from valnet.graph import (
    STATUS_FAILED,
    STATUS_GATED,
    STATUS_OK,
    CycleError,
    DuplicateNodeError,
    GraphError,
    GraphValidationError,
    MissingDependencyError,
    bounded_residual,
    execute,
    topological_order,
    validate_graph,
)
from valnet.spec import (
    Batch,
    EdgeSpec,
    GraphSpec,
    ModuleOutput,
    ModuleSpec,
    NodeSpec,
    PoolSpec,
)


# ---------------------------------------------------------------------------
# 测试夹具
# ---------------------------------------------------------------------------


def make_batch(
    ids: tuple[str, ...] = ("A", "B", "C"),
    features: dict | None = None,
    masks: dict | None = None,
) -> Batch:
    """构造最小 Batch。"""
    return Batch(
        ids=list(ids),
        features=dict(features or {}),
        masks=dict(masks or {}),
        meta={"names": {security: security for security in ids}},
    )


def make_module(
    name: str,
    values_by_id: Mapping[str, float],
    *,
    kind: str = "valuation",
    confidence: float = 0.5,
    interval_pct: float = 0.10,
    gate: Callable[[Batch], list[float]] | None = None,
    recorder: list[tuple[str, ...]] | None = None,
) -> ModuleSpec:
    """按券 id 查表返回固定值的测试模块；支持记录被调用的子批。"""

    def run(batch: Batch, upstream: Mapping[str, ModuleOutput]) -> ModuleOutput:
        if recorder is not None:
            recorder.append(tuple(batch.ids))
        selected = [values_by_id[security] for security in batch.ids]
        size = len(selected)
        intervals = []
        for value in selected:
            low, high = value * (1.0 - interval_pct), value * (1.0 + interval_pct)
            intervals.append((min(low, high), max(low, high)))
        return ModuleOutput(
            values=selected,
            intervals=intervals,
            confidence=[confidence] * size,
            evidence=[f"{name}: stub fixture"],
            diagnostics={"module": name},
        )

    return ModuleSpec(
        name=name,
        kind=kind,  # type: ignore[arg-type]
        version="test-1",
        inputs=(),
        outputs=("value",),
        run=run,
        gate=gate,
    )


def make_node(
    node_id: str,
    values_by_id: Mapping[str, float],
    *,
    deps: tuple[str, ...] = (),
    residual_alpha: float = 0.0,
    gate: Callable[[Batch], list[float]] | None = None,
    confidence: float = 0.5,
    interval_pct: float = 0.10,
    recorder: list[tuple[str, ...]] | None = None,
) -> NodeSpec:
    """构造测试节点。"""
    return NodeSpec(
        id=node_id,
        spec=make_module(
            node_id,
            values_by_id,
            confidence=confidence,
            interval_pct=interval_pct,
            recorder=recorder,
        ),
        deps=deps,
        residual_alpha=residual_alpha,
        gate=gate,
    )


def make_graph(
    nodes: tuple[NodeSpec, ...],
    *,
    edges: tuple[EdgeSpec, ...] = (),
    weights: Mapping[str, float] | None = None,
    kind: str = "linear",
    output: str = "fair_value",
) -> GraphSpec:
    """构造测试图；默认每个节点权重 1。"""
    if weights is None:
        weights = {node.id: 1.0 for node in nodes}
    return GraphSpec(
        name="test-graph",
        nodes=nodes,
        edges=edges,
        pool=PoolSpec(kind=kind, weights=tuple(weights.items())),  # type: ignore[arg-type]
        output=output,
        version="test-1",
    )


VALUES_A = {"A": 10.0, "B": 20.0, "C": 30.0}
VALUES_B = {"A": 30.0, "B": 20.0, "C": 10.0}


# ---------------------------------------------------------------------------
# 拓扑与图校验
# ---------------------------------------------------------------------------


class TopologyTest(unittest.TestCase):
    def test_dependencies_come_first(self) -> None:
        a = make_node("a", VALUES_A)
        b = make_node("b", VALUES_A, deps=("a",))
        c = make_node("c", VALUES_A, deps=("b",))
        graph = make_graph(
            (c, b, a),  # 故意逆序声明
            edges=(EdgeSpec("a", "b"), EdgeSpec("b", "c")),
            weights={"c": 1.0},
        )
        self.assertEqual(topological_order(graph), ("a", "b", "c"))
        self.assertEqual(validate_graph(graph), ("a", "b", "c"))

    def test_independent_nodes_keep_declaration_order(self) -> None:
        nodes = (
            make_node("b", VALUES_A),
            make_node("a", VALUES_A),
            make_node("c", VALUES_A),
        )
        graph = make_graph(nodes, weights={"a": 1.0})
        self.assertEqual(topological_order(graph), ("b", "a", "c"))

    def test_cycle_is_detected(self) -> None:
        a = make_node("a", VALUES_A, deps=("b",))
        b = make_node("b", VALUES_A, deps=("a",))
        graph = make_graph(
            (a, b),
            edges=(EdgeSpec("b", "a"), EdgeSpec("a", "b")),
            weights={"a": 1.0},
        )
        with self.assertRaises(CycleError):
            topological_order(graph)
        with self.assertRaises(CycleError):
            execute(graph, make_batch())

    def test_missing_dependency_is_reported(self) -> None:
        node = make_node("x", VALUES_A, deps=("ghost",))
        graph = make_graph(
            (node,), edges=(EdgeSpec("ghost", "x"),), weights={"x": 1.0}
        )
        with self.assertRaises(MissingDependencyError):
            topological_order(graph)

    def test_edges_must_match_deps(self) -> None:
        a = make_node("a", VALUES_A)
        b = make_node("b", VALUES_A, deps=("a",))
        missing_edge = make_graph((a, b), weights={"b": 1.0})
        with self.assertRaises(GraphValidationError):
            execute(missing_edge, make_batch())

        extra_edge = make_graph(
            (a, b),
            edges=(EdgeSpec("a", "b"), EdgeSpec("b", "a")),
            weights={"b": 1.0},
        )
        with self.assertRaises(GraphValidationError):
            execute(extra_edge, make_batch())

    def test_duplicate_node_id_is_rejected(self) -> None:
        graph = make_graph(
            (make_node("a", VALUES_A), make_node("a", VALUES_B)),
            weights={"a": 1.0},
        )
        with self.assertRaises(DuplicateNodeError):
            validate_graph(graph)

    def test_pool_member_must_exist(self) -> None:
        graph = make_graph(
            (make_node("a", VALUES_A),), weights={"ghost": 1.0}
        )
        with self.assertRaises(MissingDependencyError):
            validate_graph(graph)

    def test_residual_node_requires_single_dep(self) -> None:
        with self.assertRaises(ValueError):
            NodeSpec(
                id="res",
                spec=make_module("res", VALUES_A),
                deps=("a", "b"),
                residual_alpha=0.5,
            )

    def test_node_cannot_depend_on_itself(self) -> None:
        with self.assertRaises(ValueError):
            NodeSpec(
                id="loop",
                spec=make_module("loop", VALUES_A),
                deps=("loop",),
            )


# ---------------------------------------------------------------------------
# 线性池化与执行
# ---------------------------------------------------------------------------


class ExecutionTest(unittest.TestCase):
    def test_linear_pool_and_audit_fields(self) -> None:
        a = make_node("a", VALUES_A)
        b = make_node("b", VALUES_B)
        graph = make_graph(
            (a, b), weights={"a": 0.25, "b": 0.75}, output="fair_value"
        )
        result = execute(graph, make_batch())
        self.assertEqual(result.values, [25.0, 20.0, 15.0])
        self.assertEqual(result.pool_weights, {"a": 0.25, "b": 0.75})
        self.assertEqual(result.output, "fair_value")
        self.assertEqual(result.trace.statuses(), {"a": STATUS_OK, "b": STATUS_OK})

    def test_interval_and_confidence_are_pooled(self) -> None:
        a = make_node("a", {"A": 10.0}, confidence=0.8, interval_pct=0.10)
        b = make_node("b", {"A": 20.0}, confidence=0.4, interval_pct=0.20)
        graph = make_graph((a, b), weights={"a": 0.5, "b": 0.5})
        batch = make_batch(ids=("A",))
        result = execute(graph, batch)
        self.assertAlmostEqual(result.values[0], 15.0)
        interval = result.intervals[0]
        assert interval is not None
        self.assertAlmostEqual(interval[0], 12.5)  # 0.5*9 + 0.5*16
        self.assertAlmostEqual(interval[1], 17.5)  # 0.5*11 + 0.5*24
        self.assertAlmostEqual(result.confidence[0], 0.6)

    def test_empty_batch_returns_empty_result(self) -> None:
        node = make_node("only", {})
        graph = make_graph((node,), weights={"only": 1.0})
        result = execute(graph, make_batch(ids=()))
        self.assertEqual(result.values, [])
        self.assertEqual(result.intervals, [])
        self.assertEqual(result.confidence, [])
        self.assertEqual(result.trace.entries[0].value_count, 0)


# ---------------------------------------------------------------------------
# 门控
# ---------------------------------------------------------------------------


class GatingTest(unittest.TestCase):
    def test_gate_skips_security_and_renormalizes_pool(self) -> None:
        calls: list[tuple[str, ...]] = []
        gated = make_node(
            "gated",
            {"A": 100.0, "B": 200.0, "C": 300.0},
            gate=lambda batch: [0.0, 1.0, 1.0],
            recorder=calls,
        )
        other = make_node("other", {"A": 0.0, "B": 20.0, "C": 30.0})
        graph = make_graph(
            (gated, other), weights={"gated": 0.5, "other": 0.5}
        )
        result = execute(graph, make_batch())
        # 模块只在活跃子批上执行（A 被门控跳过）。
        self.assertEqual(calls, [("B", "C")])
        self.assertEqual(result.node_output("gated").values, [None, 200.0, 300.0])
        self.assertEqual(result.values, [0.0, 110.0, 165.0])
        entry = result.trace.entry("gated")
        self.assertEqual(entry.status, STATUS_OK)
        self.assertEqual(entry.gated_count, 1)
        self.assertEqual(entry.value_count, 2)

    def test_full_gate_skips_node(self) -> None:
        calls: list[tuple[str, ...]] = []
        gated = make_node(
            "gated", VALUES_A, gate=lambda batch: [0.0, 0.0, 0.0], recorder=calls
        )
        other = make_node("other", VALUES_B)
        graph = make_graph(
            (gated, other), weights={"gated": 0.5, "other": 0.5}
        )
        result = execute(graph, make_batch())
        self.assertEqual(calls, [])
        self.assertIsNone(result.node_output("gated"))
        self.assertEqual(result.values, [30.0, 20.0, 10.0])
        entry = result.trace.entry("gated")
        self.assertEqual(entry.status, STATUS_GATED)
        self.assertEqual(entry.gated_count, 3)
        self.assertEqual(result.trace.gated_nodes, ("gated",))

    def test_gated_residual_node_inherits_baseline(self) -> None:
        calls: list[tuple[str, ...]] = []
        baseline = make_node("baseline", {"A": 10.0, "B": 20.0, "C": 30.0})
        residual = make_node(
            "residual",
            {"A": 999.0, "B": 999.0, "C": 999.0},
            deps=("baseline",),
            residual_alpha=0.5,
            gate=lambda batch: [0.0, 0.0, 0.0],
            recorder=calls,
        )
        graph = make_graph(
            (baseline, residual),
            edges=(EdgeSpec("baseline", "residual"),),
            weights={"baseline": 0.5, "residual": 0.5},
        )
        result = execute(graph, make_batch())
        self.assertEqual(calls, [])
        self.assertEqual(
            result.node_output("residual").values, [10.0, 20.0, 30.0]
        )
        self.assertEqual(result.values, [10.0, 20.0, 30.0])
        entry = result.trace.entry("residual")
        self.assertEqual(entry.status, STATUS_GATED)
        self.assertEqual(entry.residual_count, 3)

    def test_bad_gate_is_isolated_as_node_failure(self) -> None:
        def bad_gate(batch: Batch) -> list[float]:
            raise RuntimeError("gate boom")

        broken = NodeSpec(
            id="broken",
            spec=make_module("broken", VALUES_A, gate=bad_gate),
        )
        good = make_node("good", VALUES_B)
        graph = make_graph((broken, good), weights={"broken": 0.5, "good": 0.5})
        result = execute(graph, make_batch())
        self.assertEqual(result.values, [30.0, 20.0, 10.0])
        entry = result.trace.entry("broken")
        self.assertEqual(entry.status, STATUS_FAILED)
        self.assertIn("gate boom", entry.error or "")

    def test_gate_length_mismatch_is_isolated(self) -> None:
        broken = make_node("broken", VALUES_A, gate=lambda batch: [1.0])
        good = make_node("good", VALUES_B)
        graph = make_graph((broken, good), weights={"broken": 0.5, "good": 0.5})
        result = execute(graph, make_batch())
        self.assertIn("长度", result.trace.entry("broken").error or "")


# ---------------------------------------------------------------------------
# 残差
# ---------------------------------------------------------------------------


class ResidualTest(unittest.TestCase):
    def test_residual_formula_and_winsorize(self) -> None:
        baseline = make_node("baseline", {"A": 100.0, "B": 100.0, "C": 100.0})
        module = make_node(
            "module",
            {"A": 120.0, "B": 200.0, "C": 80.0},
            deps=("baseline",),
            residual_alpha=0.5,
        )
        graph = make_graph(
            (baseline, module),
            edges=(EdgeSpec("baseline", "module"),),
            weights={"module": 1.0},
        )
        result = execute(graph, make_batch())
        # A: 100+0.5*20=110；B: 偏离 +100 被 winsorize 到 +50 → 125；
        # C: 100+0.5*(-20)=90。
        self.assertEqual(result.values, [110.0, 125.0, 90.0])
        entry = result.trace.entry("module")
        self.assertEqual(entry.residual_count, 3)
        self.assertEqual(entry.residual_base_missing, 0)

    def test_residual_interval_is_transformed(self) -> None:
        baseline = make_node("baseline", {"A": 100.0})
        module = make_node(
            "module",
            {"A": 120.0},
            deps=("baseline",),
            residual_alpha=0.5,
            interval_pct=0.10,
        )
        graph = make_graph(
            (baseline, module),
            edges=(EdgeSpec("baseline", "module"),),
            weights={"module": 1.0},
        )
        result = execute(graph, make_batch(ids=("A",)))
        interval = result.intervals[0]
        assert interval is not None
        self.assertAlmostEqual(interval[0], 104.0)  # 100 + 0.5*(108-100)
        self.assertAlmostEqual(interval[1], 116.0)  # 100 + 0.5*(132-100)

    def test_residual_with_failed_baseline_drops_output(self) -> None:
        def boom_run(batch: Batch, upstream: Mapping[str, ModuleOutput]) -> ModuleOutput:
            raise RuntimeError("baseline boom")

        broken = NodeSpec(
            id="baseline",
            spec=ModuleSpec(
                name="broken",
                kind="encoder",
                version="test-1",
                inputs=(),
                outputs=("value",),
                run=boom_run,
            ),
        )
        residual = make_node(
            "residual",
            VALUES_A,
            deps=("baseline",),
            residual_alpha=0.5,
        )
        graph = make_graph(
            (broken, residual),
            edges=(EdgeSpec("baseline", "residual"),),
            weights={"residual": 1.0},
        )
        result = execute(graph, make_batch())
        entry = result.trace.entry("residual")
        self.assertEqual(entry.status, STATUS_OK)
        self.assertEqual(entry.residual_base_missing, 3)
        self.assertEqual(entry.value_count, 0)
        self.assertEqual(result.values, [None, None, None])


class BoundedResidualTest(unittest.TestCase):
    def test_within_bound_is_exact(self) -> None:
        self.assertEqual(bounded_residual(100.0, 120.0, 0.5), 110.0)

    def test_outlier_is_clipped(self) -> None:
        self.assertEqual(bounded_residual(100.0, 200.0, 1.0), 150.0)
        self.assertEqual(bounded_residual(100.0, -100.0, 1.0), 50.0)

    def test_zero_alpha_returns_baseline(self) -> None:
        self.assertEqual(bounded_residual(100.0, 300.0, 0.0), 100.0)

    def test_negative_alpha(self) -> None:
        self.assertEqual(bounded_residual(100.0, 120.0, -0.5), 90.0)

    def test_invalid_inputs_raise(self) -> None:
        with self.assertRaises(ValueError):
            bounded_residual(100.0, 120.0, 0.5, clip=0.0)
        with self.assertRaises(ValueError):
            bounded_residual(float("inf"), 120.0, 0.5)


# ---------------------------------------------------------------------------
# 失败隔离与池化边界
# ---------------------------------------------------------------------------


class FailureIsolationTest(unittest.TestCase):
    def test_single_node_failure_does_not_break_graph(self) -> None:
        def boom_run(batch: Batch, upstream: Mapping[str, ModuleOutput]) -> ModuleOutput:
            raise RuntimeError("boom")

        broken = NodeSpec(
            id="broken",
            spec=ModuleSpec(
                name="broken",
                kind="valuation",
                version="test-1",
                inputs=(),
                outputs=("value",),
                run=boom_run,
            ),
        )
        good = make_node("good", VALUES_A)
        graph = make_graph((broken, good), weights={"broken": 0.5, "good": 0.5})
        result = execute(graph, make_batch())
        self.assertIsNone(result.node_output("broken"))
        self.assertEqual(result.values, [10.0, 20.0, 30.0])
        entry = result.trace.entry("broken")
        self.assertEqual(entry.status, STATUS_FAILED)
        self.assertIn("RuntimeError: boom", entry.error or "")
        self.assertEqual(result.trace.failed_nodes, ("broken",))

    def test_wrong_output_length_is_isolated(self) -> None:
        def short_run(batch: Batch, upstream: Mapping[str, ModuleOutput]) -> ModuleOutput:
            return ModuleOutput(
                values=[1.0], intervals=[None], confidence=[None]
            )

        broken = NodeSpec(
            id="short",
            spec=ModuleSpec(
                name="short",
                kind="valuation",
                version="test-1",
                inputs=(),
                outputs=("value",),
                run=short_run,
            ),
        )
        good = make_node("good", VALUES_A)
        graph = make_graph((broken, good), weights={"short": 0.5, "good": 0.5})
        result = execute(graph, make_batch())
        self.assertEqual(result.values, [10.0, 20.0, 30.0])
        self.assertIn("长度", result.trace.entry("short").error or "")

    def test_log_pool_non_positive_value_raises_graph_error(self) -> None:
        a = make_node("a", {"A": 1.0})
        b = make_node("b", {"A": -2.0})
        graph = make_graph(
            (a, b), weights={"a": 1.0, "b": 1.0}, kind="log"
        )
        with self.assertRaises(GraphError):
            execute(graph, make_batch(ids=("A",)))

    def test_product_pool_uses_raw_weights(self) -> None:
        a = make_node("a", {"A": 2.0})
        b = make_node("b", {"A": 8.0})
        graph = make_graph(
            (a, b), weights={"a": 2.0, "b": 1.0}, kind="product"
        )
        result = execute(graph, make_batch(ids=("A",)))
        self.assertAlmostEqual(result.values[0], 32.0)  # 2^2 * 8


# ---------------------------------------------------------------------------
# 确定性与 trace
# ---------------------------------------------------------------------------


class DeterminismAndTraceTest(unittest.TestCase):
    def _graph(self) -> GraphSpec:
        baseline = make_node("baseline", {"A": 10.0, "B": 20.0, "C": 30.0})
        valuation = make_node(
            "valuation", {"A": 12.0, "B": 18.0, "C": 33.0}
        )
        residual = make_node(
            "residual",
            {"A": 14.0, "B": 25.0, "C": 40.0},
            deps=("baseline",),
            residual_alpha=0.5,
        )
        return make_graph(
            (baseline, valuation, residual),
            edges=(EdgeSpec("baseline", "residual"),),
            weights={"valuation": 0.5, "residual": 0.5},
        )

    def test_same_input_same_output(self) -> None:
        graph = self._graph()
        batch = make_batch()
        first = execute(graph, batch)
        second = execute(graph, batch)
        self.assertEqual(first, second)
        self.assertEqual(first.trace, second.trace)

    def test_trace_covers_every_node_in_topological_order(self) -> None:
        graph = self._graph()
        result = execute(graph, make_batch())
        expected_order = validate_graph(graph)
        self.assertEqual(result.trace.topology, expected_order)
        self.assertEqual(
            tuple(entry.node_id for entry in result.trace.entries), expected_order
        )
        self.assertEqual(
            [entry.order for entry in result.trace.entries],
            list(range(len(graph.nodes))),
        )
        for entry in result.trace.entries:
            self.assertIn(entry.status, {STATUS_OK, STATUS_GATED, STATUS_FAILED})
            self.assertEqual(entry.module_version, "test-1")
        self.assertEqual(result.trace.graph_name, "test-graph")
        self.assertEqual(result.trace.pool_kind, "linear")
        self.assertEqual(result.trace.output, "fair_value")


# ---------------------------------------------------------------------------
# 数据契约
# ---------------------------------------------------------------------------


class BatchContractTest(unittest.TestCase):
    def test_select_returns_aligned_sub_batch(self) -> None:
        batch = Batch(
            ids=["A", "B", "C"],
            features={"v": [1.0, 2.0, 3.0], "w": [None, 5.0, 6.0]},
            masks={"m": [True, False, True]},
        )
        sub = batch.select([0, 2])
        self.assertEqual(sub.ids, ["A", "C"])
        self.assertEqual(sub.features["v"], [1.0, 3.0])
        self.assertEqual(sub.features["w"], [None, 6.0])
        self.assertEqual(sub.masks["m"], [True, True])

    def test_batch_rejects_bad_shapes(self) -> None:
        with self.assertRaises(ValueError):
            Batch(ids=["A", "B"], features={"v": [1.0]}, masks={})
        with self.assertRaises(ValueError):
            Batch(ids=["A", "A"], features={}, masks={})
        with self.assertRaises(ValueError):
            Batch(ids=["A"], features={"v": [float("nan")]}, masks={})
        with self.assertRaises(ValueError):
            Batch(ids=["A"], features={}, masks={"m": [1]})  # type: ignore[list-item]

    def test_select_rejects_bad_indices(self) -> None:
        batch = make_batch()
        with self.assertRaises(IndexError):
            batch.select([0, 3])
        with self.assertRaises(ValueError):
            batch.select([0, 0])


class ModuleOutputContractTest(unittest.TestCase):
    def test_validation(self) -> None:
        with self.assertRaises(ValueError):
            ModuleOutput(values=[1.0], intervals=[None, None], confidence=[None])
        with self.assertRaises(ValueError):
            ModuleOutput(values=[1.0], intervals=[(2.0, 1.0)], confidence=[None])
        with self.assertRaises(ValueError):
            ModuleOutput(values=[1.0], intervals=[None], confidence=[1.5])

    def test_select_expand_roundtrip(self) -> None:
        output = ModuleOutput(
            values=[10.0, 30.0],
            intervals=[(9.0, 11.0), (27.0, 33.0)],
            confidence=[0.5, 0.5],
        )
        expanded = output.expand(3, [0, 2])
        self.assertEqual(expanded.values, [10.0, None, 30.0])
        self.assertEqual(expanded.intervals[1], None)
        self.assertEqual(expanded.select([0, 2]).values, [10.0, 30.0])
        with self.assertRaises(ValueError):
            output.expand(3, [0])
        with self.assertRaises(ValueError):
            output.expand(3, [0, 0])


if __name__ == "__main__":
    unittest.main()
