# src/risk_baseline.py
# Objective 1: how much could a 6-month USD payment cost in the worst cases if left unhedged?
# Run from the fx-hedging root:  python src/risk_baseline.py
import json

import numpy as np
import pandas as pd

from config import (MASTER_FILE, OUTPUTS_DIR, VAR_ES_FILE, MC_PATHS_FILE, EXPOSURE_USD,
                    HORIZON_DAYS, N_SIMULATIONS, BLOCK_LEN, HISTORY_START, CONFIDENCE, RANDOM_SEED)


def load_history():
    """Daily log returns from the chosen history window, plus today's spot rate."""
    master = pd.read_csv(MASTER_FILE, parse_dates=["date"], index_col="date")
    returns = master.loc[HISTORY_START:, "daily_return"].dropna().to_numpy()
    spot_today = master["usd_inr_spot"].iloc[-1]
    as_of = master.index[-1].date()
    return returns, spot_today, as_of


def block_bootstrap(returns, n_sims, horizon, block_len, rng):
    """Build n_sims future return paths by gluing together random blocks of consecutive
    historical days. Keeping days together preserves volatility clustering (calm weeks stay
    calm, turbulent weeks stay turbulent), which sampling single random days would destroy."""
    n_blocks = int(np.ceil(horizon / block_len))
    # Random start day for every block of every path
    starts = rng.integers(0, len(returns) - block_len + 1, size=(n_sims, n_blocks))
    # Turn each start into block_len consecutive day indices
    idx = starts[:, :, None] + np.arange(block_len)
    # Look up the returns, flatten blocks into one path, trim to the horizon
    return returns[idx].reshape(n_sims, -1)[:, :horizon]


def simulate_paths(returns, spot_today, rng):
    """Simulated USD/INR rate for each path and day. Column 0 is today."""
    sim_returns = block_bootstrap(returns, N_SIMULATIONS, HORIZON_DAYS, BLOCK_LEN, rng)
    cumulative = np.cumsum(sim_returns, axis=1)
    paths = spot_today * np.exp(cumulative)
    return np.column_stack([np.full(N_SIMULATIONS, spot_today), paths])


def var_es(cost_increase, confidence):
    """VaR = the cost increase exceeded only (1 - confidence) of the time.
    ES = the average cost increase in those worst cases."""
    var = np.quantile(cost_increase, confidence)
    es = cost_increase[cost_increase >= var].mean()
    return var, es


def main():
    rng = np.random.default_rng(RANDOM_SEED)
    returns, spot_today, as_of = load_history()
    paths = simulate_paths(returns, spot_today, rng)

    # The importer's risk: INR weakens, so buying the USD costs more rupees.
    # Cost increase (INR) = USD amount x (rate at payment - rate today). Positive = loss.
    spot_end = paths[:, -1]
    cost_today = EXPOSURE_USD * spot_today
    cost_increase = EXPOSURE_USD * (spot_end - spot_today)
    var, es = var_es(cost_increase, CONFIDENCE)

    results = {
        "as_of": str(as_of),
        "spot_today": round(float(spot_today), 4),
        "exposure_usd": EXPOSURE_USD,
        "cost_today_inr": round(float(cost_today), 2),
        "horizon_trading_days": HORIZON_DAYS,
        "n_simulations": N_SIMULATIONS,
        "block_len": BLOCK_LEN,
        "history_start": HISTORY_START,
        "history_days_used": int(len(returns)),
        "confidence": CONFIDENCE,
        "random_seed": RANDOM_SEED,
        "spot_end_median": round(float(np.median(spot_end)), 4),
        "spot_end_p05": round(float(np.quantile(spot_end, 0.05)), 4),
        "spot_end_p95": round(float(np.quantile(spot_end, 0.95)), 4),
        "expected_cost_increase_inr": round(float(cost_increase.mean()), 2),
        "var_inr": round(float(var), 2),
        "es_inr": round(float(es), 2),
        "var_pct_of_cost": round(float(var / cost_today * 100), 3),
        "es_pct_of_cost": round(float(es / cost_today * 100), 3),
    }

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    np.save(MC_PATHS_FILE, paths.astype(np.float32))
    VAR_ES_FILE.write_text(json.dumps(results, indent=2))

    print(f"Spot on {as_of}: {spot_today:.2f} INR per USD")
    print(f"Paying USD {EXPOSURE_USD:,} today would cost INR {cost_today:,.0f}\n")
    print(f"Simulated {N_SIMULATIONS:,} paths x {HORIZON_DAYS} trading days "
          f"(blocks of {BLOCK_LEN} days, history from {HISTORY_START}, {len(returns):,} days)")
    print(f"Rate in 6 months: median {results['spot_end_median']:.2f}, "
          f"5th-95th percentile {results['spot_end_p05']:.2f} - {results['spot_end_p95']:.2f}\n")
    print(f"Expected cost increase:  INR {results['expected_cost_increase_inr']:>14,.0f}")
    print(f"VaR {CONFIDENCE:.0%}:                 INR {var:>14,.0f}  ({results['var_pct_of_cost']:.2f}% of today's cost)")
    print(f"ES  {CONFIDENCE:.0%}:                 INR {es:>14,.0f}  ({results['es_pct_of_cost']:.2f}% of today's cost)")
    print(f"\nSaved {VAR_ES_FILE.name} and {MC_PATHS_FILE.name} ({paths.shape[0]:,} x {paths.shape[1]}) to outputs/")


if __name__ == "__main__":
    main()