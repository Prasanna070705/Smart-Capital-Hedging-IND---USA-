# src/check_series.py
# Checks candidate FRED series and shows how up to date each one is.
# Run from the fx-hedging root:  python src/check_series.py
import os
from datetime import date
from dotenv import load_dotenv
from fredapi import Fred

load_dotenv()
fred = Fred(api_key=os.getenv("FRED_API_KEY"))

CANDIDATES = {
    "us_interest_rate": [
        "INTDSRUSM193N",    # current (stale) - US discount rate
        "FEDFUNDS",         # Effective Fed Funds rate, monthly
        "DFF",              # Effective Fed Funds rate, daily
        "TB3MS",            # 3-month T-bill, monthly
    ],
    "india_interest_rate": [
        "INTDSRINM193N",    # current (stale) - India discount rate
        "IR3TIB01INM156N",  # India 3-month interbank rate (OECD)
        "IRSTCI01INM156N",  # India call money / overnight rate (OECD)
        "IRLTLT01INM156N",  # India 10-year govt bond yield (OECD)
    ],
    "india_cpi": [
        "INDCPIALLMINMEI",  # current (stale) - India CPI (OECD)
        "INDCPALTT01IXNBM", # India CPI all items, index (OECD)
        "CPALTT01INM659N",  # India CPI, % change year-on-year (OECD)
        "INDCPIALLAINMEI",  # India CPI, annual
    ],
}

today = date.today()
for var, ids in CANDIDATES.items():
    print(f"\n=== {var} ===")
    for sid in ids:
        try:
            info = fred.get_series_info(sid)
            end = info["observation_end"]
            lag = (today - date.fromisoformat(end)).days
            flag = "OK " if lag < 120 else "OLD"
            print(f"  [{flag}] {sid:18s} {info['frequency_short']:2s} "
                  f"{info['observation_start']} -> {end}  ({lag} days old)  {info['title'][:60]}")
        except Exception as e:
            print(f"  [ERR] {sid:18s} {e}")

# Search FRED for any other India CPI / inflation series and list the freshest ones
print("\n=== FRED search: India CPI / inflation (freshest first) ===")
for q in ["India consumer price index", "India inflation"]:
    try:
        res = fred.search(q, order_by="last_updated", sort_order="desc", limit=15)
        for sid, row in res.iterrows():
            print(f"  {sid:20s} {row['frequency_short']:2s} ends {str(row['observation_end'])[:10]}  {row['title'][:70]}")
    except Exception as e:
        print("  search failed:", e)
