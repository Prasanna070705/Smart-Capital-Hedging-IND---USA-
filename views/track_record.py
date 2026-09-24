# views/track_record.py
# The Track record tab: how the method did in the 2012-2026 walk-forward backtest.
import streamlit as st

from advisor import load_track_record
from glossary import tip


@st.cache_data
def _record():
    return load_track_record()


def render(ctx):
    record = _record()
    if record is None:
        st.info("Run `python src/backtest.py` to add the track record.")
        return
    dec, summary = record
    st.header("How this method did, 2012-2026", help=tip("Backtest"))
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
