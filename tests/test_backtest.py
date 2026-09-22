# tests/test_backtest.py
# Tests for the walk-forward backtest. Run from the fx-hedging root:
#   python -m unittest discover tests -v
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from config import MASTER_FILE, FORWARD_QUOTES_FILE, BACKTEST_FILE, HORIZON_DAYS, RISK_LEVELS
from backtest import decision_dates, decide, realised_extra_pct


class TestBacktestMechanics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.master = pd.read_csv(MASTER_FILE, parse_dates=["date"], index_col="date")
        cls.quotes = pd.read_csv(FORWARD_QUOTES_FILE, parse_dates=["date"], index_col="date")

    def test_decision_dates_are_month_starts_with_room_for_the_payment(self):
        dates = decision_dates(self.master, "2012-01-01", HORIZON_DAYS)
        self.assertEqual(len({(d.year, d.month) for d in dates}), len(dates))   # one per month
        last_pos = self.master.index.get_loc(dates[-1])
        self.assertLess(last_pos + HORIZON_DAYS, len(self.master))

    def test_no_lookahead(self):
        # Scramble everything AFTER the decision date: the decision must not change
        d = decision_dates(self.master, "2015-06-01", HORIZON_DAYS)[0]
        future = self.master.copy()
        after = future.index > d
        future.loc[after, ["vol_20d", "vol_60d", "daily_return"]] *= 10
        a = decide(self.master, self.quotes, d, rng_seed=1)
        b = decide(future, self.quotes, d, rng_seed=1)
        self.assertEqual(a, b)

    def test_realised_cost_hand_calculated(self):
        # Spot 100, forward 102, rate ends at 110. Half hedged: (0.5 x 102 + 0.5 x 110) / 100 - 1 = 6%
        self.assertAlmostEqual(realised_extra_pct(0.5, 102, 100, 110), 6.0)
        self.assertAlmostEqual(realised_extra_pct(1.0, 102, 100, 70), 2.0)   # fully hedged: only the premium


class TestBacktestOutput(unittest.TestCase):
    """Smoke test on the saved output (run backtest.py first)."""

    @classmethod
    def setUpClass(cls):
        cls.dec = pd.read_csv(BACKTEST_FILE, parse_dates=["date", "pay_date"], index_col="date")

    def test_payments_are_six_months_later(self):
        days = (self.dec["pay_date"] - self.dec.index).dt.days
        self.assertTrue(days.between(170, 200).all())

    def test_hedges_rise_as_tolerance_falls(self):
        cols = [f"aware_{lvl}" for lvl in RISK_LEVELS]          # Very cautious ... Very relaxed
        diffs = np.diff(self.dec[cols].to_numpy(), axis=1)
        self.assertTrue((diffs <= 1e-9).all())

    def test_risk_forecast_roughly_calibrated(self):
        # VaR 95% should be exceeded about 5% of the time; allow 0-12% given overlapping windows
        rate = (self.dec["actual_move_pct"] > self.dec["predicted_var_aware"]).mean()
        self.assertLessEqual(rate, 0.12)


if __name__ == "__main__":
    unittest.main()