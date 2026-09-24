# views/recommendation.py
# The Recommendation tab: answer card first, then the evidence behind it.
import pandas as pd
import streamlit as st

from advisor import REGIME_TEXT, candidates_table, outcome_histogram
from formatting import inr_short, usd, rate
from glossary import tip


def answer_card(ctx):
    """The one thing the buyer came for, in large type at the top."""
    a, m, fwd = ctx["advice"], ctx["market"], ctx["forward"]
    with st.container(border=True):
        st.header(f"Recommendation: hedge {a['ratio']:.0%}")
        st.markdown(f"Book a forward contract for **{usd(a['hedge_usd'])}** at **{rate(fwd)}**, and buy the "
                    f"remaining **{usd(a['open_usd'])}** at the market rate when the payment is due in "
                    f"**{ctx['months']} month{'s' if ctx['months'] > 1 else ''}**.")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Hedge ratio", f"{a['ratio']:.0%}", help=tip("Hedge ratio"))
        c2.metric("Worst 1-in-20 extra cost", inr_short(a["var_inr"]),
                  f"{inr_short(a['unhedged_var_inr'])} if unhedged", delta_color="off", help=tip("VaR 95%"))
        c3.metric("Your bad-case limit", inr_short(a["budget_inr"]), help=tip("Bad-case limit"))
        c4.metric("Locked-in cost of the hedge", inr_short(a["premium_inr"]), help=tip("Forward premium"))
        if not a["fits_budget"]:
            st.warning("Even a full hedge costs more than your limit, because the forward rate is above today's "
                       "rate. A 100% hedge is the lowest-risk option available.")


def market_row(ctx):
    m, fwd = ctx["market"], ctx["forward"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Spot rate today", f"{rate(m['spot'])} per USD", help=tip("Spot rate"))
    c2.metric(f"{ctx['months']}-month forward rate", f"{rate(fwd)} per USD",
              f"{(fwd / m['spot'] - 1) * 100:+.2f}% vs spot", delta_color="off", help=tip("Forward rate"))
    c3.metric("Market regime", m["regime"], help=tip("Regime"))
    st.info(REGIME_TEXT[m["regime"]])


def distribution_chart(ctx):
    a, m = ctx["advice"], ctx["market"]
    st.subheader("What could happen: 10,000 simulated outcomes")
    ratios = [0.0] if a["ratio"] == 0 else [0.0, a["ratio"]]
    st.bar_chart(outcome_histogram(ctx["spot_end"], ctx["forward"], m["spot"], ctx["invoice_usd"], ratios),
                 stack=False, x_label="Extra cost vs paying at today's rate (₹ lakh)", y_label="% of outcomes")
    st.caption("Left of zero: the rupee strengthened and you paid less. The hedge narrows the spread: "
               "fewer painful outcomes on the right, less windfall on the left.")


def risk_curve(ctx):
    a, grid = ctx["advice"], ctx["grid"]
    curve = pd.DataFrame({
        "Hedge ratio (%)": (grid["hedge_ratio"] * 100).round(),
        "Worst 1-in-20 extra cost (lakh)": grid["var_pct"] / 100 * a["cost_today_inr"] / 1e5,
        "Your limit (lakh)": a["budget_inr"] / 1e5,
    }).set_index("Hedge ratio (%)")
    st.line_chart(curve)
    st.caption("The recommendation is the smallest hedge where the worst-case line drops below your limit line.")


def render(ctx):
    answer_card(ctx)
    market_row(ctx)
    distribution_chart(ctx)
    st.subheader("All options compared")
    st.caption("Extra rupees compared with paying at today's rate. Negative = you pay less.")
    st.dataframe(candidates_table(ctx["grid"], ctx["advice"]["cost_today_inr"], ctx["advice"]["ratio"]),
                 hide_index=True)
    risk_curve(ctx)
