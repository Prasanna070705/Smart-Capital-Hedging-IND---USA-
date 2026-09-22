# src/advisor.py
# Objective 4b helper: everything the app needs, as plain functions (no Streamlit here, so it can be tested).
# The app calls these; it never re-implements the finance itself.
import pandas as pd

from config import (FORWARD_QUOTES_FILE, BLOCK_LEN, REGIME_NAMES, TRADING_DAYS_PER_YEAR, HEDGE_RATIOS)
from forward_pricing import cip_forward
from optimizer import load_regime_history, transition_matrix, score_grid, recommend

REGIME_TEXT = {
    "Calm": "The rupee has been moving very little. Large swings are less likely, so less hedging is needed.",
    "Normal": "The rupee is moving about as much as usual.",
    "Crisis": "The rupee is unusually volatile. Large swings are more likely, so more hedging is recommended.",
}


def load_market():
    """Latest snapshot: spot, matching-tenor interest rates, today's regime, and the history
    the simulation resamples."""
    quotes = pd.read_csv(FORWARD_QUOTES_FILE, parse_dates=["date"], index_col="date")
    last = quotes.iloc[-1]
    returns, labels, regime = load_regime_history()
    return {
        "as_of": quotes.index[-1].date(),
        "spot": float(last["spot"]),
        "r_inr": float(last["r_inr_pct"]),
        "r_usd": float(last["r_usd_pct"]),
        "regime": regime,
        "returns": returns,
        "labels": labels,
        "trans": transition_matrix(labels, BLOCK_LEN, REGIME_NAMES),
    }


def score_for_tenor(market, months):
    """Forward rate and the scored hedge-ratio grid for a payment `months` from now."""
    t_years = months / 12
    horizon = max(1, round(months * TRADING_DAYS_PER_YEAR / 12))
    forward = cip_forward(market["spot"], market["r_inr"], market["r_usd"], t_years)
    grid = score_grid(market["regime"], market["returns"], market["labels"], market["trans"],
                      market["spot"], forward, horizon=horizon)
    return forward, grid


def budget_pct_from_inr(budget_inr, invoice_usd, spot):
    """A rupee overrun limit as % of today's cost."""
    return budget_inr / (invoice_usd * spot) * 100


def advise(market, forward, grid, invoice_usd, budget_pct):
    """The recommendation in rupees for this buyer."""
    spot = market["spot"]
    cost_today = invoice_usd * spot
    ratio = recommend(budget_pct, grid)
    g = grid.set_index("hedge_ratio")
    chosen, unhedged = g.loc[ratio], g.loc[0.0]
    inr = lambda pct: pct / 100 * cost_today
    return {
        "ratio": ratio,
        "hedge_usd": ratio * invoice_usd,
        "open_usd": (1 - ratio) * invoice_usd,
        "forward": forward,
        "cost_today_inr": cost_today,
        "budget_inr": inr(budget_pct),
        "fits_budget": bool(chosen["var_pct"] <= budget_pct + 1e-9),
        "premium_inr": inr((forward / spot - 1) * 100) * ratio,
        "var_inr": inr(chosen["var_pct"]),
        "es_inr": inr(chosen["es_pct"]),
        "best5_inr": inr(chosen["best5_pct"]),
        "unhedged_var_inr": inr(unhedged["var_pct"]),
        "unhedged_es_inr": inr(unhedged["es_pct"]),
    }


def candidates_table(grid, cost_today, recommended):
    """The 5 static ratios plus the recommendation, in rupee lakh (1 lakh = 100,000)."""
    g = grid.set_index("hedge_ratio")
    ratios = sorted(set(HEDGE_RATIOS) | {recommended})
    lakh = lambda pct: pct / 100 * cost_today / 1e5
    return pd.DataFrame({
        "Hedged": [f"{h:.0%}" + ("  <- recommended" if h == recommended else "") for h in ratios],
        "Extra cost on average (lakh)": [lakh(g.loc[h, "expected_pct"]) for h in ratios],
        "Worst 1-in-20 (lakh)": [lakh(g.loc[h, "var_pct"]) for h in ratios],
        "Average of worst cases (lakh)": [lakh(g.loc[h, "es_pct"]) for h in ratios],
        "Best 1-in-20 (lakh)": [lakh(g.loc[h, "best5_pct"]) for h in ratios],
    }).round(1)