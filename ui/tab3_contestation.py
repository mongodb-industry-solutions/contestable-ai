from __future__ import annotations
import difflib
import html
import uuid

import streamlit as st

from contestation.handler import add_human_argument, apply_edits_and_rescore
from data.models import DOMAIN_CONFIGS

_OPTION_COLOURS = {"A": "#2E86AB", "B": "#E67E22", "C": "#27AE60"}

_AGENT_ICONS = {
    "Endocrinologist":      "🔬",
    "Cardiologist":         "❤️",
    "Sleep Medicine":       "🌙",
    "Geriatrician":         "👴",
    "Family Physician":     "🩺",
    "String Matcher":       "🔤",
    "Documentation Reader": "📄",
    "Brick Domain Expert":  "🏗️",
}


def _word_diff_html(original: str, modified: str) -> str:
    orig_words = html.escape(original).split()
    mod_words = html.escape(modified).split()
    matcher = difflib.SequenceMatcher(None, orig_words, mod_words)
    parts = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            parts.append(" ".join(orig_words[i1:i2]))
        elif tag == "replace":
            parts.append(
                f'<span style="background:#f8d7da;color:#721c24;text-decoration:line-through;">'
                f'{" ".join(orig_words[i1:i2])}</span> '
                f'<span style="background:#d4edda;color:#155724;">{" ".join(mod_words[j1:j2])}</span>'
            )
        elif tag == "delete":
            parts.append(
                f'<span style="background:#f8d7da;color:#721c24;text-decoration:line-through;">'
                f'{" ".join(orig_words[i1:i2])}</span>'
            )
        elif tag == "insert":
            parts.append(
                f'<span style="background:#d4edda;color:#155724;">{" ".join(mod_words[j1:j2])}</span>'
            )
    return " ".join(parts)


def _confidence_bar(label: str, conf: float, colour: str) -> str:
    return (
        f'<div style="margin-bottom:8px;">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:3px;">'
        f'<span style="font-size:0.8rem;font-weight:700;color:{colour};">Option {label}</span>'
        f'<span style="font-size:0.85rem;font-weight:700;color:{colour};">{int(conf*100)}%</span>'
        f'</div>'
        f'<div style="background:#EEE;border-radius:4px;height:8px;">'
        f'<div style="background:{colour};width:{int(conf*100)}%;height:8px;border-radius:4px;"></div>'
        f'</div>'
        f"</div>"
    )


def _render_arg_card(arg: dict, edits_done: dict, reviewer_role: str = "Family Physician") -> None:
    """Render a single argument card with Accept / Reject / Modify controls."""
    aid = arg["argument_id"]
    edit = edits_done.get(aid, {})
    is_rejected = arg.get("is_rejected", False) or edit.get("edit_type") == "reject"
    is_accepted = edit.get("edit_type") == "accept"
    is_modified = edit.get("edit_type") == "modify"
    is_gp_added = arg.get("human_edit") and arg.get("edit_type") == "add"

    border_col = "#27AE60" if arg["type"] == "support" else "#E74C3C"
    agent_icon = _AGENT_ICONS.get(arg["agent_role"], "🤖")
    fs = arg.get("final_score") or 0.0

    if is_rejected:
        badge = '<span style="background:#E74C3C;color:white;padding:1px 7px;border-radius:10px;font-size:0.68rem;margin-left:4px;">REJECTED</span>'
    elif is_accepted:
        badge = '<span style="background:#27AE60;color:white;padding:1px 7px;border-radius:10px;font-size:0.68rem;margin-left:4px;">ACCEPTED</span>'
    elif is_modified:
        badge = '<span style="background:#F39C12;color:white;padding:1px 7px;border-radius:10px;font-size:0.68rem;margin-left:4px;">MODIFIED</span>'
    elif is_gp_added:
        badge = '<span style="background:#8E44AD;color:white;padding:1px 7px;border-radius:10px;font-size:0.68rem;margin-left:4px;">ADDED</span>'
    else:
        badge = ""

    if is_modified:
        orig = arg.get("original_content") or arg["content"]
        body = _word_diff_html(orig, edit["content"])
    elif is_rejected:
        body = f'<s style="color:#bbb;">{html.escape(arg["content"])}</s>'
    else:
        body = html.escape(arg["content"])

    opacity = "0.4" if is_rejected else "1"

    # Build card as a single concatenated string — no blank lines so markdown parser
    # doesn't fragment the HTML into separate paragraphs.
    card = (
        f'<div style="background:white;border:1px solid #E0E0E0;border-top:3px solid {border_col};'
        f'border-radius:6px;padding:10px 12px;margin-bottom:6px;opacity:{opacity};">'
        f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:8px;flex-wrap:wrap;">'
        f'<span>{agent_icon}</span>'
        f'<span style="font-size:0.8rem;font-weight:700;color:#222;">{arg["agent_role"]}</span>'
        f'<span style="background:#EEF2F7;color:#555;padding:1px 7px;border-radius:10px;font-size:0.7rem;">&#964;={arg["tau"]:.2f}</span>'
        f'<span style="background:#F0F0F0;color:#666;padding:1px 7px;border-radius:10px;font-size:0.7rem;">{fs:.3f}</span>'
        f'{badge}'
        f'</div>'
        f'<div style="font-size:0.8rem;color:#333;line-height:1.5;">{body}</div>'
        f'</div>'
    )
    st.markdown(card, unsafe_allow_html=True)

    if st.session_state.modifying_arg == aid:
        with st.form(key=f"modify_form_{aid}"):
            new_content = st.text_area(
                "Edit argument content",
                value=edit.get("content", arg["content"]),
                height=80,
                key=f"ta_{aid}",
            )
            c1, c2 = st.columns(2)
            with c1:
                if st.form_submit_button("Save", type="primary"):
                    st.session_state.pending_edits[aid] = {
                        "edit_type": "modify",
                        "content": new_content,
                        "editor_role": reviewer_role,
                    }
                    st.session_state.modifying_arg = None
                    st.session_state.phase3_complete = False
                    st.rerun()
            with c2:
                if st.form_submit_button("Cancel"):
                    st.session_state.modifying_arg = None
                    st.rerun()
    elif not is_rejected:
        b1, b2, b3, _ = st.columns([1, 1, 1, 4])
        with b1:
            if st.button("✓", key=f"acc_{aid}", help="Accept"):
                st.session_state.pending_edits[aid] = {"edit_type": "accept", "editor_role": reviewer_role}
                st.session_state.phase3_complete = False
                st.rerun()
        with b2:
            if st.button("✗", key=f"rej_{aid}", help="Reject"):
                st.session_state.pending_edits[aid] = {"edit_type": "reject", "editor_role": reviewer_role}
                st.session_state.phase3_complete = False
                st.rerun()
        with b3:
            if st.button("✏️", key=f"mod_{aid}", help="Modify"):
                st.session_state.modifying_arg = aid
                st.rerun()


def render_tab3() -> None:
    domain = st.session_state.get("domain", "healthcare")
    cfg = DOMAIN_CONFIGS[domain]
    reviewer_role = cfg["reviewer_role"]
    reviewer_icon = _AGENT_ICONS.get(reviewer_role, "👤")
    options = cfg["options"]
    subject_id = cfg["subject_id"]
    subject_label = cfg["subject_label"]

    phase_label = cfg["phase_labels"][2]
    st.markdown(f"### Phase 3 — {phase_label}")

    if not st.session_state.get("phase2_complete"):
        st.warning("Complete Phase 2 first.")
        return

    arguments: list[dict] = st.session_state.arguments
    confidence: dict = st.session_state.option_confidence

    if "pending_edits" not in st.session_state:
        st.session_state.pending_edits = {}
    if "modifying_arg" not in st.session_state:
        st.session_state.modifying_arg = None

    edits_done = st.session_state.pending_edits

    # ------------------------------------------------------------------ reviewer persona banner
    st.markdown(
        f'<div style="background:#EBF5FB;border:1px solid #AED6F1;border-radius:10px;'
        f'padding:12px 16px;margin-bottom:16px;display:flex;align-items:center;gap:14px;">'
        f'<div style="font-size:1.8rem;">{reviewer_icon}</div>'
        f'<div>'
        f'<div style="font-weight:700;color:#1B4F72;font-size:0.95rem;">{html.escape(reviewer_role)}</div>'
        f'<div style="font-size:0.8rem;color:#2E86AB;">Reviewing AI recommendations for {html.escape(subject_label)} {html.escape(subject_id)}</div>'
        f'<div style="font-size:0.72rem;color:#888;margin-top:1px;">'
        f'All contestation actions are attributed to this reviewer in the audit trail.'
        f'</div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ------------------------------------------------------------------ layout: cards | summary
    col_main, col_summary = st.columns([3, 1], gap="medium")

    # Summary panel
    with col_summary:
        n_rejected = sum(1 for e in edits_done.values() if e.get("edit_type") == "reject")
        n_modified = sum(1 for e in edits_done.values() if e.get("edit_type") == "modify")
        n_accepted = sum(1 for e in edits_done.values() if e.get("edit_type") == "accept")
        n_added = sum(1 for a in arguments if a.get("edit_type") == "add" and a.get("human_edit"))

        st.markdown(
            """
            <div style="background:#EBF5FB;border:1px solid #AED6F1;border-radius:8px;
                         padding:12px 14px;margin-bottom:12px;">
                <div style="font-weight:700;color:#1B4F72;margin-bottom:8px;font-size:0.9rem;">
                    Contestation Summary
                </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            f"✅ **Accepted:** {n_accepted}  \n"
            f"❌ **Rejected:** {n_rejected}  \n"
            f"✏️ **Modified:** {n_modified}  \n"
            f"➕ **Added:** {n_added}",
        )
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("**Current Scores:**")
        bars_html = "".join(
            _confidence_bar(opt, confidence.get(opt, 0), _OPTION_COLOURS.get(opt, "#333"))
            for opt in ["A", "B", "C"]
        )
        st.markdown(bars_html, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("🔄 Recompute Scores", key="recompute", type="primary", use_container_width=True):
            with st.spinner("Rescoring…"):
                updated, scores, new_conf = apply_edits_and_rescore(
                    arguments,
                    edits_done,
                    st.session_state.session_id,
                )
                st.session_state.arguments = updated
                st.session_state.arg_scores = scores
                st.session_state.option_confidence = new_conf
                st.session_state.pending_edits = {}
                st.session_state.phase3_complete = True
            st.rerun()

    # Argument cards — option selector + 2-col layout
    with col_main:
        st.markdown("#### Argument Cards")
        st.caption(
            "Pick an option below · Use **✓ Accept**, **✗ Reject**, or **✏️ Modify** · "
            "Click **Recompute Scores** when done."
        )

        # Option selector
        sel_opt = st.radio(
            "Viewing option:",
            ["A", "B", "C"],
            horizontal=True,
            format_func=lambda x: f"Option {x} — {options[x]}",
            label_visibility="collapsed",
        )

        opt_colour = _OPTION_COLOURS[sel_opt]
        opt_args = [a for a in arguments if a["option"] == sel_opt]
        sup_args = [a for a in opt_args if a["type"] == "support"]
        cha_args = [a for a in opt_args if a["type"] == "challenge"]

        # Option banner
        st.markdown(
            f'<div style="border-left:4px solid {opt_colour};padding:8px 14px;'
            f'background:white;border-radius:0 6px 6px 0;margin:8px 0 12px;">'
            f'<span style="font-weight:700;color:{opt_colour};">Option {sel_opt}</span> '
            f'<span style="color:#555;font-size:0.85rem;">{html.escape(options[sel_opt])}</span></div>',
            unsafe_allow_html=True,
        )

        col_sup, col_cha = st.columns(2, gap="medium")

        with col_sup:
            st.markdown(
                '<div style="background:#E9F7EF;border-radius:6px;padding:6px 10px;'
                'margin-bottom:10px;font-weight:700;font-size:0.82rem;color:#1E8449;">✅ Supporting Arguments</div>',
                unsafe_allow_html=True,
            )
            for arg in sup_args:
                _render_arg_card(arg, edits_done, reviewer_role)

        with col_cha:
            st.markdown(
                '<div style="background:#FDEDEC;border-radius:6px;padding:6px 10px;'
                'margin-bottom:10px;font-weight:700;font-size:0.82rem;color:#922B21;">⚠️ Challenging Arguments</div>',
                unsafe_allow_html=True,
            )
            for arg in cha_args:
                _render_arg_card(arg, edits_done, reviewer_role)

    # ------------------------------------------------------------------ add argument
    st.divider()
    st.markdown(f"#### Add {reviewer_role} Argument")

    # Pre-filled text varies by domain
    if domain == "manufacturing":
        prefill_text = (
            "AHU-1-DISCH-T is positioned in the mixed air plenum on EQ-7700 units per section 4.2 "
            "of the equipment documentation. The DISCH abbreviation refers to the discharge side of "
            "the mixing box, not the AHU discharge outlet. Option C (Mixed_Air_Temperature_Sensor) "
            "is the only mapping consistent with both the sensor's physical location and the "
            "manufacturer's naming convention documentation."
        )
    else:
        prefill_text = (
            "Patient has a documented family history of paroxysmal atrial fibrillation. "
            "The current HRV decline pattern, combined with rising nocturnal BP readings, "
            "mirrors the prodromal profile seen before arrhythmia onset in first-degree relatives. "
            "Option C is the only plan that simultaneously addresses the cardiovascular, metabolic, "
            "and sleep contributors — deferring any of these risks compounding the others."
        )

    with st.expander(f"➕ Add an argument as {reviewer_role}"):
        with st.form("add_arg_form"):
            st.markdown(
                f'<div style="font-size:0.82rem;color:#2E86AB;margin-bottom:10px;">'
                f'{reviewer_icon} Speaking as: <strong>{html.escape(reviewer_role)}</strong></div>',
                unsafe_allow_html=True,
            )
            f_col1, f_col2 = st.columns(2)
            with f_col1:
                new_option = st.selectbox(
                    "Relates to option", ["A", "B", "C"],
                    format_func=lambda x: f"Option {x}: {options[x][:45]}…",
                )
            with f_col2:
                new_type = st.radio("Argument type", ["support", "challenge"], horizontal=True)
            new_content = st.text_area(
                "Argument content", height=90,
                value=prefill_text,
            )
            if st.form_submit_button("Add Argument", type="primary"):
                if new_content.strip():
                    new_arg = {
                        "argument_id": f"reviewer_{uuid.uuid4().hex[:8]}",
                        "content": new_content.strip(),
                        "type": new_type,
                        "agent_role": reviewer_role,
                        "option": new_option,
                        "tau": 0.85,
                        "evidence_refs": [],
                        "final_score": None,
                        "editor_role": reviewer_role,
                    }
                    updated, scores, new_conf = add_human_argument(
                        st.session_state.arguments,
                        new_arg,
                        st.session_state.session_id,
                    )
                    st.session_state.arguments = updated
                    st.session_state.arg_scores = scores
                    st.session_state.option_confidence = new_conf
                    st.session_state.phase3_complete = True
                    st.success(f"Argument added by {reviewer_role} and scores recomputed.")
                    st.rerun()
                else:
                    st.error("Please enter argument content.")
