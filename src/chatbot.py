
# src/chatbot.py
# Optional chatbot. Online with an API key -> answers questions about the recommendation, grounded in
# (1) the live numbers on screen, (2) passages retrieved from the project docs, and (from Day 6) (3) the hedge
# model itself via tool calls. Offline or no key -> status() says so and the app simply hides chat.
# Uses only the standard library for HTTP, so there is nothing extra to install.
#
# Try it from the terminal:  python src/chatbot.py "Why is the recommendation 50%?"
import json
import contextvars
import os
import re
import sys
import urllib.error
import urllib.request

from dotenv import load_dotenv
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from config import (ROOT_DIR, CHAT_API_URL, CHAT_MODEL, CHAT_TIMEOUT_S, CHAT_STATUS_TIMEOUT_S,
                    CHAT_MAX_TOOL_ROUNDS, DOCS_FOR_CHAT)
from glossary import GLOSSARY
from formatting import inr_short, usd, rate

load_dotenv(ROOT_DIR / ".env")

SYSTEM_RULES = """You are the assistant inside an FX hedging app for Indian importers who must pay in US dollars.
Rules:
- Use ONLY the numbers in CURRENT RECOMMENDATION, DOCUMENT EXCERPTS or tool results. Never estimate or invent a number.
- If a question needs a number you do not have, say so, or (if a tool is available) call it.
- Explain simply, in short paragraphs, for a business owner who is not a finance expert. Amounts in lakh/crore.
- Stay on topic: this app, currency hedging, forwards, risk. Politely decline anything else.
- End any advice-like answer with: "This is a model estimate, not financial advice."
"""


# ---------- Connection ----------

_session_key = contextvars.ContextVar("chat_session_key", default="")


def use_key(key):
    """Use this key for chat calls made by the current app session (views/ask.py sets it on every run).
    Lets a public deployment run without a server-side key: only someone who has a key can chat."""
    _session_key.set((key or "").strip())


def api_key():
    return _session_key.get() or os.getenv("CHAT_API_KEY", "").strip()


def status(transport=None):
    """(online, reason). Online only if a key exists AND the provider answers quickly."""
    if not api_key():
        return False, "No API key: paste one below, or add CHAT_API_KEY=... to the .env file."
    try:
        (transport or _http)("GET", "/models", None, CHAT_STATUS_TIMEOUT_S)
        return True, f"Connected to {CHAT_API_URL.split('/')[2]} ({CHAT_MODEL})."
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return False, "The API key was rejected. Check the key you pasted, or CHAT_API_KEY in .env."
        return False, f"The chat service returned an error ({e.code})."
    except Exception:
        return False, "No internet connection (or the chat service is unreachable)."


def _http(method, path, body, timeout):
    """One call to the OpenAI-compatible API. Returns the parsed JSON response."""
    req = urllib.request.Request(
        CHAT_API_URL.rstrip("/") + path, method=method,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {api_key()}", "Content-Type": "application/json",
                 "User-Agent": "fx-hedging-advisor/1.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


# ---------- Retrieval (the "R" in RAG): TF-IDF over the docs and glossary ----------

def load_passages(paths=DOCS_FOR_CHAT):
    """Split each document at '## ' headings; add one passage per glossary term."""
    passages = []
    for p in paths:
        if not p.exists():
            continue
        for part in re.split(r"\n(?=## )", p.read_text(encoding="utf-8")):
            if part.strip():
                title = part.strip().splitlines()[0].lstrip("# ").strip()
                passages.append({"source": f"{p.name}: {title}", "text": part.strip()})
    passages += [{"source": f"Glossary: {k}", "text": f"{k}: {v}"} for k, v in GLOSSARY.items()]
    return passages


class Retriever:
    def __init__(self, passages):
        self.passages = passages
        self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
        self.matrix = self.vectorizer.fit_transform([p["text"] for p in passages])

    def search(self, question, k=4):
        scores = cosine_similarity(self.vectorizer.transform([question]), self.matrix).ravel()
        best = scores.argsort()[::-1][:k]
        return [dict(self.passages[i], score=float(scores[i])) for i in best if scores[i] > 0]


# ---------- Live context: the numbers on the buyer's screen ----------

def context_text(ctx):
    a, m = ctx["advice"], ctx["market"]
    return "\n".join([
        f"Market data as of {m['as_of']}; spot rate {rate(m['spot'])} per USD; market regime {m['regime']}.",
        f"Payment: {usd(ctx['invoice_usd'])} due in {ctx['months']} months "
        f"(about {inr_short(a['cost_today_inr'])} at today's rate).",
        f"Forward rate for that date: {rate(ctx['forward'])} per USD "
        f"({(ctx['forward'] / m['spot'] - 1) * 100:.2f}% above spot).",
        f"Risk tolerance: {ctx['level']}; bad-case limit {inr_short(a['budget_inr'])}.",
        f"Recommendation: hedge {a['ratio']:.0%}, i.e. book {usd(a['hedge_usd'])} forward and leave "
        f"{usd(a['open_usd'])} open.",
        f"Worst 1-in-20 extra cost (VaR 95%): {inr_short(a['var_inr'])} with the hedge, "
        f"{inr_short(a['unhedged_var_inr'])} unhedged. Average of the worst cases (ES 95%): "
        f"{inr_short(a['es_inr'])} with the hedge, {inr_short(a['unhedged_es_inr'])} unhedged.",
        f"Locked-in cost of the hedge: {inr_short(a['premium_inr'])}.",
        "Rule used: the smallest hedge (5% steps) whose worst 1-in-20 extra cost fits the limit.",
    ])


def build_messages(question, history, ctx, retriever):
    excerpts = retriever.search(question)
    docs = "\n\n".join(f"[{e['source']}]\n{e['text'][:1500]}" for e in excerpts)
    system = (SYSTEM_RULES + "\nCURRENT RECOMMENDATION\n" + context_text(ctx)
              + "\n\nDOCUMENT EXCERPTS\n" + (docs or "(none found)"))
    return [{"role": "system", "content": system}] + history + [{"role": "user", "content": question}], excerpts


# ---------- Grounding check: every number in the answer must come from somewhere we supplied ----------

NUMBER = re.compile(r"\d[\d,]*\.?\d*")


def _nums(text):
    out = set()
    for n in NUMBER.findall(text):
        try:
            out.add(float(n.replace(",", "").rstrip(".")))
        except ValueError:
            pass
    return out


def unverified_numbers(answer, sources):
    """Numbers in the answer that appear in none of the source texts. Allows rounding to 1 decimal place
    or within 1%, and small whole numbers (months, counts)."""
    known = set().union(*(_nums(s) for s in sources)) if sources else set()
    known_1dp = {round(k, 1) for k in known}
    bad = []
    for x in _nums(answer):
        if x in known or round(x, 1) in known_1dp or (x.is_integer() and x <= 12):
            continue
        if not any(abs(x - k) <= 0.01 * max(abs(k), 1) for k in known):
            bad.append(x)
    return sorted(bad)


# ---------- The conversation ----------

def ask(question, history, ctx, retriever, tools=None, run_tool=None, transport=None):
    """Answer one question. Returns {answer, sources, unverified, tool_calls}.
    `tools`/`run_tool` are added on Day 6; `transport` lets tests replace the HTTP call."""
    call = transport or _http
    messages, excerpts = build_messages(question, history, ctx, retriever)
    grounding = [messages[0]["content"], question]
    calls_made = []
    for _ in range(CHAT_MAX_TOOL_ROUNDS + 1):
        body = {"model": CHAT_MODEL, "messages": messages, "temperature": 0.2}
        if tools:
            body["tools"] = tools
        try:
            reply = call("POST", "/chat/completions", body, CHAT_TIMEOUT_S)["choices"][0]["message"]
        except urllib.error.HTTPError as e:
            msg = ("The free tier's rate limit was reached; wait a minute and try again." if e.code == 429
                   else f"The chat service returned an error ({e.code}).")
            return {"answer": msg, "sources": [], "unverified": [], "tool_calls": calls_made}
        except Exception:
            return {"answer": "The chat service could not be reached. The rest of the app still works.",
                    "sources": [], "unverified": [], "tool_calls": calls_made}
        tool_calls = reply.get("tool_calls") or []
        if not tool_calls or run_tool is None:
            answer = (reply.get("content") or "").strip()
            return {"answer": answer, "sources": [e["source"] for e in excerpts],
                    "unverified": unverified_numbers(answer, grounding), "tool_calls": calls_made}
        messages.append({"role": "assistant", "content": reply.get("content") or "", "tool_calls": tool_calls})
        for tc in tool_calls:
            name, args = tc["function"]["name"], tc["function"].get("arguments") or "{}"
            try:
                result = run_tool(name, json.loads(args))
            except Exception as e:                      # bad arguments: tell the model, let it recover
                result = {"error": str(e)}
            text = json.dumps(result, default=str, ensure_ascii=False)
            calls_made.append({"name": name, "arguments": args, "result": result})
            grounding.append(text)
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": text})
    return {"answer": "Stopped after too many model runs; please ask a narrower question.",
            "sources": [], "unverified": [], "tool_calls": calls_made}


if __name__ == "__main__":
    # Terminal test with the default case: INR 10 crore, 6 months, Balanced
    from config import RISK_LEVELS
    from advisor import load_market, score_for_tenor, advise
    online, reason = status()
    print(reason)
    if online:
        m = load_market()
        forward, grid = score_for_tenor(m, 6)
        usd_amt = 1e8 / m["spot"]
        ctx = {"market": m, "invoice_usd": usd_amt, "months": 6, "level": "Balanced", "forward": forward,
               "advice": advise(m, forward, grid, usd_amt, RISK_LEVELS["Balanced"])}
        q = " ".join(sys.argv[1:]) or "Why is the recommendation what it is?"
        r = ask(q, [], ctx, Retriever(load_passages()))
        print("\n" + r["answer"] + "\n\nSources:", "; ".join(r["sources"]))
        if r["unverified"]:
            print("Numbers not found in the supplied context:", r["unverified"])