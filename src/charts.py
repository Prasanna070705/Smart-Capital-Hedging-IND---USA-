# src/charts.py
# Chart specifications (Vega-Lite, the format Streamlit's st.vega_lite_chart draws). Plain dicts, so they
# can be tested without Streamlit. Each function returns (data, spec).
import pandas as pd

REGIME_COLOURS = {"Calm": "#2da44e", "Normal": "#d4a72c", "Crisis": "#cf222e"}
HEDGE_COLOURS = ["#8c959f", "#1f6feb"]      # unhedged grey, recommended hedge blue


def outcome_histogram_chart(hist, var_lakh, limit_lakh):
    """Overlaid bars of simulated extra cost, with vertical rules at the buyer's limit and at the
    recommended hedge's worst 1-in-20 cost. `hist` is advisor.outcome_histogram's output."""
    data = hist.reset_index().melt(id_vars=hist.index.name, var_name="Strategy", value_name="Share")
    data = data.rename(columns={hist.index.name: "Extra"})
    rules = pd.DataFrame({"x": [limit_lakh, var_lakh],
                          "label": ["Your limit", "Worst 1-in-20 with hedge"]})
    spec = {
        "title": "What could happen: 10,000 simulated outcomes",
        "layer": [
            {"data": {"values": data.to_dict("records")},
             "mark": {"type": "bar", "opacity": 0.6},
             "encoding": {
                 "x": {"field": "Extra", "type": "quantitative", "title": "Extra cost vs today's rate (₹ lakh)"},
                 "y": {"field": "Share", "type": "quantitative", "title": "% of outcomes", "stack": None},
                 "color": {"field": "Strategy", "type": "nominal",
                           "scale": {"range": HEDGE_COLOURS}},
                 "tooltip": [{"field": "Strategy"}, {"field": "Extra", "title": "₹ lakh"},
                             {"field": "Share", "title": "% of outcomes", "format": ".1f"}]}},
            {"data": {"values": rules.to_dict("records")},
             "mark": {"type": "rule", "strokeDash": [6, 4], "strokeWidth": 2},
             "encoding": {"x": {"field": "x", "type": "quantitative"},
                          "color": {"value": "#cf222e"},
                          "tooltip": [{"field": "label"}, {"field": "x", "title": "₹ lakh", "format": ".1f"}]}},
            {"data": {"values": rules.to_dict("records")},
             "mark": {"type": "text", "angle": 270, "dx": -8, "align": "left", "baseline": "bottom"},
             "encoding": {"x": {"field": "x", "type": "quantitative"}, "y": {"value": 5},
                          "text": {"field": "label"}}},
        ],
    }
    return data, spec


def risk_curve_chart(grid, cost_today, limit_lakh, chosen_ratio):
    """Worst 1-in-20 extra cost for every hedge ratio, the limit as a horizontal rule, and the
    recommended ratio highlighted."""
    data = pd.DataFrame({"Hedge": (grid["hedge_ratio"] * 100).round(),
                         "VaR": grid["var_pct"] / 100 * cost_today / 1e5})
    data["Recommended"] = data["Hedge"] == round(chosen_ratio * 100)
    spec = {
        "title": "Risk for every hedge ratio",
        "layer": [
            {"data": {"values": data.to_dict("records")}, "mark": {"type": "line", "point": True},
             "encoding": {"x": {"field": "Hedge", "type": "quantitative", "title": "Hedge ratio (%)"},
                          "y": {"field": "VaR", "type": "quantitative", "title": "Worst 1-in-20 extra cost (₹ lakh)"},
                          "tooltip": [{"field": "Hedge", "title": "Hedge %"},
                                      {"field": "VaR", "title": "₹ lakh", "format": ".1f"}]}},
            {"data": {"values": [{"limit": limit_lakh}]},
             "mark": {"type": "rule", "strokeDash": [6, 4], "color": "#cf222e"},
             "encoding": {"y": {"field": "limit", "type": "quantitative"}}},
            {"data": {"values": data[data["Recommended"]].to_dict("records")},
             "mark": {"type": "point", "size": 250, "filled": True, "color": "#1f6feb"},
             "encoding": {"x": {"field": "Hedge", "type": "quantitative"},
                          "y": {"field": "VaR", "type": "quantitative"}}},
        ],
    }
    return data, spec


def regime_timeline_chart(labels, days=500):
    """Last `days` trading days of 20-day volatility, each day coloured by its regime.
    `labels` is outputs/regime_labels.csv (index date, columns vol_20d and regime)."""
    recent = labels.tail(days).reset_index()
    data = pd.DataFrame({"Date": recent["date"].dt.strftime("%Y-%m-%d"),
                         "Volatility": recent["vol_20d"] * 100, "Regime": recent["regime"]})
    spec = {
        "title": "Rupee volatility and market regime, last 2 years",
        "mark": {"type": "bar", "width": {"band": 1}},
        "encoding": {
            "x": {"field": "Date", "type": "temporal", "title": None},
            "y": {"field": "Volatility", "type": "quantitative", "title": "20-day volatility (% a year)"},
            "color": {"field": "Regime", "type": "nominal",
                      "scale": {"domain": list(REGIME_COLOURS), "range": list(REGIME_COLOURS.values())}},
            "tooltip": [{"field": "Date", "type": "temporal"}, {"field": "Regime"},
                        {"field": "Volatility", "format": ".1f", "title": "Volatility %"}]},
    }
    return data, spec