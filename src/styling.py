# src/styling.py
# v1.1 Day 7b: dark (black and deep blue) and light looks for the app. Plain CSS builders, no Streamlit,
# so they can be tested; views/theme.py puts the chosen one on the page.
DARK_GRADIENT = "linear-gradient(135deg, #000000 0%, #050b1a 40%, #0a1a33 75%, #02060f 100%)"
LIGHT_GRADIENT = "linear-gradient(135deg, #ffffff 0%, #f3f6fb 50%, #e6edf8 100%)"


def page_css(mode="dark"):
    """CSS for 'dark' (the default, matching .streamlit/config.toml) or 'light'."""
    if mode == "dark":
        return f"""
<style>
.stApp {{ background: {DARK_GRADIENT}; background-attachment: fixed; }}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stSidebar"] {{ background: rgba(5, 11, 26, 0.92); }}
[data-testid="stVerticalBlockBorderWrapper"], [data-testid="stExpander"] details {{
    background: rgba(15, 28, 51, 0.55); border-radius: 12px;
}}
</style>
"""
    if mode == "light":
        # Streamlit itself stays in its dark theme; this repaints the page light. Charts and tables draw
        # themselves in the dark theme, so they are colour-inverted (hue kept) to look light as well.
        return f"""
<style>
.stApp {{ background: {LIGHT_GRADIENT}; background-attachment: fixed; }}
.stApp, .stApp p, .stApp li, .stApp label, .stApp span, .stApp h1, .stApp h2, .stApp h3,
[data-testid="stMetricValue"], [data-testid="stMetricLabel"], [data-testid="stCaptionContainer"] {{ color: #0b1a33 !important; }}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stSidebar"] {{ background: #eef3fb; }}
[data-baseweb="input"] > div, [data-baseweb="select"] > div, [data-baseweb="base-input"], textarea, input {{
    background: #ffffff !important; color: #0b1a33 !important;
}}
[data-testid="stVerticalBlockBorderWrapper"], [data-testid="stExpander"] details {{
    background: rgba(255, 255, 255, 0.75); border-radius: 12px;
}}
[data-testid="stDataFrame"], [data-testid="stVegaLiteChart"], [data-testid="stArrowVegaLiteChart"] {{
    filter: invert(1) hue-rotate(180deg);
}}
</style>
"""
    raise ValueError("mode must be 'dark' or 'light'")
