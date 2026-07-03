from __future__ import annotations
import html
from datetime import datetime, timedelta, timezone

import plotly.graph_objects as go
import streamlit as st

from data import db


# ------------------------------------------------------------------ Healthcare helpers

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


def _render_tab1_healthcare() -> None:
    st.markdown("### Phase 1 — Patient Overview & Complexity Assessment")

    if not st.session_state.get("phase1_complete"):
        st.info(
            "Click **Run Phase 1** to analyse Patient PAT-0074's 3-week device data and assess clinical complexity."
        )
        if st.button("▶ Run Phase 1", key="run_phase1", type="primary"):
            with st.spinner("Analysing IoMT telemetry and retrieving similar cases…"):
                from agents.patient_analyzer import run_patient_analyzer
                ctx = run_patient_analyzer("PAT-0074", session_id=st.session_state.session_id)
                st.session_state.patient_context = ctx
                st.session_state.phase1_complete = True
            st.rerun()
        return

    ctx = st.session_state.patient_context

    readings = db.get_telemetry_for_patient("PAT-0074")
    if not readings:
        st.warning("No telemetry found — run seed_data.py first.")
        return

    timestamps = sorted({r["timestamp"] for r in readings})
    base_date = min(timestamps)
    total_days = (max(timestamps) - base_date).days

    col_left, col_right = st.columns(2, gap="medium")

    with col_left:
        cgm = _get_device_series(readings, "cgm")
        fig_cgm = go.Figure()
        fig_cgm.add_trace(go.Scatter(
            x=[t for t, _ in cgm], y=[v for _, v in cgm],
            mode="lines+markers", line=dict(color="#2E86AB", width=2),
            marker=dict(size=4), name="Glucose",
        ))
        fig_cgm.add_shape(**_red_zone_shape(5, total_days, base_date))
        fig_cgm.add_hline(y=10.0, line_dash="dot", line_color="#E74C3C",
                           annotation_text="10.0 alert", annotation_position="top left")
        fig_cgm.update_layout(
            title="Blood Glucose (CGM)", yaxis_title="mmol/L",
            height=220, margin=dict(t=36, b=20, l=40, r=10),
            paper_bgcolor="#FFFFFF", plot_bgcolor="#F8FAFC",
        )
        st.plotly_chart(fig_cgm, use_container_width=True)

        bp_sys = _get_device_series(readings, "bp_cuff", "systolic")
        bp_dia = _get_device_series(readings, "bp_cuff", "diastolic")
        fig_bp = go.Figure()
        fig_bp.add_trace(go.Scatter(
            x=[t for t, _ in bp_sys], y=[v for _, v in bp_sys],
            mode="lines+markers", name="Systolic",
            line=dict(color="#1B4F72", width=2), marker=dict(size=5),
        ))
        fig_bp.add_trace(go.Scatter(
            x=[t for t, _ in bp_dia], y=[v for _, v in bp_dia],
            mode="lines+markers", name="Diastolic",
            line=dict(color="#AED6F1", width=2), marker=dict(size=5),
        ))
        fig_bp.add_shape(**_red_zone_shape(5, total_days, base_date))
        fig_bp.update_layout(
            title="Blood Pressure", yaxis_title="mmHg",
            height=220, margin=dict(t=36, b=20, l=40, r=10),
            paper_bgcolor="#FFFFFF", plot_bgcolor="#F8FAFC",
            legend=dict(orientation="h", y=1.1),
        )
        st.plotly_chart(fig_bp, use_container_width=True)

    with col_right:
        hrv = _get_device_series(readings, "wearable_hrv")
        fig_hrv = go.Figure()
        fig_hrv.add_trace(go.Scatter(
            x=[t for t, _ in hrv], y=[v for _, v in hrv],
            mode="lines+markers", line=dict(color="#8E44AD", width=2),
            marker=dict(size=5), name="HRV",
        ))
        fig_hrv.add_shape(**_red_zone_shape(5, total_days, base_date))
        fig_hrv.update_layout(
            title="Heart Rate Variability (HRV)", yaxis_title="ms",
            height=220, margin=dict(t=36, b=20, l=40, r=10),
            paper_bgcolor="#FFFFFF", plot_bgcolor="#F8FAFC",
        )
        st.plotly_chart(fig_hrv, use_container_width=True)

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

    st.divider()
    st.markdown("#### Clinical Complexity Assessment")

    badge_color = {"High": "#E74C3C", "Medium": "#F39C12", "Low": "#27AE60"}.get(
        ctx.complexity_score, "#888"
    )
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">'
        f'<span style="background:{badge_color};color:white;padding:4px 14px;'
        f'border-radius:20px;font-weight:700;font-size:1rem;">'
        f'{html.escape(ctx.complexity_score)} Complexity</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(ctx.complexity_reason)

    if ctx.key_concerns:
        st.markdown("**Key concerns:**")
        for concern in ctx.key_concerns:
            st.markdown(f"- {concern}")

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


# ------------------------------------------------------------------ Manufacturing helpers

def _render_tab1_manufacturing() -> None:
    st.markdown("### Phase 1 — Site Overview & Mapping Complexity Assessment")

    if not st.session_state.get("phase1_complete"):
        st.info(
            "Click **Run Phase 1** to analyse Site SITE-0042's HVAC point naming and assess mapping complexity."
        )
        if st.button("▶ Run Phase 1", key="run_phase1", type="primary"):
            with st.spinner("Analysing HVAC point data and retrieving similar verified mappings…"):
                from agents.site_reader import run_site_reader
                ctx = run_site_reader("SITE-0042", session_id=st.session_state.session_id)
                st.session_state.site_context = ctx
                st.session_state.phase1_complete = True
            st.rerun()
        return

    ctx = st.session_state.site_context

    # ------------------------------------------------------------------ site info
    info_col1, info_col2, info_col3 = st.columns(3, gap="medium")

    with info_col1:
        st.markdown(
            f'<div style="background:white;border:1px solid #D5D8DC;border-radius:8px;padding:14px;">'
            f'<div style="font-size:0.7rem;text-transform:uppercase;color:#888;letter-spacing:0.05em;">Site</div>'
            f'<div style="font-weight:700;font-size:1rem;color:#1B4F72;">{html.escape(ctx.site_id)}</div>'
            f'<div style="font-size:0.82rem;color:#555;margin-top:2px;">{html.escape(ctx.site_type)}</div>'
            f'<div style="font-size:0.78rem;color:#888;">{html.escape(ctx.location)}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with info_col2:
        st.markdown(
            f'<div style="background:white;border:1px solid #D5D8DC;border-radius:8px;padding:14px;">'
            f'<div style="font-size:0.7rem;text-transform:uppercase;color:#888;letter-spacing:0.05em;">Equipment</div>'
            f'<div style="font-weight:700;font-size:0.9rem;color:#1B4F72;">{html.escape(ctx.equipment_series)}</div>'
            f'<div style="font-size:0.78rem;color:#555;margin-top:4px;">'
            f'<strong>{ctx.total_points}</strong> total points &nbsp;·&nbsp; '
            f'<span style="color:#E67E22;font-weight:600;">{ctx.ambiguous_points}</span> ambiguous'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with info_col3:
        badge_color = {"High": "#E74C3C", "Medium": "#F39C12", "Low": "#27AE60"}.get(
            ctx.complexity_score, "#888"
        )
        st.markdown(
            f'<div style="background:white;border:1px solid #D5D8DC;border-radius:8px;padding:14px;">'
            f'<div style="font-size:0.7rem;text-transform:uppercase;color:#888;letter-spacing:0.05em;">Mapping Complexity</div>'
            f'<div style="margin-top:6px;">'
            f'<span style="background:{badge_color};color:white;padding:3px 12px;'
            f'border-radius:20px;font-weight:700;font-size:0.9rem;">{html.escape(ctx.complexity_score)}</span>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ------------------------------------------------------------------ focus point + complexity
    st.divider()
    st.markdown("#### Focus Point for Review")

    fp_col, reason_col = st.columns([1, 2], gap="medium")
    with fp_col:
        st.markdown(
            f'<div style="background:#1B4F72;color:white;border-radius:10px;padding:20px;text-align:center;">'
            f'<div style="font-size:0.75rem;opacity:0.8;text-transform:uppercase;letter-spacing:0.05em;">Point Name</div>'
            f'<div style="font-size:1.4rem;font-weight:700;font-family:monospace;margin:8px 0;">'
            f'{html.escape(ctx.focus_point)}</div>'
            f'<div style="font-size:0.78rem;opacity:0.85;">{html.escape(ctx.equipment_series)}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with reason_col:
        st.markdown(f"**Point description:** {ctx.point_description}")
        st.markdown(f"**Why this is complex:** {ctx.complexity_reason}")

    # ------------------------------------------------------------------ documentation fragments
    st.divider()
    st.markdown("#### Equipment Documentation Fragments")

    if not ctx.documentation_fragments:
        st.info("No documentation fragments available.")
    else:
        for i, frag in enumerate(ctx.documentation_fragments):
            st.markdown(
                f'<div style="background:#F8FAFC;border-left:3px solid #2E86AB;'
                f'padding:10px 14px;border-radius:0 6px 6px 0;margin-bottom:8px;'
                f'font-size:0.83rem;color:#333;line-height:1.5;">'
                f'<span style="font-size:0.7rem;color:#2E86AB;font-weight:700;'
                f'text-transform:uppercase;letter-spacing:0.04em;">Fragment {i+1}</span><br>'
                f'{html.escape(frag)}'
                f'</div>',
                unsafe_allow_html=True,
            )

    # ------------------------------------------------------------------ similar verified mappings
    st.divider()
    st.markdown("#### 3 Most Similar Verified Mappings (Atlas Vector Search)")

    if not ctx.similar_mappings:
        st.info("No similar mappings retrieved — check that the mapping_vector_index has finished building.")
    else:
        for i, mapping in enumerate(ctx.similar_mappings):
            score_pct = round(mapping.get("score", 0) * 100, 1)
            brick_class = mapping.get("verified_brick_class", "")
            brick_colour = (
                "#2E86AB" if "Supply" in brick_class
                else "#E67E22" if "Discharge" in brick_class
                else "#27AE60"
            )
            with st.expander(
                f"Match {i + 1} — {mapping.get('point_name', '')} "
                f"| Similarity: {score_pct}% | {brick_class}"
            ):
                m1, m2 = st.columns(2)
                with m1:
                    st.markdown(f"**Point name:** `{mapping.get('point_name', '')}`")
                    st.markdown(f"**Equipment:** {mapping.get('equipment_series', '')}")
                    st.markdown(f"**Site:** {mapping.get('site_id', '')}")
                with m2:
                    st.markdown(
                        f'<span style="background:{brick_colour};color:white;padding:3px 10px;'
                        f'border-radius:10px;font-size:0.8rem;font-weight:600;">'
                        f'{html.escape(brick_class)}</span>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(f"**Verified by:** {mapping.get('verified_by', '')}")
                st.markdown(f"**Notes:** {mapping.get('notes', '')}")

    # ------------------------------------------------------------------ equipment summary
    if ctx.equipment_summary:
        st.divider()
        st.markdown("#### Equipment Series Analysis")
        st.markdown(ctx.equipment_summary)


# ------------------------------------------------------------------ Entry point

def render_tab1() -> None:
    domain = st.session_state.get("domain", "healthcare")
    if domain == "manufacturing":
        _render_tab1_manufacturing()
    else:
        _render_tab1_healthcare()
