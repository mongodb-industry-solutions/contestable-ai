from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from agents.specialist_agents import run_single_specialist
from argumentation.qbaf import run_scoring
from data import db
from data.models import AGENT_ROLES, CARE_OPTIONS

_AGENT_ICONS = {
    "Endocrinologist": "🔬",
    "Cardiologist": "❤️",
    "Sleep Medicine": "🌙",
    "Geriatrician": "👴",
}

_AGENT_COLOURS = {
    "Endocrinologist": "#1B4F72",
    "Cardiologist": "#A93226",
    "Sleep Medicine": "#6C3483",
    "Geriatrician": "#1E8449",
}

_OPTION_COLOURS = {"A": "#2E86AB", "B": "#E67E22", "C": "#27AE60"}


def _build_arg_graph(arguments: list[dict], scores: dict[str, float]) -> go.Figure:
    """Create a Plotly scatter-based argument interaction graph."""
    active = [a for a in arguments if not a.get("is_rejected", False)]
    agent_list = AGENT_ROLES
    option_list = ["A", "B", "C"]
    option_x = {"A": 0.0, "B": 2.5, "C": 5.0}
    agent_offset = {r: i * 0.55 for i, r in enumerate(agent_list)}
    type_y = {"support": 1.0, "challenge": -1.0}

    pos: dict[str, tuple[float, float]] = {}
    for arg in active:
        x = option_x.get(arg["option"], 0) + agent_offset.get(arg["agent_role"], 0)
        y = type_y.get(arg["type"], 0)
        pos[arg["argument_id"]] = (x, y)

    # Build attack edges (challenge → support, red) within each option
    edge_traces = []
    by_option: dict[str, dict[str, list]] = {}
    for arg in active:
        opt = arg["option"]
        if opt not in by_option:
            by_option[opt] = {"support": [], "challenge": []}
        by_option[opt][arg["type"]].append(arg)

    for opt, groups in by_option.items():
        for c_arg in groups["challenge"]:
            for s_arg in groups["support"]:
                if c_arg["argument_id"] in pos and s_arg["argument_id"] in pos:
                    cx, cy = pos[c_arg["argument_id"]]
                    sx, sy = pos[s_arg["argument_id"]]
                    edge_traces.append(go.Scatter(
                        x=[cx, sx, None], y=[cy, sy, None],
                        mode="lines",
                        line=dict(color="rgba(231,76,60,0.35)", width=1.2),
                        showlegend=False, hoverinfo="none",
                    ))

    # Node trace
    node_x, node_y, colours, sizes, texts, hovers = [], [], [], [], [], []
    for arg in active:
        if arg["argument_id"] not in pos:
            continue
        x, y = pos[arg["argument_id"]]
        node_x.append(x)
        node_y.append(y)
        colour = "#27AE60" if arg["type"] == "support" else "#E74C3C"
        colours.append(colour)
        fs = arg.get("final_score") or 0.0
        sizes.append(10 + int(fs * 22))
        short_role = arg["agent_role"][:4]
        texts.append(f"{_AGENT_ICONS.get(arg['agent_role'], '')} {short_role}")
        hovers.append(
            f"<b>{arg['agent_role']}</b> — Option {arg['option']} ({arg['type']})<br>"
            f"τ={arg['tau']:.2f} | score={fs:.3f}<br>"
            f"{arg['content'][:120]}…"
        )

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode="markers+text",
        marker=dict(size=sizes, color=colours, line=dict(color="white", width=1.5)),
        text=texts,
        textposition="top center",
        textfont=dict(size=9),
        hovertext=hovers,
        hoverinfo="text",
        showlegend=False,
    )

    # Option labels
    annotations = []
    for opt, bx in option_x.items():
        annotations.append(dict(
            x=bx + 0.8, y=1.55,
            text=f"<b>Option {opt}</b>",
            showarrow=False,
            font=dict(size=12, color=_OPTION_COLOURS.get(opt, "#333")),
        ))
    annotations.append(dict(x=-0.5, y=1.05, text="Support ↑", showarrow=False,
                             font=dict(size=10, color="#27AE60")))
    annotations.append(dict(x=-0.5, y=-1.05, text="Challenge ↓", showarrow=False,
                             font=dict(size=10, color="#E74C3C")))

    fig = go.Figure(data=[*edge_traces, node_trace])
    fig.update_layout(
        height=340,
        margin=dict(t=20, b=20, l=10, r=10),
        paper_bgcolor="#F8FAFC",
        plot_bgcolor="#F8FAFC",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-1, 7]),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-1.8, 2.0]),
        annotations=annotations,
    )
    return fig


def render_tab2() -> None:
    st.markdown("### Phase 2 — Multi-Agent Argumentation")

    if not st.session_state.get("phase1_complete"):
        st.warning("Complete Phase 1 first.")
        return

    if not st.session_state.get("phase2_complete"):
        st.info(
            "Four specialist AI agents will each review Patient PAT-0074's device trends and generate "
            "supporting and challenging arguments for the three care plan options."
        )

        _AGENT_FOCUS = {
            "Endocrinologist": "analysing CGM glucose trends and insulin management options…",
            "Cardiologist":    "reviewing HRV decline and blood pressure trajectory…",
            "Sleep Medicine":  "assessing sleep disruption and its downstream systemic effects…",
            "Geriatrician":    "synthesising all device streams into a holistic frailty assessment…",
        }

        if st.button("▶ Run Phase 2", key="run_phase2", type="primary"):
            ctx = st.session_state.patient_context
            all_arguments: list[dict] = []
            error_occurred = False

            with st.status("Running specialist agents…", expanded=True) as status:
                progress = st.progress(0)

                for i, role in enumerate(AGENT_ROLES):
                    icon = _AGENT_ICONS.get(role, "🤖")
                    focus = _AGENT_FOCUS.get(role, "generating arguments…")
                    st.write(f"{icon} **{role}** — {focus}")
                    progress.progress((i) / len(AGENT_ROLES),
                                      text=f"Agent {i+1} of {len(AGENT_ROLES)}: {role}")
                    try:
                        args = run_single_specialist(role, ctx, st.session_state.session_id)
                        all_arguments.extend(args)
                        n_sup = sum(1 for a in args if a["type"] == "support")
                        n_cha = sum(1 for a in args if a["type"] == "challenge")
                        st.write(f"  ✅ {role} complete — {n_sup} supporting, {n_cha} challenging arguments")
                    except Exception as e:
                        st.write(f"  ❌ {role} failed: {e}")
                        error_occurred = True
                        break

                    progress.progress((i + 1) / len(AGENT_ROLES))

                if error_occurred:
                    status.update(label="One or more agents failed — see errors above.", state="error")
                else:
                    st.write("⚙️ Scoring arguments via bipolar argumentation framework…")
                    scores, confidence = run_scoring(all_arguments)
                    for arg in all_arguments:
                        arg["final_score"] = scores.get(arg["argument_id"])
                    db.save_arguments(all_arguments)
                    progress.progress(1.0, text="Complete")
                    status.update(label="All 4 agents complete — arguments scored.", state="complete",
                                  expanded=False)
                    st.session_state.arguments = all_arguments
                    st.session_state.arg_scores = scores
                    st.session_state.option_confidence = confidence
                    st.session_state.option_confidence_initial = dict(confidence)
                    st.session_state.phase2_complete = True
                    st.rerun()
        return

    arguments: list[dict] = st.session_state.arguments
    scores: dict = st.session_state.arg_scores
    confidence: dict = st.session_state.option_confidence

    # ------------------------------------------------------------------ agent cards
    st.markdown("#### Agent Contributions")
    cols = st.columns(4, gap="small")
    for i, role in enumerate(AGENT_ROLES):
        role_args = [a for a in arguments if a["agent_role"] == role]
        icon = _AGENT_ICONS.get(role, "🤖")
        colour = _AGENT_COLOURS.get(role, "#333")
        with cols[i]:
            st.markdown(
                f"""
                <div style="background:white;border:1px solid #D5D8DC;border-radius:10px;
                             padding:12px;text-align:center;border-top:4px solid {colour};">
                    <div style="font-size:1.8rem;">{icon}</div>
                    <div style="font-weight:700;font-size:0.85rem;color:{colour};">{role}</div>
                    <div style="font-size:0.75rem;color:#888;margin-top:4px;">
                        {len([a for a in role_args if a['type']=='support'])} support &nbsp;·&nbsp;
                        {len([a for a in role_args if a['type']=='challenge'])} challenge
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # ------------------------------------------------------------------ option confidence
    st.divider()
    st.markdown("#### Option Confidence Scores")

    conf_cols = st.columns(3, gap="medium")
    for i, (opt, label) in enumerate(CARE_OPTIONS.items()):
        conf = confidence.get(opt, 0.0)
        colour = "#27AE60" if conf > 0.65 else "#F39C12" if conf > 0.35 else "#E74C3C"
        with conf_cols[i]:
            st.markdown(
                f"""
                <div style="background:white;border:1px solid #D5D8DC;border-radius:8px;padding:14px;">
                    <div style="font-weight:700;color:{colour};font-size:1rem;">Option {opt}</div>
                    <div style="font-size:0.8rem;color:#555;margin:4px 0 8px;">{label}</div>
                    <div style="background:#EEE;border-radius:6px;height:10px;">
                        <div style="background:{colour};width:{int(conf*100)}%;height:10px;border-radius:6px;"></div>
                    </div>
                    <div style="font-size:0.9rem;font-weight:700;margin-top:6px;color:{colour};">
                        {int(conf*100)}%
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # ------------------------------------------------------------------ argument details
    st.divider()
    st.markdown("#### Arguments by Agent")

    for role in AGENT_ROLES:
        role_args = [a for a in arguments if a["agent_role"] == role]
        icon = _AGENT_ICONS.get(role, "🤖")
        colour = _AGENT_COLOURS.get(role, "#333")
        with st.expander(f"{icon} {role}", expanded=False):
            arg_cols = st.columns(3, gap="small")
            for j, opt in enumerate(["A", "B", "C"]):
                opt_args = [a for a in role_args if a["option"] == opt]
                with arg_cols[j]:
                    st.markdown(
                        f"<div style='font-weight:600;color:{_OPTION_COLOURS[opt]};font-size:0.85rem;'>"
                        f"Option {opt}</div>",
                        unsafe_allow_html=True,
                    )
                    for arg in opt_args:
                        fs = arg.get("final_score") or 0.0
                        border_col = "#27AE60" if arg["type"] == "support" else "#E74C3C"
                        type_label = "✅ Support" if arg["type"] == "support" else "⚠️ Challenge"
                        st.markdown(
                            f"""
                            <div style="background:#FAFAFA;border-left:3px solid {border_col};
                                         padding:8px;border-radius:0 6px 6px 0;margin-bottom:8px;
                                         font-size:0.78rem;">
                                <div style="color:{border_col};font-weight:600;margin-bottom:4px;">
                                    {type_label}
                                </div>
                                <div style="color:#333;line-height:1.4;">{arg['content']}</div>
                                <div style="display:flex;gap:8px;margin-top:6px;">
                                    <span style="background:#2E86AB;color:white;padding:1px 7px;
                                                 border-radius:10px;font-size:0.7rem;">τ={arg['tau']:.2f}</span>
                                    <span style="background:#555;color:white;padding:1px 7px;
                                                 border-radius:10px;font-size:0.7rem;">
                                        score={fs:.3f}</span>
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

    # ------------------------------------------------------------------ interaction graph
    st.divider()
    st.markdown("#### Argument Interaction Graph")
    st.caption(
        "Green nodes = supporting arguments | Red nodes = challenging arguments | "
        "Red edges = attack relations | Node size ∝ final score"
    )
    fig = _build_arg_graph(arguments, scores)
    st.plotly_chart(fig, use_container_width=True)
