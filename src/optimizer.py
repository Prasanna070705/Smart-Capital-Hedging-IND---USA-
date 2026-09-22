# src/optimizer.py
# Objective 4a: recommend a hedge ratio from today's regime and the buyer's risk tolerance.
# Run from the fx-hedging root (after forward_pricing.py and regime_model.py):  python src/optimizer.py
import json

import numpy as np
import pandas as pd

from config import (MASTER_FILE, REGIME_LABELS_FILE, FORWARD_QUOTES_FILE, UTILITY_SCORES_FILE,
                    CANDIDATES_FILE, REGIME_NAMES, BLOCK_LEN, HORIZON_DAYS, N_SIMULATIONS,
                    CONFIDENCE, RANDOM_SEED, RATIO_GRID, RISK_LEVELS, HEDGE_RATIOS, VAR_ES_FILE)
from risk_baseline import var_es


# ---------- 1. Regime-aware simulation ----------

def load_regime_history():
    """Daily log returns and regime labels for the same days (2000 onward)."""
    master = pd.read_csv(MASTER_FILE, parse_dates=["date"], index_col="date")
    labels = pd.read_csv(REGIME_LABELS_FILE, parse_dates=["date"], index_col="date")["regime"]
    returns = master.loc[labels.index, "daily_return"].to_numpy()
    return returns, labels.to_numpy(), labels.iloc[-1]


def transition_matrix(labels, step, names):
    """P(regime in `step` days | regime today), counted from history. Rows sum to 1."""
    t = pd.crosstab(labels[:-step], labels[step:], normalize="index")
    return t.reindex(index=names, columns=names).fillna(0.0)


def simulate_returns(returns, labels, start_regime, trans, names, n_sims, horizon, block_len, rng):
    """Block bootstrap where each 10-day block is drawn from days of the path's current regime,
    and the regime then moves on by the historical transition probabilities. So a path that
    starts Calm stays calm-ish but can drift into Normal or Crisis, as history did."""
    n = len(returns)
    starts_by_regime = {r: np.flatnonzero(labels[: n - block_len + 1] == r) for r in names}
    cum_p = trans.cumsum(axis=1).to_numpy()
    n_blocks = int(np.ceil(horizon / block_len))
    regime = np.full(n_sims, names.index(start_regime))
    out = np.empty((n_sims, n_blocks * block_len))
    for b in range(n_blocks):
        for i, r in enumerate(names):
            paths = np.flatnonzero(regime == i)
            if paths.size:
                s = rng.choice(starts_by_regime[r], size=paths.size)
                out[paths, b * block_len:(b + 1) * block_len] = returns[s[:, None] + np.arange(block_len)]
        u = rng.random(n_sims)
        regime = (u[:, None] > cum_p[regime]).sum(axis=1)          # next block's regime
    return out[:, :horizon]


def end_rates(sim_returns, spot, forward=None):
    """Spot rate on the payment date for every path. If `forward` is given, rescale so the
    average path ends at the forward: the market's own expectation (see walkthrough)."""
    end = spot * np.exp(sim_returns.sum(axis=1))
    return end * forward / end.mean() if forward is not None else end


# ---------- 2. Scoring hedge ratios ----------

def score_ratio(ratio, forward, spot, spot_end, confidence):
    """Extra cost vs paying at today's spot, as % of today's cost, when `ratio` is hedged."""
    extra = (ratio * forward + (1 - ratio) * spot_end) / spot * 100 - 100
    var, es = var_es(extra, confidence)
    return {"hedge_ratio": ratio, "expected_pct": extra.mean(), "var_pct": var, "es_pct": es,
            "best5_pct": np.quantile(extra, 1 - confidence)}


def recommend(budget_pct, scores):
    """Smallest hedge ratio whose VaR fits the budget. If none fits (budget below the forward
    premium), hedge 100%: that is the lowest risk available."""
    ok = scores[scores["var_pct"] <= budget_pct + 1e-9]
    return float(ok["hedge_ratio"].min()) if len(ok) else 1.0


def score_grid(regime, returns, labels, trans, spot, forward, horizon=HORIZON_DAYS, seed=RANDOM_SEED):
    """All grid ratios scored for paths that start in `regime`."""
    rng = np.random.default_rng(seed)
    sims = simulate_returns(returns, labels, regime, trans, REGIME_NAMES, N_SIMULATIONS,
                            horizon, BLOCK_LEN, rng)
    spot_end = end_rates(sims, spot, forward)
    return pd.DataFrame([score_ratio(h, forward, spot, spot_end, CONFIDENCE) for h in RATIO_GRID])


# ---------- 3. Run everything ----------

def main():
    returns, labels, today_regime = load_regime_history()
    trans = transition_matrix(labels, BLOCK_LEN, REGIME_NAMES)
    quotes = pd.read_csv(FORWARD_QUOTES_FILE, parse_dates=["date"], index_col="date")
    spot, forward = quotes["spot"].iloc[-1], quotes["forward"].iloc[-1]
    premium = (forward / spot - 1) * 100

    print(f"1. Regime transitions over {BLOCK_LEN} trading days (row = now, column = {BLOCK_LEN} days later)")
    print("   " + " " * 8 + "".join(f"{c:>9s}" for c in REGIME_NAMES))
    for r in REGIME_NAMES:
        print(f"   {r:8s}" + "".join(f"{trans.loc[r, c]:>9.1%}" for c in REGIME_NAMES))

    # Validation: raw (uncentred) simulation vs Objective 1 and vs what actually happened (Day 9)
    stationary = pd.Series(labels).value_counts(normalize=True)
    rng = np.random.default_rng(RANDOM_SEED)
    mixed = []
    for r in REGIME_NAMES:   # start regimes in their historical proportions
        n = int(round(stationary[r] * N_SIMULATIONS))
        mixed.append(simulate_returns(returns, labels, r, trans, REGIME_NAMES, n, HORIZON_DAYS, BLOCK_LEN, rng))
    raw_pct = (np.exp(np.vstack(mixed).sum(axis=1)) - 1) * 100
    obj1 = json.loads(VAR_ES_FILE.read_text())["var_pct_of_cost"]
    print(f"\n2. Check: regime simulation with starting regimes in historical proportions gives "
          f"VaR {np.quantile(raw_pct, CONFIDENCE):.2f}% (Objective 1: {obj1:.2f}%)")

    # Score every regime
    grids = {}
    print(f"\n3. Unhedged risk by starting regime (centred on the forward {forward:.4f}; "
          f"premium {premium:.2f}%)")
    print(f"   {'regime':8s}{'VaR 95%':>9s}{'ES 95%':>9s}{'best 5%':>9s}")
    for r in REGIME_NAMES:
        g = score_grid(r, returns, labels, trans, spot, forward)
        g.insert(0, "regime", r)
        grids[r] = g
        u = g.iloc[0]
        print(f"   {r:8s}{u['var_pct']:>8.2f}%{u['es_pct']:>8.2f}%{u['best5_pct']:>8.2f}%")
    scores = pd.concat(grids.values(), ignore_index=True)
    scores.round(4).to_csv(UTILITY_SCORES_FILE, index=False)

    print("\n4. Recommended hedge ratio (smallest hedge whose VaR fits the budget)")
    print(f"   {'risk tolerance':16s}{'VaR budget':>11s}" + "".join(f"{r:>9s}" for r in REGIME_NAMES))
    for level, budget in RISK_LEVELS.items():
        recs = [recommend(budget, grids[r]) for r in REGIME_NAMES]
        print(f"   {level:16s}{budget:>10.1f}%" + "".join(f"{h:>9.0%}" for h in recs))

    # The plan's 6 candidate portfolios, today: 5 static ratios + the regime-aware recommendation
    today = grids[today_regime].set_index("hedge_ratio")
    balanced = recommend(RISK_LEVELS["Balanced"], grids[today_regime])
    cand = today.loc[HEDGE_RATIOS + [balanced]].reset_index()
    cand.insert(0, "portfolio", [f"Static {h:.0%}" for h in HEDGE_RATIOS] + [f"Regime-aware ({balanced:.0%})"])
    cand.drop(columns="regime").round(4).to_csv(CANDIDATES_FILE, index=False)
    print(f"\n5. Today's regime: {today_regime}. The 6 candidates for a Balanced buyer "
          f"(budget {RISK_LEVELS['Balanced']:.1f}%), % of today's cost:")
    print(f"   {'portfolio':22s}{'expected':>9s}{'VaR 95%':>9s}{'ES 95%':>9s}{'best 5%':>9s}  fits budget?")
    for _, c in cand.iterrows():
        fits = "yes" if c["var_pct"] <= RISK_LEVELS["Balanced"] + 1e-9 else "no"
        print(f"   {c['portfolio']:22s}{c['expected_pct']:>8.2f}%{c['var_pct']:>8.2f}%"
              f"{c['es_pct']:>8.2f}%{c['best5_pct']:>8.2f}%  {fits}")
    print(f"\nSaved {UTILITY_SCORES_FILE.name} and {CANDIDATES_FILE.name} to outputs/")


if __name__ == "__main__":
    main()