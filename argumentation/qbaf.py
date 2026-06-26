from __future__ import annotations
import math


def sigmoid(x: float) -> float:
    x = max(-20.0, min(20.0, x))  # clamp to avoid overflow
    return 1.0 / (1.0 + math.exp(-x))


def build_relations(
    arguments: list[dict],
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """
    Build support and attack sets for each argument.

    Within each option:
    - Support arguments support each other (coalition effect)
    - Challenge arguments support each other
    - Challenge arguments attack support arguments and vice versa
    """
    active = [a for a in arguments if not a.get("is_rejected", False)]
    arg_ids = [a["argument_id"] for a in active]

    supporters: dict[str, list[str]] = {aid: [] for aid in arg_ids}
    attackers: dict[str, list[str]] = {aid: [] for aid in arg_ids}

    by_option: dict[str, dict[str, list[str]]] = {}
    for arg in active:
        opt = arg["option"]
        if opt not in by_option:
            by_option[opt] = {"support": [], "challenge": []}
        by_option[opt][arg["type"]].append(arg["argument_id"])

    for opt, groups in by_option.items():
        sup_ids = groups["support"]
        chal_ids = groups["challenge"]

        for a in sup_ids:
            for b in sup_ids:
                if a != b:
                    supporters[a].append(b)

        for a in chal_ids:
            for b in chal_ids:
                if a != b:
                    supporters[a].append(b)

        for c in chal_ids:
            for s in sup_ids:
                attackers[s].append(c)

        for s in sup_ids:
            for c in chal_ids:
                attackers[c].append(s)

    return supporters, attackers


def compute_qbaf_scores(
    arguments: list[dict],
    alpha: float = 0.3,
    iterations: int = 10,
) -> dict[str, float]:
    """
    Iteratively compute final QBAF scores for all non-rejected arguments.
    f(x) = sigmoid(tau(x) + alpha * sum(f(y) : y in R+(x)) - alpha * sum(f(z) : z in R-(x)))
    """
    active = [a for a in arguments if not a.get("is_rejected", False)]
    if not active:
        return {}

    arg_ids = [a["argument_id"] for a in active]
    tau = {a["argument_id"]: float(a["tau"]) for a in active}
    supporters, attackers = build_relations(arguments)

    scores: dict[str, float] = dict(tau)

    for _ in range(iterations):
        new_scores: dict[str, float] = {}
        for aid in arg_ids:
            sup_sum = sum(scores.get(s, 0.0) for s in supporters[aid])
            att_sum = sum(scores.get(a, 0.0) for a in attackers[aid])
            new_scores[aid] = sigmoid(tau[aid] + alpha * sup_sum - alpha * att_sum)
        scores = new_scores

    return scores


def compute_option_confidence(
    arguments: list[dict],
    scores: dict[str, float],
) -> dict[str, float]:
    """
    Per-option confidence = (sum of support final scores - sum of challenge final scores),
    normalized to [0, 1] across all options.
    """
    active = [a for a in arguments if not a.get("is_rejected", False)]
    options = list({a["option"] for a in active})
    if not options:
        return {}

    raw: dict[str, float] = {}
    for opt in options:
        opt_args = [a for a in active if a["option"] == opt]
        sup = sum(scores.get(a["argument_id"], 0.0) for a in opt_args if a["type"] == "support")
        chal = sum(scores.get(a["argument_id"], 0.0) for a in opt_args if a["type"] == "challenge")
        raw[opt] = sup - chal

    values = list(raw.values())
    min_v, max_v = min(values), max(values)

    if max_v == min_v:
        return {opt: 0.5 for opt in options}

    return {opt: round((raw[opt] - min_v) / (max_v - min_v), 4) for opt in options}


def run_scoring(arguments: list[dict]) -> tuple[dict[str, float], dict[str, float]]:
    """Convenience wrapper: returns (scores_per_argument, confidence_per_option)."""
    scores = compute_qbaf_scores(arguments)
    confidence = compute_option_confidence(arguments, scores)
    return scores, confidence
