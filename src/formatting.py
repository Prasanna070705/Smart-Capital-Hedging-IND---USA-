# src/formatting.py
# v1.1 Day 1: how numbers and the answer are written for an Indian buyer. No finance here and no Streamlit,
# so every function is plain text in, plain text out, and can be tested.
LAKH = 1e5
CRORE = 1e7


def indian_digits(n):
    """Group a whole number the Indian way: 12345678 -> '1,23,45,678' (last 3 digits, then pairs)."""
    s = str(abs(int(n)))
    head, tail = s[:-3], s[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return ("-" if n < 0 else "") + ",".join(groups + [tail])


def inr(amount, decimals=0):
    """Full rupee amount with Indian grouping: 12345678 -> '₹1,23,45,678'; -500.5, 2 -> '-₹500.50'."""
    text = f"{abs(amount):.{decimals}f}"
    whole, _, frac = text.partition(".")
    negative = amount < 0 and float(text) != 0          # -0.4 rounds to ₹0, not -₹0
    return ("-" if negative else "") + "₹" + indian_digits(int(whole)) + ("." + frac if frac else "")


def inr_short(amount, decimals=1):
    """Rupees in the unit an Indian buyer reads fastest: '₹10.0 crore', '₹39.8 lakh', or '₹85,000'."""
    size = abs(amount)
    sign = "-" if amount < 0 else ""
    if round(size / CRORE, decimals) >= 1:
        return f"{sign}₹{size / CRORE:,.{decimals}f} crore"
    if round(size / LAKH, decimals) >= 1:
        return f"{sign}₹{size / LAKH:,.{decimals}f} lakh"
    return inr(amount)


def usd(amount):
    """Dollar amounts keep the international grouping the bank's dealing desk uses: 'USD 521,540'."""
    return f"USD {amount:,.0f}"


def rate(inr_per_usd):
    """An exchange rate: '₹96.62 per USD'."""
    return f"₹{inr_per_usd:.2f} per USD"


def months_text(months):
    return f"{months} month" + ("" if months == 1 else "s")


def answer_card(a, months):
    """The one-glance answer at the top of the app, built from advisor.advise()'s output.
    Returns plain sentences (Markdown bold allowed); the app only displays them."""
    ratio, when = a["ratio"], months_text(months)
    if ratio == 0:
        action = (f"Don't book a forward today. Buy the full **{usd(a['open_usd'])}** at the market rate "
                  f"when the payment is due in {when}.")
    elif ratio == 1:
        action = (f"Book a forward contract today for the full **{usd(a['hedge_usd'])}** at "
                  f"{rate(a['forward'])}, due in {when}.")
    else:
        action = (f"Book a forward contract today for **{usd(a['hedge_usd'])}** at {rate(a['forward'])}. "
                  f"Buy the other **{usd(a['open_usd'])}** at the market rate when the payment is due "
                  f"in {when}.")

    bad, unhedged, limit = inr_short(a["var_inr"]), inr_short(a["unhedged_var_inr"]), inr_short(a["budget_inr"])
    if a["fits_budget"]:
        protection = (f"In a 1-in-20 bad case you would pay about **{bad}** more than at today's rate, within "
                      f"your limit of {limit}.")
    else:
        protection = (f"In a 1-in-20 bad case you would pay about **{bad}** more than at today's rate. That is "
                      f"above your limit of {limit}, but it is the lowest risk available.")
    if ratio > 0:
        protection += f" Without a hedge it could be {unhedged}."

    cost = (f"Locking in costs **{inr_short(a['premium_inr'])}** compared with today's rate, because the "
            f"forward rate is above the spot rate." if ratio > 0 and a["premium_inr"] > 0 else "")
    return {
        "headline": f"Recommendation: hedge {ratio:.0%}",
        "action": action,
        "protection": protection,
        "cost": cost,
        "status": "fits" if a["fits_budget"] else "over",
    }
