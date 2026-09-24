# tests/test_chatbot.py
# Tests for the chatbot's plumbing, using a fake API (no internet or key needed).
# Run from the fx-hedging root:  python -m unittest discover tests -v
import json
import os
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from config import RISK_LEVELS
from advisor import load_market, score_for_tenor, advise
import chatbot
from chatbot import Retriever, load_passages, context_text, unverified_numbers, ask, status


def make_ctx():
    m = load_market()
    forward, grid = score_for_tenor(m, 6)
    usd = 1e8 / m["spot"]
    return {"market": m, "invoice_usd": usd, "months": 6, "level": "Balanced", "forward": forward,
            "advice": advise(m, forward, grid, usd, RISK_LEVELS["Balanced"])}


def fake_api(replies):
    """A stand-in for the HTTP call: returns the scripted replies in order and records requests."""
    sent = []

    def transport(method, path, body, timeout):
        sent.append(body)
        return {"choices": [{"message": replies.pop(0)}]}
    return transport, sent


class TestChatbot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx = make_ctx()
        cls.retriever = Retriever(load_passages())

    def test_offline_without_key(self):
        with mock.patch.dict(os.environ, {"CHAT_API_KEY": ""}):
            online, reason = status()
        self.assertFalse(online)
        self.assertIn("No API key", reason)

    def test_offline_when_unreachable(self):
        def down(*a):
            raise urllib.error.URLError("no network")
        with mock.patch.dict(os.environ, {"CHAT_API_KEY": "test"}):
            self.assertFalse(status(transport=down)[0])
            self.assertTrue(status(transport=lambda *a: {"data": []})[0])

    def test_retrieval_finds_the_right_passage(self):
        self.assertEqual(self.retriever.search("what is expected shortfall")[0]["source"], "Glossary: ES 95%")
        sources = [r["source"] for r in self.retriever.search("how was the walk-forward backtest done")]
        self.assertTrue(any("Backtest" in s for s in sources))

    def test_context_has_the_live_numbers(self):
        text = context_text(self.ctx)
        self.assertIn("hedge 50%", text)
        self.assertIn("₹39.8 lakh", text)
        self.assertIn("Calm", text)

    def test_grounding_check(self):
        sources = ["VaR is ₹39.8 lakh with the hedge and ₹71.7 lakh unhedged; forward ₹96.62"]
        self.assertEqual(unverified_numbers("It is ₹39.8 lakh, versus ₹71.7 lakh.", sources), [])
        self.assertEqual(unverified_numbers("It could reach ₹55.5 lakh.", sources), [55.5])

    def test_plain_answer_is_grounded(self):
        transport, sent = fake_api([{"content": "Hedge 50%: the worst case falls to ₹39.8 lakh from ₹71.7 lakh."}])
        r = ask("Why 50%?", [], self.ctx, self.retriever, transport=transport)
        self.assertEqual(r["unverified"], [])
        self.assertIn("CURRENT RECOMMENDATION", sent[0]["messages"][0]["content"])
        self.assertTrue(r["sources"])

    def test_invented_number_is_flagged(self):
        transport, _ = fake_api([{"content": "Unhedged you could lose ₹3.4 crore."}])
        r = ask("Worst case?", [], self.ctx, self.retriever, transport=transport)
        self.assertIn(3.4, r["unverified"])

    def test_rate_limit_message(self):
        def limited(*a):
            raise urllib.error.HTTPError("u", 429, "Too Many Requests", {}, None)
        r = ask("hi", [], self.ctx, self.retriever, transport=limited)
        self.assertIn("rate limit", r["answer"])

    def test_tool_loop(self):
        replies = [
            {"content": "", "tool_calls": [{"id": "c1", "type": "function",
                                            "function": {"name": "echo", "arguments": json.dumps({"x": 123.45})}}]},
            {"content": "The tool said 123.45."},
        ]
        transport, sent = fake_api(replies)
        r = ask("run it", [], self.ctx, self.retriever, tools=[{"type": "function"}],
                run_tool=lambda name, args: {"value": args["x"]}, transport=transport)
        self.assertEqual(r["answer"], "The tool said 123.45.")
        self.assertEqual(r["unverified"], [])                           # 123.45 came from the tool
        self.assertEqual(sent[1]["messages"][-1]["role"], "tool")


if __name__ == "__main__":
    unittest.main()