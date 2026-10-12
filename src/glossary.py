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


# Longer explanations for the Glossary tab (markdown). Same keys as GLOSSARY.
DETAILS = {
    "Spot rate": """
The price of one US dollar in rupees for a deal done today. The app uses the daily USD/INR reference rate published
by FRED (series DEXINUS), so it is a mid-market rate: a bank will quote you slightly more when you buy dollars.

**Why it matters here:** every "extra cost" in the app is measured against paying at today's spot rate. If the spot
rate is 95 and you end up paying 97 per dollar, the extra cost is 2 rupees for every dollar of the invoice.
""",
    "Forward rate": """
A rate you agree with your bank today for buying dollars on a fixed future date. Nothing is exchanged now; on the
payment date you buy the agreed dollars at the agreed rate, whatever the market rate is by then.

- **What you gain:** certainty. A weaker rupee can no longer raise the cost of the hedged part.
- **What you give up:** if the rupee strengthens, you still pay the forward rate on the hedged part.

The app works out a fair forward rate from interest rates (see *Covered interest parity*). A real bank quote adds a
spread on top; the Insights tab lets you type in your bank's quote and reruns the recommendation with it.
""",
    "Forward premium": """
The gap between the forward rate and today's spot rate, as a percentage: forward / spot - 1. It is the known,
locked-in cost of hedging. The app shows it for your payment date and, on the Insights tab, as a yearly rate so
different payment dates can be compared.

**Where it comes from:** Indian interest rates are usually higher than US rates, so rupees earn more than dollars
over the same period. The forward rate is higher than spot by just enough to cancel that advantage. A narrow gap
between the two interest rates means a small premium, which makes hedging cheap.

**How to read it:** hedging pays off when the rupee weakens by more than the premium, and costs money when it
weakens by less. On average the two are close, so the point of hedging is to cut the bad outcomes, not to save money.
""",
    "Hedge ratio": """
The share of the dollar payment you lock in with a forward contract. The rest stays open and is bought at the market
rate on the payment date.

    total cost = hedge ratio x invoice x forward rate + (1 - hedge ratio) x invoice x rate on the payment date

- **0%:** fully exposed. Cheapest if the rupee strengthens, most painful if it weakens.
- **100%:** the cost is known today. No risk left, and no benefit if the rupee strengthens.
- **In between:** a mix. Raising the ratio lowers the worst case and gives up some of the possible gain.

The app tests every ratio from 0% to 100% in steps of 5% and recommends the smallest one that fits your bad-case
limit.
""",
    "VaR 95%": """
Value at Risk at 95% confidence. The app simulates 10,000 possible futures for the rupee, works out the extra cost
of your payment in each one compared with paying at today's spot rate, and sorts them from best to worst. VaR 95% is
the extra cost at the 95% mark: 19 futures in 20 are no worse than this, 1 in 20 is worse.

**Example:** a VaR of INR 40 lakh means that in 9,500 of the 10,000 simulated futures the payment costs at most
INR 40 lakh more than it would today, and in the other 500 it costs more than that.

**What it does not tell you:** how bad those worst 500 futures are. That is what *ES 95%* measures. The app labels
VaR as the "worst 1-in-20 extra cost".
""",
    "ES 95%": """
Expected Shortfall at 95% confidence: the average extra cost across the worst 5% of simulated futures, the ones
beyond the VaR mark. It answers "when things go badly, how badly on average?"

ES is always at least as large as VaR. A big gap between the two means the bad outcomes have a long tail: rare, but
very expensive. In the "All options compared" table it is the column "Average of worst cases".
""",
    "Regime": """
A label for how calm or stormy the rupee market is right now. The app measures how much the rupee has moved over the
last 20 and 60 trading days (its volatility) and groups every day since 2000 into three clusters with K-Means:

- **Calm:** the rupee is moving very little.
- **Normal:** it is moving about as much as usual.
- **Crisis:** it is unusually volatile, as in 2008, 2013 or 2020.

**Why it matters here:** volatility comes in streaks, so today's regime says something about the next few months.
The simulation starts from today's regime and lets it change along the way at the rate seen in history. A riskier
starting regime gives wider outcomes, so the same bad-case limit needs a larger hedge.
""",
    "Bad-case limit": """
The largest extra cost you say you could absorb if things go badly, where "badly" means the 1-in-20 case (VaR 95%).
It is the one input that expresses your appetite for risk.

The risk tolerance slider sets it as a share of the payment's cost today: 1% (Very cautious), 2.5% (Cautious),
4% (Balanced), 6% (Relaxed) or 9% (Very relaxed). You can also type your own limit in rupees in the sidebar.

**How it drives the answer:** the app recommends the smallest hedge whose VaR is within this limit. A tighter limit
means a larger hedge. If even a 100% hedge is above the limit, because the forward premium alone costs more than you
allowed, the app recommends 100% and says so.
""",
    "Covered interest parity": """
The rule that sets a fair forward rate. There are two ways to have dollars on the payment date: buy them now and
hold them at the US interest rate, or hold rupees at the Indian interest rate and buy dollars later at the forward
rate. If the two did not cost the same, traders would profit from the gap until it closed. So:

    forward = spot x (1 + India rate x t) / (1 + US rate x t)

where t is the time to payment in years. The app uses India's 3-month interbank rate and the US 3-month Treasury
bill rate. Because the India rate is usually the higher one, the forward is usually above spot.

**Limits:** this is the fair rate before a bank's spread, and the interest rates are published with a lag of about
two months.
""",
    "Monte Carlo simulation": """
A way to measure risk by building many possible futures instead of guessing one. The app builds 10,000 paths for the
rupee up to your payment date.

- Each path is stitched together from real 10-trading-day stretches of rupee history since 2000. Using whole
  stretches, not single days, keeps the way calm and stormy days cluster together.
- Each path starts in today's regime and may switch regime along the way, as often as history shows.
- The paths are centred on the forward rate, the market's own expectation, so on average every hedge ratio costs
  about the same. What differs between hedge ratios is how wide the outcomes are.

VaR, ES and the outcome chart are all read off these 10,000 futures. The random seed is fixed, so the same inputs
always give the same answer.
""",
    "Backtest": """
A check of the method against the past. For every month since 2012 the app made a recommendation using only the data
that was available on that day, then looked up what the rupee actually did over the next 6 months and worked out
what each strategy would have cost. That gives 171 decisions that were never fitted to their own outcomes.

The Track record tab compares the method with fixed hedges of 0%, 25%, 50%, 75% and 100%.

**Limits:** the past is one history, not a guarantee. A method that did well from 2012 to 2026 can still do badly
in a kind of market that period did not contain.
""",
}


def slug(term):
    """Page anchor for a term on the Glossary tab, e.g. 'VaR 95%' -> 'glossary-var-95'."""
    return "glossary-" + "-".join("".join(c if c.isalnum() else " " for c in term.lower()).split())


def tip(term):
    """Tooltip text for a term (empty string if unknown). The bold term is what views/chrome.py reads to
    open the right Glossary entry when the ? is clicked."""
    if term not in GLOSSARY:
        return ""
    return f"**{term}:** {GLOSSARY[term]}\n\n*Click the ? for the full explanation.*"
