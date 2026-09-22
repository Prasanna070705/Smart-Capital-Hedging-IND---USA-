# tests/test_charts.py
# Tests for the data behind the app's charts and track record. Run from the fx-hedging root:
#   python -m unittest discover tests -v
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from advisor import (load_market, simulate_payment, scores_from_paths, score_for_tenor, outcome_histogram,
                     load_track_record)


class TestChartData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load_market()
        cls.fwd, cls.end = simulate_payment(cls.m, 6)

    def test_paths_and_grid_agree_with_score_for_tenor(self):
        fwd2, grid2 = score_for_tenor(self.m, 6)
        grid = scores_from_paths(self.fwd, self.m["spot"], self.end)
        self.assertAlmostEqual(self.fwd, fwd2)
        self.assertTrue(np.allclose(grid.to_numpy(), grid2.to_numpy()))

    def test_histogram_shares_sum_to_100(self):
        h = outcome_histogram(self.end, self.fwd, self.m["spot"], 1e6, [0.0, 0.5])
        np.testing.assert_allclose(h.sum().to_numpy(), 100.0)

    def test_hedging_narrows_the_spread(self):
        h = outcome_histogram(self.end, self.fwd, self.m["spot"], 1e6, [0.0, 0.5])
        centres = h.index.to_numpy()
        spread = {c: np.sqrt(np.average((centres - np.average(centres, weights=h[c])) ** 2, weights=h[c]))
                  for c in h.columns}
        self.assertLess(spread["Hedge 50%"], spread["Hedge 0%"])

    def test_full_hedge_alone_does_not_break(self):
        h = outcome_histogram(self.end, self.fwd, self.m["spot"], 1e6, [1.0])
        self.assertAlmostEqual(h["Hedge 100%"].max(), 100.0)

    def test_track_record_loads(self):
        record = load_track_record()
        self.assertIsNotNone(record)
        dec, summary = record
        self.assertGreater(len(dec), 100)
        self.assertIn("Static 50%", set(summary["strategy"]))


if __name__ == "__main__":
    unittest.main()