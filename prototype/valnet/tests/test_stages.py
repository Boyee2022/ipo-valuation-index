"""四段式执行器测试：A 数据、B 加载、C 批处理/断点、D 指数拟合。"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from valnet.graph import execute
from valnet.modules import DCM
from valnet.spec import Batch, ModuleOutput
from valnet.stages import (
    StageAOutput,
    demo_batch,
    demo_graph,
    stage_a,
    stage_b,
    stage_c,
    stage_d,
)


class TestStageA(unittest.TestCase):
    def test_stage_a_derives_dcm_and_digest(self) -> None:
        batch = demo_batch()
        out = stage_a(batch.features, batch.masks, batch.ids, batch.meta)
        self.assertIsInstance(out, StageAOutput)
        self.assertIn("dcm_base", out.batch.features)
        self.assertIn("discount", out.batch.features)
        self.assertIn("has_dcm", out.batch.masks)
        self.assertEqual(out.manifest["rows"], len(batch))
        self.assertEqual(len(out.manifest["digest"]), 16)

    def test_stage_a_deterministic(self) -> None:
        batch = demo_batch()
        one = stage_a(batch.features, batch.masks, batch.ids, batch.meta)
        two = stage_a(batch.features, batch.masks, batch.ids, batch.meta)
        self.assertEqual(one.manifest["digest"], two.manifest["digest"])


class TestStageB(unittest.TestCase):
    def test_registry_includes_dcm(self) -> None:
        report = stage_b()
        self.assertIn("dcf", report.loaded)
        self.assertIn("dcm", report.loaded)
        self.assertIn("comparable", report.loaded)
        self.assertEqual(report.failed, ())
        self.assertEqual(report.count, 5)

    def test_registry_rejects_duplicate(self) -> None:
        report = stage_b([DCM, DCM])
        self.assertEqual(report.loaded, ("dcm",))
        self.assertEqual(report.failed, ("dcm",))


class TestStageC(unittest.TestCase):
    def test_chunked_matches_full(self) -> None:
        batch = demo_batch()
        graph = demo_graph()
        expected = execute(graph, batch)
        with tempfile.TemporaryDirectory() as tmp:
            report = stage_c(graph, batch, tmp, "b1", chunk_size=2)
        self.assertEqual(list(report.ids), batch.ids)
        self.assertEqual(len(report.values), len(batch))
        for got, want in zip(report.values, expected.values):
            self.assertAlmostEqual(got, want, places=12) if got is not None else self.assertIsNone(want)
        self.assertEqual(report.chunks_total, 2)
        self.assertEqual(report.executed_chunks, 2)

    def test_resume_skips_done_chunks(self) -> None:
        batch = demo_batch()
        graph = demo_graph()
        with tempfile.TemporaryDirectory() as tmp:
            first = stage_c(graph, batch, tmp, "b1", chunk_size=1)
            self.assertEqual(first.executed_chunks, 3)
            second = stage_c(graph, batch, tmp, "b1", chunk_size=1)
            self.assertEqual(second.executed_chunks, 0)
            self.assertEqual(second.chunks_done, 3)
            self.assertEqual(first.values, second.values)

    def test_manifest_and_atomic_files(self) -> None:
        batch = demo_batch()
        graph = demo_graph()
        with tempfile.TemporaryDirectory() as tmp:
            stage_c(graph, batch, tmp, "b1", chunk_size=1)
            root = Path(tmp) / "b1"
            manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["total"], 3)
            self.assertEqual(manifest["status"], {"0": "done", "1": "done", "2": "done"})
            self.assertTrue((root / "chunk_0000.json").exists())
            self.assertFalse(list(root.glob("*.tmp*")))

    def test_chunk_size_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                stage_c(demo_graph(), demo_batch(), tmp, "b1", chunk_size=0)


class TestStageD(unittest.TestCase):
    def test_index_fit_covers_and_weights_sum(self) -> None:
        batch = demo_batch()
        graph = demo_graph()
        with tempfile.TemporaryDirectory() as tmp:
            report = stage_c(graph, batch, tmp, "b1", chunk_size=2)
        fit = stage_d(report, batch)
        self.assertEqual(fit.covered, 3)
        self.assertEqual(fit.total, 3)
        self.assertIsNotNone(fit.value)
        self.assertAlmostEqual(sum(fit.weights.values()), 1.0, places=12)

    def test_missing_weight_feature_raises(self) -> None:
        batch = demo_batch()
        with tempfile.TemporaryDirectory() as tmp:
            report = stage_c(demo_graph(), batch, tmp, "b1", chunk_size=2)
        with self.assertRaises(ValueError):
            stage_d(report, batch, weight_feature="missing")


class TestDCM(unittest.TestCase):
    def test_dcm_basic(self) -> None:
        batch = Batch(
            ids=["X"],
            features={"dcm_base": [10.0], "growth": [0.1], "discount": [0.2]},
            masks={"has_dcm": [True]},
        )
        out: ModuleOutput = DCM.run(batch, {})
        self.assertAlmostEqual(out.values[0], 10.0 * 1.1 / 1.2, places=12)  # type: ignore[arg-type]
        self.assertIsNotNone(out.intervals[0])

    def test_dcm_requires_discount_above_growth(self) -> None:
        batch = Batch(
            ids=["X"],
            features={"dcm_base": [10.0], "growth": [0.2], "discount": [0.2]},
            masks={"has_dcm": [True]},
        )
        out = DCM.run(batch, {})
        self.assertIsNone(out.values[0])
        self.assertEqual(out.diagnostics["invalid"], 1)

    def test_dcm_mask_skips(self) -> None:
        batch = Batch(
            ids=["X"],
            features={"dcm_base": [10.0], "growth": [0.1], "discount": [0.2]},
            masks={"has_dcm": [False]},
        )
        out = DCM.run(batch, {})
        self.assertIsNone(out.values[0])


if __name__ == "__main__":
    unittest.main()
