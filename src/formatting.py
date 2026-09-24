# src/formatting.py
# Number formatting for Indian users: 1,23,45,678 grouping, and amounts in lakh or crore.

LAKH = 1e5
CRORE = 1e7


def indian_group(n):
    """12345678 -> '1,23,45,678' (last 3 digits, then groups of 2). Whole numbers only."""
    sign = "-" if n < 0 else ""
    digits = str(int(round(abs(n))))
    if len(digits) <= 3:
        return sign + digits
    head, tail = digits[:-3], digits[-3:]
    pairs = []
    while len(head) > 2:
        pairs.insert(0, head[-2:])
        head = head[:-2]
    return sign + ",".join([head] + pairs + [tail])


def inr(amount):
    """Full rupee amount: 9,58,70,000 -> '₹9,58,70,000'."""
    return ("-" if amount < 0 else "") + "₹" + indian_group(abs(amount))


def inr_short(amount):
    """Readable rupee amount: crore from 1 crore up, lakh below that. 3,98,00,000 -> '₹3.98 crore'."""
    sign = "-" if amount < 0 else ""
    a = abs(amount)
    if a >= CRORE:
        return f"{sign}₹{a / CRORE:,.2f} crore"
    return f"{sign}₹{a / LAKH:,.1f} lakh"


def usd(amount):
    """USD with international grouping: 521540 -> 'USD 521,540'."""
    return f"USD {amount:,.0f}"


def rate(value):
    """An exchange rate: 96.618 -> '₹96.62'."""
    return f"₹{value:,.2f}"
