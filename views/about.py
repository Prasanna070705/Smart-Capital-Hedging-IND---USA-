# views/about.py
# The How it works tab: method, limits and a glossary.
import streamlit as st

from glossary import GLOSSARY


def render(ctx):
    m = ctx["market"]
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
- This is a model built on past data, not financial advice. Confirm with your bank before booking a forward.
""")
    st.subheader("Glossary")
    for term, meaning in GLOSSARY.items():
        st.markdown(f"**{term}:** {meaning}")
