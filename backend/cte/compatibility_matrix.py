"""Compatibility Matrix V2: versioned, explainable pairwise rules.

No authoritative compatibility score is calculated. Unmatched pairs remain UNKNOWN;
heuristic rules are labeled and must not be presented as validated predictions.
"""
from __future__ import annotations
from itertools import product
from math import isfinite
from typing import Any, Mapping

VERSION = "2.0"
SCIENTIFIC_STATUS = "IMPLEMENTATION_BASELINE"
DOMAINS = {
    "P1": "state_and_resources",
    "P2": "stable_traits",
    "P3": "self_regulation_and_cognition",
    "P4": "values_and_priorities",
    "P5": "behavior_and_social_roles",
}
VALUE_TENSION_RULES = {
    frozenset(("Order", "Autonomy")): "Potential tension between order and autonomy",
    frozenset(("Security", "Freedom")): "Potential tension between security and freedom",
    frozenset(("Achievement", "Compassion")): "Potential tension between achievement and compassion",
}
ROLE_SYNERGY_RULES = {
    frozenset(("Leader", "Strategist")): "SYNERGY",
    frozenset(("Organizer", "Mediator")): "SYNERGY",
    frozenset(("Strategist", "Organizer")): "SYNERGY",
    frozenset(("Leader", "Mediator")): "COMPLEMENT",
}
ROLE_COMPETITION_RULES = {
    frozenset(("Leader", "Leader")), frozenset(("Organizer", "Organizer")),
    frozenset(("Strategist", "Strategist")), frozenset(("Mediator", "Mediator")),
}

def _numeric_profile(profile: Mapping[str, Any], person: str) -> dict[str, float]:
    normalized: dict[str, float] = {}
    for key, value in profile.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(float(value)):
            raise ValueError(f"{person}.{key} must be a finite number")
        normalized[str(key)] = float(value)
    return normalized

def evaluate_compatibility_matrix(
    profile_a: Mapping[str, Any], profile_b: Mapping[str, Any], *,
    roles_a: set[str] | list[str] | tuple[str, ...] = (),
    roles_b: set[str] | list[str] | tuple[str, ...] = (),
    contexts: set[str] | list[str] | tuple[str, ...] = (),
) -> dict[str, Any]:
    """Return explainable findings. Numeric inputs must share a meaningful scale."""
    a, b = _numeric_profile(profile_a, "profile_a"), _numeric_profile(profile_b, "profile_b")
    role_a, role_b = sorted(set(roles_a)), sorted(set(roles_b))
    context_list = sorted(set(contexts))
    rows: list[dict[str, Any]] = []
    for trait in sorted(set(a) | set(b)):
        av, bv = a.get(trait), b.get(trait)
        observed = av is not None and bv is not None
        rows.append({
            "kind": "TRAIT_ALIGNMENT", "pair": [trait, trait], "trait": trait,
            "a_value": av, "b_value": bv,
            "gap": abs(av - bv) if observed else None,
            "status": "OBSERVED_ALIGNMENT" if observed else "UNKNOWN",
            "rule_id": None, "evidence_class": "DESCRIPTIVE" if observed else "NONE",
            "explanation": ("Both values are present; the gap is descriptive, not a compatibility verdict."
                if observed else "No validated rule or complete measurement for this trait."),
            "contexts": context_list,
        })
    common = sorted(set(a) & set(b))
    for left, right in product(common, common):
        if left >= right:
            continue
        pair = frozenset((left, right))
        if pair in VALUE_TENSION_RULES:
            rows.append({
                "kind": "VALUE_TENSION", "pair": sorted(pair),
                "a_priorities": {left: a[left], right: a[right]},
                "b_priorities": {left: b[left], right: b[right]},
                "status": "CONDITIONAL",
                "rule_id": "value_tension." + ".".join(sorted(pair)).lower(),
                "evidence_class": "HEURISTIC", "explanation": VALUE_TENSION_RULES[pair],
                "contexts": context_list, "requires_human_review": True,
            })
    for ra in role_a:
        for rb in role_b:
            pair = frozenset((ra, rb))
            if pair in ROLE_COMPETITION_RULES:
                status, interaction, rule = "CONDITIONAL", "COMPETITION", "role_competition"
            elif pair in ROLE_SYNERGY_RULES:
                status, interaction, rule = "CONDITIONAL", ROLE_SYNERGY_RULES[pair], "role_interaction"
            else:
                status, interaction, rule = "UNKNOWN", "UNKNOWN", None
            rows.append({
                "kind": "ROLE_INTERACTION", "pair": [ra, rb], "interaction": interaction,
                "status": status, "rule_id": rule,
                "evidence_class": "HEURISTIC" if rule else "NONE",
                "explanation": ("Heuristic role interaction; confirm against goals, context and observed behavior."
                    if rule else "No interaction rule registered for this role pair."),
                "contexts": context_list, "requires_human_review": bool(rule),
            })
    known = sum(row["status"] != "UNKNOWN" for row in rows)
    return {
        "version": VERSION, "scientific_status": SCIENTIFIC_STATUS,
        "authoritative_scalar": False,
        "status": "PARTIAL" if rows and known < len(rows) else ("ESTIMATED" if rows else "UNKNOWN"),
        "coverage": {"known_rows": known, "total_rows": len(rows), "unknown_rows": len(rows) - known},
        "domains": DOMAINS.copy(), "rows": rows, "contexts": context_list,
        "limitations": [
            "No authoritative compatibility percentage is produced.",
            "Heuristic rules are not empirically validated predictions.",
            "Missing rules or measurements remain UNKNOWN.",
            "Observed alignment gaps do not establish compatibility or incompatibility.",
        ],
    }
