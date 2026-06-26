from __future__ import annotations
import html
from datetime import datetime

import plotly.graph_objects as go
import streamlit as st

from agents.careplan_agent import run_careplan_agent
from data.models import CARE_OPTIONS

_OPTION_COLOURS = {"A": "#2E86AB", "B": "#E67E22", "C": "#27AE60"}


def _before_after_chart(scores_before: dict, scores_after: dict) -> go.Figure:
    options = ["A", "B", "C"]
    y_before = [scores_before.get(o, 0) * 100 for o in options]
    y_after = [scores_after.get(o, 0) * 100 for o in options]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Before contestation",
        x=options, y=y_before,
        marker_color="#AED6F1",
        offsetgroup=0,
    ))
    fig.add_trace(go.Bar(
        name="After contestation",
        x=options, y=y_after,
        marker_color=[_OPTION_COLOURS.get(o, "#333") for o in options],
        offsetgroup=1,
    ))
    fig.update_layout(
        barmode="group",
        yaxis_title="Confidence (%)",
        yaxis=dict(range=[0, 100]),
        height=260,
        margin=dict(t=20, b=40, l=40, r=10),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#F8FAFC",
        legend=dict(orientation="h", y=1.1),
    )
    return fig


def render_tab4() -> None:
    st.markdown("### Phase 4 — Care Plan & Audit Trail")

    if not st.session_state.get("phase3_complete"):
        st.warning("Complete Phase 3 (Human Contestation) first.")
        return

    if not st.session_state.get("phase4_complete"):
        st.info("Generate the final care plan from the validated argument set.")
        if st.button("▶ Generate Care Plan", key="run_phase4", type="primary"):
            with st.spinner("Generating care plan…"):
                ctx = st.session_state.patient_context
                care_plan = run_careplan_agent(
                    patient_context=ctx,
                    arguments=st.session_state.arguments,
                    option_scores_before=st.session_state.option_confidence_initial,
                    option_scores_after=st.session_state.option_confidence,
                    session_id=st.session_state.session_id,
                )
                st.session_state.care_plan = care_plan
                st.session_state.phase4_complete = True
            st.rerun()
        return

    plan: dict = st.session_state.care_plan
    rec_opt = plan.get("recommended_option", "C")
    opt_colour = _OPTION_COLOURS.get(rec_opt, "#27AE60")

    # ------------------------------------------------------------------ recommendation banner
    st.markdown(
        f"""
        <div style="background:{opt_colour};color:white;border-radius:10px;padding:18px 20px;margin-bottom:20px;">
            <div style="font-size:0.85rem;text-transform:uppercase;letter-spacing:0.06em;opacity:0.85;">
                Recommended Care Plan
            </div>
            <div style="font-size:1.5rem;font-weight:700;margin:4px 0;">
                Option {rec_opt}: {html.escape(CARE_OPTIONS.get(rec_opt, ''))}
            </div>
            <div style="font-size:0.9rem;opacity:0.9;margin-top:8px;">{html.escape(plan.get('rationale', ''))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        st.markdown("#### Implementation Steps")
        for i, step in enumerate(plan.get("implementation_steps", []), 1):
            st.markdown(
                f"""
                <div style="display:flex;align-items:flex-start;gap:10px;margin-bottom:10px;">
                    <div style="min-width:24px;height:24px;background:{opt_colour};color:white;
                                 border-radius:50%;display:flex;align-items:center;justify-content:center;
                                 font-weight:700;font-size:0.8rem;">{i}</div>
                    <div style="font-size:0.88rem;color:#333;padding-top:3px;">{html.escape(step)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with col_right:
        st.markdown("#### Decisive Arguments")
        for da in plan.get("decisive_arguments", []):
            st.markdown(
                f'<div style="background:#F8FAFC;border-left:3px solid {opt_colour};'
                f'padding:8px 12px;border-radius:0 6px 6px 0;margin-bottom:8px;'
                f'font-size:0.83rem;color:#333;">{html.escape(da)}</div>',
                unsafe_allow_html=True,
            )

    # ------------------------------------------------------------------ contestation impact
    st.divider()
    st.markdown("#### Contestation Impact")
    st.caption("How human expert input shifted option confidence scores")

    impact_col1, impact_col2 = st.columns([3, 2])

    with impact_col1:
        scores_before = plan.get("option_scores_before", {})
        scores_after = plan.get("option_scores_after", {})
        fig = _before_after_chart(scores_before, scores_after)
        st.plotly_chart(fig, use_container_width=True)

    with impact_col2:
        st.markdown(plan.get("confidence_summary", ""))

    # ------------------------------------------------------------------ audit trail
    st.divider()
    st.markdown("#### Audit Trail")

    audit = plan.get("audit_entries", [])
    if not audit:
        st.info("No human edits were recorded in this session.")
    else:
        rows = []
        for entry in audit:
            ts = entry.get("timestamp")
            if isinstance(ts, datetime):
                ts_str = ts.strftime("%H:%M:%S")
            else:
                ts_str = str(ts)[:19] if ts else "—"
            rows.append({
                "Argument ID": entry.get("argument_id", "")[:16] + "…",
                "Agent Role": entry.get("agent_role", ""),
                "Option": entry.get("option", ""),
                "Edit Type": entry.get("edit_type", ""),
                "Editor Role": entry.get("editor_role", ""),
                "Timestamp": ts_str,
                "Content (truncated)": str(entry.get("current_content", ""))[:80] + "…",
            })
        import pandas as pd
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # ------------------------------------------------------------------ save
    st.divider()
    if st.button("💾 Save to MongoDB", key="save_mongo"):
        st.success("Care plan already saved to MongoDB `care_plans` collection.")
