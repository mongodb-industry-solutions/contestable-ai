from __future__ import annotations
import streamlit as st

from data.models import DOMAIN_CONFIGS


def render_sidebar() -> None:
    domain = st.session_state.get("domain", "healthcare")
    cfg = DOMAIN_CONFIGS[domain]

    with st.sidebar:
        # ------------------------------------------------------------------ header
        st.markdown(
            f"""
            <div style="background:#1B4F72;padding:16px 12px;border-radius:8px;margin-bottom:16px;">
                <h2 style="color:white;margin:0;font-size:1.1rem;">
                    {cfg["icon"]} Contestable AI
                </h2>
                <p style="color:#AED6F1;margin:4px 0 0;font-size:0.75rem;">
                    {cfg["subtitle"]}
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ------------------------------------------------------------------ subject panel
        if domain == "healthcare":
            st.markdown("#### Patient")
            st.markdown(
                """
                <div style="background:#EBF5FB;border:1px solid #AED6F1;border-radius:8px;padding:12px;">
                    <strong>Patient ID: PAT-0074</strong><br/>
                    <span style="color:#555;font-size:0.85rem;">74 years old &nbsp;·&nbsp; Male</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown("#### Connected Devices")
            devices = [
                ("🩸", "Continuous Glucose Monitor", "CGM readings ×3/day"),
                ("⌚", "Wearable (HRV + Sleep)", "Overnight + morning sync"),
                ("💉", "Blood Pressure Cuff", "Daily morning reading"),
            ]
            for icon, name, detail in devices:
                st.markdown(
                    f"""
                    <div style="display:flex;align-items:flex-start;margin-bottom:8px;">
                        <span style="font-size:1.1rem;margin-right:8px;">{icon}</span>
                        <div>
                            <div style="font-size:0.85rem;font-weight:600;">{name}</div>
                            <div style="font-size:0.75rem;color:#888;">{detail}</div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            st.markdown("#### Review Period")
            st.markdown(
                "<div style='font-size:0.85rem;color:#555;'>Past 21 days (3 weeks)</div>",
                unsafe_allow_html=True,
            )

            st.markdown("#### Reviewing Clinician")
            st.markdown(
                """
                <div style="background:#EBF5FB;border:1px solid #AED6F1;border-radius:8px;
                             padding:10px 12px;display:flex;align-items:center;gap:10px;">
                    <span style="font-size:1.4rem;">🩺</span>
                    <div>
                        <div style="font-weight:700;font-size:0.85rem;color:#1B4F72;">Family Physician</div>
                        <div style="font-size:0.75rem;color:#2E86AB;">Reviewing Clinician</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        else:  # manufacturing
            st.markdown("#### Site")
            st.markdown(
                """
                <div style="background:#EBF5FB;border:1px solid #AED6F1;border-radius:8px;padding:12px;">
                    <strong>Site ID: SITE-0042</strong><br/>
                    <span style="color:#555;font-size:0.85rem;">
                        Commercial Office Building &nbsp;·&nbsp; Chicago, IL
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown("#### Equipment")
            st.markdown(
                """
                <div style="display:flex;align-items:flex-start;margin-bottom:8px;">
                    <span style="font-size:1.1rem;margin-right:8px;">🌡️</span>
                    <div>
                        <div style="font-size:0.85rem;font-weight:600;">HVAC Systems Manufacturer EQ-7700</div>
                        <div style="font-size:0.75rem;color:#888;">247 points · 18 ambiguous</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown("#### Focus Point")
            st.markdown(
                """
                <div style="background:#EBF5FB;border:1px solid #AED6F1;border-radius:8px;
                             padding:10px 12px;">
                    <code style="font-size:0.95rem;color:#1B4F72;font-weight:700;">AHU-1-DISCH-T</code>
                    <div style="font-size:0.75rem;color:#2E86AB;margin-top:4px;">Ambiguous temperature sensor</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown("#### Reviewing Expert")
            st.markdown(
                """
                <div style="background:#EBF5FB;border:1px solid #AED6F1;border-radius:8px;
                             padding:10px 12px;display:flex;align-items:center;gap:10px;">
                    <span style="font-size:1.4rem;">🏗️</span>
                    <div>
                        <div style="font-weight:700;font-size:0.85rem;color:#1B4F72;">Brick Domain Expert</div>
                        <div style="font-size:0.75rem;color:#2E86AB;">Reviewing Mapping Proposal</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.divider()

        # ------------------------------------------------------------------ demo guide
        with st.expander("🎯 Demo Guide", expanded=False):
            if domain == "healthcare":
                st.markdown(
                    """
This demo shows AI making a contestable care plan decision. Human expertise can challenge, override, and audit the outcome in real time.

---

**Phase 1 — Patient Overview**
- Click **▶ Run Phase 1**
- Wait ~20s for AI to analyse PAT-0074's IoMT data
- Review the trends and complexity score

---

**Phase 2 — Argumentation**
- Click **▶ Run Phase 2**
- Watch 4 specialist agents generate arguments live (~2 min)
- Note: **Option A leads** at ~100% confidence

---

**Phase 3 — Contestation**
1. Select **Option C** using the radio buttons
2. Find the **Cardiologist** challenge card
3. Click **✗** to reject it
4. Scroll to **Add GP Argument** → Option C, support
5. Text is pre-filled — click **Add Argument**
6. Click **🔄 Recompute Scores**
7. **Option C overtakes Option A** ✅

---

**Phase 4 — Care Plan**
- Click **▶ Generate Care Plan**
- Review the before/after chart and Audit Trail

---

All data is saved in MongoDB and every action is auditable.
                    """
                )
            else:
                st.markdown(
                    """
This demo shows AI proposing an HVAC metadata mapping that a domain expert can challenge and correct with a full audit trail.

---

**Phase 1 — Site Overview**
- Click **▶ Run Phase 1**
- Wait ~20s for AI to analyse SITE-0042's point names
- Note the focus point **AHU-1-DISCH-T** and the similar verified mappings

---

**Phase 2 — Mapping Analysis**
- Click **▶ Run Phase 2**
- Watch 2 agents debate the mapping (~1 min)
- **String Matcher** favors Option B (Discharge)
- **Documentation Reader** favors Option C (Mixed Air)

---

**Phase 3 — Expert Review**
1. Select **Option C** using the radio buttons
2. Find the **String Matcher** challenge card
3. Click **✗** to reject it
4. Open **Add Expert Argument** → Option C, support
5. Text is pre-filled — click **Add Argument**
6. Click **🔄 Recompute Scores**
7. **Option C wins** with documentation backing ✅

---

**Phase 4 — Onboarding Record**
- Click **▶ Generate Onboarding Record**
- Review the verified Brick class, propagation steps, and Audit Trail

---

All mapping decisions and expert review actions are saved in MongoDB.
                    """
                )

        st.divider()

        # ------------------------------------------------------------------ phase status
        st.markdown("#### Phase Status")
        phase_labels = cfg["phase_labels"]
        phase_keys = ["phase1_complete", "phase2_complete", "phase3_complete", "phase4_complete"]
        for num, (label, key) in enumerate(zip(phase_labels, phase_keys), 1):
            done = st.session_state.get(key, False)
            colour = "#27AE60" if done else "#BDC3C7"
            icon = "✓" if done else str(num)
            st.markdown(
                f'<div style="display:flex;align-items:center;margin-bottom:6px;">'
                f'<div style="width:22px;height:22px;border-radius:50%;background:{colour};'
                f'color:white;font-size:0.7rem;font-weight:700;'
                f'display:flex;align-items:center;justify-content:center;'
                f'margin-right:8px;flex-shrink:0;">{icon}</div>'
                f'<span style="font-size:0.85rem;color:{"#2C3E50" if done else "#888"};">{label}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.divider()

        # ------------------------------------------------------------------ change domain button
        if st.button("🔄 Change Domain", key="change_domain", use_container_width=True):
            # Reset all phase state when switching domains
            for key in [
                "domain", "phase1_complete", "phase2_complete", "phase3_complete", "phase4_complete",
                "patient_context", "site_context", "arguments", "arg_scores",
                "option_confidence", "option_confidence_initial",
                "care_plan", "onboarding_record", "pending_edits", "modifying_arg",
            ]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

        if st.session_state.get("session_id"):
            st.markdown(
                f"<div style='font-size:0.7rem;color:#aaa;'>Session: "
                f"{st.session_state.session_id[:8]}…</div>",
                unsafe_allow_html=True,
            )
