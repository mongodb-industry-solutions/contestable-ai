"""
IoMT Contestable AI — Post-Event Trend Review
Streamlit entry point. Run with: streamlit run app.py
"""
from __future__ import annotations
import uuid

import streamlit as st

# data.config loads .env and exposes all env vars; importing it here ensures
# the environment is initialised before any other module reads it.
import data.config  # noqa: F401

st.set_page_config(
    page_title="IoMT Contestable AI Review",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ------------------------------------------------------------------ global CSS
st.markdown(
    """
    <style>
    /* Base palette */
    :root {
        --primary:   #1B4F72;
        --secondary: #2E86AB;
        --bg:        #F0F4F8;
        --card:      #FFFFFF;
        --text:      #2C3E50;
        --muted:     #7F8C8D;
        --success:   #27AE60;
        --warning:   #F39C12;
        --danger:    #E74C3C;
        --border:    #D5D8DC;
    }

    /* App background */
    .stApp { background-color: #F0F4F8; }
    section[data-testid="stSidebar"] { background-color: #EBF5FB; border-right: 1px solid #D6EAF8; }

    /* Tabs */
    div[data-testid="stTabs"] button[data-baseweb="tab"] {
        font-weight: 600;
        font-size: 0.85rem;
        color: #555;
        padding: 8px 18px;
    }
    div[data-testid="stTabs"] button[aria-selected="true"] {
        color: #1B4F72 !important;
        border-bottom: 3px solid #1B4F72 !important;
    }

    /* Buttons */
    div.stButton > button[kind="primary"] {
        background-color: #1B4F72;
        color: white;
        border: none;
        border-radius: 6px;
        font-weight: 600;
    }
    div.stButton > button[kind="primary"]:hover { background-color: #154360; }

    /* Metric */
    div[data-testid="stMetric"] { background: white; border-radius: 8px; padding: 12px; }

    /* Progress bar: colour only the fill, not the track */
    .stProgress > div > div[role="progressbar"] { background-color: #EBF5FB; }
    .stProgress > div > div[role="progressbar"] > div { background-color: #2E86AB; }

    /* Expander */
    div[data-testid="stExpander"] { border: 1px solid #D5D8DC; border-radius: 8px; }

    /* Push content below Streamlit's fixed header bar (~60px) */
    div.block-container { padding-top: 4.5rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------ session init
def _init_session() -> None:
    defaults = {
        "session_id": uuid.uuid4().hex,
        "phase1_complete": False,
        "phase2_complete": False,
        "phase3_complete": False,
        "phase4_complete": False,
        "patient_context": None,
        "arguments": [],
        "arg_scores": {},
        "option_confidence": {},
        "option_confidence_initial": {},
        "care_plan": None,
        "pending_edits": {},
        "modifying_arg": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_session()

# ------------------------------------------------------------------ sidebar
from ui.sidebar import render_sidebar
render_sidebar()

# ------------------------------------------------------------------ progress indicator
phases = [
    ("1", "Patient Overview", "phase1_complete"),
    ("2", "Argumentation",    "phase2_complete"),
    ("3", "Contestation",     "phase3_complete"),
    ("4", "Care Plan",        "phase4_complete"),
]

progress_html = '<div style="display:flex;align-items:center;gap:0;margin-bottom:18px;">'
for i, (num, label, key) in enumerate(phases):
    done = st.session_state.get(key, False)
    active = (
        (i == 0 and not done) or
        (i > 0 and st.session_state.get(phases[i-1][2]) and not done)
    )
    dot_bg = "#1B4F72" if done else ("#2E86AB" if active else "#BDC3C7")
    text_col = "#1B4F72" if done or active else "#AAA"
    tick = "✓" if done else num
    progress_html += f"""
    <div style="display:flex;align-items:center;">
        <div style="width:28px;height:28px;border-radius:50%;background:{dot_bg};
                     color:white;font-weight:700;font-size:0.78rem;
                     display:flex;align-items:center;justify-content:center;">
            {tick}
        </div>
        <span style="font-size:0.8rem;font-weight:600;color:{text_col};margin:0 6px;">
            {label}
        </span>
    </div>
    """
    if i < len(phases) - 1:
        connector_col = "#1B4F72" if done else "#D5D8DC"
        progress_html += (
            f'<div style="flex:1;height:2px;background:{connector_col};'
            f'min-width:20px;max-width:60px;"></div>'
        )

progress_html += "</div>"
st.markdown(progress_html, unsafe_allow_html=True)

# ------------------------------------------------------------------ main tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Phase 1: Patient Overview",
    "🧠 Phase 2: Argumentation",
    "✋ Phase 3: Contestation",
    "📋 Phase 4: Care Plan",
])

from ui.tab1_overview    import render_tab1
from ui.tab2_argumentation import render_tab2
from ui.tab3_contestation import render_tab3
from ui.tab4_careplan    import render_tab4

with tab1:
    render_tab1()
with tab2:
    render_tab2()
with tab3:
    render_tab3()
with tab4:
    render_tab4()
