# tests/test_chat_tools.py
# Tests for the chatbot's tools (Day 6). No internet needed. Run from the fx-hedging root:
#   python -m unittest discover tests -v
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from advisor import load_market
from chat_tools import TOOLS, run_tool


class TestChatTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load_market()

    def test_default_case_matches_the_app(self):
        r = run_tool("run_hedge_model", {"amount": 10, "unit": "INR_crore", "months": 6,
                                         "risk_level": "Balanced"}, self.m)
        self.assertEqual(r["recommended_hedge_pct"], 50)
        self.assertEqual(r["worst_1_in_20_extra_cost_hedged"], "₹39.8 lakh")
        self.assertEqual(r["worst_1_in_20_extra_cost_unhedged"], "₹71.7 lakh")

    def test_usd_and_custom_limit(self):
        r = run_tool("run_hedge_model", {"amount": 1_000_000, "unit": "USD", "months": 3, "limit_lakh": 20}, self.m)
        self.assertEqual(r["risk_level"], "custom")
        self.assertEqual(r["bad_case_limit"], "₹20.0 lakh")

    def test_bad_arguments_raise(self):
        with self.assertRaises(ValueError):
            run_tool("run_hedge_model", {"amount": 10, "unit": "INR_crore", "months": 15}, self.m)
        with self.assertRaises(ValueError):
            run_tool("run_hedge_model", {"amount": 10, "unit": "INR_crore", "months": 6, "risk_level": "Wild"}, self.m)
        with self.assertRaises(ValueError):
            run_tool("delete_everything", {}, self.m)

    def test_cost_context_tool(self):
        r = run_tool("hedging_cost_context", {}, self.m)
        self.assertEqual(r["verdict"], "cheap")

    def test_tool_schemas_are_complete(self):
        names = {t["function"]["name"] for t in TOOLS}
        self.assertEqual(names, {"run_hedge_model", "hedging_cost_context"})
        for t in TOOLS:
            self.assertEqual(t["function"]["parameters"]["type"], "object")


if __name__ == "__main__":
    unittest.main()