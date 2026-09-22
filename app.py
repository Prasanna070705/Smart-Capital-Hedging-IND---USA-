# app.py
# Objective 4b: the hedging advisor. Run from the fx-hedging root:  streamlit run app.py
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from config import RISK_LEVELS
from advisor import (REGIME_TEXT, load_market, simulate_payment, scores_from_paths, budget_pct_from_inr,
                     advise, candidates_table, outcome_histogram, load_track_record)

STALE_AFTER_DAYS = 30   # warn when the market snapshot is older than this

st.set_page_config(page_title="FX Hedging Advisor", layout="wide")


# ---------- Cached loaders: the heavy work runs once, not on every click ----------
@st.cache_resource
def market():
    return load_market()


@st.cache_data
def payment_paths(months):
    return simulate_payment(market(), months)


@st.cache_data
def track_record():
    return load_track_record()


def lakh(inr):
    return f"₹{inr / 1e5:,.1f} lakh"


# ---------- Inputs ----------
m = market()
st.title("USD payment hedging advisor")
st.caption(f"For Indian importers paying in US dollars. Market data as of {m['as_of']}.")
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
                             key="risk_level")
    budget_pct = RISK_LEVELS[level]
    with st.expander("Or set your own limit in rupees"):
        own = st.number_input("Largest extra cost you could absorb in a bad case (₹ lakh)",
                              min_value=0.0, value=0.0, step=1.0, key="own_limit",
                              help="Leave at 0 to use the risk tolerance above.")
        if own > 0:
            budget_pct = budget_pct_from_inr(own * 1e5, invoice_usd, m["spot"])

# ---------- Calculation (from src/, cached) ----------
forward, spot_end = payment_paths(months)
grid = scores_from_paths(forward, m["spot"], spot_end)
a = advise(m, forward, grid, invoice_usd, budget_pct)

tab_rec, tab_track, tab_about = st.tabs(["Recommendation", "Track record", "How it works"])

# ---------- Tab 1: the recommendation ----------
with tab_rec:
    c1, c2, c3 = st.columns(3)
    c1.metric("Spot rate today", f"₹{m['spot']:.2f} per USD")
    c2.metric(f"{months}-month forward rate", f"₹{forward:.2f} per USD",
              f"{(forward / m['spot'] - 1) * 100:+.2f}% vs spot", delta_color="off")
    c3.metric("Market regime", m["regime"])
    st.info(REGIME_TEXT[m["regime"]])

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
        st.warning("Even a full hedge costs more than your limit, because the forward rate is above today's "
                   "rate. A 100% hedge is the lowest-risk option available.")

    st.subheader("What could happen: 10,000 simulated outcomes")
    ratios = [0.0] if a["ratio"] == 0 else [0.0, a["ratio"]]
    st.bar_chart(outcome_histogram(spot_end, forward, m["spot"], invoice_usd, ratios), stack=False,
                 x_label="Extra cost vs paying at today's rate (₹ lakh)", y_label="% of outcomes")
    st.caption("Left of zero: the rupee strengthened and you paid less. The hedge narrows the spread: "
               "fewer painful outcomes on the right, less windfall on the left.")

    st.subheader("All options compared")
    st.caption("Extra rupees compared with paying at today's rate. Negative = you pay less.")
    st.dataframe(candidates_table(grid, a["cost_today_inr"], a["ratio"]), hide_index=True)

    risk_curve = pd.DataFrame({
        "Hedge ratio (%)": (grid["hedge_ratio"] * 100).round(),
        "Worst 1-in-20 extra cost (lakh)": grid["var_pct"] / 100 * a["cost_today_inr"] / 1e5,
        "Your limit (lakh)": a["budget_inr"] / 1e5,
    }).set_index("Hedge ratio (%)")
    st.line_chart(risk_curve)
    st.caption("The recommendation is the smallest hedge where the worst-case line drops below your limit line: "
               "you get the protection you need and keep the rest of the upside if the rupee strengthens.")

# ---------- Tab 2: how the method did in the past ----------
with tab_track:
    record = track_record()
    if record is None:
        st.info("Run `python src/backtest.py` to add the track record.")
    else:
        dec, summary = record
        st.header("How this method did, 2012-2026")
        st.write(f"{len(dec)} monthly decisions, each made using only data available that day, then checked "
                 "against the rupee's actual rate 6 months later. Figures are % of the payment's cost.")
        show = summary.head(7).rename(columns={
            "strategy": "Strategy", "avg_hedge": "Average hedge", "avg_extra_pct": "Average extra cost %",
            "worst_5pct": "1-in-20 bad case %", "worst_pct": "Worst %", "best_pct": "Best %"})
        show["Average hedge"] = (show["Average hedge"] * 100).round().astype(int).astype(str) + "%"
        st.dataframe(show.drop(columns="std_extra_pct").round(2), hide_index=True)

        st.subheader("Forward premium vs what the rupee actually did")
        st.line_chart(dec[["premium_pct", "actual_move_pct"]].rename(columns={
            "premium_pct": "Forward premium (cost of hedging) %",
            "actual_move_pct": "Actual rupee move over the next 6 months %"}))
        st.caption("When the actual move ends above the premium, hedging paid off. On average since 2012 the "
                   f"premium was {dec['premium_pct'].mean():.2f}% and the move {dec['actual_move_pct'].mean():.2f}%: "
                   "hedging costs about what it saves, and its value is cutting the bad outcomes.")

        st.subheader("Recommended hedge over time (Balanced buyer)")
        st.line_chart((dec[["aware_Balanced"]] * 100).rename(columns={"aware_Balanced": "Hedge ratio %"}))
        st.caption("In 2012-2016 the forward premium alone was about 4%, at the Balanced limit, so the tool "
                   "hedged 100%. As interest-rate gaps narrowed it hedged less, and more in volatile spells.")

# ---------- Tab 3: method and limits ----------
with tab_about:
    st.markdown(f"""
- **Risk** comes from 10,000 simulated rupee paths built from real 2000-{m['as_of'].year} history, starting from today's
  regime (**{m['regime']}**) and allowing it to change along the way.
- **The regime** is found by K-Means on 20- and 60-day rupee volatility: Calm, Normal or Crisis.
- **The forward rate** uses covered interest parity with India's 3-month interbank rate ({m['r_inr']:.2f}%) and the
  US 3-month T-bill rate ({m['r_usd']:.2f}%). A bank's quote will include a spread on top.
- **On average every option costs about the same** (the forward premium): the simulation is centred on the forward,
  the market's own expectation. Hedging changes how bad it can get, not the average.
- **The recommendation** is the smallest hedge (in 5% steps) whose 1-in-20 bad case fits your limit.
- Data is a fixed snapshot from {m['as_of']}; interest rates carry a 2-month publication lag.
- Payments due in under a month: use 1 month. Amounts are converted at today's spot rate.
- This is a model built on past data, not financial advice. Confirm with your bank before booking a forward.
""")