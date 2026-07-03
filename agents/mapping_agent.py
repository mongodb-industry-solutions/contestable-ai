from __future__ import annotations
import json
import re
import uuid
from datetime import datetime, timezone

from crewai import Agent, Crew, Process, Task

from argumentation.qbaf import run_scoring
from data import db
from data.config import make_crewai_llm
from data.models import MAPPING_OPTIONS, SiteContext

_OPTION_DESCRIPTIONS = "\n".join(
    f"  Option {k}: {v}" for k, v in MAPPING_OPTIONS.items()
)

_AGENT_CONFIGS = {
    "String Matcher": {
        "goal": "Determine the most likely Brick ontology mapping for the HVAC point name using only string pattern analysis",
        "backstory": (
            "You are a string-pattern matching specialist who maps HVAC point names to ontology classes "
            "purely by analysing the name's abbreviations and structure. You have no access to equipment "
            "documentation or physical installation details — your judgment comes entirely from the text "
            "of the point name itself and common HVAC naming conventions across the industry."
        ),
        "rule": (
            "You can ONLY use the point name string itself. Do not reference any documentation or sensor "
            "location information. Base all arguments solely on the abbreviations and structure of the name."
        ),
    },
    "Documentation Reader": {
        "goal": "Determine the correct Brick ontology mapping by reading equipment documentation fragments",
        "backstory": (
            "You are a documentation analyst who maps HVAC points to ontology classes by reading equipment "
            "manuals, point lists, and installation guides. You prioritise explicit manufacturer documentation "
            "over naming convention assumptions and cite specific sections when making your case."
        ),
        "rule": (
            "You MUST base your arguments on the documentation fragments provided. Cite specific section "
            "numbers or appendix references where relevant. Do not assume from the name alone — ground "
            "every argument in what the documentation actually states."
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


def run_single_mapping_agent(
    role: str,
    site_context: SiteContext,
    session_id: str,
) -> list[dict]:
    """Run one mapping agent; returns list of 6 argument dicts (2 per option)."""
    config = _AGENT_CONFIGS[role]

    fragments_text = "\n\n".join(
        f"[{i+1}] {f}" for i, f in enumerate(site_context.documentation_fragments)
    )

    if role == "String Matcher":
        context_section = (
            f"FOCUS POINT NAME: {site_context.focus_point}\n\n"
            f"CONSTRAINT: {config['rule']}"
        )
    else:
        context_section = (
            f"FOCUS POINT NAME: {site_context.focus_point}\n\n"
            f"EQUIPMENT DOCUMENTATION FRAGMENTS:\n{fragments_text}\n\n"
            f"CONSTRAINT: {config['rule']}"
        )

    agent = Agent(
        role=role,
        goal=config["goal"],
        backstory=config["backstory"],
        llm=make_crewai_llm(),
        verbose=False,
    )

    task = Task(
        description=f"""
You are the {role} on the AI mapping panel for site {site_context.site_id}.
Equipment series: {site_context.equipment_series}.

{context_section}

THREE BRICK ONTOLOGY MAPPING OPTIONS UNDER CONSIDERATION:
{_OPTION_DESCRIPTIONS}

For each of the three options (A, B, C), produce exactly ONE supporting argument and ONE challenging argument
from your specialist perspective.

Assign tau (intrinsic strength 0.0-1.0) based on how well-evidenced the argument is given your information
source. Where your source is ambiguous or inconclusive, assign lower tau values honestly.

Return ONLY a JSON object in this exact format:
{{
  "arguments": [
    {{
      "option": "A",
      "type": "support",
      "content": "As the {role}, I support Option A because...",
      "tau": 0.55,
      "evidence_refs": ["string pattern analysis"]
    }},
    {{
      "option": "A",
      "type": "challenge",
      "content": "However, Option A is challenged because...",
      "tau": 0.65,
      "evidence_refs": []
    }},
    {{
      "option": "B",
      "type": "support",
      "content": "...",
      "tau": 0.75,
      "evidence_refs": []
    }},
    {{
      "option": "B",
      "type": "challenge",
      "content": "...",
      "tau": 0.50,
      "evidence_refs": []
    }},
    {{
      "option": "C",
      "type": "support",
      "content": "...",
      "tau": 0.45,
      "evidence_refs": []
    }},
    {{
      "option": "C",
      "type": "challenge",
      "content": "...",
      "tau": 0.70,
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
        # Sanitise role prefix for argument_id (remove spaces)
        role_prefix = role[:4].lower().replace(" ", "_")
        arg = {
            "argument_id": f"{role_prefix}_{raw_arg['option']}_{raw_arg['type'][:3]}_{uuid.uuid4().hex[:6]}",
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


def run_mapping_agents(
    site_context: SiteContext,
    session_id: str,
) -> tuple[list[dict], dict[str, float], dict[str, float]]:
    """
    Phase 2 (manufacturing): Run both mapping agents, score via QBAF.
    Returns (arguments, per_argument_scores, per_option_confidence).
    """
    all_arguments: list[dict] = []

    for role in _AGENT_CONFIGS:
        print(f"  Running {role} agent...")
        args = run_single_mapping_agent(role, site_context, session_id)
        all_arguments.extend(args)

    scores, confidence = run_scoring(all_arguments)
    for arg in all_arguments:
        arg["final_score"] = scores.get(arg["argument_id"])

    db.save_arguments(all_arguments)

    return all_arguments, scores, confidence
