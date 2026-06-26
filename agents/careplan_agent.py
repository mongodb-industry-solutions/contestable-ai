from __future__ import annotations
import json
import re
from datetime import datetime, timezone

from crewai import Agent, Crew, Process, Task

from data import db
from data.config import make_crewai_llm
from data.models import CARE_OPTIONS, PatientContext

_OPTION_DESCRIPTIONS = "\n".join(
    f"  Option {k}: {v}" for k, v in CARE_OPTIONS.items()
)


def _extract_json(text: str) -> dict:
    text = text.strip()
    block = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if block:
        return json.loads(block.group(1).strip())
    obj = re.search(r"\{[\s\S]*\}", text)
    if obj:
        return json.loads(obj.group())
    return json.loads(text)


def run_careplan_agent(
    patient_context: PatientContext,
    arguments: list[dict],
    option_scores_before: dict[str, float],
    option_scores_after: dict[str, float],
    session_id: str,
) -> dict:
    """
    Phase 4: Generate structured care plan from validated arguments.
    Returns care plan dict and persists to MongoDB.
    """
    if not option_scores_after:
        option_scores_after = {opt: 0.0 for opt in ["A", "B", "C"]}
    recommended_option = max(option_scores_after, key=option_scores_after.get)

    # Prepare top arguments by final score for context
    active = [a for a in arguments if not a.get("is_rejected", False)]
    sorted_args = sorted(active, key=lambda a: a.get("final_score", 0), reverse=True)
    top_args = sorted_args[:6]

    top_args_text = "\n".join(
        f"  [{a['agent_role']} | Opt {a['option']} | {a['type']} | score={a.get('final_score', 0):.3f}]: {a['content'][:150]}"
        for a in top_args
    )

    scores_text = "\n".join(
        f"  Option {opt}: before={option_scores_before.get(opt, 0):.3f} → after={option_scores_after.get(opt, 0):.3f}"
        for opt in ["A", "B", "C"]
    )

    # Count contestation edits
    edits = [a for a in arguments if a.get("human_edit")]
    rejected = [a for a in edits if a.get("is_rejected")]
    modified = [a for a in edits if a.get("edit_type") == "modify"]
    added = [a for a in edits if a.get("edit_type") == "add"]

    agent = Agent(
        role="Senior Clinician and Care Coordinator",
        goal="Generate a clear, evidence-based, clinician-ready care plan for this IoMT patient",
        backstory=(
            "You are a geriatric medicine specialist and care coordinator with expertise in translating "
            "AI-assisted argumentation frameworks into actionable care plans. You write clearly for "
            "clinicians, citing the evidence and noting how human expert input shaped the recommendation."
        ),
        llm=make_crewai_llm(),
        verbose=False,
    )

    task = Task(
        description=f"""
You are generating the final care plan for patient PAT-0074 (74yo male, IoMT patient) based on a completed
multi-agent argumentation and human contestation workflow.

PATIENT (ID: PAT-0074): {patient_context.patient_summary}

CARE PLAN OPTIONS:
{_OPTION_DESCRIPTIONS}

OPTION CONFIDENCE SCORES (before → after human contestation):
{scores_text}

RECOMMENDED OPTION (highest confidence after contestation): Option {recommended_option}
= {CARE_OPTIONS[recommended_option]}

HUMAN CONTESTATION SUMMARY:
  - {len(rejected)} argument(s) rejected
  - {len(modified)} argument(s) modified
  - {len(added)} argument(s) added by clinician

TOP ARGUMENTS BY FINAL SCORE:
{top_args_text}

Generate a structured care plan as a JSON object with exactly these fields:
{{
  "recommended_option": "{recommended_option}",
  "rationale": "2-3 sentence explanation of why this option was selected, referencing key arguments and the contestation outcome",
  "implementation_steps": [
    "Step 1: ...",
    "Step 2: ...",
    "Step 3: ...",
    "Step 4: ..."
  ],
  "decisive_arguments": [
    "Argument summary that was most decisive (include agent role and score)",
    "Second most decisive argument",
    "Third most decisive argument"
  ],
  "confidence_summary": "One paragraph summarising the confidence levels and what changed during contestation"
}}

Return ONLY the JSON object.
""",
        expected_output="JSON care plan",
        agent=agent,
    )

    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
    result = crew.kickoff()
    parsed = _extract_json(result.raw)

    # Assemble audit trail from human-edited arguments
    audit_entries = []
    for arg in arguments:
        if arg.get("human_edit"):
            audit_entries.append({
                "argument_id": arg["argument_id"],
                "original_content": arg.get("original_content") or arg["content"],
                "current_content": arg["content"],
                "edit_type": arg.get("edit_type"),
                "editor_role": arg.get("editor_role", "Clinician"),
                "agent_role": arg["agent_role"],
                "option": arg["option"],
                "timestamp": arg.get("timestamp", datetime.now(timezone.utc)),
            })

    care_plan = {
        "session_id": session_id,
        "patient_id": patient_context.patient_id,
        "timestamp": datetime.now(timezone.utc),
        "recommended_option": parsed.get("recommended_option", recommended_option),
        "rationale": parsed.get("rationale", ""),
        "implementation_steps": parsed.get("implementation_steps", []),
        "decisive_arguments": parsed.get("decisive_arguments", []),
        "option_scores_before": option_scores_before,
        "option_scores_after": option_scores_after,
        "confidence_summary": parsed.get("confidence_summary", ""),
        "audit_entries": audit_entries,
    }

    db.save_care_plan(care_plan)
    return care_plan
