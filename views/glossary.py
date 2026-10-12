# views/glossary.py
# The Glossary tab: the full explanation of every term. Clicking a ? next to a term anywhere in the app
# opens this tab at that term (see views/chrome.py).
import streamlit as st

from glossary import GLOSSARY, DETAILS, slug


def render(ctx):
    st.caption("Every term the app uses, in plain language. Click the ? next to a term anywhere in the app to "
               "jump to it here.")
    for term in GLOSSARY:
        st.subheader(term, anchor=slug(term))
        st.markdown(DETAILS[term])
