# tests/test_charts_v11.py
# Tests for the v1.1 chart specifications. Run from the fx-hedging root:
#   python -m unittest discover tests -v
import json
import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from config import REGIME_LABELS_FILE
from advisor import load_market, simulate_payment, scores_from_paths, advise, outcome_histogram
from charts import outcome_histogram_chart, risk_curve_chart, regime_timeline_chart


class TestCharts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        m = load_market()
        cls.fwd, cls.end = simulate_payment(m, 6)
        cls.grid = scores_from_paths(cls.fwd, m["spot"], cls.end)
        cls.usd = 1e8 / m["spot"]
        cls.a = advise(m, cls.fwd, cls.grid, cls.usd, 4.0)
        cls.m = m

    def test_histogram_marks_limit_and_var(self):
        hist = outcome_histogram(self.end, self.fwd, self.m["spot"], self.usd, [0.0, 0.5])
        data, spec = outcome_histogram_chart(hist, self.a["var_inr"] / 1e5, self.a["budget_inr"] / 1e5)
        rules = spec["layer"][1]["data"]["values"]
        self.assertAlmostEqual(rules[0]["x"], 40.0, places=1)          # limit: 4% of 10 crore = 40 lakh
        self.assertAlmostEqual(rules[1]["x"], 39.8, places=1)          # VaR with 50% hedge
        self.assertEqual(set(data["Strategy"]), {"Hedge 0%", "Hedge 50%"})
        json.dumps(spec)                                               # must be plain JSON for Streamlit

    def test_risk_curve_highlights_one_point(self):
        data, spec = risk_curve_chart(self.grid, self.a["cost_today_inr"], 40.0, self.a["ratio"])
        self.assertEqual(data["Recommended"].sum(), 1)
        self.assertEqual(data.loc[data["Recommended"], "Hedge"].iloc[0], 50)
        json.dumps(spec)

    def test_regime_timeline(self):
        labels = pd.read_csv(REGIME_LABELS_FILE, parse_dates=["date"], index_col="date")
        data, spec = regime_timeline_chart(labels, days=500)
        self.assertEqual(len(data), 500)
        self.assertTrue(set(data["Regime"]) <= {"Calm", "Normal", "Crisis"})
        json.dumps(spec)


if __name__ == "__main__":
    unittest.main()