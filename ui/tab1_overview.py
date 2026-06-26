from __future__ import annotations
from datetime import datetime, timedelta, timezone

import plotly.graph_objects as go
import streamlit as st

from agents.patient_analyzer import run_patient_analyzer
from data import db


def _get_device_series(readings: list[dict], device: str, reading: str | None = None):
    out = []
    for r in readings:
        if r["metadata"]["device"] != device:
            continue
        if reading and r["metadata"].get("reading") != reading:
            continue
        out.append((r["timestamp"], float(r["value"])))
    return sorted(out)


def _red_zone_shape(start_day_offset: int, total_days: int, base_date: datetime):
    red_start = base_date + timedelta(days=total_days - start_day_offset)
    red_end = base_date + timedelta(days=total_days + 1)
    return dict(
        type="rect",
        xref="x",
        yref="paper",
        x0=red_start,
        x1=red_end,
        y0=0,
        y1=1,
        fillcolor="rgba(231,76,60,0.08)",
        line_width=0,
    )


def render_tab1() -> None:
    st.markdown("### Phase 1 — Patient Overview & Complexity Assessment")

    if not st.session_state.get("phase1_complete"):
        st.info(
            "Click **Run Phase 1** to analyse Patient PAT-0074's 3-week device data and assess clinical complexity."
        )
        if st.button("▶ Run Phase 1", key="run_phase1", type="primary"):
            with st.spinner("Analysing IoMT telemetry and retrieving similar cases…"):
                ctx = run_patient_analyzer("PAT-0074")
                st.session_state.patient_context = ctx
                st.session_state.phase1_complete = True
            st.rerun()
        return

    ctx = st.session_state.patient_context

    # ------------------------------------------------------------------ charts
    readings = db.get_telemetry_for_patient("PAT-0074")
    if not readings:
        st.warning("No telemetry found — run seed_data.py first.")
        return

    timestamps = sorted({r["timestamp"] for r in readings})
    base_date = min(timestamps)
    total_days = (max(timestamps) - base_date).days

    col_left, col_right = st.columns(2, gap="medium")

    with col_left:
        # Glucose chart
        cgm = _get_device_series(readings, "cgm")
        times_cgm = [t for t, _ in cgm]
        vals_cgm = [v for _, v in cgm]
        fig_cgm = go.Figure()
        fig_cgm.add_trace(go.Scatter(x=times_cgm, y=vals_cgm, mode="lines+markers",
                                      line=dict(color="#2E86AB", width=2),
                                      marker=dict(size=4), name="Glucose"))
        fig_cgm.add_shape(**_red_zone_shape(5, total_days, base_date))
        fig_cgm.add_hline(y=10.0, line_dash="dot", line_color="#E74C3C",
                           annotation_text="10.0 alert", annotation_position="top left")
        fig_cgm.update_layout(
            title="Blood Glucose (CGM)", yaxis_title="mmol/L",
            height=220, margin=dict(t=36, b=20, l=40, r=10),
            paper_bgcolor="#FFFFFF", plot_bgcolor="#F8FAFC",
        )
        st.plotly_chart(fig_cgm, use_container_width=True)

        # BP chart
        bp_sys = _get_device_series(readings, "bp_cuff", "systolic")
        bp_dia = _get_device_series(readings, "bp_cuff", "diastolic")
        fig_bp = go.Figure()
        fig_bp.add_trace(go.Scatter(x=[t for t, _ in bp_sys], y=[v for _, v in bp_sys],
                                     mode="lines+markers", name="Systolic",
                                     line=dict(color="#1B4F72", width=2), marker=dict(size=5)))
        fig_bp.add_trace(go.Scatter(x=[t for t, _ in bp_dia], y=[v for _, v in bp_dia],
                                     mode="lines+markers", name="Diastolic",
                                     line=dict(color="#AED6F1", width=2), marker=dict(size=5)))
        fig_bp.add_shape(**_red_zone_shape(5, total_days, base_date))
        fig_bp.update_layout(
            title="Blood Pressure", yaxis_title="mmHg",
            height=220, margin=dict(t=36, b=20, l=40, r=10),
            paper_bgcolor="#FFFFFF", plot_bgcolor="#F8FAFC",
            legend=dict(orientation="h", y=1.1),
        )
        st.plotly_chart(fig_bp, use_container_width=True)

    with col_right:
        # HRV chart
        hrv = _get_device_series(readings, "wearable_hrv")
        fig_hrv = go.Figure()
        fig_hrv.add_trace(go.Scatter(x=[t for t, _ in hrv], y=[v for _, v in hrv],
                                      mode="lines+markers", line=dict(color="#8E44AD", width=2),
                                      marker=dict(size=5), name="HRV"))
        fig_hrv.add_shape(**_red_zone_shape(5, total_days, base_date))
        fig_hrv.update_layout(
            title="Heart Rate Variability (HRV)", yaxis_title="ms",
            height=220, margin=dict(t=36, b=20, l=40, r=10),
            paper_bgcolor="#FFFFFF", plot_bgcolor="#F8FAFC",
        )
        st.plotly_chart(fig_hrv, use_container_width=True)

        # Sleep chart
        sleep = _get_device_series(readings, "wearable_sleep")
        colors_sleep = [
            "#E74C3C" if v < 5.0 else "#F39C12" if v < 6.0 else "#27AE60"
            for _, v in sleep
        ]
        fig_sleep = go.Figure()
        fig_sleep.add_trace(go.Bar(
            x=[t for t, _ in sleep], y=[v for _, v in sleep],
            marker_color=colors_sleep, name="Sleep",
        ))
        fig_sleep.add_hline(y=6.0, line_dash="dot", line_color="#27AE60",
                             annotation_text="6h target", annotation_position="top left")
        fig_sleep.add_shape(**_red_zone_shape(5, total_days, base_date))
        fig_sleep.update_layout(
            title="Nightly Sleep Duration", yaxis_title="hours",
            height=220, margin=dict(t=36, b=20, l=40, r=10),
            paper_bgcolor="#FFFFFF", plot_bgcolor="#F8FAFC",
        )
        st.plotly_chart(fig_sleep, use_container_width=True)

    st.caption("🔴 Red shading = last 5 days (period of concern)")

    # ------------------------------------------------------------------ complexity
    st.divider()
    st.markdown("#### Clinical Complexity Assessment")

    badge_color = {"High": "#E74C3C", "Medium": "#F39C12", "Low": "#27AE60"}.get(
        ctx.complexity_score, "#888"
    )
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
            <span style="background:{badge_color};color:white;padding:4px 14px;
                         border-radius:20px;font-weight:700;font-size:1rem;">
                {ctx.complexity_score} Complexity
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(ctx.complexity_reason)

    if ctx.key_concerns:
        st.markdown("**Key concerns:**")
        for concern in ctx.key_concerns:
            st.markdown(f"- {concern}")

    # ------------------------------------------------------------------ similar cases
    st.divider()
    st.markdown("#### 3 Most Similar Historical Cases (Atlas Vector Search)")

    if not ctx.similar_cases:
        st.info("No similar cases retrieved — check that the vector index has finished building.")
    else:
        for i, case in enumerate(ctx.similar_cases):
            score_pct = round(case.get("score", 0) * 100, 1)
            with st.expander(
                f"Case {i + 1} — Age {case.get('age', '?')} | Outcome: {case.get('outcome', '?')} "
                f"| Similarity: {score_pct}%"
            ):
                st.markdown(f"**Summary:** {case.get('summary', '')}")
                if case.get("device_trends"):
                    st.markdown("**Device trends:**")
                    for k, v in case["device_trends"].items():
                        st.markdown(f"- {k}: {v}")
                if case.get("care_plan_changes"):
                    st.markdown("**Interventions that worked:**")
                    for step in case["care_plan_changes"]:
                        st.markdown(f"- {step}")
