from __future__ import annotations
import json
import re
import uuid
from datetime import datetime, timezone

from crewai import Agent, Crew, Process, Task

from argumentation.qbaf import run_scoring
from data import db
from data.config import make_crewai_llm
from data.models import CARE_OPTIONS, PatientContext

_OPTION_DESCRIPTIONS = "\n".join(
    f"  Option {k}: {v}" for k, v in CARE_OPTIONS.items()
)

_SPECIALIST_CONFIGS = {
    "Endocrinologist": {
        "goal": "Evaluate glycaemic control and insulin management options for this patient",
        "backstory": (
            "You are a consultant endocrinologist specialising in diabetes technology and CGM interpretation. "
            "You focus primarily on glucose trends, HbA1c trajectory, and insulin dosing strategies. "
            "You place high evidential weight on CGM spike patterns as indicators of urgent need."
        ),
    },
    "Cardiologist": {
        "goal": "Evaluate cardiovascular risk from HRV decline and blood pressure trajectory",
        "backstory": (
            "You are an interventional cardiologist with expertise in remote cardiac monitoring. "
            "You interpret HRV and blood pressure telemetry to assess arrhythmia risk, hypertensive urgency, "
            "and the need for cardiology workup. You weigh cardiac risk signals carefully but contextually."
        ),
    },
    "Sleep Medicine": {
        "goal": "Assess the clinical impact of sleep disruption and its systemic downstream effects",
        "backstory": (
            "You are a sleep medicine specialist who understands how poor sleep quality drives "
            "metabolic, cardiovascular, and cognitive decline in elderly patients. "
            "You advocate for treating sleep disruption as a root cause, not a secondary concern."
        ),
    },
    "Geriatrician": {
        "goal": "Synthesise all device streams into a holistic recommendation tailored to elderly patient complexity",
        "backstory": (
            "You are a consultant geriatrician with 25 years of experience managing multi-morbid elderly patients. "
            "You weigh all clinical streams together, considering frailty, polypharmacy, and the risk of "
            "under- or over-treating multiple concurrent conditions in an older adult."
        ),
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


def _build_cases_text(cases: list[dict]) -> str:
    lines = []
    for i, c in enumerate(cases, 1):
        lines.append(
            f"  Case {i} (age {c.get('age', '?')}): {c.get('summary', '')[:200]} "
            f"→ Outcome: {c.get('outcome', '?')} | Changes: {'; '.join(c.get('care_plan_changes', [])[:2])}"
        )
    return "\n".join(lines) if lines else "  No similar cases available."


def run_single_specialist(
    role: str,
    patient_context: PatientContext,
    session_id: str,
) -> list[dict]:
    """Run one specialist agent; returns list of 6 argument dicts (2 per option)."""
    config = _SPECIALIST_CONFIGS[role]
    cases_text = _build_cases_text(patient_context.similar_cases)

    agent = Agent(
        role=f"{role} Specialist",
        goal=config["goal"],
        backstory=config["backstory"],
        llm=make_crewai_llm(),
        verbose=False,
    )

    task = Task(
        description=f"""
You are the {role} on the clinical AI panel for patient PAT-0074, a 74-year-old male IoMT patient.

PATIENT SUMMARY:
{patient_context.patient_summary}

KEY CONCERNS:
{chr(10).join(f'  - {c}' for c in patient_context.key_concerns)}

DEVICE TRENDS (your evidence base):
  Glucose: {patient_context.glucose_trend}
  HRV: {patient_context.hrv_trend}
  BP: {patient_context.bp_trend}
  Sleep: {patient_context.sleep_trend}

SIMILAR HISTORICAL CASES (cite these as evidence where relevant):
{cases_text}

THREE CARE PLAN OPTIONS UNDER CONSIDERATION:
{_OPTION_DESCRIPTIONS}

YOUR TASK:
For each of the three options (A, B, C), produce exactly ONE supporting argument and ONE challenging argument
from your specialist perspective. Cite specific device readings or historical cases.

Assign tau (intrinsic strength 0.0-1.0) based on how well-evidenced and clinically sound the argument is.
Be honest — assign lower tau to weaker arguments even if they nominally support a preferred option.

Return ONLY a JSON object in this exact format:
{{
  "arguments": [
    {{
      "option": "A",
      "type": "support",
      "content": "As the {role}, I support Option A because...",
      "tau": 0.82,
      "evidence_refs": ["hist_001", "specific device reading"]
    }},
    {{
      "option": "A",
      "type": "challenge",
      "content": "However, Option A is challenged by...",
      "tau": 0.55,
      "evidence_refs": ["hist_003"]
    }},
    {{
      "option": "B",
      "type": "support",
      "content": "...",
      "tau": 0.70,
      "evidence_refs": []
    }},
    {{
      "option": "B",
      "type": "challenge",
      "content": "...",
      "tau": 0.60,
      "evidence_refs": []
    }},
    {{
      "option": "C",
      "type": "support",
      "content": "...",
      "tau": 0.65,
      "evidence_refs": []
    }},
    {{
      "option": "C",
      "type": "challenge",
      "content": "...",
      "tau": 0.50,
      "evidence_refs": []
    }}
  ]
}}

Return ONLY the JSON object. No preamble or explanation.
""",
        expected_output="JSON with 6 arguments (2 per option: 1 support + 1 challenge)",
        agent=agent,
    )

    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
    result = crew.kickoff()
    parsed = _extract_json(result.raw)

    arguments = []
    for raw_arg in parsed.get("arguments", []):
        arg = {
            "argument_id": f"{role[:4].lower()}_{raw_arg['option']}_{raw_arg['type'][:3]}_{uuid.uuid4().hex[:6]}",
            "session_id": session_id,
            "content": raw_arg["content"],
            "type": raw_arg["type"],
            "agent_role": role,
            "option": raw_arg["option"],
            "tau": float(raw_arg.get("tau", 0.5)),
            "evidence_refs": raw_arg.get("evidence_refs", []),
            "final_score": None,
            "human_edit": False,
            "edit_type": None,
            "original_content": None,
            "editor_role": None,
            "is_rejected": False,
            "timestamp": datetime.now(timezone.utc),
        }
        arguments.append(arg)

    return arguments


def run_specialist_agents(
    patient_context: PatientContext,
    session_id: str,
) -> tuple[list[dict], dict[str, float], dict[str, float]]:
    """
    Phase 2: Run all 4 specialist agents, score arguments via QBAF.
    Returns (arguments, per_argument_scores, per_option_confidence).
    """
    all_arguments: list[dict] = []

    for role in _SPECIALIST_CONFIGS:
        print(f"  Running {role} agent...")
        args = run_single_specialist(role, patient_context, session_id)
        all_arguments.extend(args)

    # Score all arguments
    scores, confidence = run_scoring(all_arguments)
    for arg in all_arguments:
        arg["final_score"] = scores.get(arg["argument_id"])

    # Persist to MongoDB
    db.save_arguments(all_arguments)

    return all_arguments, scores, confidence
