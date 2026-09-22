# tests/test_week1_smoke.py
# Smoke test: do the committed Week 1 outputs agree with each other and with the known results?
# Run from the fx-hedging root:  python -m unittest discover tests -v
import json
import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from config import (MASTER_FILE, VAR_ES_FILE, FORWARD_QUOTES_FILE, STATIC_HEDGE_FILE, OUTPUTS_DIR,
                    EXPOSURE_USD, HEDGE_RATIOS)


class TestWeek1Outputs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.master = pd.read_csv(MASTER_FILE, parse_dates=["date"], index_col="date")
        cls.var_es = json.loads(VAR_ES_FILE.read_text())
        cls.validation = json.loads((OUTPUTS_DIR / "obj1_validation.json").read_text())
        cls.quotes = pd.read_csv(FORWARD_QUOTES_FILE, parse_dates=["date"], index_col="date")
        cls.hedge = pd.read_csv(STATIC_HEDGE_FILE).set_index("hedge_ratio")

    # ---- The stages agree with each other ----
    def test_all_stages_share_the_same_last_date(self):
        last = self.master.index[-1]
        self.assertEqual(str(last.date()), self.var_es["as_of"])
        self.assertEqual(self.quotes.index[-1], last)

    def test_all_stages_share_the_same_spot(self):
        spot = self.master["usd_inr_spot"].iloc[-1]
        self.assertAlmostEqual(self.var_es["spot_today"], spot, places=4)
        self.assertAlmostEqual(self.quotes["spot"].iloc[-1], spot, places=4)

    def test_unhedged_row_equals_objective_1(self):
        self.assertAlmostEqual(self.hedge.loc[0.0, "var_inr"], self.var_es["var_inr"], delta=1)
        self.assertAlmostEqual(self.hedge.loc[0.0, "es_inr"], self.var_es["es_inr"], delta=1)

    def test_full_hedge_row_equals_forward_premium(self):
        premium = EXPOSURE_USD * (self.quotes["forward"].iloc[-1] - self.quotes["spot"].iloc[-1])
        for col in ["locked_premium_inr", "expected_increase_inr", "var_inr", "es_inr"]:
            self.assertAlmostEqual(self.hedge.loc[1.0, col], premium, delta=1)

    def test_every_hedge_ratio_present_and_risk_falls(self):
        self.assertEqual(list(self.hedge.index), HEDGE_RATIOS)
        self.assertTrue(self.hedge["var_inr"].is_monotonic_decreasing)

    def test_objective_1_validation_passed(self):
        self.assertTrue(self.validation["all_pass"])

    # ---- Known results for the 2026-09-18 snapshot (update these if you refresh the data) ----
    def test_snapshot_values(self):
        self.assertEqual(len(self.master), 13_403)
        self.assertAlmostEqual(self.var_es["var_pct_of_cost"], 9.196, places=2)
        self.assertAlmostEqual(self.quotes["forward"].iloc[-1], 96.6182, places=3)


if __name__ == "__main__":
    unittest.main()