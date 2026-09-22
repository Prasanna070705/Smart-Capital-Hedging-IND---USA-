# src/find_tenor_rates.py
# Objective 2 needs US and India interest rates with the SAME maturity as the forward (ideally 6 months).
# This checks likely FRED series, searches for others, and recommends a matching pair.
# Run from the fx-hedging root:  python src/find_tenor_rates.py
import os
from datetime import date

from dotenv import load_dotenv
from fredapi import Fred

load_dotenv()
fred = Fred(api_key=os.getenv("FRED_API_KEY"))
FRESH_DAYS = 120   # a series counts as current if its last value is at most ~4 months old

CANDIDATES = {
    "6m": {"us": ["TB6MS"],
           "india": ["IR6TTS01INM156N"]},
    "3m": {"us": ["TB3MS"],
           "india": ["INDIR3TIB01STM", "IR3TTS01INM156N", "IR3TIB01INM156N"]},
}


def describe(series_id):
    """Return (is_fresh, text) for one series, or (False, error) if it does not exist."""
    try:
        info = fred.get_series_info(series_id)
    except Exception as e:
        return False, f"  [ERR] {series_id:18s} {e}"
    end = info["observation_end"]
    lag = (date.today() - date.fromisoformat(end)).days
    fresh = lag <= FRESH_DAYS
    return fresh, (f"  [{'OK ' if fresh else 'OLD'}] {series_id:18s} {info['frequency_short']:2s} "
                   f"{info['observation_start']} -> {end}  ({lag} days old)  {info['title'][:60]}")


fresh_ids = {}
for tenor, countries in CANDIDATES.items():
    for country, ids in countries.items():
        print(f"\n=== {tenor} {country} ===")
        for sid in ids:
            fresh, text = describe(sid)
            print(text)
            if fresh:
                fresh_ids.setdefault((tenor, country), sid)

print("\n=== FRED search: India short-term rates (freshest first) ===")
for q in ["India treasury bill", "India 3-month interest rate", "India interbank rate"]:
    try:
        res = fred.search(q, order_by="last_updated", sort_order="desc", limit=8)
        for sid, row in res.iterrows():
            print(f"  {sid:20s} {row['frequency_short']:2s} ends {str(row['observation_end'])[:10]}  {row['title'][:70]}")
    except Exception as e:
        print(f"  search '{q}' found nothing ({e})")

print("\n=== RECOMMENDATION ===")
for tenor in ["6m", "3m"]:
    us, india = fresh_ids.get((tenor, "us")), fresh_ids.get((tenor, "india"))
    if us and india:
        print(f"  Use the {tenor} pair:  us_tbill_rate = {us}   india_tbill_rate = {india}")
        break
else:
    print("  No current matching-tenor pair found. Paste this whole output to Claude.")