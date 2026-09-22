# tests/test_optimizer.py
# Unit and smoke tests for the hedge recommendation. Run from the fx-hedging root:
#   python -m unittest discover tests -v
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from config import UTILITY_SCORES_FILE, REGIME_NAMES, RISK_LEVELS
from optimizer import transition_matrix, simulate_returns, end_rates, score_ratio, recommend

NAMES = ["Calm", "Normal", "Crisis"]


def toy_history():
    """300 days: first 100 Calm, next 100 Normal, last 100 Crisis. Each day's 'return' is its own
    position, so we can see exactly which historical days a simulation used."""
    labels = np.array(["Calm"] * 100 + ["Normal"] * 100 + ["Crisis"] * 100)
    return np.arange(300, dtype=float), labels


class TestSimulation(unittest.TestCase):
    def test_transition_rows_sum_to_one(self):
        _, labels = toy_history()
        t = transition_matrix(labels, 10, NAMES)
        np.testing.assert_allclose(t.sum(axis=1), 1.0)

    def test_first_block_comes_from_the_starting_regime(self):
        returns, labels = toy_history()
        t = transition_matrix(labels, 10, NAMES)
        sims = simulate_returns(returns, labels, "Crisis", t, NAMES, 500, 30, 10, np.random.default_rng(0))
        self.assertEqual(sims.shape, (500, 30))
        self.assertTrue((sims[:, 0] >= 200).all())            # Crisis days are positions 200-299
        self.assertTrue(np.all(np.diff(sims[:, :10], axis=1) == 1))   # consecutive days inside a block

    def test_centering_puts_the_average_at_the_forward(self):
        rng = np.random.default_rng(1)
        end = end_rates(rng.normal(0.0003, 0.004, (5000, 126)), 95.0, forward=96.0)
        self.assertAlmostEqual(end.mean(), 96.0, places=8)


class TestScoring(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(2)
        self.spot, self.fwd = 95.0, 96.0
        self.end = end_rates(rng.normal(0, 0.004, (20000, 126)), self.spot, self.fwd)
        self.grid = pd.DataFrame([score_ratio(h, self.fwd, self.spot, self.end, 0.95)
                                  for h in np.linspace(0, 1, 21)])

    def test_full_hedge_costs_exactly_the_premium(self):
        premium = (96 / 95 - 1) * 100
        full = score_ratio(1.0, self.fwd, self.spot, self.end, 0.95)
        for k in ["expected_pct", "var_pct", "es_pct", "best5_pct"]:
            self.assertAlmostEqual(full[k], premium, places=8)

    def test_expected_cost_same_for_every_ratio(self):
        # Centred on the forward, hedging changes the risk, not the average cost
        np.testing.assert_allclose(self.grid["expected_pct"], self.grid["expected_pct"].iloc[0], atol=1e-8)

    def test_recommend_picks_smallest_ratio_that_fits(self):
        budget = 3.0
        h = recommend(budget, self.grid)
        self.assertLessEqual(self.grid.set_index("hedge_ratio").loc[h, "var_pct"], budget)
        smaller = self.grid[self.grid["hedge_ratio"] < h - 1e-9]
        self.assertTrue((smaller["var_pct"] > budget).all())

    def test_budget_below_premium_means_full_hedge(self):
        self.assertEqual(recommend(0.1, self.grid), 1.0)

    def test_more_tolerance_never_means_more_hedging(self):
        recs = [recommend(b, self.grid) for b in [0.5, 1, 2, 4, 6, 9, 20]]
        self.assertEqual(recs, sorted(recs, reverse=True))


class TestSavedScores(unittest.TestCase):
    """Smoke test on the real output (run optimizer.py first)."""

    def test_riskier_regimes_never_get_less_hedging(self):
        scores = pd.read_csv(UTILITY_SCORES_FILE)
        for budget in RISK_LEVELS.values():
            recs = [recommend(budget, scores[scores["regime"] == r]) for r in REGIME_NAMES]
            self.assertEqual(recs, sorted(recs), f"budget {budget}%: {recs}")

    def test_sanity_extremes(self):
        # The plan's check: very cautious -> fully hedged; very relaxed in calm markets -> unhedged
        calm = pd.read_csv(UTILITY_SCORES_FILE).query("regime == 'Calm'")
        self.assertEqual(recommend(RISK_LEVELS["Very cautious"], calm), 1.0)
        self.assertEqual(recommend(RISK_LEVELS["Very relaxed"], calm), 0.0)


if __name__ == "__main__":
    unittest.main()