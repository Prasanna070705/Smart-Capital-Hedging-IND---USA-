# src/forward_pricing.py
# Objective 2 (part 1): the fair 6-month USD/INR forward rate from covered interest parity (CIP).
# Run from the fx-hedging root:  python src/forward_pricing.py
import pandas as pd

from config import (MASTER_FILE, OUTPUTS_DIR, FORWARD_QUOTES_FILE, FORWARD_TENOR_YEARS,
                    FORWARD_RATE_COLUMNS, OVERNIGHT_RATE_COLUMNS)


def cip_forward(spot, r_inr_pct, r_usd_pct, t_years):
    """Covered interest parity with simple interest:
        F = S x (1 + r_INR x t) / (1 + r_USD x t)
    Rates are annual percentages (6.5 means 6.5%). If rupee rates are higher than dollar rates,
    the forward is above spot: that gap is what a bank charges to lock in the rate today."""
    return spot * (1 + r_inr_pct / 100 * t_years) / (1 + r_usd_pct / 100 * t_years)


def forward_premium_pct(forward, spot, t_years):
    """Forward premium over spot: (F / S - 1), as a % for the period and annualised."""
    period = (forward / spot - 1) * 100
    return period, period / t_years


def build_quotes(master, rate_cols, t_years):
    """Forward rate and premium for every trading day that has both interest rates."""
    df = master[["usd_inr_spot", rate_cols["inr"], rate_cols["usd"]]].dropna().copy()
    df.columns = ["spot", "r_inr_pct", "r_usd_pct"]
    df["forward"] = cip_forward(df["spot"], df["r_inr_pct"], df["r_usd_pct"], t_years)
    df["premium_pct"], df["premium_annual_pct"] = forward_premium_pct(df["forward"], df["spot"], t_years)
    return df


def main():
    master = pd.read_csv(MASTER_FILE, parse_dates=["date"], index_col="date")
    quotes = build_quotes(master, FORWARD_RATE_COLUMNS, FORWARD_TENOR_YEARS)

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    quotes.round(6).to_csv(FORWARD_QUOTES_FILE, index_label="date")

    today = quotes.iloc[-1]
    print(f"Saved {FORWARD_QUOTES_FILE.name}: {len(quotes):,} days, "
          f"{quotes.index.min().date()} -> {quotes.index.max().date()}\n")
    print(f"6-month forward on {quotes.index[-1].date()} (matching-tenor rates: "
          f"{FORWARD_RATE_COLUMNS['inr']}, {FORWARD_RATE_COLUMNS['usd']})")
    print(f"  Spot                 {today['spot']:8.4f} INR per USD")
    print(f"  India rate           {today['r_inr_pct']:8.4f} % per year")
    print(f"  US rate              {today['r_usd_pct']:8.4f} % per year")
    print(f"  Forward (CIP)        {today['forward']:8.4f} INR per USD")
    print(f"  Premium              {today['premium_pct']:8.4f} % for 6 months "
          f"({today['premium_annual_pct']:.4f} % annualised)")

    # Hand check, spelled out so you can redo it on a calculator
    t = FORWARD_TENOR_YEARS
    print(f"\n  By hand: {today['spot']:.4f} x (1 + {today['r_inr_pct']:.4f}/100 x {t}) "
          f"/ (1 + {today['r_usd_pct']:.4f}/100 x {t}) = {today['forward']:.4f}")

    # Tenor mismatch: what if we had used the overnight rates instead?
    overnight = build_quotes(master, OVERNIGHT_RATE_COLUMNS, t).iloc[-1]
    print(f"\n  Same calculation with overnight rates ({OVERNIGHT_RATE_COLUMNS['inr']}, "
          f"{OVERNIGHT_RATE_COLUMNS['usd']}): forward {overnight['forward']:.4f}, "
          f"premium {overnight['premium_annual_pct']:.4f} % annualised")
    print(f"  Tenor mismatch changes the annual premium by "
          f"{overnight['premium_annual_pct'] - today['premium_annual_pct']:+.4f} percentage points")


if __name__ == "__main__":
    main()