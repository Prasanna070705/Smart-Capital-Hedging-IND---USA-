# src/glossary.py
# v1.1 Day 1: plain-language explanations shown as tooltips in the app (and, from Day 5, used by the chatbot).
# One place for every definition, so the app, the summary and the chatbot never explain a term differently.
GLOSSARY = {
    "spot rate": "Today's exchange rate: how many rupees one US dollar costs if you buy it now.",
    "forward rate": "The rate a bank lets you lock in today for buying dollars on a future date. It is usually "
                    "a little above today's rate because Indian interest rates are higher than US ones.",
    "forward contract": "An agreement with your bank to buy a fixed amount of dollars on a set date at the "
                        "forward rate, whatever the market rate is by then.",
    "hedge ratio": "The share of your payment you lock in with a forward contract. 0% means you take the "
                   "market rate on the day; 100% means the whole payment is fixed today.",
    "bad case": "The extra cost you would face in a 1-in-20 bad outcome: 19 out of 20 simulated outcomes "
                "cost less than this. Finance calls it the 95% Value at Risk (VaR).",
    "worst cases average": "The average extra cost across the worst 1 in 20 outcomes, so it also counts how bad "
                           "the very worst ones get. Finance calls it Expected Shortfall (ES).",
    "locked-in cost": "What hedging costs you for sure: the gap between the forward rate and today's rate, on "
                      "the part you hedge. It is the price of removing the risk on that part.",
    "risk limit": "The largest extra cost you could absorb in a 1-in-20 bad case. The tool recommends the "
                  "smallest hedge that keeps the bad case within this limit.",
    "risk tolerance": "How much extra cost you can live with if the rupee weakens. Cautious buyers get bigger "
                      "hedges; relaxed buyers keep more of the upside if the rupee strengthens.",
    "market regime": "How jumpy the rupee has been lately, grouped as Calm, Normal or Crisis from its 20- and "
                     "60-day volatility. Jumpier markets call for more hedging.",
    "months until payment": "How long until you must pay the invoice. Longer waits leave more time for the "
                            "rupee to move, so they carry more risk.",
    "simulated outcomes": "10,000 possible paths for the rupee up to your payment date, rebuilt from real "
                          "history since 2000 and started from today's market regime.",
    "lakh": "1 lakh = ₹1,00,000 (one hundred thousand rupees).",
    "crore": "1 crore = ₹1,00,00,000 (ten million rupees, or 100 lakh).",
}


def tip(term):
    """The tooltip text for a term; raises KeyError naming the term if it's missing, so typos fail tests."""
    key = term.lower()
    if key not in GLOSSARY:
        raise KeyError(f"No glossary entry for {term!r}")
    return GLOSSARY[key]
