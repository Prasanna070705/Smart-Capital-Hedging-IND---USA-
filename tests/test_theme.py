# tests/test_theme.py
# Tests for the v1.1 Day 7b look: dark (black and deep blue) by default, with a light option.
# Run from the fx-hedging root:  python -m unittest discover tests -v
import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from config import DEFAULT_DARK_MODE
from styling import page_css, DARK_GRADIENT, LIGHT_GRADIENT


class TestTheme(unittest.TestCase):
    def test_dark_is_the_default(self):
        cfg = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text())
        self.assertEqual(cfg["theme"]["base"], "dark")
        self.assertTrue(DEFAULT_DARK_MODE)

    def test_dark_is_black_and_blue(self):
        css = page_css("dark")
        self.assertIn(DARK_GRADIENT, css)
        self.assertIn("#000000", DARK_GRADIENT)

    def test_light_mode_repaints_charts_and_tables(self):
        css = page_css("light")
        self.assertIn(LIGHT_GRADIENT, css)
        self.assertIn("invert(1)", css)

    def test_no_animation_and_bad_mode_rejected(self):
        self.assertNotIn("iframe", page_css("dark") + page_css("light"))
        with self.assertRaises(ValueError):
            page_css("sepia")


if __name__ == "__main__":
    unittest.main()
