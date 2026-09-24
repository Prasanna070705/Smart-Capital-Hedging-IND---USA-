# app.py
# The hedging advisor. Run from the fx-hedging root:  streamlit run app.py
# This file only collects inputs and runs the calculation; each tab lives in views/.
import sys
from datetime import date
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from config import RISK_LEVELS
from advisor import load_market, simulate_payment, scores_from_paths, budget_pct_from_inr, advise
from formatting import rate
from views import recommendation, insights, track_record, about
from views import recommendation, insights, track_record, about, ask

STALE_AFTER_DAYS = 30   # warn when the market snapshot is older than this

# Tabs in display order: (label, module with a render(ctx) function). Later days add entries here.
TABS = [
    ("Recommendation", recommendation),
    ("Insights", insights),
    ("Track record", track_record),
    ("Ask", ask),
    ("How it works", about),
]

st.set_page_config(page_title="FX Hedging Advisor", page_icon="💱", layout="wide")


# ---------- Cached loaders: the heavy work runs once, not on every click ----------
@st.cache_resource
def market():
    return load_market()


@st.cache_data
def payment_paths(months):
    return simulate_payment(market(), months)


# ---------- Inputs ----------
m = market()
st.title("USD payment hedging advisor")
st.caption(f"For Indian importers paying in US dollars · market data as of {m['as_of']} · "
           f"spot {rate(m['spot'])} per USD")
age = (date.today() - m["as_of"]).days
if age > STALE_AFTER_DAYS:
    st.warning(f"The market data is {age} days old. Rates and the regime may have changed; "
               "refresh it with `python src/run_all.py --fetch` before relying on the numbers.")

with st.sidebar:
    st.header("Your payment")
    unit = st.radio("Enter the amount in", ["INR crore (at today's rate)", "USD"], key="unit")
    if unit == "USD":
        invoice_usd = st.number_input("Invoice amount (USD)", min_value=1_000.0, max_value=1e10,
                                      value=1_000_000.0, step=10_000.0, format="%.0f", key="amount_usd")
    else:
        crore = st.number_input("Amount (₹ crore)", min_value=0.01, max_value=100_000.0, value=10.0,
                                step=0.5, key="amount_crore")
        invoice_usd = crore * 1e7 / m["spot"]
    months = st.slider("Months until payment", min_value=1, max_value=12, value=6, key="months",
                       help="For payments due in less than a month, use 1: the tool's shortest horizon.")

    st.header("Your risk tolerance")
    level = st.select_slider("How much risk can you take?", options=list(RISK_LEVELS), value="Balanced",
                             key="risk_level",
                             help="Sets the largest extra cost you could absorb in a 1-in-20 bad case, "
                                  "from 1% of the payment (Very cautious) to 9% (Very relaxed).")
    budget_pct = RISK_LEVELS[level]
    with st.expander("Or set your own limit in rupees"):
        own = st.number_input("Largest extra cost you could absorb in a bad case (₹ lakh)",
                              min_value=0.0, value=0.0, step=1.0, key="own_limit",
                              help="Leave at 0 to use the risk tolerance above.")
        if own > 0:
            budget_pct = budget_pct_from_inr(own * 1e5, invoice_usd, m["spot"])
    st.divider()
    ask.sidebar_status()

# ---------- Calculation (all finance comes from src/, cached) ----------
forward, spot_end = payment_paths(months)
grid = scores_from_paths(forward, m["spot"], spot_end)
ctx = {
    "market": m, "invoice_usd": invoice_usd, "months": months, "level": level, "budget_pct": budget_pct,
    "forward": forward, "spot_end": spot_end, "grid": grid,
    "advice": advise(m, forward, grid, invoice_usd, budget_pct),
}

for tab, (_, view) in zip(st.tabs([label for label, _ in TABS]), TABS):
    with tab:
        view.render(ctx)
