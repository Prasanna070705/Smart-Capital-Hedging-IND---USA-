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
    "us_tbill_rate": "TB3MS",              # Day 5: US 3-month T-bill rate, monthly (matches India's 3-month tenor)
    "india_tbill_rate": "INDIR3TIB01STM",   # Day 5: India 3-month interbank rate, monthly (OECD); no India T-bill series on FRED
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


# ---- Objective 1: baseline risk / Monte Carlo (Day 3) ----
OUTPUTS_DIR = ROOT_DIR / "outputs"
VAR_ES_FILE = OUTPUTS_DIR / "var_es.json"
MC_PATHS_FILE = OUTPUTS_DIR / "mc_paths.npy"

EXPOSURE_USD = 1_000_000         # the importer must pay this many USD at the end of the horizon
HORIZON_DAYS = 126               # 6 months in TRADING days (~21 per month); the plan's "180 days" is calendar days
N_SIMULATIONS = 10_000           # number of simulated future paths
BLOCK_LEN = 10                   # days per bootstrap block (2 trading weeks), keeps volatility clustering
HISTORY_START = "2000-01-01"     # sample only from the market-determined era (see walkthrough)
CONFIDENCE = 0.95                # VaR / ES confidence level
RANDOM_SEED = 42                 # fixed seed = same results every run


# ---- Objective 2: static hedge / forward pricing (Day 5) ----
FORWARD_QUOTES_FILE = OUTPUTS_DIR / "forward_quotes.csv"
FORWARD_TENOR_YEARS = 0.5        # 6-month forward; CIP uses simple interest: (1 + r x t)
FORWARD_RATE_COLUMNS = {"inr": "india_tbill_rate", "usd": "us_tbill_rate"}   # matching-tenor rates
OVERNIGHT_RATE_COLUMNS = {"inr": "india_interest_rate", "usd": "us_interest_rate"}  # for the tenor-mismatch comparison