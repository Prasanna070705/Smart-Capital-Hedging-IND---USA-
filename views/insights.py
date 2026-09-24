# views/insights.py
# The Insights tab: context a buyer can act on beyond the headline recommendation.
import pandas as pd
import streamlit as st

from config import MASTER_FILE, TRADING_DAYS_PER_YEAR
from advisor import advise
from insights import premium_context, breakeven, tenor_curve, stress_replay, bank_quote_grid, summary_csv
from formatting import rate, inr_short
from glossary import tip


@st.cache_data
def _premium():
    return premium_context()


@st.cache_data
def _tenors(_market, invoice_usd, budget_pct):
    # The leading underscore tells Streamlit not to hash the market data; the result is cached per amount and limit
    return tenor_curve(_market, invoice_usd, budget_pct)


@st.cache_data
def _master():
    return pd.read_csv(MASTER_FILE, parse_dates=["date"], index_col="date")


def cheapness(ctx):
    p = _premium()
    st.subheader(f"Is hedging cheap right now? {p['verdict'].capitalize()}.", help=tip("Forward premium"))
    c1, c2, c3 = st.columns(3)
    c1.metric("Forward premium today", f"{p['today']:.2f}% a year")
    c2.metric(f"Average since {p['since']}", f"{p['average']:.2f}% a year")
    c3.metric("Cheaper than today", f"{p['percentile']:.0f}% of past days")
    st.caption(f"Since {p['since']} the premium has ranged from {p['low']:.2f}% to {p['high']:.2f}% a year. "
               "It is set by the gap between Indian and US interest rates, so a narrow gap makes hedging cheap.")


def breakeven_box(ctx):
    b = breakeven(ctx["forward"], ctx["spot_end"])
    st.subheader("Break-even rate")
    st.markdown(f"Hedging saves money if the rupee is **weaker than {rate(b['rate'])} per USD** on your payment "
                f"date. In the 10,000 simulated futures that happened **{b['hedge_wins_pct']:.0f}%** of the time. "
                "Either way, the hedge's real job is capping the bad outcomes.")


def payment_date_curve(ctx):
    st.subheader("How the payment date changes the picture")
    t = _tenors(ctx["market"], ctx["invoice_usd"], ctx["budget_pct"])
    st.line_chart(t.set_index("Months")[["Unhedged worst 1-in-20 (lakh)", "Hedged worst 1-in-20 (lakh)"]])
    st.dataframe(t.round(2), hide_index=True)
    st.caption("Risk grows with time, so longer payment terms need more hedging to stay within the same limit. "
               "Worth knowing when negotiating payment terms with the supplier.")


def stress_test(ctx):
    a, m = ctx["advice"], ctx["market"]
    st.subheader("If history repeated: real rupee shocks replayed on your payment")
    horizon = max(1, round(ctx["months"] * TRADING_DAYS_PER_YEAR / 12))
    t = stress_replay(_master(), m["spot"], ctx["forward"], ctx["invoice_usd"], a["ratio"], horizon)
    st.dataframe(t.round(1), hide_index=True)
    st.caption(f"Each row takes the rupee's actual move over {ctx['months']} month(s) from the date shown and "
               f"applies it to today's rate. The hedge column uses the recommended {a['ratio']:.0%} hedge.")


def bank_quote(ctx):
    a, m = ctx["advice"], ctx["market"]
    st.subheader("Have a quote from your bank?")
    bank = st.number_input("Forward rate your bank offered (₹ per USD, 0 = skip)", min_value=0.0, value=0.0,
                           step=0.01, format="%.4f", key="bank_rate",
                           help="Banks add a spread to the fair (covered interest parity) rate. "
                                "Entering the real quote recomputes the recommendation with it.")
    if bank <= 0:
        return
    grid = bank_quote_grid(bank, m["spot"], ctx["spot_end"])
    b = advise(m, bank, grid, ctx["invoice_usd"], ctx["budget_pct"])
    spread = (bank / ctx["forward"] - 1) * 100
    c1, c2, c3 = st.columns(3)
    c1.metric("Bank spread over the fair rate", f"{spread:+.2f}%", f"{bank - ctx['forward']:+.4f} ₹ per USD",
              delta_color="off")
    c2.metric("Recommended hedge with this quote", f"{b['ratio']:.0%}", f"{(b['ratio'] - a['ratio']) * 100:+.0f} points",
              delta_color="off")
    c3.metric("Locked-in cost of the hedge", inr_short(b["premium_inr"]),
              f"{inr_short(b['premium_inr'] - a['premium_inr'])} vs fair rate", delta_color="off")
    if not b["fits_budget"]:
        st.warning("With this quote even a full hedge costs more than your limit.")


def download(ctx):
    st.download_button("Download a one-page summary (CSV)", data=summary_csv(ctx, _premium()),
                       file_name=f"hedge_summary_{ctx['market']['as_of']}.csv", mime="text/csv")


def render(ctx):
    cheapness(ctx)
    breakeven_box(ctx)
    payment_date_curve(ctx)
    stress_test(ctx)
    bank_quote(ctx)
    download(ctx)