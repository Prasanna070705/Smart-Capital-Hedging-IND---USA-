# views/theme.py
# v1.1 Day 7b: dark mode by default, with a Dark/Light switch at the top of the sidebar.
import streamlit as st

from config import DEFAULT_DARK_MODE
from styling import page_css


def apply():
    dark = st.sidebar.toggle("Dark mode", value=DEFAULT_DARK_MODE, key="dark_mode")
    st.markdown(page_css("dark" if dark else "light"), unsafe_allow_html=True)
