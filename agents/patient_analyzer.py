from __future__ import annotations
import json
import re
from datetime import timezone

from crewai import Agent, Crew, Process, Task

from data import db
from data.config import embed_query, make_crewai_llm
from data.models import PatientContext


def _aggregate_telemetry(readings: list[dict]) -> dict:
    """Aggregate raw telemetry into per-device trend summaries."""
    cgm, hrv, sleep, bp_sys, bp_dia = [], [], [], [], []

    for r in readings:
        device = r["metadata"]["device"]
        val = float(r["value"])
        if device == "cgm":
            cgm.append((r["timestamp"], val))
        elif device == "wearable_hrv":
            hrv.append((r["timestamp"], val))
        elif device == "wearable_sleep":
            sleep.append((r["timestamp"], val))
        elif device == "bp_cuff":
            if r["metadata"].get("reading") == "systolic":
                bp_sys.append((r["timestamp"], val))
            else:
                bp_dia.append((r["timestamp"], val))

    def trend_str(series: list[tuple], label: str, unit: str) -> str:
        if not series:
            return f"{label}: no data"
        vals = [v for _, v in series]
        first_3 = [v for _, v in series[:3]]
        last_3 = [v for _, v in series[-3:]]
        avg_start = sum(first_3) / len(first_3)
        avg_end = sum(last_3) / len(last_3)
        direction = "↑ rising" if avg_end > avg_start + 1 else ("↓ declining" if avg_end < avg_start - 1 else "→ stable")
        return (
            f"{label}: start≈{avg_start:.1f}{unit}, current≈{avg_end:.1f}{unit}, "
            f"3-wk avg={sum(vals)/len(vals):.1f}{unit} — {direction}"
        )

    return {
        "glucose": trend_str(cgm, "Glucose (CGM)", " mmol/L"),
        "hrv": trend_str(hrv, "HRV", "ms"),
        "sleep": trend_str(sleep, "Sleep", "h"),
        "bp_systolic": trend_str(bp_sys, "BP Systolic", " mmHg"),
        "bp_diastolic": trend_str(bp_dia, "BP Diastolic", " mmHg"),
        "raw": {
            "cgm_last5_avg": round(sum(v for _, v in cgm[-15:]) / max(1, len(cgm[-15:])), 1),
            "hrv_first": round(sum(v for _, v in hrv[:3]) / max(1, len(hrv[:3])), 1) if hrv else None,
            "hrv_last": round(sum(v for _, v in hrv[-3:]) / max(1, len(hrv[-3:])), 1) if hrv else None,
            "bp_sys_first": round(sum(v for _, v in bp_sys[:3]) / max(1, len(bp_sys[:3])), 0) if bp_sys else None,
            "bp_sys_last": round(sum(v for _, v in bp_sys[-3:]) / max(1, len(bp_sys[-3:])), 0) if bp_sys else None,
            "sleep_avg": round(sum(v for _, v in sleep) / max(1, len(sleep)), 1) if sleep else None,
        },
    }


def _extract_json(text: str) -> dict:
    text = text.strip()
    block = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if block:
        return json.loads(block.group(1).strip())
    obj = re.search(r"\{[\s\S]*\}", text)
    if obj:
        return json.loads(obj.group())
    return json.loads(text)


def run_patient_analyzer(patient_id: str = "PAT-0074", session_id: str = "") -> PatientContext:
    """
    Phase 1: Analyze device telemetry, compute complexity, retrieve similar cases.
    Returns a PatientContext with all fields populated.
    """
    readings = db.get_telemetry_for_patient(patient_id)
    trends = _aggregate_telemetry(readings)
    trends_text = "\n".join(f"  {k}: {v}" for k, v in trends.items() if k != "raw")

    agent = Agent(
        role="Senior IoMT Data Analyst",
        goal="Analyze patient IoMT device trends and produce a structured clinical complexity assessment",
        backstory=(
            "You are a specialist in Internet of Medical Things (IoMT) data analytics with 20+ years "
            "of experience in geriatric care. You synthesize multi-device telemetry into actionable "
            "clinical summaries and can identify patterns of multi-system decline in elderly patients."
        ),
        llm=make_crewai_llm(),
        verbose=False,
    )

    task = Task(
        description=f"""
Analyze the following 3-week IoMT device trend summary for patient {patient_id} (74yo male):

DEVICE TRENDS:
{trends_text}

RAW STATS:
  Glucose last 5 days avg: {trends['raw']['cgm_last5_avg']} mmol/L
  HRV: {trends['raw']['hrv_first']}ms (start) → {trends['raw']['hrv_last']}ms (now)
  BP Systolic: {trends['raw']['bp_sys_first']} (start) → {trends['raw']['bp_sys_last']} mmHg (now)
  Sleep avg: {trends['raw']['sleep_avg']} hours

Provide your assessment as a JSON object with exactly these fields:
{{
  "complexity_score": "High",
  "complexity_reason": "2-3 sentence explanation of why complexity is High",
  "patient_summary": "3-4 sentence clinical summary of the patient's current status",
  "key_concerns": ["concern 1", "concern 2", "concern 3"],
  "glucose_trend": "one sentence describing the glucose trend",
  "hrv_trend": "one sentence describing the HRV trend",
  "bp_trend": "one sentence describing the BP trend",
  "sleep_trend": "one sentence describing the sleep trend"
}}

Return ONLY the JSON object.
""",
        expected_output="JSON object with complexity assessment",
        agent=agent,
    )

    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
    result = crew.kickoff()
    parsed = _extract_json(result.raw)

    # Embed patient summary for vector search (query mode for retrieval)
    embedding = embed_query(parsed.get("patient_summary", ""))

    # Retrieve similar cases
    similar_cases = db.vector_search_cases(embedding, k=3)

    ctx = PatientContext(
        patient_id=patient_id,
        complexity_score=parsed.get("complexity_score", "High"),
        complexity_reason=parsed.get("complexity_reason", ""),
        patient_summary=parsed.get("patient_summary", ""),
        key_concerns=parsed.get("key_concerns", []),
        glucose_trend=parsed.get("glucose_trend", ""),
        hrv_trend=parsed.get("hrv_trend", ""),
        bp_trend=parsed.get("bp_trend", ""),
        sleep_trend=parsed.get("sleep_trend", ""),
        similar_cases=similar_cases,
    )

    if session_id:
        db.save_context(ctx.model_dump(), session_id, "healthcare")

    return ctx
