# tests/test_app.py
# End-to-end test of the Streamlit app, run headless (no browser). Run from the fx-hedging root:
#   python -m unittest discover tests -v
# Skipped automatically if Streamlit isn't installed.
import unittest
from pathlib import Path

try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    AppTest = None

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def recommendation(at):
    """The 'Recommendation: hedge X%' header text."""
    return next(h.value for h in at.header if h.value.startswith("Recommendation"))


@unittest.skipIf(AppTest is None, "Streamlit not installed")
class TestApp(unittest.TestCase):
    def setUp(self):
        self.at = AppTest.from_file(APP, default_timeout=60).run()

    def test_default_inputs(self):
        # INR 10 crore, 6 months, Balanced, Calm market (2026-09-18 snapshot)
        self.assertEqual(len(self.at.exception), 0)
        self.assertEqual(recommendation(self.at), "Recommendation: hedge 50%")

    def test_risk_levels_at_both_ends(self):
        self.at.select_slider(key="risk_level").set_value("Very cautious").run()
        self.assertEqual(recommendation(self.at), "Recommendation: hedge 100%")
        self.at.select_slider(key="risk_level").set_value("Very relaxed").run()
        self.assertEqual(recommendation(self.at), "Recommendation: hedge 0%")
        self.assertEqual(len(self.at.exception), 0)

    def test_edge_case_usd_one_month_tiny_limit(self):
        self.at.radio(key="unit").set_value("USD").run()
        self.at.slider(key="months").set_value(1).run()
        self.at.number_input(key="own_limit").set_value(0.5).run()
        self.assertEqual(len(self.at.exception), 0)
        self.assertEqual(recommendation(self.at), "Recommendation: hedge 100%")
        self.assertTrue(any("Even a full hedge" in w.value for w in self.at.warning))

    def test_every_payment_length_runs(self):
        for months in (1, 3, 9, 12):
            self.at.slider(key="months").set_value(months).run()
            self.assertEqual(len(self.at.exception), 0, f"{months} months")


if __name__ == "__main__":
    unittest.main()