# tests/chatbot_eval.py
# Evaluates the REAL chatbot on 15 questions with known answers (needs internet and CHAT_API_KEY).
# Not a unit test (the file name doesn't start with test_), so run_all.py skips it. Run it yourself:
#   python tests/chatbot_eval.py
import csv
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from config import RISK_LEVELS, OUTPUTS_DIR
from advisor import load_market, score_for_tenor, advise
import chatbot
from chat_tools import TOOLS, run_tool

PAUSE_S = 15         # Groq's free plan allows 8,000 tokens a minute, about 4 requests; slow down if you see rate-limit answers

# (question, facts: each inner list = acceptable spellings, ALL groups must appear, tool expected?, refusal?)
CASES = [
    ("What hedge ratio do you recommend for my payment?", [["50%"]], False, False),
    ("What is the worst 1-in-20 extra cost if I don't hedge at all?", [["71.7"]], False, False),
    ("What forward rate would I lock in?", [["96.62"]], False, False),
    ("What is the current market regime?", [["Calm", "calm"]], False, False),
    ("Why not hedge 100%?", [["upside", "strengthen", "benefit", "gain"]], False, False),
    ("What is expected shortfall, in simple words?", [["average", "worst"]], False, False),
    ("How was the backtest done?", [["171", "2012", "walk-forward", "Walk-forward"]], False, False),
    ("Why does the regime model use only volatility?", [["inflation", "CPI", "drift"]], False, False),
    ("What is covered interest parity?", [["interest"]], False, False),
    ("What if my payment is due in 9 months instead?", [["70%"]], True, False),
    ("What if the amount is 20 crore, still 6 months, Balanced?", [["50%"]], True, False),
    ("I am very cautious. How much should I hedge on my 10 crore payment in 6 months?", [["100%"]], True, False),
    ("Is hedging cheap right now compared with the past?", [["cheap", "low", "below"]], True, False),
    ("Which stock should I buy this week?", [["can't", "cannot", "only help", "not able", "outside"]], False, True),
    ("Write me a poem about cricket.", [["can't", "cannot", "only help", "not able", "outside"]], False, True),
]


def plain(text):
    """Undo typographic spacing so fact checks match: '50\u202f%' -> '50%', 'walk\u2011forward' -> 'walk-forward'."""
    text = text.replace("\u202f", " ").replace("\u00a0", " ").replace("\u2009", " ")
    text = text.replace("\u2011", "-").replace("\u2010", "-").replace("\u2013", "-")
    return re.sub(r"(\d)\s+%", r"\1%", text)


def default_ctx(m):
    forward, grid = score_for_tenor(m, 6)
    usd = 1e8 / m["spot"]
    return {"market": m, "invoice_usd": usd, "months": 6, "level": "Balanced", "forward": forward,
            "advice": advise(m, forward, grid, usd, RISK_LEVELS["Balanced"])}


def main():
    online, reason = chatbot.status()
    print(reason)
    if not online:
        sys.exit("The evaluation needs the chatbot online.")
    m = load_market()
    ctx = default_ctx(m)
    retriever = chatbot.Retriever(chatbot.load_passages())
    rows, passed = [], 0
    for i, (q, facts, want_tool, refusal) in enumerate(CASES, 1):
        r = chatbot.ask(q, [], ctx, retriever, tools=TOOLS, run_tool=lambda n, a: run_tool(n, a, m))
        ans = r["answer"]
        has_facts = all(any(s in plain(ans) for s in group) for group in facts)
        used_tool = bool(r["tool_calls"])
        grounded = not r["unverified"]
        ok = has_facts and grounded and (used_tool or not want_tool)
        passed += ok
        print(f"{i:2d}. {'PASS' if ok else 'FAIL'}  facts={'y' if has_facts else 'n'} "
              f"grounded={'y' if grounded else 'n'} tool={'y' if used_tool else 'n'}  {q}")
        if not ok:
            print("      answer:", ans[:300].replace("\n", " "))
        rows.append({"question": q, "pass": ok, "facts": has_facts, "grounded": grounded,
                     "tool_expected": want_tool, "tool_used": used_tool, "unverified": r["unverified"],
                     "answer": ans})
        time.sleep(PAUSE_S)
    out = OUTPUTS_DIR / "chatbot_eval.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"\n{passed}/{len(CASES)} passed. Model: {chatbot.CHAT_MODEL}. Saved {out.name} to outputs/")


if __name__ == "__main__":
    main()