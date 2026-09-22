# src/advisor.py
# Objective 4b helper: everything the app needs, as plain functions (no Streamlit here, so it can be tested).
# The app calls these; it never re-implements the finance itself.
import numpy as np
import pandas as pd

from config import (FORWARD_QUOTES_FILE, BACKTEST_FILE, BACKTEST_SUMMARY_FILE, BLOCK_LEN, REGIME_NAMES,
                    TRADING_DAYS_PER_YEAR, HEDGE_RATIOS, RATIO_GRID, N_SIMULATIONS, CONFIDENCE, RANDOM_SEED)
from forward_pricing import cip_forward
from optimizer import (load_regime_history, transition_matrix, simulate_returns, end_rates, score_ratio,
                       recommend)

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


def simulate_payment(market, months):
    """Forward rate and 10,000 simulated rates on the payment date (centred on the forward) for a
    payment `months` from now. Same random seed and steps as optimizer.score_grid."""
    horizon = max(1, round(months * TRADING_DAYS_PER_YEAR / 12))
    forward = cip_forward(market["spot"], market["r_inr"], market["r_usd"], months / 12)
    sims = simulate_returns(market["returns"], market["labels"], market["regime"], market["trans"],
                            REGIME_NAMES, N_SIMULATIONS, horizon, BLOCK_LEN, np.random.default_rng(RANDOM_SEED))
    return forward, end_rates(sims, market["spot"], forward)


def scores_from_paths(forward, spot, spot_end):
    """Every hedge ratio on the grid scored on the same simulated rates."""
    return pd.DataFrame([score_ratio(h, forward, spot, spot_end, CONFIDENCE) for h in RATIO_GRID])


def score_for_tenor(market, months):
    """Forward rate and the scored hedge-ratio grid for a payment `months` from now."""
    forward, spot_end = simulate_payment(market, months)
    return forward, scores_from_paths(forward, market["spot"], spot_end)


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


def outcome_histogram(spot_end, forward, spot, invoice_usd, ratios, bins=40):
    """How often each extra cost (INR lakh vs paying at today's spot) happens, for each hedge ratio,
    on shared bins so the shapes can be compared on one chart. Rows = bin centres, values = % of paths.
    The most extreme 0.5% at each end are folded into the outer bins so the chart stays readable."""
    extra = {h: invoice_usd * (h * forward + (1 - h) * spot_end - spot) / 1e5 for h in ratios}
    everything = np.concatenate(list(extra.values()))
    lo, hi = np.percentile(everything, [0.5, 99.5])
    if hi - lo < 1e-9:                      # e.g. only a 100% hedge: every path costs the same
        lo, hi = lo - 0.5, hi + 0.5
    extra = {h: np.clip(v, lo, hi) for h, v in extra.items()}
    edges = np.linspace(lo, hi, bins + 1)
    centres = np.round((edges[:-1] + edges[1:]) / 2, 1)
    cols = {f"Hedge {h:.0%}": np.histogram(v, bins=edges)[0] / len(v) * 100 for h, v in extra.items()}
    return pd.DataFrame(cols, index=pd.Index(centres, name="Extra cost (INR lakh)"))


def load_track_record():
    """Backtest results for the app's 'Track record' tab, or None if backtest.py hasn't been run."""
    if not (BACKTEST_FILE.exists() and BACKTEST_SUMMARY_FILE.exists()):
        return None
    dec = pd.read_csv(BACKTEST_FILE, parse_dates=["date"], index_col="date")
    summary = pd.read_csv(BACKTEST_SUMMARY_FILE)
    return dec, summary