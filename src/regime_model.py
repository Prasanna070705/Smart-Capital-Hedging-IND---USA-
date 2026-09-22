# src/regime_model.py
# Objective 3, step 2: find market regimes with K-Means and label them Calm / Normal / Crisis.
# Run from the fx-hedging root (after regime_features.py):  python src/regime_model.py
import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

from config import (MASTER_FILE, REGIME_FEATURES_FILE, SCALER_FILE, KMEANS_FILE, REGIME_LABELS_FILE,
                    K_SELECTION_FILE, REGIME_FEATURES, K_CANDIDATES, N_REGIMES, REGIME_NAMES,
                    KMEANS_N_INIT, RANDOM_SEED, HORIZON_DAYS)

# Well-known stress periods, used only to sanity-check the labels (never to train)
KNOWN_PERIODS = {
    "GFC (Sep 2008 - Mar 2009)":     ("2008-09-15", "2009-03-31"),
    "Taper tantrum (Jun - Sep 2013)": ("2013-06-01", "2013-09-30"),
    "COVID shock (Mar - May 2020)":  ("2020-03-01", "2020-05-31"),
    "Quiet year (2024)":             ("2024-01-01", "2024-12-31"),
}
STABILITY_SEEDS = [0, 1, 2]


def fit_kmeans(Z, k, seed):
    return KMeans(n_clusters=k, n_init=KMEANS_N_INIT, random_state=seed).fit(Z)


def compare_k(Z, candidates, seed):
    """Elbow (inertia) and silhouette for each k. Silhouette uses a 4,000-day sample to stay fast."""
    rows = []
    for k in candidates:
        km = fit_kmeans(Z, k, seed)
        sil = silhouette_score(Z, km.labels_, sample_size=min(4000, len(Z)), random_state=seed)
        rows.append({"k": k, "inertia": km.inertia_, "silhouette": sil})
    return pd.DataFrame(rows)


def name_clusters(km, scaler, features, names):
    """Map cluster numbers to names by the centre's vol_20d: lowest = first name (Calm).
    K-Means numbers clusters arbitrarily, so this must be redone after every refit."""
    centres = scaler.inverse_transform(km.cluster_centers_)
    vol_col = features.index("vol_20d")
    order = np.argsort(centres[:, vol_col])          # cluster ids from calmest to most volatile
    return {int(cluster): names[rank] for rank, cluster in enumerate(order)}


def label(km, scaler, mapping, X):
    """Regime name for each row of raw (unscaled) features."""
    return pd.Series([mapping[c] for c in km.predict(scaler.transform(X))], index=X.index, name="regime")


def main():
    feats = pd.read_csv(REGIME_FEATURES_FILE, parse_dates=["date"], index_col="date")
    X = feats[REGIME_FEATURES]
    Z = feats[[f"z_{c}" for c in REGIME_FEATURES]].to_numpy()
    scaler = joblib.load(SCALER_FILE)

    # 1. How many clusters does the data support?
    comp = compare_k(Z, K_CANDIDATES, RANDOM_SEED)
    comp.round(4).to_csv(K_SELECTION_FILE, index=False)
    print("1. Choosing k (higher silhouette = better separated; look for the elbow in inertia)")
    print(f"   {'k':>3s}{'inertia':>10s}{'drop':>8s}{'silhouette':>12s}")
    prev = None
    for _, r in comp.iterrows():
        drop = "" if prev is None else f"{(1 - r['inertia'] / prev):.0%}"
        mark = "  <- chosen" if r["k"] == N_REGIMES else ""
        print(f"   {int(r['k']):>3d}{r['inertia']:>10.0f}{drop:>8s}{r['silhouette']:>12.3f}{mark}")
        prev = r["inertia"]

    # 2. Fit the chosen model and name its clusters
    km = fit_kmeans(Z, N_REGIMES, RANDOM_SEED)
    mapping = name_clusters(km, scaler, REGIME_FEATURES, REGIME_NAMES)
    regimes = label(km, scaler, mapping, X)

    centres = pd.DataFrame(scaler.inverse_transform(km.cluster_centers_), columns=REGIME_FEATURES)
    centres["regime"] = [mapping[i] for i in range(N_REGIMES)]
    centres["days"] = [(regimes == mapping[i]).sum() for i in range(N_REGIMES)]
    centres = centres.set_index("regime").loc[REGIME_NAMES[:N_REGIMES]]
    print(f"\n2. Regime centres (k = {N_REGIMES}), in real units")
    print(f"   {'regime':8s}" + "".join(f"{c:>12s}" for c in REGIME_FEATURES) + f"{'days':>8s}{'share':>7s}")
    for name, r in centres.iterrows():
        print(f"   {name:8s}" + "".join(f"{r[c]:>12.3f}" for c in REGIME_FEATURES)
              + f"{int(r['days']):>8,}{r['days'] / len(regimes):>7.0%}")

    # 3. Sanity checks against history
    print("\n3. Regimes during known periods (share of days)")
    for label_, (a, b) in KNOWN_PERIODS.items():
        shares = regimes.loc[a:b].value_counts(normalize=True)
        text = ", ".join(f"{n} {shares.get(n, 0):.0%}" for n in REGIME_NAMES[:N_REGIMES] if shares.get(n, 0) > 0)
        print(f"   {label_:32s} {text}")
    switches = (regimes != regimes.shift()).sum() - 1
    years = (regimes.index[-1] - regimes.index[0]).days / 365.25
    print(f"   Regime changes: {switches} in {years:.1f} years ({switches / years:.1f} per year)")

    # 4. Stability: refit with other seeds; same labels?
    print("\n4. Stability across random seeds (share of days with the same label as seed "
          f"{RANDOM_SEED})")
    for s in STABILITY_SEEDS:
        km_s = fit_kmeans(Z, N_REGIMES, s)
        agree = (label(km_s, scaler, name_clusters(km_s, scaler, REGIME_FEATURES, REGIME_NAMES), X) == regimes).mean()
        print(f"   seed {s}: {agree:.2%}")

    # 5. Do regimes tell us anything about the NEXT 6 months? (evaluation only - uses future data,
    #    which is fine for checking, never for training)
    master = pd.read_csv(MASTER_FILE, parse_dates=["date"], index_col="date")
    spot = master["usd_inr_spot"]
    ahead = pd.DataFrame({
        "regime": regimes,
        "move_pct": (spot.shift(-HORIZON_DAYS) / spot - 1).reindex(regimes.index) * 100,
        "vol_pct": (master["daily_return"].rolling(HORIZON_DAYS).std().shift(-HORIZON_DAYS)
                    * np.sqrt(252)).reindex(regimes.index) * 100,
    }).dropna()
    print(f"\n5. What happened in the {HORIZON_DAYS} trading days AFTER each regime (does it predict risk?)")
    print(f"   {'regime':8s}{'days':>7s}{'avg move':>10s}{'worst 5%':>10s}{'next vol':>10s}")
    for name in REGIME_NAMES[:N_REGIMES]:
        g = ahead[ahead["regime"] == name]
        print(f"   {name:8s}{len(g):>7,}{g['move_pct'].mean():>9.1f}%{g['move_pct'].quantile(0.95):>9.1f}%"
              f"{g['vol_pct'].mean():>9.1f}%")

    # 6. Save
    labels_out = pd.concat([X, regimes], axis=1)
    labels_out.round(6).to_csv(REGIME_LABELS_FILE, index_label="date")
    joblib.dump({"kmeans": km, "mapping": mapping, "features": REGIME_FEATURES,
                 "trained_from": str(X.index[0].date()), "trained_to": str(X.index[-1].date()),
                 "sklearn_version": sklearn.__version__}, KMEANS_FILE)

    today = regimes.index[-1]
    run_len = (regimes[::-1] != regimes.iloc[-1]).argmax()
    print(f"\n6. Current regime on {today.date()}: {regimes.iloc[-1]} "
          f"(for the last {run_len} trading days)")
    print("   " + ", ".join(f"{c} {X[c].iloc[-1]:.1%}" for c in REGIME_FEATURES))
    print(f"\nSaved {REGIME_LABELS_FILE.name}, {K_SELECTION_FILE.name} to outputs/ and {KMEANS_FILE.name} to models/")


if __name__ == "__main__":
    main()