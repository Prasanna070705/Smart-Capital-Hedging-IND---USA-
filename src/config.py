# src/config.py
from pathlib import Path

# Paths are anchored to the project root, so scripts work from any folder
ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT_DIR / "data" / "raw"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"

FRED_SERIES = {
    "usd_inr_spot": "DEXINUS",             # daily INR per USD spot rate
    "us_cpi": "CPIAUCSL",                   # US CPI, all urban consumers, monthly
    "india_cpi": "INDCPIALLMINMEI",         # India CPI, monthly (OECD) - ENDS 2025-03, training only; no live FRED replacement
    "us_interest_rate": "FEDFUNDS",         # US effective Fed Funds rate, monthly (was INTDSRUSM193N, ended 2021-08)
    "india_interest_rate": "IRSTCI01INM156N", # India call money rate, monthly (was INTDSRINM193N, ended 2022-07)
    "india_reer": "CCRETT01INM661N",        # India real effective exchange rate, CPI-based, monthly (live substitute for India CPI)
}


# ---- Feature engineering settings (Day 2) ----
MASTER_FILE = PROCESSED_DIR / "processed_fx_master.csv"

TRADING_DAYS_PER_YEAR = 252      # used to annualise daily volatility
VOL_WINDOWS = [20, 60]           # trailing windows (in trading days) for vol_20d, vol_60d

# Monthly macro data is published weeks after the month ends.
# Shifting it by 2 months means we never use a number before it was public.
MACRO_LAG_MONTHS = 2

# If a monthly series stops updating, stop carrying its last value forward after this many days
MACRO_MAX_STALE_DAYS = 45