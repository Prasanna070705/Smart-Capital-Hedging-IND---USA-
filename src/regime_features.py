# src/regime_features.py
# Objective 3, step 1: choose, build and standardise the features the regime model learns from.
# Run from the fx-hedging root:  python src/regime_features.py
import joblib
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from config import (MASTER_FILE, MODELS_DIR, REGIME_FEATURES_FILE, SCALER_FILE,
                    REGIME_FEATURES, REGIME_HISTORY_START, RANDOM_SEED)

# Feature sets compared before choosing (the plan's original set is the last one)
FEATURE_SETS = {
    "volatility only":          ["vol_20d", "vol_60d"],
    "volatility + rate_diff":   ["vol_20d", "vol_60d", "rate_diff"],
    "volatility + inflation":   ["vol_20d", "vol_60d", "inflation_diff"],
}
CRISES = {"GFC": ("2008-09-15", "2009-03-31"), "Taper": ("2013-06-01", "2013-09-30")}
RECENT = ("2022-01-01", None)   # the years that matter most for today's hedging decision


def build_feature_matrix(master, features, start):
    """Chosen feature columns from `start` onward, keeping only days where every feature exists.
    Every column is already strictly trailing (built in features.py), so no row uses future data."""
    return master.loc[start:, features].dropna()


def fit_scaler(X):
    """z-score each feature (mean 0, std 1) so no feature dominates K-Means by its units."""
    return StandardScaler().fit(X)


def quick_regimes(X, k=3):
    """Quick K-Means with k=3, clusters named by vol_20d (lowest = Calm). Used only to compare feature sets."""
    scaler = fit_scaler(X)
    km = KMeans(n_clusters=k, n_init=10, random_state=RANDOM_SEED).fit(scaler.transform(X))
    centre_vol = scaler.inverse_transform(km.cluster_centers_)[:, 0]
    names = dict(zip(centre_vol.argsort(), ["Calm", "Normal", "Crisis"]))
    return pd.Series([names[c] for c in km.labels_], index=X.index)


def main():
    master = pd.read_csv(MASTER_FILE, parse_dates=["date"], index_col="date")
    last_day = master.index[-1]

    # 1. Compare feature sets on what the hedging tool needs
    print("1. Comparing feature sets (quick K-Means, k = 3)")
    print(f"   {'feature set':26s}{'live today?':>12s}{'GFC crisis':>12s}{'Taper crisis':>14s}"
          f"{'2022+ Calm':>12s}{'changes/yr':>12s}")
    for name, feats in FEATURE_SETS.items():
        X = build_feature_matrix(master, feats, REGIME_HISTORY_START)
        reg = quick_regimes(X)
        live = "yes" if X.index[-1] == last_day else f"no ({X.index[-1]:%Y-%m})"
        crisis = [(reg.loc[a:b] == "Crisis").mean() for a, b in CRISES.values()]
        recent_calm = (reg.loc[RECENT[0]:] == "Calm").mean()
        per_year = ((reg != reg.shift()).sum() - 1) / ((reg.index[-1] - reg.index[0]).days / 365.25)
        print(f"   {name:26s}{live:>12s}{crisis[0]:>12.0%}{crisis[1]:>14.0%}{recent_calm:>12.0%}{per_year:>12.1f}")

    print("\n   Macro levels drift over decades: rate_diff averaged "
          f"{master.loc['2000':'2012', 'rate_diff'].mean():.1f} points in 2000-2012 but "
          f"{master.loc['2022':, 'rate_diff'].mean():.1f} since 2022.")

    # 2. Build, standardise and save the chosen matrix
    X = build_feature_matrix(master, REGIME_FEATURES, REGIME_HISTORY_START)
    scaler = fit_scaler(X)
    Z = pd.DataFrame(scaler.transform(X), index=X.index, columns=[f"z_{c}" for c in REGIME_FEATURES])
    pd.concat([X, Z], axis=1).round(6).to_csv(REGIME_FEATURES_FILE, index_label="date")
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(scaler, SCALER_FILE)

    print(f"\n2. Chosen features: {', '.join(REGIME_FEATURES)}  "
          f"({len(X):,} days, {X.index[0].date()} -> {X.index[-1].date()})")
    print(f"   {'feature':12s}{'mean':>9s}{'std':>9s}{'min':>9s}{'max':>9s}")
    for col in REGIME_FEATURES:
        c = X[col]
        print(f"   {col:12s}{c.mean():>9.3f}{c.std():>9.3f}{c.min():>9.3f}{c.max():>9.3f}")
    print(f"   After scaling: largest |mean| {Z.mean().abs().max():.1e}, std {Z.std(ddof=0).mean():.3f}")

    # 3. Lookahead check: rebuilding with data cut at an earlier date gives identical rows
    cut = pd.Timestamp("2015-06-30")
    same = build_feature_matrix(master.loc[:cut], REGIME_FEATURES, REGIME_HISTORY_START).equals(X.loc[:cut])
    print(f"\n3. Lookahead check: rows up to {cut.date()} identical with or without later data: "
          f"{'PASS' if same else 'FAIL'}")

    print(f"\nSaved {REGIME_FEATURES_FILE.name} to data/processed/ and {SCALER_FILE.name} to models/")
    if not same:
        raise SystemExit("Lookahead check failed")


if __name__ == "__main__":
    main()