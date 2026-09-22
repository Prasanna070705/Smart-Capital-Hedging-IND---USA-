# src/ingestion.py
import os
from dotenv import load_dotenv
from fredapi import Fred
from config import RAW_DIR, FRED_SERIES

load_dotenv()
fred = Fred(api_key=os.getenv("FRED_API_KEY"))

RAW_DIR.mkdir(parents=True, exist_ok=True)

for name, series_id in FRED_SERIES.items():
    data = fred.get_series(series_id)
    df = data.reset_index()
    df.columns = ["date", name]
    out_path = RAW_DIR / f"{name}.csv"
    df.to_csv(out_path, index=False)
    print(f"{name:22s} ({series_id:16s}): {len(df):5d} rows, {df['date'].min().date()} → {df['date'].max().date()}")