# src/glossary.py
# Plain-language definitions, used for the app's tooltips and (from Day 5) by the chatbot.

GLOSSARY = {
    "Spot rate": "The exchange rate today: how many rupees one US dollar costs right now.",
    "Forward rate": "A rate agreed today for buying dollars on a future date. Booking it removes the risk of the "
                    "rupee weakening, and also the chance of it strengthening.",
    "Forward premium": "How much higher the forward rate is than today's spot rate. It is the cost of hedging, and "
                       "it comes from India's interest rates being higher than US rates (covered interest parity).",
    "Hedge ratio": "The share of the payment locked in with a forward contract. 50% means half the dollars are "
                   "bought at the forward rate and half at whatever the rate is on the payment date.",
    "VaR 95%": "Value at Risk: the extra cost that is exceeded in only 1 of 20 simulated futures. Here it is called "
               "the 'worst 1-in-20 extra cost'.",
    "ES 95%": "Expected Shortfall: the average extra cost across the worst 1 in 20 futures. Always at least as "
              "large as VaR.",
    "Regime": "The state of the rupee market, found by K-Means on 20- and 60-day volatility: Calm, Normal or "
              "Crisis. Riskier regimes lead to more hedging.",
    "Bad-case limit": "The largest extra cost the buyer says they could absorb in a 1-in-20 bad case. The tool "
                      "recommends the smallest hedge that keeps VaR within it.",
    "Covered interest parity": "The rule that prices the forward: forward = spot x (1 + India rate x t) / "
                               "(1 + US rate x t), so holding rupees or dollars for the period costs the same.",
    "Monte Carlo simulation": "Building 10,000 possible futures for the rupee by stitching together real 10-day "
                              "stretches of 2000-2026 history, starting from today's regime.",
    "Backtest": "Testing the method on the past: 171 monthly decisions since 2012, each using only data available "
                "that day, checked against what the rupee actually did 6 months later.",
}


def tip(term):
    """Tooltip text for a term (empty string if unknown)."""
    return GLOSSARY.get(term, "")
