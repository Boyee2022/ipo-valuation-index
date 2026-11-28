"""池化语义测试：线性池 / 对数池 / 专家乘积 / 区间传播 / 权重归一 / None 跳过。"""

import math
import unittest

from valnet.pooling import (
    PoolingError,
    linear_pool,
    log_pool,
    pool_confidence,
    pool_intervals,
    pool_values,
    product_pool,
)


class LinearPoolTest(unittest.TestCase):
    """线性池：加权平均 + 逐券权重再归一。"""

    def test_weighted_mean(self) -> None:
        self.assertAlmostEqual(
            linear_pool([1.0, 2.0, 3.0], [1.0, 1.0, 1.0]), 2.0
        )
        self.assertAlmostEqual(
            linear_pool([10.0, 20.0], [1.0, 3.0]), 17.5
        )

    def test_weight_scale_invariance(self) -> None:
        base = linear_pool([2.0, 4.0, 8.0], [1.0, 2.0, 1.0])
        scaled = linear_pool([2.0, 4.0, 8.0], [10.0, 20.0, 10.0])
        self.assertAlmostEqual(base, scaled)

    def test_none_values_skipped_and_weights_renormalized(self) -> None:
        # 权重 1+3=4，值 10 与 20 → (1*10 + 3*20)/4 = 17.5。
        self.assertAlmostEqual(
            linear_pool([10.0, None, 20.0], [1.0, 1.0, 3.0]), 17.5
        )
        self.assertAlmostEqual(linear_pool([None, 5.0], [1.0, 3.0]), 5.0)

    def test_none_weight_skips_pair(self) -> None:
        self.assertAlmostEqual(linear_pool([10.0, 1000.0], [1.0, None]), 10.0)

    def test_all_none_returns_none(self) -> None:
        self.assertIsNone(linear_pool([None, None], [1.0, 1.0]))

    def test_zero_total_weight_returns_none(self) -> None:
        self.assertIsNone(linear_pool([10.0, 20.0], [0.0, 0.0]))
        self.assertIsNone(linear_pool([10.0, None], [0.0, 1.0]))

    def test_empty_returns_none(self) -> None:
        self.assertIsNone(linear_pool([], []))

    def test_single_member(self) -> None:
        self.assertAlmostEqual(linear_pool([7.5], [0.3]), 7.5)

    def test_negative_values_are_allowed(self) -> None:
        self.assertAlmostEqual(linear_pool([-10.0, 10.0], [1.0, 1.0]), 0.0)

    def test_negative_weight_raises(self) -> None:
        with self.assertRaises(PoolingError):
            linear_pool([1.0, 2.0], [1.0, -1.0])

    def test_length_mismatch_raises(self) -> None:
        with self.assertRaises(PoolingError):
            linear_pool([1.0, 2.0], [1.0])

    def test_non_finite_value_raises(self) -> None:
        with self.assertRaises(PoolingError):
            linear_pool([float("nan")], [1.0])


class LogPoolTest(unittest.TestCase):
    """对数池：加权几何平均（权重和归一）。"""

    def test_geometric_mean(self) -> None:
        self.assertAlmostEqual(log_pool([4.0, 9.0], [1.0, 1.0]), 6.0)

    def test_weighted_geometric_mean_matches_formula(self) -> None:
        expected = math.exp((math.log(2.0) + 2.0 * math.log(8.0)) / 3.0)
        self.assertAlmostEqual(log_pool([2.0, 8.0], [1.0, 2.0]), expected)

    def test_weight_scale_invariance(self) -> None:
        base = log_pool([2.0, 8.0], [1.0, 2.0])
        scaled = log_pool([2.0, 8.0], [3.0, 6.0])
        self.assertAlmostEqual(base, scaled)

    def test_non_positive_values_raise(self) -> None:
        for values in ([0.0, 9.0], [4.0, -1.0]):
            with self.subTest(values=values):
                with self.assertRaises(PoolingError):
                    log_pool(values, [1.0, 1.0])

    def test_none_values_skipped(self) -> None:
        self.assertAlmostEqual(log_pool([4.0, None, 9.0], [1.0, 1.0, 1.0]), 6.0)

    def test_all_none_or_empty_returns_none(self) -> None:
        self.assertIsNone(log_pool([None, None], [1.0, 1.0]))
        self.assertIsNone(log_pool([], []))
        self.assertIsNone(log_pool([4.0], [0.0]))


class ProductPoolTest(unittest.TestCase):
    """专家乘积：exp(Σ w ln v)，权重默认不归一。"""

    def test_product_of_likelihoods(self) -> None:
        # 4^1 * 9^1 = 36，而不是几何平均 6。
        self.assertAlmostEqual(product_pool([4.0, 9.0], [1.0, 1.0]), 36.0)

    def test_distinct_from_log_when_weights_not_normalized(self) -> None:
        product = product_pool([2.0, 8.0], [2.0, 1.0])
        logarithmic = log_pool([2.0, 8.0], [2.0, 1.0])
        self.assertAlmostEqual(product, 32.0)  # 2^2 * 8 = 32
        self.assertAlmostEqual(logarithmic, 32.0 ** (1.0 / 3.0))
        self.assertNotAlmostEqual(product, logarithmic)

    def test_normalized_weights_equal_log_pool(self) -> None:
        # 权重和为 1 时专家乘积与加权几何平均数值一致（语义仍是乘积）。
        self.assertAlmostEqual(product_pool([4.0, 9.0], [0.5, 0.5]), 6.0)
        self.assertAlmostEqual(
            product_pool([4.0, 9.0], [1.0, 1.0], normalize_weights=True), 6.0
        )

    def test_non_positive_values_raise(self) -> None:
        for values in ([0.0, 9.0], [-4.0, 9.0]):
            with self.subTest(values=values):
                with self.assertRaises(PoolingError):
                    product_pool(values, [1.0, 1.0])

    def test_none_values_skipped(self) -> None:
        self.assertAlmostEqual(product_pool([4.0, None, 9.0], [1.0, 1.0, 1.0]), 36.0)

    def test_empty_returns_none(self) -> None:
        self.assertIsNone(product_pool([], []))
        self.assertIsNone(product_pool([4.0], [0.0]))


class PoolValuesDispatchTest(unittest.TestCase):
    """池化方式分派。"""

    def test_dispatch(self) -> None:
        self.assertAlmostEqual(pool_values("linear", [1.0, 3.0], [1.0, 1.0]), 2.0)
        self.assertAlmostEqual(pool_values("log", [4.0, 9.0], [1.0, 1.0]), 6.0)
        self.assertAlmostEqual(
            pool_values("product", [4.0, 9.0], [1.0, 1.0]), 36.0
        )

    def test_unknown_kind_raises(self) -> None:
        with self.assertRaises(PoolingError):
            pool_values("median", [1.0], [1.0])  # type: ignore[arg-type]


class PoolIntervalsTest(unittest.TestCase):
    """区间传播：端点按同一权重合成，跳过 None。"""

    def test_linear_interval_endpoints(self) -> None:
        # lo=(1*1+3*3)/4=2.5，hi=(1*2+3*5)/4=4.25。
        self.assertEqual(pool_intervals([(1.0, 2.0), (3.0, 5.0)], [1.0, 3.0]), (2.5, 4.25))

    def test_skip_none_intervals(self) -> None:
        self.assertEqual(
            pool_intervals([None, (2.0, 4.0)], [1.0, 1.0], "linear"), (2.0, 4.0)
        )
        self.assertIsNone(pool_intervals([None, None], [1.0, 1.0]))

    def test_log_interval_geometric_endpoints(self) -> None:
        low, high = pool_intervals(
            [(4.0, 9.0), (16.0, 25.0)], [1.0, 1.0], "log"
        )
        self.assertAlmostEqual(low, 8.0)   # sqrt(4*16)
        self.assertAlmostEqual(high, 15.0)  # sqrt(9*25)

    def test_product_interval_uses_raw_weights(self) -> None:
        low, high = pool_intervals([(2.0, 4.0)], [2.0], "product")
        self.assertAlmostEqual(low, 4.0)   # 2^2
        self.assertAlmostEqual(high, 16.0)  # 4^2

    def test_log_interval_requires_positive_endpoints(self) -> None:
        with self.assertRaises(PoolingError):
            pool_intervals([(0.0, 1.0)], [1.0], "log")

    def test_interval_length_mismatch_raises(self) -> None:
        with self.assertRaises(PoolingError):
            pool_intervals([(1.0, 2.0)], [1.0, 1.0])


class PoolConfidenceTest(unittest.TestCase):
    """置信度始终线性合成。"""

    def test_confidence_is_linear(self) -> None:
        self.assertAlmostEqual(pool_confidence([0.8, 0.4], [1.0, 1.0]), 0.6)

    def test_confidence_skips_none(self) -> None:
        self.assertAlmostEqual(pool_confidence([0.8, None], [1.0, 1.0]), 0.8)
        self.assertIsNone(pool_confidence([None], [1.0]))


if __name__ == "__main__":
    unittest.main()
