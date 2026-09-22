# src/backtest.py
# Walk-forward backtest: at the start of every month since 2012, decide a hedge using ONLY data
# available that day, then check what the payment actually cost 6 months later.
# Run from the fx-hedging root:  python src/backtest.py      (about 20 seconds)
import time

import numpy as np
import pandas as pd

from config import (MASTER_FILE, FORWARD_QUOTES_FILE, BACKTEST_FILE, BACKTEST_SUMMARY_FILE, BACKTEST_START,
                    BACKTEST_N_SIMS, REGIME_FEATURES, REGIME_HISTORY_START, REGIME_NAMES, N_REGIMES,
                    HORIZON_DAYS, BLOCK_LEN, CONFIDENCE, RANDOM_SEED, RATIO_GRID, RISK_LEVELS, HEDGE_RATIOS)
from regime_features import build_feature_matrix, fit_scaler
from regime_model import fit_kmeans, name_clusters, label
from risk_baseline import block_bootstrap
from optimizer import transition_matrix, simulate_returns, end_rates, score_ratio, recommend


def decision_dates(master, start, horizon):
    """First trading day of each month from `start`, keeping only dates whose payment date
    (`horizon` trading days later) is inside the data."""
    idx = master.index
    firsts = pd.Series(idx, index=idx).loc[start:].groupby(idx[idx >= start].to_period("M")).first()
    last_ok = idx[len(idx) - 1 - horizon]
    return [d for d in firsts if d <= last_ok]


def grid_scores(spot_end, forward, spot):
    return pd.DataFrame([score_ratio(h, forward, spot, spot_end, CONFIDENCE) for h in RATIO_GRID])


def decide(master, quotes, d, rng_seed):
    """Everything the tool would have said on day d, using data up to and including d only."""
    past = master.loc[:d]

    # Regime model refit on the past only (scaler, clusters and names all re-learned)
    X = build_feature_matrix(past, REGIME_FEATURES, REGIME_HISTORY_START)
    scaler = fit_scaler(X)
    km = fit_kmeans(scaler.transform(X), N_REGIMES, RANDOM_SEED)
    labels = label(km, scaler, name_clusters(km, scaler, REGIME_FEATURES, REGIME_NAMES), X)
    regime = labels.iloc[-1]

    returns = past.loc[labels.index, "daily_return"].to_numpy()
    trans = transition_matrix(labels.to_numpy(), BLOCK_LEN, REGIME_NAMES)
    spot, forward = quotes.loc[d, "spot"], quotes.loc[d, "forward"]

    # Regime-aware simulation (Day 10's method) and a regime-blind one (Day 3's plain bootstrap)
    rng = np.random.default_rng(rng_seed)
    aware = simulate_returns(returns, labels.to_numpy(), regime, trans, REGIME_NAMES,
                             BACKTEST_N_SIMS, HORIZON_DAYS, BLOCK_LEN, rng)
    blind = block_bootstrap(returns, BACKTEST_N_SIMS, HORIZON_DAYS, BLOCK_LEN, np.random.default_rng(rng_seed))
    g_aware = grid_scores(end_rates(aware, spot, forward), forward, spot)
    g_blind = grid_scores(end_rates(blind, spot, forward), forward, spot)

    row = {"date": d, "regime": regime, "spot": spot, "forward": forward,
           "vol_20d": X["vol_20d"].iloc[-1], "predicted_var_aware": g_aware.iloc[0]["var_pct"],
           "predicted_var_blind": g_blind.iloc[0]["var_pct"]}
    for level, budget in RISK_LEVELS.items():
        row[f"aware_{level}"] = recommend(budget, g_aware)
        row[f"blind_{level}"] = recommend(budget, g_blind)
    return row


def realised_extra_pct(ratio, forward, spot, spot_end):
    """What the payment actually cost vs today's spot, % of today's cost."""
    return ((ratio * forward + (1 - ratio) * spot_end) / spot - 1) * 100


def summarise(name, ratios, dec):
    """Realised results of hedging `ratios` (one per decision), % of the cost at decision time."""
    extra = realised_extra_pct(ratios, dec["forward"], dec["spot"], dec["spot_end"])
    return {"strategy": name, "avg_hedge": np.mean(ratios), "avg_extra_pct": extra.mean(),
            "std_extra_pct": extra.std(), "worst_5pct": np.quantile(extra, CONFIDENCE),
            "worst_pct": extra.max(), "best_pct": extra.min()}


def print_table(title, rows):
    print(title)
    print(f"   {'strategy':30s}{'avg hedge':>10s}{'average':>9s}{'std':>7s}{'worst 5%':>10s}{'worst':>8s}{'best':>8s}")
    for r in rows:
        print(f"   {r['strategy']:30s}{r['avg_hedge']:>10.0%}{r['avg_extra_pct']:>8.2f}%{r['std_extra_pct']:>6.2f}%"
              f"{r['worst_5pct']:>9.2f}%{r['worst_pct']:>7.2f}%{r['best_pct']:>7.2f}%")


def main():
    start_time = time.time()
    master = pd.read_csv(MASTER_FILE, parse_dates=["date"], index_col="date")
    quotes = pd.read_csv(FORWARD_QUOTES_FILE, parse_dates=["date"], index_col="date")
    dates = [d for d in decision_dates(master, BACKTEST_START, HORIZON_DAYS) if d in quotes.index]

    rows = []
    for i, d in enumerate(dates):
        rows.append(decide(master, quotes, d, RANDOM_SEED + i))
        if (i + 1) % 50 == 0:
            print(f"   ... {i + 1}/{len(dates)} decisions ({time.time() - start_time:.0f}s)")
    dec = pd.DataFrame(rows).set_index("date")

    # What actually happened: the spot rate HORIZON_DAYS trading days after each decision
    pos = master.index.get_indexer(dec.index)
    dec["spot_end"] = master["usd_inr_spot"].to_numpy()[pos + HORIZON_DAYS]
    dec["actual_move_pct"] = (dec["spot_end"] / dec["spot"] - 1) * 100
    dec["premium_pct"] = (dec["forward"] / dec["spot"] - 1) * 100
    dec.round(4).assign(pay_date=master.index[pos + HORIZON_DAYS]).to_csv(BACKTEST_FILE, index_label="date")

    n = len(dec)
    print(f"\n{n} monthly decisions, {dec.index[0]:%Y-%m} to {dec.index[-1]:%Y-%m}, "
          f"about {n * 21 // HORIZON_DAYS} non-overlapping 6-month periods")
    print("Regime at decision time: " + ", ".join(f"{r} {(dec['regime'] == r).sum()}" for r in REGIME_NAMES))
    by_year = dec["premium_pct"].groupby(dec.index.year).mean()
    print(f"Forward premium per 6 months: {by_year.iloc[0]:.1f}% in {by_year.index[0]}, "
          f"{by_year.iloc[-1]:.1f}% in {by_year.index[-1]} (average {dec['premium_pct'].mean():.2f}%, "
          f"actual rupee move average {dec['actual_move_pct'].mean():.2f}%)")

    # 1. The plan's headline test: Balanced regime-aware vs the static ratios
    head = [summarise(f"Static {h:.0%}", np.full(n, h), dec) for h in HEDGE_RATIOS]
    head += [summarise("Balanced, regime-blind", dec["blind_Balanced"].to_numpy(), dec),
             summarise("Balanced, regime-aware", dec["aware_Balanced"].to_numpy(), dec)]
    print_table("\n1. Realised extra cost, % of cost at decision time", head)

    # 2. Fair test: same AVERAGE hedge, fixed vs adjusted each month
    print("\n2. Same average hedge: does adjusting month by month beat holding it fixed?")
    fair = []
    for level in RISK_LEVELS:
        a = dec[f"aware_{level}"].to_numpy()
        trio = [summarise(f"{level}: regime-aware", a, dec),
                summarise(f"{level}: regime-blind", dec[f"blind_{level}"].to_numpy(), dec),
                summarise(f"{level}: fixed at {a.mean():.0%}", np.full(n, a.mean()), dec)]
        fair += trio
        for r in trio:
            print(f"   {r['strategy']:30s}{r['avg_hedge']:>10.0%}{r['avg_extra_pct']:>8.2f}%{r['std_extra_pct']:>6.2f}%"
                  f"{r['worst_5pct']:>9.2f}%{r['worst_pct']:>7.2f}%{r['best_pct']:>7.2f}%")

    # 3. Were the risk forecasts right? Unhedged VaR 95% should be exceeded about 5% of the time
    print("\n3. Risk forecast check: how often the actual 6-month move exceeded the predicted VaR 95% (target 5%)")
    print(f"   {'':10s}{'months':>7s}{'aware VaR':>11s}{'exceeded':>10s}{'blind VaR':>11s}{'exceeded':>10s}{'actual worst 5%':>17s}")
    groups = [("All", dec)] + [(r, dec[dec["regime"] == r]) for r in REGIME_NAMES]
    for name, g in groups:
        if len(g) == 0:
            continue
        act = g["actual_move_pct"]
        worst = f"{np.quantile(act, CONFIDENCE):.2f}%" if len(g) >= 20 else f"({act.max():.2f}% max)"
        print(f"   {name:10s}{len(g):>7d}{g['predicted_var_aware'].mean():>10.2f}%"
              f"{(act > g['predicted_var_aware']).mean():>10.1%}{g['predicted_var_blind'].mean():>10.2f}%"
              f"{(act > g['predicted_var_blind']).mean():>10.1%}{worst:>17s}")

    pd.DataFrame(head + fair).round(4).to_csv(BACKTEST_SUMMARY_FILE, index=False)
    print(f"\nSaved {BACKTEST_FILE.name} and {BACKTEST_SUMMARY_FILE.name} to outputs/ "
          f"({time.time() - start_time:.0f}s)")


if __name__ == "__main__":
    main()