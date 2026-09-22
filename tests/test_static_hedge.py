# tests/test_static_hedge.py
# Unit tests for the static hedge comparison. Run from the fx-hedging root:
#   python -m unittest discover tests -v
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from static_hedge import hedged_cost, compare_ratios, history_check


class TestHedgedCost(unittest.TestCase):
    def test_hand_calculated(self):
        # USD 1,000, 25% at forward 100, 75% at spot 110: 1000 x (0.25 x 100 + 0.75 x 110) = 107,500
        self.assertAlmostEqual(hedged_cost(0.25, 100, 110, 1000), 107_500)

    def test_full_hedge_ignores_spot(self):
        self.assertAlmostEqual(hedged_cost(1.0, 100, 150, 1000), hedged_cost(1.0, 100, 60, 1000))


class TestCompareRatios(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(0)
        self.spot_end = 95 * np.exp(rng.normal(0.01, 0.05, 20_000))
        self.t = compare_ratios([0, 0.5, 1], 96.0, 95.0, self.spot_end, 1_000_000, 0.95).set_index("hedge_ratio")

    def test_full_hedge_has_no_risk(self):
        # 100% hedged: every path costs exactly 1,000,000 x (96 - 95) = 1,000,000 more than today
        full = self.t.loc[1]
        for col in ["expected_increase_inr", "var_inr", "es_inr", "best_5pct_inr", "locked_premium_inr"]:
            self.assertAlmostEqual(full[col], 1_000_000, places=2)
        self.assertAlmostEqual(full["std_inr"], 0, places=4)

    def test_no_hedge_locks_nothing(self):
        self.assertEqual(self.t.loc[0, "locked_premium_inr"], 0)

    def test_expected_cost_is_linear_in_ratio(self):
        mid = (self.t.loc[0, "expected_increase_inr"] + self.t.loc[1, "expected_increase_inr"]) / 2
        self.assertAlmostEqual(self.t.loc[0.5, "expected_increase_inr"], mid, places=2)

    def test_more_hedging_less_risk(self):
        self.assertGreater(self.t.loc[0, "var_inr"], self.t.loc[0.5, "var_inr"])
        self.assertGreater(self.t.loc[0.5, "var_inr"], self.t.loc[1, "var_inr"])


class TestHistoryCheck(unittest.TestCase):
    def test_hand_built_series(self):
        # Spot rises 1 rupee a day. Forward = spot + 1.5, horizon 2 days: realised = spot + 2,
        # so the forward is always cheaper than waiting.
        dates = pd.bdate_range("2020-01-01", periods=10)
        master = pd.DataFrame({"usd_inr_spot": np.arange(100.0, 110.0)}, index=dates)
        quotes = pd.DataFrame({"spot": master["usd_inr_spot"], "forward": master["usd_inr_spot"] + 1.5})
        h = history_check(master, quotes, 2)
        self.assertEqual(h["windows"], 8)
        self.assertEqual(h["forward_cheaper_share"], 1.0)


if __name__ == "__main__":
    unittest.main()
    