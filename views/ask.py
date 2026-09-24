# views/ask.py
# The Ask tab: an optional chatbot. With internet and an API key it answers questions about the
# recommendation; otherwise it explains why chat is off, and the rest of the app is unaffected.
import streamlit as st

import chatbot
from chat_tools import TOOLS, run_tool


@st.cache_data(ttl=300, show_spinner=False)
def chat_status():
    """(online, reason), rechecked at most every 5 minutes."""
    return chatbot.status()


@st.cache_resource
def _retriever():
    return chatbot.Retriever(chatbot.load_passages())


def sidebar_status():
    online, _ = chat_status()
    st.caption("Chat assistant: **on**" if online else "Chat assistant: off (working offline)")


def render(ctx):
    online, reason = chat_status()
    if not online:
        st.info(f"Chat is off. {reason} The hedge recommendation and all other tabs work normally without it.")
        if st.button("Check again", key="chat_recheck"):
            chat_status.clear()
            st.rerun()
        return

    st.caption(f"{reason} Your questions and the numbers on screen are sent to the chat provider. "
               "Answers are model estimates, not financial advice.")
    history = st.session_state.setdefault("chat_history", [])
    for msg in history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    question = st.chat_input("Ask about your recommendation, e.g. 'What if I pay in 9 months?'", key="chat_q")
    if not question:
        return
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            r = chatbot.ask(question, history[-6:], ctx, _retriever(), tools=TOOLS,
                            run_tool=lambda name, args: run_tool(name, args, ctx["market"]))
        st.markdown(r["answer"])
        for call in r["tool_calls"]:
            with st.expander(f"Ran the hedge model: {call['name']}"):
                st.json(call["result"])
        if r["sources"]:
            st.caption("Sources: " + "; ".join(r["sources"]))
        if r["unverified"]:
            st.warning("Check these numbers; they don't appear in the app's data: "
                       + ", ".join(f"{x:g}" for x in r["unverified"]))
    history += [{"role": "user", "content": question}, {"role": "assistant", "content": r["answer"]}]