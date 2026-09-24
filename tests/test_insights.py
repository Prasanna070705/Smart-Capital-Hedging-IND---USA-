# tests/test_insights.py
# Tests for the v1.1 insights. Run from the fx-hedging root:
#   python -m unittest discover tests -v
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from config import MASTER_FILE
from advisor import load_market, simulate_payment, scores_from_paths, advise
from insights import premium_context, breakeven, tenor_curve, stress_replay, bank_quote_grid, summary_csv


class TestInsights(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load_market()

    def test_premium_context_snapshot(self):
        p = premium_context()
        self.assertAlmostEqual(p["today"], 1.56, places=2)             # 2026-09-18 snapshot
        self.assertEqual(p["verdict"], "cheap")
        self.assertTrue(p["low"] <= p["today"] <= p["high"])

    def test_breakeven_hand_built(self):
        b = breakeven(100.0, np.array([98.0, 99.0, 101.0, 102.0]))
        self.assertEqual(b["hedge_wins_pct"], 50.0)                    # 2 of 4 paths end above the forward

    def test_breakeven_is_the_forward(self):
        fwd, end = simulate_payment(self.m, 6)
        self.assertAlmostEqual(breakeven(fwd, end)["rate"], fwd)

    def test_tenor_curve(self):
        t = tenor_curve(self.m, 1e8 / self.m["spot"], 4.0)
        self.assertEqual(list(t["Months"]), list(range(1, 13)))
        self.assertTrue(t["Forward"].is_monotonic_increasing)          # India rates above US rates
        self.assertTrue(t["Unhedged worst 1-in-20 (lakh)"].is_monotonic_increasing)
        self.assertEqual(t.loc[t["Months"] == 6, "Hedge %"].iloc[0], 50.0)   # matches the main recommendation
        self.assertTrue((t["Hedged worst 1-in-20 (lakh)"] <= 40.0 + 1e-6).all())   # always within the limit

        # ---------- Day 4 ----------
    def test_stress_replay_hand_check(self):
        master = pd.read_csv(MASTER_FILE, parse_dates=["date"], index_col="date")
        t = stress_replay(master, 100.0, 101.0, 1_000_000, 0.5, 126).set_index("Episode")
        taper = t.loc["2013 taper tantrum"]
        self.assertAlmostEqual(taper["Rupee move %"], (61.09 / 53.65 - 1) * 100, places=2)
        end = 100 * 61.09 / 53.65
        self.assertAlmostEqual(taper["Extra cost unhedged (lakh)"], 1e6 * (end - 100) / 1e5, places=3)
        self.assertAlmostEqual(taper["Extra cost with hedge (lakh)"],
                               1e6 * (0.5 * 101 + 0.5 * end - 100) / 1e5, places=3)

    def test_bank_spread_means_more_hedging_cost(self):
        fwd, end = simulate_payment(self.m, 6)
        fair = advise(self.m, fwd, scores_from_paths(fwd, self.m["spot"], end), 1e6, 4.0)
        dear = advise(self.m, fwd + 0.5, bank_quote_grid(fwd + 0.5, self.m["spot"], end), 1e6, 4.0)
        self.assertGreaterEqual(dear["ratio"], fair["ratio"] - 1e-9)     # never needs less hedging
        self.assertGreater(dear["premium_inr"] / max(dear["ratio"], 1e-9),
                           fair["premium_inr"] / max(fair["ratio"], 1e-9))

    def test_summary_csv(self):
        fwd, end = simulate_payment(self.m, 6)
        grid = scores_from_paths(fwd, self.m["spot"], end)
        ctx = {"market": self.m, "invoice_usd": 1e6, "months": 6, "forward": fwd,
               "advice": advise(self.m, fwd, grid, 1e6, 4.0)}
        text = summary_csv(ctx, premium_context()).decode()
        self.assertIn("Recommended hedge ratio (%)", text)
        self.assertIn("not financial advice", text)


if __name__ == "__main__":
    unittest.main()