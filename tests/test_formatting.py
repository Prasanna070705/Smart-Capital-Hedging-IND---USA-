# tests/test_formatting.py
# Tests for Indian number formatting and the glossary. Run from the fx-hedging root:
#   python -m unittest discover tests -v
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from formatting import indian_group, inr, inr_short, usd, rate
from glossary import GLOSSARY, tip


class TestFormatting(unittest.TestCase):
    def test_indian_grouping(self):
        self.assertEqual(indian_group(999), "999")
        self.assertEqual(indian_group(1000), "1,000")
        self.assertEqual(indian_group(100000), "1,00,000")
        self.assertEqual(indian_group(12345678), "1,23,45,678")
        self.assertEqual(indian_group(-9587000), "-95,87,000")

    def test_rupee_amounts(self):
        self.assertEqual(inr(95870000), "₹9,58,70,000")
        self.assertEqual(inr_short(3980000), "₹39.8 lakh")
        self.assertEqual(inr_short(100000000), "₹10.00 crore")
        self.assertEqual(inr_short(-5030000), "-₹50.3 lakh")

    def test_other_formats(self):
        self.assertEqual(usd(521540.4), "USD 521,540")
        self.assertEqual(rate(96.6182), "₹96.62")

    def test_glossary(self):
        self.assertIn("VaR 95%", GLOSSARY)
        self.assertEqual(tip("not a term"), "")
        self.assertTrue(all(len(v) > 20 for v in GLOSSARY.values()))


if __name__ == "__main__":
    unittest.main()
