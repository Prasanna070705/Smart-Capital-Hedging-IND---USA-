# tests/test_regime.py
# Unit and smoke tests for regime detection. Run from the fx-hedging root:
#   python -m unittest discover tests -v
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from config import MASTER_FILE, REGIME_LABELS_FILE, REGIME_NAMES
from regime_features import build_feature_matrix, fit_scaler
from regime_model import fit_kmeans, name_clusters, label


def three_blobs():
    """Synthetic data with three obvious volatility levels: 2%, 6% and 15%."""
    rng = np.random.default_rng(0)
    rows = [rng.normal([v, v], 0.003, size=(200, 2)) for v in (0.15, 0.02, 0.06)]   # deliberately unsorted
    idx = pd.bdate_range("2020-01-01", periods=600)
    return pd.DataFrame(np.vstack(rows), index=idx, columns=["vol_20d", "vol_60d"])


class TestFeatures(unittest.TestCase):
    def test_drops_missing_and_respects_start(self):
        idx = pd.bdate_range("1999-12-28", periods=6)
        m = pd.DataFrame({"a": [1, 2, np.nan, 4, 5, 6], "b": [1.0] * 6}, index=idx)
        X = build_feature_matrix(m, ["a", "b"], "2000-01-01")
        self.assertTrue(X.index[0] >= pd.Timestamp("2000-01-01"))
        self.assertFalse(X.isna().any().any())

    def test_scaler_gives_mean_0_std_1(self):
        X = three_blobs()
        Z = fit_scaler(X).transform(X)
        np.testing.assert_allclose(Z.mean(axis=0), 0, atol=1e-10)
        np.testing.assert_allclose(Z.std(axis=0), 1, atol=1e-10)


class TestNaming(unittest.TestCase):
    def setUp(self):
        self.X = three_blobs()
        self.scaler = fit_scaler(self.X)
        self.km = fit_kmeans(self.scaler.transform(self.X), 3, seed=42)
        self.mapping = name_clusters(self.km, self.scaler, ["vol_20d", "vol_60d"], REGIME_NAMES)
        self.regimes = label(self.km, self.scaler, self.mapping, self.X)

    def test_names_follow_volatility(self):
        # Rows 0-199 were 15% vol, 200-399 were 2%, 400-599 were 6%
        self.assertTrue((self.regimes.iloc[:200] == "Crisis").all())
        self.assertTrue((self.regimes.iloc[200:400] == "Calm").all())
        self.assertTrue((self.regimes.iloc[400:] == "Normal").all())

    def test_naming_survives_a_different_seed(self):
        # Cluster numbers change with the seed; the names must not
        km2 = fit_kmeans(self.scaler.transform(self.X), 3, seed=7)
        other = label(km2, self.scaler, name_clusters(km2, self.scaler, ["vol_20d", "vol_60d"], REGIME_NAMES), self.X)
        self.assertTrue((other == self.regimes).all())


class TestRegimeOutputs(unittest.TestCase):
    """Smoke test on the real saved output (run regime_model.py first)."""

    def test_labels_cover_up_to_the_last_day(self):
        master = pd.read_csv(MASTER_FILE, parse_dates=["date"], index_col="date")
        labels = pd.read_csv(REGIME_LABELS_FILE, parse_dates=["date"], index_col="date")
        self.assertEqual(labels.index[-1], master.index[-1])
        self.assertTrue(set(labels["regime"]) <= set(REGIME_NAMES))

    def test_known_crises_and_snapshot(self):
        labels = pd.read_csv(REGIME_LABELS_FILE, parse_dates=["date"], index_col="date")["regime"]
        self.assertTrue((labels.loc["2008-10-01":"2008-12-31"] == "Crisis").all())
        self.assertEqual(labels.iloc[-1], "Calm")   # 2026-09-18 snapshot; update after a data refresh


if __name__ == "__main__":
    unittest.main()