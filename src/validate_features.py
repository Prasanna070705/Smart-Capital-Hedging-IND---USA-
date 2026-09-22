# src/validate_features.py
# Checks that processed_fx_master.csv is correct. Run from the fx-hedging root:
#   python src/validate_features.py
import numpy as np
import pandas as pd

from config import MASTER_FILE
import features

master = pd.read_csv(MASTER_FILE, parse_dates=["date"], index_col="date")
raw_spot = features.load_raw("usd_inr_spot").dropna()
passed = 0


def check(ok, msg):
    global passed
    if not ok:
        raise AssertionError("FAILED: " + msg)
    passed += 1
    print("  PASS ", msg)


print("1. Table structure")
check(master.index.is_monotonic_increasing, "dates are in order")
check(not master.index.duplicated().any(), "no duplicate dates")
check(master.index.dayofweek.max() <= 4, "only weekdays (Mon-Fri)")

print("2. Spot rates match the raw FRED file")
sample = master.sample(20, random_state=0).index
check(np.allclose(master.loc[sample, "usd_inr_spot"], raw_spot.loc[sample]),
      "20 random dates match data/raw/usd_inr_spot.csv exactly")

print("3. Returns and volatility are calculated correctly")
d = master.index[1000]
prev = raw_spot.index[raw_spot.index.get_loc(d) - 1]
check(np.isclose(master.loc[d, "daily_return"], np.log(raw_spot[d] / raw_spot[prev])),
      f"daily_return on {d.date()} = ln(today/yesterday), recomputed by hand")
check((master["vol_20d"] >= 0).all() and (master["vol_20d"] < 1).all(),
      "vol_20d always between 0% and 100% a year (0% = rate was fixed that month)")

print("4. No lookahead (features only use past data)")
cut = pd.Timestamp("2015-06-30")
spot_cut = raw_spot.loc[:cut]                            # pretend today is 2015-06-30
vol_cut = np.log(spot_cut).diff().rolling(60).std() * np.sqrt(252)
last = vol_cut.index[-1]
check(np.isclose(vol_cut.iloc[-1], master.loc[last, "vol_60d"]),
      f"vol_60d on {last.date()} is identical whether or not later data exists")
check(master.loc["2025-01-15", "us_cpi"] == features.load_raw("us_cpi").loc["2024-11-01"],
      "US CPI used on 2025-01-15 is the Nov 2024 value (2-month publication lag)")

print("5. Crisis periods show higher volatility than normal")
median_vol = master["vol_20d"].median()
for label, date in [("GFC", "2008-10-31"), ("Taper tantrum", "2013-08-30"), ("COVID", "2020-03-31")]:
    v = master.loc[:date, "vol_20d"].iloc[-1]
    check(v > median_vol, f"{label} ({date}): vol_20d {v:.1%} > median {median_vol:.1%}")

print(f"\nAll {passed} checks passed.")
print("\nSpot rates to compare by eye with FRED (fred.stlouisfed.org/series/DEXINUS):")
for date in ["1991-07-01", "2008-10-31", "2013-08-28", "2020-03-31", str(master.index[-1].date())]:
    row = master.loc[:date].iloc[-1]
    print(f"  {row.name.date()}  {row['usd_inr_spot']:.2f} INR per USD")