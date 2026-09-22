# app.py
# Objective 4b: the hedging advisor. Run from the fx-hedging root:  streamlit run app.py
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from config import RISK_LEVELS
from advisor import (REGIME_TEXT, load_market, score_for_tenor, budget_pct_from_inr, advise,
                     candidates_table)

st.set_page_config(page_title="FX Hedging Advisor", layout="wide")


# ---------- Cached loaders: the heavy work runs once, not on every click ----------
@st.cache_resource
def market():
    return load_market()


@st.cache_data
def tenor_scores(months):
    return score_for_tenor(market(), months)


def lakh(inr):
    return f"₹{inr / 1e5:,.1f} lakh"


# ---------- Inputs ----------
m = market()
st.title("USD payment hedging advisor")
st.caption(f"For Indian importers paying in US dollars. Market data as of {m['as_of']}.")

with st.sidebar:
    st.header("Your payment")
    unit = st.radio("Enter the amount in", ["INR crore (at today's rate)", "USD"], horizontal=False)
    if unit == "USD":
        invoice_usd = st.number_input("Invoice amount (USD)", min_value=1_000.0, value=1_000_000.0,
                                      step=10_000.0, format="%.0f")
    else:
        crore = st.number_input("Amount (₹ crore)", min_value=0.01, value=10.0, step=0.5)
        invoice_usd = crore * 1e7 / m["spot"]
    months = st.slider("Months until payment", min_value=1, max_value=12, value=6)

    st.header("Your risk tolerance")
    level = st.select_slider("How much risk can you take?", options=list(RISK_LEVELS), value="Balanced")
    budget_pct = RISK_LEVELS[level]
    with st.expander("Or set your own limit in rupees"):
        own = st.number_input("Largest extra cost you could absorb in a bad case (₹ lakh)",
                              min_value=0.0, value=0.0, step=1.0)
        if own > 0:
            budget_pct = budget_pct_from_inr(own * 1e5, invoice_usd, m["spot"])

# ---------- Calculation (from src/, cached) ----------
forward, grid = tenor_scores(months)
a = advise(m, forward, grid, invoice_usd, budget_pct)

# ---------- Market today ----------
c1, c2, c3 = st.columns(3)
c1.metric("Spot rate today", f"₹{m['spot']:.2f} per USD")
c2.metric(f"{months}-month forward rate", f"₹{forward:.2f} per USD",
          f"{(forward / m['spot'] - 1) * 100:+.2f}% vs spot", delta_color="off")
c3.metric("Market regime", m["regime"])
st.info(REGIME_TEXT[m["regime"]])

# ---------- Recommendation ----------
st.header(f"Recommendation: hedge {a['ratio']:.0%}")
st.write(
    f"Book a forward contract for **USD {a['hedge_usd']:,.0f}** at ₹{forward:.2f}, and buy the remaining "
    f"**USD {a['open_usd']:,.0f}** at the market rate when the payment is due."
)
r1, r2, r3 = st.columns(3)
r1.metric("Your bad-case limit", lakh(a["budget_inr"]))
r2.metric("Worst 1-in-20 extra cost with this hedge", lakh(a["var_inr"]),
          f"{lakh(a['unhedged_var_inr'])} if unhedged", delta_color="off")
r3.metric("Locked-in cost of the hedge", lakh(a["premium_inr"]))
if not a["fits_budget"]:
    st.warning("Even a full hedge costs more than your limit, because the forward rate is above today's rate. "
               "A 100% hedge is the lowest-risk option available.")

# ---------- Every option side by side ----------
st.subheader("All options compared")
st.caption("Extra rupees compared with paying at today's rate. Negative = you pay less.")
st.dataframe(candidates_table(grid, a["cost_today_inr"], a["ratio"]), hide_index=True)

chart = pd.DataFrame({
    "Hedge ratio (%)": (grid["hedge_ratio"] * 100).round(),
    "Worst 1-in-20 extra cost (lakh)": grid["var_pct"] / 100 * a["cost_today_inr"] / 1e5,
    "Your limit (lakh)": a["budget_inr"] / 1e5,
}).set_index("Hedge ratio (%)")
st.line_chart(chart)
st.caption("The recommendation is the smallest hedge where the worst-case line drops below your limit line: "
           "you get the protection you need and keep the rest of the upside if the rupee strengthens.")

with st.expander("How this works and its limits"):
    st.markdown(f"""
- **Risk** comes from 10,000 simulated rupee paths built from real 2000-{m['as_of'].year} history, starting from today's
  regime (**{m['regime']}**) and allowing it to change along the way.
- **The forward rate** uses covered interest parity with India's 3-month interbank rate ({m['r_inr']:.2f}%) and the
  US 3-month T-bill rate ({m['r_usd']:.2f}%). A bank's quote will include a spread on top.
- **On average every option costs about the same** (the forward premium): the simulation is centred on the forward,
  the market's own expectation. Hedging changes how bad it can get, not the average.
- Data is a fixed snapshot from {m['as_of']}; interest rates carry a 2-month publication lag.
- This is a model built on past data, not financial advice. Confirm with your bank before booking a forward.
""")