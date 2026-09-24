# src/chat_tools.py
# Tools the chatbot may call (Day 6). Each one runs the project's own model, so "what if" answers come
# from the same code as the app, never from the language model's guesswork.
from config import RISK_LEVELS
from advisor import score_for_tenor, advise, budget_pct_from_inr
from insights import premium_context
from formatting import inr_short, usd, rate

TOOLS = [
    {"type": "function", "function": {
        "name": "run_hedge_model",
        "description": "Run the hedging model for a USD payment and return the recommended hedge ratio and "
                       "the costs. Use for any 'what if' about amount, payment date or risk tolerance.",
        "parameters": {"type": "object", "properties": {
            "amount": {"type": "number", "description": "Payment size, in the units given by 'unit'."},
            "unit": {"type": "string", "enum": ["INR_crore", "USD"],
                     "description": "INR_crore = crore rupees at today's rate; USD = US dollars."},
            "months": {"type": "integer", "minimum": 1, "maximum": 12, "description": "Months until payment."},
            "risk_level": {"type": "string", "enum": list(RISK_LEVELS),
                           "description": "Risk tolerance. Ignored if limit_lakh is given."},
            "limit_lakh": {"type": "number",
                           "description": "Optional: largest extra cost the buyer can absorb, in INR lakh."},
        }, "required": ["amount", "unit", "months"]}}},
    {"type": "function", "function": {
        "name": "hedging_cost_context",
        "description": "Today's forward premium (the cost of hedging) compared with its history since 2012.",
        "parameters": {"type": "object", "properties": {}}}},
]


def run_tool(name, args, market):
    """Execute one tool call. `market` is advisor.load_market()'s output. Raises ValueError on bad input
    (the chatbot passes the message back to the model so it can correct itself)."""
    if name == "hedging_cost_context":
        p = premium_context()
        return {"premium_today_pct_a_year": round(p["today"], 2), "average_since_2012_pct": round(p["average"], 2),
                "share_of_past_days_cheaper_pct": round(p["percentile"]), "verdict": p["verdict"]}
    if name != "run_hedge_model":
        raise ValueError(f"Unknown tool {name}")

    amount, unit = float(args["amount"]), args["unit"]
    months = int(args["months"])
    if amount <= 0 or not 1 <= months <= 12:
        raise ValueError("amount must be positive and months between 1 and 12")
    invoice_usd = amount if unit == "USD" else amount * 1e7 / market["spot"]

    forward, grid = score_for_tenor(market, months)
    if args.get("limit_lakh"):
        budget, level = budget_pct_from_inr(float(args["limit_lakh"]) * 1e5, invoice_usd, market["spot"]), "custom"
    else:
        level = args.get("risk_level") or "Balanced"
        if level not in RISK_LEVELS:
            raise ValueError(f"risk_level must be one of {list(RISK_LEVELS)}")
        budget = RISK_LEVELS[level]
    a = advise(market, forward, grid, invoice_usd, budget)
    return {
        "payment": usd(invoice_usd), "payment_in_inr_today": inr_short(a["cost_today_inr"]), "months": months,
        "risk_level": level, "bad_case_limit": inr_short(a["budget_inr"]), "market_regime": market["regime"],
        "forward_rate": rate(forward), "recommended_hedge_pct": round(a["ratio"] * 100),
        "usd_to_book_forward": usd(a["hedge_usd"]), "usd_left_open": usd(a["open_usd"]),
        "worst_1_in_20_extra_cost_hedged": inr_short(a["var_inr"]),
        "worst_1_in_20_extra_cost_unhedged": inr_short(a["unhedged_var_inr"]),
        "locked_in_cost_of_hedge": inr_short(a["premium_inr"]), "fits_limit": a["fits_budget"],
    }
