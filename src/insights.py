# src/insights.py
# Extra insights for the app (v1.1). Plain functions over existing outputs; no new finance model.
import numpy as np
import pandas as pd

from config import FORWARD_QUOTES_FILE
from advisor import score_for_tenor, advise


def premium_context(quotes=None):
    """Is hedging cheap right now? Today's annualised forward premium against its own history
    (every trading day with a matching-tenor forward, 2012 onward)."""
    if quotes is None:
        quotes = pd.read_csv(FORWARD_QUOTES_FILE, parse_dates=["date"], index_col="date")
    hist = quotes["premium_annual_pct"]
    today = float(hist.iloc[-1])
    pct = float((hist < today).mean() * 100)          # share of past days that were cheaper
    return {"today": today, "average": float(hist.mean()), "percentile": pct,
            "low": float(hist.min()), "high": float(hist.max()), "since": hist.index[0].year,
            "verdict": "cheap" if pct < 25 else "expensive" if pct > 75 else "about normal"}


def breakeven(forward, spot_end):
    """The forward rate is the break-even: hedging wins if the rupee ends weaker than it.
    Returns the rate and the simulated chance that hedging turns out cheaper."""
    return {"rate": float(forward), "hedge_wins_pct": float((spot_end > forward).mean() * 100)}


def tenor_curve(market, invoice_usd, budget_pct, months_list=range(1, 13)):
    """Recommended hedge and bad-case costs for every payment date from 1 to 12 months."""
    rows = []
    for months in months_list:
        forward, grid = score_for_tenor(market, months)
        a = advise(market, forward, grid, invoice_usd, budget_pct)
        rows.append({"Months": months, "Forward": forward, "Hedge %": a["ratio"] * 100,
                     "Unhedged worst 1-in-20 (lakh)": a["unhedged_var_inr"] / 1e5,
                     "Hedged worst 1-in-20 (lakh)": a["var_inr"] / 1e5,
                     "Locked-in cost (lakh)": a["premium_inr"] / 1e5})
    return pd.DataFrame(rows)



# ---------- Day 4: stress replay, bank quote, downloadable summary ----------

# Real episodes of rupee weakness: (label, first trading day). The move over the next HORIZON_DAYS
# trading days is replayed on today's payment.
STRESS_EVENTS = [
    ("1991 balance-of-payments crisis", "1991-06-03"),
    ("2008 global financial crisis", "2008-08-01"),
    ("2013 taper tantrum", "2013-05-01"),
    ("2018 emerging-market sell-off", "2018-04-02"),
    ("2020 COVID shock", "2020-02-03"),
]


def stress_replay(master, spot, forward, invoice_usd, ratio, horizon, events=STRESS_EVENTS):
    """What each historical episode's actual move would cost this payment, unhedged and hedged.
    The move is measured from the event's start to `horizon` trading days later."""
    s = master["usd_inr_spot"].dropna()
    rows = []
    for label, start in events:
        i = s.index.searchsorted(pd.Timestamp(start))
        if i + horizon >= len(s):
            continue
        move = s.iloc[i + horizon] / s.iloc[i] - 1
        end = spot * (1 + move)
        cost = lambda h: invoice_usd * (h * forward + (1 - h) * end - spot)
        rows.append({"Episode": label, "From": s.index[i].date(), "Rupee move %": move * 100,
                     "Extra cost unhedged (lakh)": cost(0.0) / 1e5,
                     "Extra cost with hedge (lakh)": cost(ratio) / 1e5})
    return pd.DataFrame(rows)


def bank_quote_grid(bank_forward, spot, spot_end, confidence=0.95):
    """Score every hedge ratio using the forward rate the bank actually offers. The simulated rates stay
    centred on the fair (CIP) forward: a bank spread makes hedging dearer, it doesn't move the market."""
    from config import RATIO_GRID
    from optimizer import score_ratio
    return pd.DataFrame([score_ratio(h, bank_forward, spot, spot_end, confidence) for h in RATIO_GRID])


def summary_csv(ctx, premium):
    """One-page summary of the recommendation as CSV text (opens in Excel)."""
    a, m = ctx["advice"], ctx["market"]
    rows = [
        ("Market data as of", m["as_of"]),
        ("Spot rate (INR per USD)", round(m["spot"], 4)),
        ("Market regime", m["regime"]),
        ("Payment amount (USD)", round(ctx["invoice_usd"], 2)),
        ("Months until payment", ctx["months"]),
        ("Forward rate (INR per USD)", round(ctx["forward"], 4)),
        ("Forward premium today (% a year)", round(premium["today"], 2)),
        ("Bad-case limit (INR)", round(a["budget_inr"])),
        ("Recommended hedge ratio (%)", round(a["ratio"] * 100)),
        ("USD to book forward", round(a["hedge_usd"], 2)),
        ("USD left open", round(a["open_usd"], 2)),
        ("Worst 1-in-20 extra cost with hedge (INR)", round(a["var_inr"])),
        ("Worst 1-in-20 extra cost unhedged (INR)", round(a["unhedged_var_inr"])),
        ("Locked-in cost of the hedge (INR)", round(a["premium_inr"])),
        ("Note", "Model output from past data, not financial advice. Confirm the forward rate with your bank."),
    ]
    return pd.DataFrame(rows, columns=["Item", "Value"]).to_csv(index=False).encode("utf-8")