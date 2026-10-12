# tests/test_theme.py
# The look is set by Streamlit's native theme in .streamlit/config.toml (no injected CSS).
# Run from the fx-hedging root:  python -m unittest discover tests -v
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KEYS = {"primaryColor", "backgroundColor", "secondaryBackgroundColor", "textColor", "chartCategoricalColors"}


class TestTheme(unittest.TestCase):
    def test_light_and_dark_are_both_defined(self):
        theme = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text())["theme"]
        for mode in ("light", "dark"):
            self.assertLessEqual(KEYS, set(theme[mode]), mode)

    def test_dark_is_black_and_blue(self):
        theme = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text())["theme"]
        self.assertEqual(theme["dark"]["backgroundColor"], "#050b1a")

    def test_no_injected_css(self):
        for f in [ROOT / "app.py", *(ROOT / "views").glob("*.py")]:
            self.assertNotIn("unsafe_allow_html", f.read_text(), f.name)


if __name__ == "__main__":
    unittest.main()
