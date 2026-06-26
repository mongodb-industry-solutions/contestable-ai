from __future__ import annotations
from datetime import datetime
from argumentation.qbaf import run_scoring
from data import db


def apply_edits_and_rescore(
    arguments: list[dict],
    edits: dict[str, dict],
    session_id: str,
) -> tuple[list[dict], dict[str, float], dict[str, float]]:
    """
    Apply human edits to the argument list, rerun QBAF scoring, and persist to MongoDB.

    edits: { argument_id: {"edit_type": "accept"|"reject"|"modify", "content": str, "editor_role": str} }

    Returns updated arguments, new per-argument scores, new per-option confidence.
    """
    updated = []
    for arg in arguments:
        arg = dict(arg)
        aid = arg["argument_id"]
        if aid in edits:
            edit = edits[aid]
            edit_type = edit["edit_type"]
            arg["human_edit"] = True
            arg["edit_type"] = edit_type
            arg["editor_role"] = edit.get("editor_role", "Clinician")
            arg["timestamp"] = datetime.utcnow()

            if edit_type == "reject":
                arg["is_rejected"] = True
            elif edit_type == "modify":
                arg["original_content"] = arg.get("original_content") or arg["content"]
                arg["content"] = edit["content"]
                arg["is_rejected"] = False
            elif edit_type == "accept":
                arg["is_rejected"] = False
        updated.append(arg)

    scores, confidence = run_scoring(updated)

    # Attach final scores back onto each argument
    for arg in updated:
        arg["final_score"] = scores.get(arg["argument_id"])

    db.save_arguments(updated)
    return updated, scores, confidence


def add_human_argument(
    arguments: list[dict],
    new_arg: dict,
    session_id: str,
) -> tuple[list[dict], dict[str, float], dict[str, float]]:
    """Append a new human-authored argument, rescore, and persist."""
    new_arg["session_id"] = session_id
    new_arg["human_edit"] = True
    new_arg["edit_type"] = "add"
    new_arg["timestamp"] = datetime.utcnow()
    new_arg["is_rejected"] = False

    arguments = list(arguments) + [new_arg]
    scores, confidence = run_scoring(arguments)

    for arg in arguments:
        arg["final_score"] = scores.get(arg["argument_id"])

    db.save_arguments(arguments)
    return arguments, scores, confidence
