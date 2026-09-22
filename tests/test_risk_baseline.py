# tests/test_risk_baseline.py
# Unit tests for the Monte Carlo engine. Run from the fx-hedging root:
#   python -m unittest discover tests -v
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))  # so "import risk_baseline" works

from config import HORIZON_DAYS, N_SIMULATIONS
from risk_baseline import block_bootstrap, simulate_paths, var_es


class TestVarEs(unittest.TestCase):
    def test_hand_calculated_values(self):
        # Cost increases 1, 2, ..., 100. By hand:
        # 95th percentile (linear interpolation) = 95 + 0.05 * (96 - 95) = 95.05
        # ES = average of the values at or above 95.05 = (96+97+98+99+100) / 5 = 98
        var, es = var_es(np.arange(1, 101, dtype=float), 0.95)
        self.assertAlmostEqual(var, 95.05)
        self.assertAlmostEqual(es, 98.0)

    def test_es_never_below_var(self):
        data = np.random.default_rng(0).standard_t(df=3, size=50_000)  # fat-tailed
        var, es = var_es(data, 0.95)
        self.assertGreaterEqual(es, var)


class TestBlockBootstrap(unittest.TestCase):
    def setUp(self):
        self.returns = np.arange(1000, dtype=float)   # value = its own position, easy to trace

    def test_shape(self):
        sims = block_bootstrap(self.returns, 50, 126, 10, np.random.default_rng(1))
        self.assertEqual(sims.shape, (50, 126))

    def test_blocks_are_consecutive_days(self):
        sims = block_bootstrap(self.returns, 50, 126, 10, np.random.default_rng(1))
        for start in range(0, 120, 10):   # inside each 10-day block, days follow each other
            block = sims[:, start:start + 10]
            self.assertTrue(np.all(np.diff(block, axis=1) == 1))

    def test_only_samples_real_days(self):
        sims = block_bootstrap(self.returns, 200, 126, 10, np.random.default_rng(1))
        self.assertTrue(sims.min() >= 0 and sims.max() <= 999)

    def test_same_seed_same_result(self):
        a = block_bootstrap(self.returns, 20, 126, 10, np.random.default_rng(42))
        b = block_bootstrap(self.returns, 20, 126, 10, np.random.default_rng(42))
        np.testing.assert_array_equal(a, b)


class TestSimulatePaths(unittest.TestCase):
    def test_paths_start_at_today(self):
        paths = simulate_paths(np.full(500, 0.001), 95.0, np.random.default_rng(0))
        self.assertEqual(paths.shape, (N_SIMULATIONS, HORIZON_DAYS + 1))
        self.assertTrue(np.all(paths[:, 0] == 95.0))

    def test_constant_return_gives_exact_end_rate(self):
        # Every day +0.1%: the end rate must be 95 * e^(0.001 * 126) on every path
        paths = simulate_paths(np.full(500, 0.001), 95.0, np.random.default_rng(0))
        np.testing.assert_allclose(paths[:, -1], 95.0 * np.exp(0.001 * HORIZON_DAYS))

    def test_weakening_rupee_is_a_loss(self):
        # Sign convention: if the rupee only weakens, the importer's cost increase must be positive
        paths = simulate_paths(np.full(500, 0.002), 95.0, np.random.default_rng(0))
        cost_increase = 1_000_000 * (paths[:, -1] - 95.0)
        var, es = var_es(cost_increase, 0.95)
        self.assertGreater(var, 0)
        self.assertGreater(es, 0)


if __name__ == "__main__":
    unittest.main()