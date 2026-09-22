# src/features.py
# Stage 2: turns the raw FRED CSVs into one daily table: data/processed/processed_fx_master.csv
# Run from the fx-hedging root:  python src/features.py
import numpy as np
import pandas as pd

from config import (RAW_DIR, PROCESSED_DIR, MASTER_FILE, TRADING_DAYS_PER_YEAR,
                    VOL_WINDOWS, MACRO_LAG_MONTHS, MACRO_MAX_STALE_DAYS, FRED_SERIES)

# Every series in config.py except the daily spot rate is monthly (added Day 5: picks up new series automatically)
MONTHLY_SERIES = [name for name in FRED_SERIES if name != "usd_inr_spot"]

def load_raw(name):
    """Read one raw CSV into a Series indexed by date."""
    df = pd.read_csv(RAW_DIR / f"{name}.csv", parse_dates=["date"])
    return df.set_index("date")[name].sort_index()


def build_daily_fx():
    """Daily spot rate, log return and trailing volatility."""
    spot = load_raw("usd_inr_spot").dropna()   # drop blank rows (market holidays)
    fx = spot.to_frame()

    # Log return: ln(today / yesterday). Positive = INR weakened (costlier to buy USD).
    fx["daily_return"] = np.log(fx["usd_inr_spot"]).diff()

    # Trailing (backward-looking) rolling volatility, annualised
    for w in VOL_WINDOWS:
        fx[f"vol_{w}d"] = fx["daily_return"].rolling(w).std() * np.sqrt(TRADING_DAYS_PER_YEAR)
    return fx


def build_monthly_macro():
    """Monthly macro table, with derived features and a publication lag applied."""
    macro = pd.concat([load_raw(n) for n in MONTHLY_SERIES], axis=1)

    # Fill single isolated gaps (e.g. US CPI 2025-10) by interpolation; never extend past the end
    macro = macro.interpolate(limit=1, limit_area="inside")

    # Year-on-year inflation (%) and the India-minus-US gaps
    macro["us_inflation_yoy"] = macro["us_cpi"].pct_change(12, fill_method=None) * 100
    macro["india_inflation_yoy"] = macro["india_cpi"].pct_change(12, fill_method=None) * 100
    macro["inflation_diff"] = macro["india_inflation_yoy"] - macro["us_inflation_yoy"]
    macro["rate_diff"] = macro["india_interest_rate"] - macro["us_interest_rate"]

    macro["rate_diff"] = macro["india_interest_rate"] - macro["us_interest_rate"]
    if "india_tbill_rate" in macro and "us_tbill_rate" in macro:   
        # Day 5: matching-tenor gap for CIP
        macro["tbill_diff"] = macro["india_tbill_rate"] - macro["us_tbill_rate"]

    # Publication lag: January's value only becomes usable from March 1 (with a 2-month lag)
    macro.index = macro.index + pd.DateOffset(months=MACRO_LAG_MONTHS)
    macro.index.name = "available_from"
    return macro


def merge_macro_onto_daily(fx, macro):
    """Attach, to each trading day, the latest macro value that was already public on that day."""
    daily = fx.reset_index().rename(columns={"index": "date"})
    monthly = macro.reset_index()
    out = pd.DataFrame({"date": daily["date"]})
    for col in macro.columns:
        # Each column separately, so one series ending early doesn't blank the others
        one = monthly[["available_from", col]].dropna()
        merged = pd.merge_asof(daily[["date"]], one, left_on="date", right_on="available_from",
                               direction="backward",
                               tolerance=pd.Timedelta(days=MACRO_MAX_STALE_DAYS))
        out[col] = merged[col].values
    return daily.merge(out, on="date").set_index("date")


def main():
    fx = build_daily_fx()
    macro = build_monthly_macro()
    master = merge_macro_onto_daily(fx, macro)

    # Start where the longest volatility window is fully available
    master = master.loc[master[f"vol_{max(VOL_WINDOWS)}d"].first_valid_index():]

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    master.to_csv(MASTER_FILE, index_label="date")

    print(f"Saved {MASTER_FILE}")
    print(f"{len(master):,} rows, {master.index.min().date()} -> {master.index.max().date()}\n")
    print("Last date with a value, per column:")
    for col in master.columns:
        print(f"  {col:22s} {master[col].last_valid_index().date()}   missing: {master[col].isna().sum():,}")


if __name__ == "__main__":
    main()