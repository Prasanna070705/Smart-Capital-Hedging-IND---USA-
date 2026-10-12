# views/chrome.py
# Page furniture that Streamlit has no widget for, as one small inline component:
#   1. a Light/Dark switch (Streamlit can only switch theme from its own Settings menu),
#   2. a slow ambient background animation,
#   3. clicking a ? next to a glossary term opens the Glossary tab at that term.
import streamlit as st

HTML = """
<button id="fx-theme" type="button" aria-label="Switch between light and dark mode"></button>
"""

# isolate_styles=False below makes this CSS apply to the whole page, which the background needs.
CSS = """
#fx-theme {
    font: inherit; font-size: 0.875rem; cursor: pointer; padding: 0.3rem 0.8rem;
    color: var(--st-text-color); background: var(--st-background-color);
    border: 1px solid var(--st-border-color); border-radius: var(--st-base-radius);
}
#fx-theme:hover, #fx-theme:focus-visible { border-color: var(--st-primary-color); color: var(--st-primary-color); }

/* Ambient background: two blurred colour fields drifting slowly behind the content */
[data-testid="stAppViewContainer"], [data-testid="stMain"], [data-testid="stHeader"] { background: transparent; }
.stApp::before, .stApp::after {
    content: ""; position: fixed; z-index: 0; pointer-events: none;
    width: 60vmax; height: 60vmax; border-radius: 50%; filter: blur(90px); opacity: 0.22;
    animation: fx-drift 40s ease-in-out infinite alternate;
}
.stApp::before { top: -25vmax; left: 15vw; background: radial-gradient(circle, #1f6feb 0%, transparent 65%); }
.stApp::after {
    bottom: -30vmax; right: -10vw; background: radial-gradient(circle, #12b5a5 0%, transparent 65%);
    animation-duration: 55s; animation-direction: alternate-reverse;
}
@keyframes fx-drift {
    from { transform: translate3d(0, 0, 0) scale(1); }
    to   { transform: translate3d(10vw, 8vh, 0) scale(1.2); }
}
@media (prefers-reduced-motion: reduce) { .stApp::before, .stApp::after { animation: none; } }

[id^="glossary-"] { scroll-margin-top: 4rem; }
"""

JS = """
export default function ({ parentElement }) {
  // 1. Light/Dark switch. Streamlit keeps the visitor's choice under this localStorage key and reads it
  //    only when the page loads, so the switch saves the choice and reloads.
  const KEY = `stActiveTheme-${window.location.pathname}-v2`
  const isDark = () => {
    let saved = null
    try { saved = JSON.parse(window.localStorage.getItem(KEY)) } catch (e) {}
    if (saved === "Dark") return true
    if (saved === "Light") return false
    return window.matchMedia("(prefers-color-scheme: dark)").matches
  }
  const btn = parentElement.querySelector("#fx-theme")
  if (btn) {
    btn.textContent = isDark() ? "\u2600 Light mode" : "\u263E Dark mode"
    btn.onclick = () => {
      window.localStorage.setItem(KEY, JSON.stringify(isDark() ? "Light" : "Dark"))
      window.location.reload()
    }
  }

  // 3. Glossary links. The open tooltip starts with the term in bold (glossary.tip); read it, switch to
  //    the Glossary tab and scroll to that term's heading. Help icons without a bold term are left alone.
  if (window.__fxGlossaryLinks) return
  window.__fxGlossaryLinks = true
  document.addEventListener("click", (event) => {
    const icon = event.target.closest && event.target.closest(".stTooltipIcon")
    if (!icon) return
    const described = icon.querySelector("[aria-describedby]")
    const tooltip = (described && document.getElementById(described.getAttribute("aria-describedby")))
      || document.querySelector('[data-testid="stTooltipContent"]')
    const bold = tooltip && tooltip.querySelector("strong")
    if (!bold) return
    const term = bold.textContent.replace(/:$/, "")
    const id = "glossary-" + term.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim().split(" ").join("-")
    const tab = [...document.querySelectorAll('[role="tab"]')].find((t) => t.textContent.includes("Glossary"))
    if (!tab) return
    tab.click()
    let tries = 0
    const go = () => {
      const heading = document.getElementById(id)
      if (heading && heading.offsetParent) heading.scrollIntoView({ behavior: "smooth", block: "start" })
      else if (tries++ < 20) setTimeout(go, 100)
    }
    go()
  }, true)
}
"""

def render():
    # Registered on every run, not once at import: a fresh Streamlit runtime (each AppTest in tests/test_app.py)
    # starts with an empty component registry while this module stays imported
    st.components.v2.component("fx_chrome", html=HTML, css=CSS, js=JS, isolate_styles=False)(key="fx_chrome")
