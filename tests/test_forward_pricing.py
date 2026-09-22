# tests/test_forward_pricing.py
# Unit tests for covered interest parity. Run from the fx-hedging root:
#   python -m unittest discover tests -v
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from forward_pricing import cip_forward, forward_premium_pct


class TestCipForward(unittest.TestCase):
    def test_hand_calculated_forward(self):
        # Spot 100, India 6%, US 4%, 6 months. By hand:
        # F = 100 x (1 + 0.06 x 0.5) / (1 + 0.04 x 0.5) = 100 x 1.03 / 1.02 = 100.980392...
        self.assertAlmostEqual(cip_forward(100, 6, 4, 0.5), 100 * 1.03 / 1.02, places=10)
        self.assertAlmostEqual(cip_forward(100, 6, 4, 0.5), 100.9803921569, places=8)

    def test_equal_rates_give_forward_equal_to_spot(self):
        self.assertAlmostEqual(cip_forward(95.87, 5, 5, 0.5), 95.87)

    def test_higher_rupee_rate_means_forward_above_spot(self):
        self.assertGreater(cip_forward(95.87, 6.5, 4.0, 0.5), 95.87)
        self.assertLess(cip_forward(95.87, 3.0, 4.0, 0.5), 95.87)

    def test_zero_tenor_gives_spot(self):
        self.assertAlmostEqual(cip_forward(95.87, 6.5, 4.0, 0.0), 95.87)

    def test_uses_period_rate_not_annual_rate(self):
        # The classic mistake: using annual rates without x t. Must NOT equal 100 x 1.06 / 1.04
        self.assertNotAlmostEqual(cip_forward(100, 6, 4, 0.5), 100 * 1.06 / 1.04, places=4)


class TestForwardPremium(unittest.TestCase):
    def test_premium_hand_calculated(self):
        # Forward 101 on spot 100 over 6 months: 1% for the period, 2% annualised
        period, annual = forward_premium_pct(101, 100, 0.5)
        self.assertAlmostEqual(period, 1.0)
        self.assertAlmostEqual(annual, 2.0)


if __name__ == "__main__":
    unittest.main()