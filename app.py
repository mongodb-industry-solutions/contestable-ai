"""
IoMT Contestable AI
Streamlit entry point. Run with: streamlit run app.py
"""
from __future__ import annotations
import uuid

import streamlit as st

import data.config  # noqa: F401 — loads .env before any other module

st.set_page_config(
    page_title="Contestable AI",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ------------------------------------------------------------------ global CSS
st.markdown(
    """
    <style>
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

    .stApp { background-color: #F0F4F8; }
    section[data-testid="stSidebar"] { background-color: #EBF5FB; border-right: 1px solid #D6EAF8; }

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

    div.stButton > button[kind="primary"] {
        background-color: #1B4F72;
        color: white;
        border: none;
        border-radius: 6px;
        font-weight: 600;
    }
    div.stButton > button[kind="primary"]:hover { background-color: #154360; }

    div[data-testid="stMetric"] { background: white; border-radius: 8px; padding: 12px; }

    .stProgress > div > div[role="progressbar"] { background-color: #EBF5FB; }
    .stProgress > div > div[role="progressbar"] > div { background-color: #2E86AB; }

    div[data-testid="stExpander"] { border: 1px solid #D5D8DC; border-radius: 8px; }

    div.block-container { padding-top: 4.5rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ------------------------------------------------------------------ session init
def _init_session() -> None:
    defaults = {
        "session_id": uuid.uuid4().hex,
        "domain": None,
        "phase1_complete": False,
        "phase2_complete": False,
        "phase3_complete": False,
        "phase4_complete": False,
        "patient_context": None,
        "site_context": None,
        "arguments": [],
        "arg_scores": {},
        "option_confidence": {},
        "option_confidence_initial": {},
        "care_plan": None,
        "onboarding_record": None,
        "pending_edits": {},
        "modifying_arg": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_session()


# ------------------------------------------------------------------ domain switcher
def _render_domain_selector() -> None:
    st.markdown(
        """
        <div style="text-align:center;padding:32px 0 16px;">
            <h1 style="color:#1B4F72;font-size:2rem;margin-bottom:8px;">Contestable AI</h1>
            <p style="color:#555;font-size:1rem;max-width:520px;margin:0 auto 32px;">
                Human experts challenge, override, and audit AI recommendations.
                Every decision is transparent and attributable.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_left, col_mid, col_right = st.columns([1, 3, 1])
    with col_mid:
        card_left, card_right = st.columns(2, gap="large")

        with card_left:
            st.markdown(
                """
                <div style="background:white;border:2px solid #D6EAF8;border-radius:12px;
                             padding:24px 20px;text-align:center;min-height:200px;">
                    <div style="font-size:2.8rem;margin-bottom:12px;">🏥</div>
                    <div style="font-weight:700;font-size:1.1rem;color:#1B4F72;margin-bottom:8px;">
                        Healthcare
                    </div>
                    <div style="font-size:0.82rem;color:#555;line-height:1.5;margin-bottom:16px;">
                        Four AI specialist agents analyse 21 days of IoMT wearable data and debate
                        three care plan options. A Family Physician reviews and contests the recommendation.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Select Healthcare", key="sel_healthcare", type="primary", use_container_width=True):
                st.session_state.domain = "healthcare"
                st.rerun()

        with card_right:
            st.markdown(
                """
                <div style="background:white;border:2px solid #D6EAF8;border-radius:12px;
                             padding:24px 20px;text-align:center;min-height:200px;">
                    <div style="font-size:2.8rem;margin-bottom:12px;">🏭</div>
                    <div style="font-weight:700;font-size:1.1rem;color:#1B4F72;margin-bottom:8px;">
                        Manufacturing
                    </div>
                    <div style="font-size:0.82rem;color:#555;line-height:1.5;margin-bottom:16px;">
                        Two AI agents analyse a synthetic site's vendor-specific HVAC point names and propose
                        Brick ontology mappings. A domain expert reviews and corrects the proposal.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Select Manufacturing", key="sel_manufacturing", type="primary", use_container_width=True):
                st.session_state.domain = "manufacturing"
                st.rerun()


# ------------------------------------------------------------------ show domain selector if no domain chosen
if not st.session_state.domain:
    _render_domain_selector()
    st.stop()


# ------------------------------------------------------------------ sidebar
from ui.sidebar import render_sidebar
render_sidebar()

domain = st.session_state.domain
from data.models import DOMAIN_CONFIGS
cfg = DOMAIN_CONFIGS[domain]

# ------------------------------------------------------------------ progress indicator
phases = list(zip(
    ["1", "2", "3", "4"],
    cfg["phase_labels"],
    ["phase1_complete", "phase2_complete", "phase3_complete", "phase4_complete"],
))

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
icons = cfg["phase_icons"]
labels = cfg["phase_labels"]
tab1, tab2, tab3, tab4 = st.tabs([
    f"{icons[0]} Phase 1: {labels[0]}",
    f"{icons[1]} Phase 2: {labels[1]}",
    f"{icons[2]} Phase 3: {labels[2]}",
    f"{icons[3]} Phase 4: {labels[3]}",
])

from ui.tab1_overview     import render_tab1
from ui.tab2_argumentation import render_tab2
from ui.tab3_contestation  import render_tab3
from ui.tab4_careplan      import render_tab4

with tab1:
    render_tab1()
with tab2:
    render_tab2()
with tab3:
    render_tab3()
with tab4:
    render_tab4()
