# tests/test_formatting.py
# v1.1 Day 1: Indian number format, the answer card and the glossary. Run from the fx-hedging root:
#   python -m unittest discover tests -v
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from config import RISK_LEVELS
from advisor import load_market, score_for_tenor, advise
from formatting import indian_digits, inr, inr_short, usd, rate, months_text, answer_card
from glossary import GLOSSARY, tip

APP = Path(__file__).resolve().parent.parent / "app.py"


class TestIndianFormat(unittest.TestCase):
    def test_grouping(self):
        cases = {0: "0", 7: "7", 999: "999", 1000: "1,000", 99999: "99,999", 100000: "1,00,000",
                 12345678: "1,23,45,678", 1000000000: "1,00,00,00,000", -4000000: "-40,00,000"}
        for n, text in cases.items():
            self.assertEqual(indian_digits(n), text, n)

    def test_rupees(self):
        self.assertEqual(inr(12345678), "₹1,23,45,678")
        self.assertEqual(inr(1e8), "₹10,00,00,000")
        self.assertEqual(inr(-500.5, 2), "-₹500.50")
        self.assertEqual(inr(99999.6), "₹1,00,000")      # rounding carries into the next group
        self.assertEqual(inr(-0.4), "₹0")                # no negative zero

    def test_short_units(self):
        self.assertEqual(inr_short(1e8), "₹10.0 crore")
        self.assertEqual(inr_short(3_976_083), "₹39.8 lakh")
        self.assertEqual(inr_short(-2_126_240), "-₹21.3 lakh")
        self.assertEqual(inr_short(85_000), "₹85,000")
        self.assertEqual(inr_short(9_999_990), "₹1.0 crore")   # rounds up across the unit boundary

    def test_other_formats(self):
        self.assertEqual(usd(521539.58), "USD 521,540")
        self.assertEqual(rate(96.61821), "₹96.62 per USD")
        self.assertEqual(months_text(1), "1 month")
        self.assertEqual(months_text(6), "6 months")


class TestAnswerCard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load_market()
        cls.fwd, cls.grid = score_for_tenor(cls.m, 6)

    def card(self, level, usd_amount=None):
        usd_amount = usd_amount or 1e8 / self.m["spot"]
        a = advise(self.m, self.fwd, self.grid, usd_amount, RISK_LEVELS[level])
        return a, answer_card(a, 6)

    def test_ten_crore_example(self):
        # Same buyer as the README: ₹10 crore, 6 months, Balanced, 2026-09-18 snapshot -> hedge 50%
        a, c = self.card("Balanced")
        self.assertEqual(c["headline"], "Recommendation: hedge 50%")
        self.assertIn("USD 521,540", c["action"])
        self.assertIn("₹96.62 per USD", c["action"])
        self.assertIn("₹39.8 lakh", c["protection"])
        self.assertIn("₹71.7 lakh", c["protection"])
        self.assertEqual(c["status"], "fits")

    def test_no_hedge_and_full_hedge_wording(self):
        _, relaxed = self.card("Very relaxed")
        self.assertEqual(relaxed["headline"], "Recommendation: hedge 0%")
        self.assertIn("Don't book a forward", relaxed["action"])
        self.assertEqual(relaxed["cost"], "")
        _, cautious = self.card("Very cautious")
        self.assertEqual(cautious["headline"], "Recommendation: hedge 100%")
        self.assertIn("full", cautious["action"])
        self.assertIn("Locking in costs", cautious["cost"])

    def test_over_limit_is_said_plainly(self):
        a = advise(self.m, self.fwd, self.grid, 1_000_000, 0.1)      # a limit tighter than the premium
        c = answer_card(a, 6)
        self.assertEqual(c["status"], "over")
        self.assertIn("above your limit", c["protection"])

    def test_every_number_in_the_card_comes_from_advise(self):
        # The card only rewords advise(): each rupee figure it shows is one of advise()'s amounts
        a, c = self.card("Balanced")
        shown = re.findall(r"₹([\d.,]+) lakh", " ".join(c.values()))
        allowed = {inr_short(a[k]).split("₹")[1].split(" ")[0]
                   for k in ("var_inr", "unhedged_var_inr", "budget_inr", "premium_inr")}
        self.assertTrue(shown)
        self.assertTrue(set(shown) <= allowed, set(shown) - allowed)


class TestGlossary(unittest.TestCase):
    def test_entries_are_short_plain_sentences(self):
        for term, text in GLOSSARY.items():
            self.assertEqual(term, term.lower())
            self.assertTrue(text.endswith(")") or text.endswith("."), term)
            self.assertLess(len(text), 260, term)

    def test_lookup(self):
        self.assertEqual(tip("Spot rate"), GLOSSARY["spot rate"])
        with self.assertRaises(KeyError):
            tip("no such term")

    def test_every_tooltip_the_app_asks_for_exists(self):
        # Catches a typo in app.py's tip("...") calls without needing Streamlit
        used = re.findall(r'tip\("([^"]+)"\)', APP.read_text(encoding="utf-8"))
        self.assertTrue(used)
        for term in used:
            tip(term)


if __name__ == "__main__":
    unittest.main()
