# src/static_hedge.py
# Objective 2 (part 2): cost and risk of hedging 0%, 25%, 50%, 75% and 100% of the payment with the forward.
# Run from the fx-hedging root (after forward_pricing.py):  python src/static_hedge.py
import numpy as np
import pandas as pd

from config import (MASTER_FILE, FORWARD_QUOTES_FILE, STATIC_HEDGE_FILE, EXPOSURE_USD, HORIZON_DAYS,
                    CONFIDENCE, RANDOM_SEED, HEDGE_RATIOS, REAL_FORWARD_PREMIUM_ANNUAL_PCT)
from risk_baseline import load_history, simulate_paths, var_es


def hedged_cost(ratio, forward, spot_end, exposure_usd):
    """Rupees paid on the payment date when `ratio` of the USD is bought at the forward rate
    and the rest at whatever the spot rate turns out to be."""
    return exposure_usd * (ratio * forward + (1 - ratio) * spot_end)


def compare_ratios(ratios, forward, spot_today, spot_end, exposure_usd, confidence):
    """One row per hedge ratio: locked-in hedging cost, expected cost increase, VaR and ES,
    all in INR relative to paying at today's spot rate."""
    cost_today = exposure_usd * spot_today
    rows = []
    for h in ratios:
        increase = hedged_cost(h, forward, spot_end, exposure_usd) - cost_today
        var, es = var_es(increase, confidence)
        rows.append({
            "hedge_ratio": h,
            "locked_premium_inr": h * exposure_usd * (forward - spot_today),
            "expected_increase_inr": increase.mean(),
            "std_inr": increase.std(),
            "best_5pct_inr": np.quantile(increase, 1 - confidence),
            "var_inr": var,
            "es_inr": es,
            "var_pct_of_cost": var / cost_today * 100,
        })
    return pd.DataFrame(rows)


def history_check(master, quotes, horizon):
    """Since the forward series starts: how often would a full forward hedge have beaten waiting?
    Compares each day's forward with the actual spot rate `horizon` trading days later."""
    spot = master["usd_inr_spot"]
    realised = spot.shift(-horizon).reindex(quotes.index)
    df = pd.DataFrame({"forward": quotes["forward"], "spot": quotes["spot"], "realised": realised}).dropna()
    saving_pct = (df["realised"] / df["forward"] - 1) * 100   # > 0: the forward was cheaper
    return {
        "windows": len(df),
        "first": df.index.min().date(),
        "last": df.index.max().date(),
        "forward_cheaper_share": (saving_pct > 0).mean(),
        "avg_premium_pct": ((df["forward"] / df["spot"] - 1) * 100).mean(),
        "avg_depreciation_pct": ((df["realised"] / df["spot"] - 1) * 100).mean(),
        "worst_saving_pct": saving_pct.min(),
        "best_saving_pct": saving_pct.max(),
    }


def main():
    # Same simulated paths as risk_baseline.py (same seed), recomputed exactly rather than loaded
    returns, spot_today, as_of = load_history()
    paths = simulate_paths(returns, spot_today, np.random.default_rng(RANDOM_SEED))
    spot_end = paths[:, -1]

    quotes = pd.read_csv(FORWARD_QUOTES_FILE, parse_dates=["date"], index_col="date")
    forward = quotes["forward"].iloc[-1]
    premium_annual = quotes["premium_annual_pct"].iloc[-1]

    table = compare_ratios(HEDGE_RATIOS, forward, spot_today, spot_end, EXPOSURE_USD, CONFIDENCE)
    table.round(2).to_csv(STATIC_HEDGE_FILE, index=False)

    print(f"USD {EXPOSURE_USD:,} due in 6 months. Spot {spot_today:.4f}, 6-month forward {forward:.4f} "
          f"(as of {as_of})")
    print("All figures: extra rupees vs paying at today's spot, in INR millions\n")
    print(f"  {'Hedged':>7s} {'Locked cost':>12s} {'Expected':>9s} {'Best 5%':>8s} "
          f"{'VaR 95%':>8s} {'ES 95%':>8s} {'VaR %':>6s}")
    for _, r in table.iterrows():
        print(f"  {r['hedge_ratio']:>7.0%} {r['locked_premium_inr'] / 1e6:>12.2f} "
              f"{r['expected_increase_inr'] / 1e6:>9.2f} {r['best_5pct_inr'] / 1e6:>8.2f} "
              f"{r['var_inr'] / 1e6:>8.2f} {r['es_inr'] / 1e6:>8.2f} {r['var_pct_of_cost']:>5.2f}%")
    print(f"\nSaved {STATIC_HEDGE_FILE.name} to outputs/")

    # How has the forward done historically?
    master = pd.read_csv(MASTER_FILE, parse_dates=["date"], index_col="date")
    h = history_check(master, quotes, HORIZON_DAYS)
    print(f"\nHistory check, {h['windows']:,} six-month windows ({h['first']} -> {h['last']} start dates):")
    print(f"  Average forward premium        {h['avg_premium_pct']:5.2f} % per 6 months")
    print(f"  Average actual depreciation    {h['avg_depreciation_pct']:5.2f} % per 6 months")
    print(f"  Forward was cheaper than waiting in {h['forward_cheaper_share']:.0%} of windows "
          f"(range {h['worst_saving_pct']:+.1f}% to {h['best_saving_pct']:+.1f}%)")

    # CIP vs a real market quote
    print("\nCIP vs a real forward quote:")
    if REAL_FORWARD_PREMIUM_ANNUAL_PCT is None:
        print("  Not checked yet - set REAL_FORWARD_PREMIUM_ANNUAL_PCT in config.py (see walkthrough step 5)")
    else:
        gap = premium_annual - REAL_FORWARD_PREMIUM_ANNUAL_PCT
        print(f"  CIP premium {premium_annual:.2f}% vs market {REAL_FORWARD_PREMIUM_ANNUAL_PCT:.2f}% "
              f"(annualised): gap {gap:+.2f} percentage points")


if __name__ == "__main__":
    main()