"""Visual theme for the AI Report Builder.

Grounded in the Hospital Aleman identity:

  - The wordmark is a black geometric sans with a medical cross built into
    the "H". White is the brand's own background, so the interface uses
    white rather than a coloured banner.
  - Deep teal is the clinical accent: it reads as health without falling
    into the generic pale-blue "medical dashboard" look.
  - The gold of the Joint Commission seal appears only next to the
    accreditation mark, never as decoration.

Typography pairs Outfit (geometric, echoing the wordmark) for headings
with Inter (excellent tabular figures) for data and body copy.
"""

from __future__ import annotations

import base64

import streamlit as st


# ======================================================================
# Tokens
# ======================================================================
INK = "#14171A"          # wordmark black
INK_SOFT = "#5B6670"     # secondary text
LINE = "#E4E9E8"         # hairline borders
MIST = "#F4F7F6"         # page / surface tint
PAPER = "#FFFFFF"
TEAL = "#0B6E63"         # primary clinical accent
TEAL_DEEP = "#075048"
TEAL_SOFT = "#E4F0EE"
GOLD = "#B08A3E"         # accreditation seal
OK = "#2E7D5B"
WARN = "#B4791F"
BAD = "#C0392B"


def _render(markup: str) -> None:
    """Send raw HTML/CSS to the page.

    st.html() is the API meant for this: it does not go through Markdown,
    so blank lines, asterisks in CSS comments and "*" selectors cannot be
    mangled into visible text. st.markdown() is only a fallback for older
    Streamlit versions.
    """
    body = _compact(markup)
    if hasattr(st, "html"):
        st.html(body)
    else:
        st.markdown(body, unsafe_allow_html=True)


def _compact(markup: str) -> str:
    """Remove blank lines from an HTML/CSS block.

    Markdown ends a raw-HTML block at the first blank line, so anything
    after it would be printed as literal text instead of being rendered.
    """
    return "\n".join(line for line in markup.splitlines() if line.strip())


def _logo_data_uri() -> str:
    try:
        from app.report_generator.logo_data import LOGO_HA_APAISADO_B64
        return "data:image/png;base64," + LOGO_HA_APAISADO_B64
    except Exception:
        return ""


def inject_css() -> None:
    """Apply the theme. Call once per page, before anything is drawn."""
    _render("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap');
:root {
  --ink: %(ink)s;
  --ink-soft: %(ink_soft)s;
  --line: %(line)s;
  --mist: %(mist)s;
  --paper: %(paper)s;
  --teal: %(teal)s;
  --teal-deep: %(teal_deep)s;
  --teal-soft: %(teal_soft)s;
  --gold: %(gold)s;
  --ok: %(ok)s;
  --warn: %(warn)s;
  --bad: %(bad)s;
  --radius: 10px;
}

/* ---------- base ---------- */
html, body, [class*="css"], .stApp {
  font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif;
  color: var(--ink);
}
.stApp { background: var(--mist); }

.block-container {
  max-width: 1180px;
  padding-top: 3.4rem;
  padding-bottom: 4rem;
}

h1, h2, h3, h4 {
  font-family: 'Outfit', 'Inter', sans-serif;
  color: var(--ink);
  letter-spacing: -0.015em;
}

/* Numbers should line up in tables and cards */
.ha-value, [data-testid="stDataFrame"] { font-variant-numeric: tabular-nums; }

/* ---------- masthead ---------- */
.ha-masthead {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 1.15rem 1.5rem 0.95rem;
  margin-bottom: 1.6rem;
  display: flex;
  align-items: center;
  gap: 1.5rem;
  position: relative;
  overflow: hidden;
}
.ha-masthead::after {          /* accreditation hairline */
  content: "";
  position: absolute;
  left: 0; right: 0; bottom: 0;
  height: 2px;
  background: linear-gradient(90deg, var(--teal) 0 62%%, var(--gold) 62%% 100%%);
}
.ha-masthead img { height: 46px; width: auto; display: block; }
.ha-rule {
  width: 1px; align-self: stretch; background: var(--line);
  margin: 0.15rem 0;
}
.ha-titles h1 {
  font-size: 1.32rem; font-weight: 600; margin: 0; line-height: 1.2;
}
.ha-titles p {
  font-size: 0.86rem; color: var(--ink-soft); margin: 0.18rem 0 0;
}

/* ---------- section headers: the cross from the logo ---------- */
.ha-step {
  display: flex; align-items: center; gap: 0.7rem;
  margin: 2.1rem 0 0.9rem;
}
.ha-cross {
  position: relative; flex: none;
  width: 20px; height: 20px; border-radius: 4px;
  background: var(--teal-soft);
}
.ha-cross::before, .ha-cross::after {
  content: ""; position: absolute; background: var(--teal); border-radius: 1px;
}
.ha-cross::before { left: 9px; top: 4.5px; width: 2px; height: 11px; }
.ha-cross::after  { top: 9px; left: 4.5px; height: 2px; width: 11px; }
.ha-step h3 {
  font-size: 1.06rem; font-weight: 600; margin: 0;
}
.ha-step .ha-n {
  font-size: 0.74rem; font-weight: 600; color: var(--teal);
  letter-spacing: 0.09em; text-transform: uppercase;
}

/* ---------- cards ---------- */
.ha-card {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 0.95rem 1.05rem;
  height: 100%%;
}
.ha-card .ha-label {
  font-size: 0.72rem; font-weight: 600; letter-spacing: 0.07em;
  text-transform: uppercase; color: var(--ink-soft);
}
.ha-card .ha-value {
  font-family: 'Outfit', sans-serif;
  font-size: 1.72rem; font-weight: 600; line-height: 1.15;
  margin-top: 0.28rem; color: var(--ink);
}
.ha-card .ha-sub { font-size: 0.78rem; color: var(--ink-soft); margin-top: 0.1rem; }
.ha-up { color: var(--ok); font-size: 0.82rem; font-weight: 600; }
.ha-down { color: var(--bad); font-size: 0.82rem; font-weight: 600; }

/* Accent strip on top of a card */
.ha-card.ha-accent { border-top: 3px solid var(--teal); }

/* ---------- campaign chips ---------- */
.ha-chip {
  display: inline-block; padding: 3px 10px; border-radius: 999px;
  font-size: 0.74rem; font-weight: 600; margin: 2px 3px 2px 0;
  background: var(--teal-soft); color: var(--teal-deep);
  border: 1px solid rgba(11,110,99,0.16);
}
.ha-chip.ha-muted { background: #F0F2F4; color: var(--ink-soft); border-color: var(--line); }

/* ---------- streamlit widgets ---------- */
section[data-testid="stSidebar"] {
  background: var(--paper);
  border-right: 1px solid var(--line);
}
section[data-testid="stSidebar"] .block-container { padding-top: 1.2rem; }

.stButton > button, .stDownloadButton > button {
  font-family: 'Inter', sans-serif;
  font-weight: 600; font-size: 0.88rem;
  border-radius: 8px; border: 1px solid var(--line);
  background: var(--paper); color: var(--ink);
  transition: border-color .15s ease, background .15s ease;
}
.stButton > button:hover, .stDownloadButton > button:hover {
  border-color: var(--teal); color: var(--teal-deep); background: var(--teal-soft);
}
.stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] {
  background: var(--teal); border-color: var(--teal); color: #fff;
}
.stButton > button[kind="primary"]:hover, .stDownloadButton > button[kind="primary"]:hover {
  background: var(--teal-deep); border-color: var(--teal-deep); color: #fff;
}
.stButton > button:focus-visible, .stDownloadButton > button:focus-visible {
  outline: 2px solid var(--teal); outline-offset: 2px;
}

[data-testid="stFileUploader"] section {
  background: var(--paper);
  border: 1px dashed #C9D4D2;
  border-radius: var(--radius);
}
[data-testid="stFileUploader"] section:hover { border-color: var(--teal); }

[data-testid="stExpander"] {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: var(--radius);
}
[data-testid="stExpander"] summary { font-weight: 600; font-size: 0.9rem; }

div[data-baseweb="select"] > div {
  border-radius: 8px; border-color: var(--line);
}

[data-testid="stDataFrame"] { border: 1px solid var(--line); border-radius: var(--radius); }

/* Alerts: quieter, aligned to the palette */
div[data-testid="stAlert"] {
  border-radius: var(--radius);
  border: 1px solid var(--line);
  font-size: 0.87rem;
}

hr { border-color: var(--line); }

/* Respect reduced-motion preferences */
@media (prefers-reduced-motion: reduce) {
  * { transition: none !important; animation: none !important; }
}

/* Mobile */
@media (max-width: 640px) {
  .ha-masthead { flex-direction: column; align-items: flex-start; gap: 0.8rem; }
  .ha-rule { display: none; }
  .ha-card .ha-value { font-size: 1.45rem; }
}
/* ---------- force the light appearance ---------- */
/* The hospital identity is black on white. If the browser or the Streamlit
   deployment is in dark mode, the widgets would render dark while this
   stylesheet assumes light surfaces, leaving black inputs and unreadable
   labels. These rules pin the surfaces and text colours. */
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
  background: var(--mist) !important; color: var(--ink) !important;
}
[data-testid="stHeader"] { background: transparent !important; }
[data-testid="stAppViewContainer"] * { color: var(--ink); }
.ha-card .ha-label, .ha-card .ha-sub, .ha-titles p, .ha-step .ha-n,
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] * {
  color: var(--ink-soft) !important;
}
.ha-step .ha-n { color: var(--teal) !important; }
.ha-up { color: var(--ok) !important; }
.ha-down { color: var(--bad) !important; }
/* Sidebar */
section[data-testid="stSidebar"], section[data-testid="stSidebar"] > div {
  background: var(--paper) !important;
}
section[data-testid="stSidebar"] * { color: var(--ink) !important; }
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"],
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] * {
  color: var(--ink-soft) !important;
}
/* Text inputs, selects and text areas */
input, textarea, select,
[data-baseweb="input"], [data-baseweb="base-input"],
[data-baseweb="input"] > div, [data-baseweb="select"] > div,
[data-baseweb="popover"] div[role="listbox"] {
  background: var(--paper) !important;
  color: var(--ink) !important;
  border-color: var(--line) !important;
  -webkit-text-fill-color: var(--ink) !important;
}
input::placeholder, textarea::placeholder { color: #9AA5AD !important; }
/* Widget labels */
[data-testid="stWidgetLabel"], [data-testid="stWidgetLabel"] * , label {
  color: var(--ink) !important;
}
/* File uploader */
[data-testid="stFileUploader"] section,
[data-testid="stFileUploaderDropzone"],
[data-testid="stFileUploaderDropzoneInstructions"] {
  background: var(--paper) !important;
}
[data-testid="stFileUploaderDropzoneInstructions"],
[data-testid="stFileUploaderDropzoneInstructions"] * { color: var(--ink-soft) !important; }
[data-testid="stFileUploader"] button {
  background: var(--paper) !important; color: var(--ink) !important;
  border: 1px solid var(--line) !important;
}
/* Surfaces that must stay white */
[data-testid="stExpander"], [data-testid="stExpander"] details,
[data-testid="stDataFrame"], [data-testid="stTable"], [data-testid="stPopoverBody"] {
  background: var(--paper) !important;
}
/* Buttons keep their own palette */
.stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"],
.stButton > button[kind="primary"] *, .stDownloadButton > button[kind="primary"] * {
  color: #fff !important;
}
</style>
        """
        % {
            "ink": INK, "ink_soft": INK_SOFT, "line": LINE, "mist": MIST,
            "paper": PAPER, "teal": TEAL, "teal_deep": TEAL_DEEP,
            "teal_soft": TEAL_SOFT, "gold": GOLD, "ok": OK,
            "warn": WARN, "bad": BAD,
        })


def masthead(title: str, subtitle: str) -> None:
    """Header band with the hospital logo and the page title."""
    uri = _logo_data_uri()
    logo = f'<img src="{uri}" alt="Hospital Aleman">' if uri else ""
    _render(f"""
<div class="ha-masthead">
  {logo}
  <div class="ha-rule"></div>
  <div class="ha-titles">
    <h1>{title}</h1>
    <p>{subtitle}</p>
  </div>
</div>
    """)


def step(number: int, title: str) -> None:
    """Section heading marked with the cross from the logo."""
    _render(f"""
<div class="ha-step">
  <div class="ha-cross"></div>
  <div>
    <div class="ha-n">Paso {number}</div>
    <h3>{title}</h3>
  </div>
</div>
    """)


def card(label: str, value: str, sub: str = "", variation: str = "",
         accent: bool = False) -> str:
    """Return the HTML for a metric card."""
    extra = ""
    if variation and variation.strip() not in ("", "-"):
        cls = "ha-up" if "\u25b2" in variation else "ha-down"
        extra = f'<div class="{cls}">{variation}</div>'
    elif sub:
        extra = f'<div class="ha-sub">{sub}</div>'
    cls = "ha-card ha-accent" if accent else "ha-card"
    return (f'<div class="{cls}"><div class="ha-label">{label}</div>'
            f'<div class="ha-value">{value}</div>{extra}</div>')


def chip(text: str, muted: bool = False) -> str:
    """Return the HTML for a small labelled chip."""
    return f'<span class="ha-chip{" ha-muted" if muted else ""}">{text}</span>'


def show_card(label: str, value: str, sub: str = "", variation: str = "",
              accent: bool = False) -> None:
    """Draw a metric card."""
    _render(card(label, value, sub=sub, variation=variation, accent=accent))


def show_chips(items, muted_when=None) -> None:
    """Draw a row of chips. *muted_when* receives each item and returns bool."""
    html = "".join(chip(t, muted=bool(muted_when(t)) if muted_when else False)
                   for t in items)
    _render(f"<div>{html}</div>")
