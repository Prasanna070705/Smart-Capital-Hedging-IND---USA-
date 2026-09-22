# tests/test_advisor.py
# Tests for the functions behind the app. Run from the fx-hedging root:
#   python -m unittest discover tests -v
import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from config import FORWARD_QUOTES_FILE, RISK_LEVELS
from advisor import load_market, score_for_tenor, budget_pct_from_inr, advise, candidates_table


class TestAdvisor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load_market()
        cls.fwd6, cls.grid6 = score_for_tenor(cls.m, 6)

    def test_six_month_forward_matches_objective_2(self):
        quotes = pd.read_csv(FORWARD_QUOTES_FILE)
        self.assertAlmostEqual(self.fwd6, quotes["forward"].iloc[-1], places=4)

    def test_longer_payments_have_higher_forwards_and_more_risk(self):
        # India's rate is above the US rate, so the forward rises with time; risk grows too
        f3, g3 = score_for_tenor(self.m, 3)
        f12, g12 = score_for_tenor(self.m, 12)
        self.assertLess(f3, self.fwd6)
        self.assertLess(self.fwd6, f12)
        self.assertLess(g3.iloc[0]["var_pct"], g12.iloc[0]["var_pct"])

    def test_rupee_budget_conversion(self):
        # ₹40 lakh on a USD 1,000,000 payment at 100 = 4,00,00,000 -> 40 lakh is 4% of 10 crore
        self.assertAlmostEqual(budget_pct_from_inr(40e5, 1_000_000, 100.0), 4.0)

    def test_amounts_scale_with_the_invoice(self):
        a1 = advise(self.m, self.fwd6, self.grid6, 1_000_000, RISK_LEVELS["Balanced"])
        a2 = advise(self.m, self.fwd6, self.grid6, 2_000_000, RISK_LEVELS["Balanced"])
        self.assertEqual(a1["ratio"], a2["ratio"])
        self.assertAlmostEqual(a2["var_inr"], 2 * a1["var_inr"], places=2)
        self.assertAlmostEqual(a1["hedge_usd"] + a1["open_usd"], 1_000_000)

    def test_ten_crore_example(self):
        # The 10-crore electronics buyer, 6 months, Balanced, Calm market (2026-09-18 snapshot)
        usd = 1e8 / self.m["spot"]
        a = advise(self.m, self.fwd6, self.grid6, usd, RISK_LEVELS["Balanced"])
        self.assertEqual(a["ratio"], 0.5)
        self.assertTrue(a["fits_budget"])
        self.assertLessEqual(a["var_inr"], a["budget_inr"])

    def test_candidates_table_has_the_recommendation(self):
        t = candidates_table(self.grid6, 1e8, 0.5)
        self.assertEqual(len(t), 5)
        self.assertTrue(t["Hedged"].str.contains("recommended").any())


if __name__ == "__main__":
    unittest.main()