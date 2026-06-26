from __future__ import annotations
import streamlit as st


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown(
            """
            <div style="background:#1B4F72;padding:16px 12px;border-radius:8px;margin-bottom:16px;">
                <h2 style="color:white;margin:0;font-size:1.1rem;">IoMT Contestable AI</h2>
                <p style="color:#AED6F1;margin:4px 0 0;font-size:0.75rem;">
                    Post-Event Trend Review
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

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

        st.divider()

        st.markdown("#### Reviewing Clinician")
        st.markdown(
            """
            <div style="background:#EBF5FB;border:1px solid #AED6F1;border-radius:8px;
                         padding:10px 12px;display:flex;align-items:center;gap:10px;">
                <span style="font-size:1.4rem;">🩺</span>
                <div>
                    <div style="font-weight:700;font-size:0.85rem;color:#1B4F72;">
                        Family Physician
                    </div>
                    <div style="font-size:0.75rem;color:#2E86AB;">Reviewing Clinician</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.divider()
        with st.expander("🎯 Demo Guide", expanded=False):
            st.markdown(
                """
This demo shows AI making a contestable decision — where human expertise can challenge, override, and audit the outcome in real time. 

---

**Phase 1 — Patient Overview**
- Click **▶ Run Phase 1**
- Wait ~20s for the AI to analyse PAT-0074's IoMT data
- Review the trends and complexity score

---

**Phase 2 — Argumentation**
- Click **▶ Run Phase 2**
- Watch 4 specialist agents generate arguments live (~2 min)
- Note: **Option A leads** at ~100% confidence

---

**Phase 3 — Contestation** 
1. Select **Option C** using the radio buttons
2. Find the **Cardiologist ⚠️ Challenge** card
3. Click **✗** to reject it
4. Scroll to **Add GP Argument** → Option C, support
5. Text is pre-filled — click **Add Argument**
6. Click **🔄 Recompute Scores**
7. **Option C overtakes Option A** ✅

---

**Phase 4 — Care Plan**
- Click **▶ Generate Care Plan**
- Show the before/after chart and Audit Trail

---

 All data generated is saved in MongoDB including past cases and everything is auditable.
                """,
            )

        st.divider()

        # Phase status
        st.markdown("#### Phase Status")
        phases = [
            ("1", "Patient Overview", "phase1_complete"),
            ("2", "Argumentation", "phase2_complete"),
            ("3", "Contestation", "phase3_complete"),
            ("4", "Care Plan", "phase4_complete"),
        ]
        for num, label, key in phases:
            done = st.session_state.get(key, False)
            colour = "#27AE60" if done else "#BDC3C7"
            icon = "✓" if done else num
            st.markdown(
                f"""
                <div style="display:flex;align-items:center;margin-bottom:6px;">
                    <div style="width:22px;height:22px;border-radius:50%;background:{colour};
                                color:white;font-size:0.7rem;font-weight:700;
                                display:flex;align-items:center;justify-content:center;
                                margin-right:8px;flex-shrink:0;">{icon}</div>
                    <span style="font-size:0.85rem;color:{'#2C3E50' if done else '#888'};">{label}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        if st.session_state.get("session_id"):
            st.divider()
            st.markdown(
                f"<div style='font-size:0.7rem;color:#aaa;'>Session: "
                f"{st.session_state.session_id[:8]}…</div>",
                unsafe_allow_html=True,
            )
