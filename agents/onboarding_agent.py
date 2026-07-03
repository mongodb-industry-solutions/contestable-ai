from __future__ import annotations
import json
import re
from datetime import datetime, timezone

from crewai import Agent, Crew, Process, Task

from data import db
from data.config import make_crewai_llm
from data.models import MAPPING_OPTIONS, SiteContext

_OPTION_DESCRIPTIONS = "\n".join(
    f"  Option {k}: {v}" for k, v in MAPPING_OPTIONS.items()
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


def run_onboarding_agent(
    site_context: SiteContext,
    arguments: list[dict],
    option_scores_before: dict[str, float],
    option_scores_after: dict[str, float],
    session_id: str,
) -> dict:
    """
    Phase 4 (manufacturing): Generate onboarding record from validated arguments.
    Returns onboarding record dict and persists to MongoDB.
    """
    if not option_scores_after:
        option_scores_after = {opt: 0.0 for opt in ["A", "B", "C"]}
    recommended_option = max(option_scores_after, key=option_scores_after.get)

    active = [a for a in arguments if not a.get("is_rejected", False)]
    sorted_args = sorted(active, key=lambda a: a.get("final_score", 0), reverse=True)
    top_args = sorted_args[:6]

    top_args_text = "\n".join(
        f"  [{a['agent_role']} | Opt {a['option']} | {a['type']} | score={a.get('final_score', 0):.3f}]: {a['content'][:150]}"
        for a in top_args
    )

    scores_text = "\n".join(
        f"  Option {opt}: before={option_scores_before.get(opt, 0):.3f} -> after={option_scores_after.get(opt, 0):.3f}"
        for opt in ["A", "B", "C"]
    )

    edits = [a for a in arguments if a.get("human_edit")]
    rejected = [a for a in edits if a.get("is_rejected")]
    modified = [a for a in edits if a.get("edit_type") == "modify"]
    added = [a for a in edits if a.get("edit_type") == "add"]

    agent = Agent(
        role="Brick Ontology Integration Specialist",
        goal="Generate a structured onboarding record documenting the verified HVAC point mapping decision",
        backstory=(
            "You are a Brick ontology integration specialist who documents verified metadata mapping decisions "
            "for HVAC systems. You write clearly for building automation engineers, citing the evidence and "
            "noting how human expert review shaped the final verified mapping."
        ),
        llm=make_crewai_llm(),
        verbose=False,
    )

    task = Task(
        description=f"""
Generate an onboarding record for site {site_context.site_id}, equipment {site_context.equipment_series}.

FOCUS POINT: {site_context.focus_point}
POINT DESCRIPTION: {site_context.point_description}

MAPPING OPTIONS:
{_OPTION_DESCRIPTIONS}

OPTION CONFIDENCE SCORES (before -> after expert review):
{scores_text}

VERIFIED MAPPING (highest confidence after expert review): Option {recommended_option}
= {MAPPING_OPTIONS[recommended_option]}

EXPERT REVIEW SUMMARY:
  - {len(rejected)} argument(s) rejected
  - {len(modified)} argument(s) modified
  - {len(added)} argument(s) added by domain expert

TOP ARGUMENTS BY FINAL SCORE:
{top_args_text}

Generate a structured onboarding record as a JSON object with exactly these fields:
{{
  "verified_brick_class": "{MAPPING_OPTIONS[recommended_option]}",
  "confidence_pct": {int(option_scores_after.get(recommended_option, 0) * 100)},
  "rationale": "2-3 sentence explanation of why this mapping was selected, referencing key arguments and the expert review outcome",
  "propagation_steps": [
    "Step 1: ...",
    "Step 2: ...",
    "Step 3: ...",
    "Step 4: ..."
  ],
  "decisive_arguments": [
    "Most decisive argument summary (include agent role and score)",
    "Second most decisive argument",
    "Third most decisive argument"
  ],
  "confidence_summary": "One paragraph summarising confidence levels and what changed during expert review"
}}

Return ONLY the JSON object.
""",
        expected_output="JSON onboarding record",
        agent=agent,
    )

    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
    result = crew.kickoff()
    parsed = _extract_json(result.raw)

    audit_entries = []
    for arg in arguments:
        if arg.get("human_edit"):
            audit_entries.append({
                "argument_id": arg["argument_id"],
                "original_content": arg.get("original_content") or arg["content"],
                "current_content": arg["content"],
                "edit_type": arg.get("edit_type"),
                "editor_role": arg.get("editor_role", "Brick Domain Expert"),
                "agent_role": arg["agent_role"],
                "option": arg["option"],
                "timestamp": arg.get("timestamp", datetime.now(timezone.utc)),
            })

    record = {
        "session_id": session_id,
        "site_id": site_context.site_id,
        "focus_point": site_context.focus_point,
        "equipment_series": site_context.equipment_series,
        "timestamp": datetime.now(timezone.utc),
        "verified_brick_class": parsed.get("verified_brick_class", MAPPING_OPTIONS[recommended_option]),
        "confidence_pct": parsed.get("confidence_pct", int(option_scores_after.get(recommended_option, 0) * 100)),
        "rationale": parsed.get("rationale", ""),
        "propagation_steps": parsed.get("propagation_steps", []),
        "decisive_arguments": parsed.get("decisive_arguments", []),
        "option_scores_before": option_scores_before,
        "option_scores_after": option_scores_after,
        "confidence_summary": parsed.get("confidence_summary", ""),
        "audit_entries": audit_entries,
    }

    db.save_onboarding_record(record)
    return record
