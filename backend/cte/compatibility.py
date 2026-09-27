"""Compatibility Engine V1.0.

Compatibility is a structured three-vector assessment rather than a single
authoritative percentage. Outputs are model-derived (DRV) unless explicitly
bound to an external/evidence source by the caller.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from statistics import mean
from typing import Any, Mapping

from .provenance import derived_provenance

VERSION = "1.0"

V1_KEYS = ("tempo", "energy", "reactivity", "recovery")
V1_ALIASES = {
    "tempo": ("tempo", "decision_tempo"),
    "energy": ("energy", "subjective_energy"),
    "reactivity": ("reactivity",),
    "recovery": ("recovery", "recovery_index"),
}

ROLE_SYNERGY_DEFAULTS = {
    frozenset(("Leader", "Strategist")): "SYNERGY",
    frozenset(("Organizer", "Mediator")): "SYNERGY",
    frozenset(("Strategist", "Organizer")): "SYNERGY",
    frozenset(("Leader", "Mediator")): "COMPLEMENT",
}

ROLE_COMPETITION_DEFAULTS = {
    frozenset(("Leader", "Leader")): "COMPETITION",
    frozenset(("Organizer", "Organizer")): "COMPETITION",
    frozenset(("Strategist", "Strategist")): "COMPETITION",
    frozenset(("Mediator", "Mediator")): "COMPETITION",
}

POTENTIAL_VALUE_CONFLICTS = {
    frozenset(("Order", "Autonomy")): "Potential tension between order and autonomy",
    frozenset(("Security", "Freedom")): "Potential tension between security and freedom",
    frozenset(("Achievement", "Compassion")): "Potential tension between achievement and compassion",
}


def _rank(values: list[float]) -> list[float]:
    # Average ranks for ties; this is the conventional Spearman treatment.
    indexed = sorted(enumerate(values), key=lambda pair: pair[1])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i
        while j + 1 < len(indexed) and indexed[j + 1][1] == indexed[i][1]:
            j += 1
        average_rank = (i + 1 + j + 1) / 2.0
        for k in range(i, j + 1):
            ranks[indexed[k][0]] = average_rank
        i = j + 1
    return ranks


def _corr(a: list[float], b: list[float]) -> float | None:
    if len(a) < 2:
        return None
    ma, mb = mean(a), mean(b)
    da = [x - ma for x in a]
    db = [y - mb for y in b]
    den = sqrt(sum(x * x for x in da) * sum(y * y for y in db))
    return None if den == 0 else sum(x * y for x, y in zip(da, db)) / den


def spearman(a: list[float], b: list[float]) -> float | None:
    return None if len(a) != len(b) or len(a) < 2 else _corr(_rank(a), _rank(b))


def _value(values: Mapping[str, float], canonical: str) -> float | None:
    for key in V1_ALIASES[canonical]:
        if key in values:
            return float(values[key])
    return None


def _provenance(note: str, payload: Any):
    return derived_provenance("compatibility.engine", VERSION, payload, note)


def compatibility_v1(a: Mapping[str, float], b: Mapping[str, float]) -> dict[str, Any]:
    dimensions: dict[str, dict[str, Any]] = {}
    missing_a: list[str] = []
    missing_b: list[str] = []
    for key in V1_KEYS:
        av, bv = _value(a, key), _value(b, key)
        if av is None:
            missing_a.append(key)
        if bv is None:
            missing_b.append(key)
        dimensions[key] = {
            "a": av,
            "b": bv,
            "delta": None if av is None or bv is None else av - bv,
            "absolute_delta": None if av is None or bv is None else abs(av - bv),
        }
    status = "ESTIMATED" if not (set(missing_a) | set(missing_b)) else "PARTIAL"
    return {
        "vector": "V1",
        "status": status,
        "dimensions": dimensions,
        "missing_a": missing_a,
        "missing_b": missing_b,
        "provenance": _provenance(
            "Model-derived Bio/Tempo alignment deltas",
            {"a": dict(a), "b": dict(b), "dimensions": dimensions},
        ),
    }


def compatibility_v2(a: Mapping[str, float], b: Mapping[str, float]) -> dict[str, Any]:
    common = sorted(set(a) & set(b))
    rho = spearman([float(a[k]) for k in common], [float(b[k]) for k in common]) if len(common) >= 2 else None

    pair_rows: list[dict[str, Any]] = []
    top_alignments: list[dict[str, Any]] = []
    value_gaps: list[dict[str, Any]] = []
    conflict_zones: list[dict[str, Any]] = []

    for key in common:
        delta = float(a[key]) - float(b[key])
        row = {"value": key, "a": float(a[key]), "b": float(b[key]), "delta": delta, "absolute_gap": abs(delta)}
        pair_rows.append(row)

    top_alignments = sorted(pair_rows, key=lambda x: (x["absolute_gap"], x["value"]))[:5]
    value_gaps = sorted(pair_rows, key=lambda x: (-x["absolute_gap"], x["value"]))[:5]

    for pair, explanation in POTENTIAL_VALUE_CONFLICTS.items():
        x, y = pair
        if x in a and x in b and y in a and y in b:
            conflict_zones.append({
                "values": [x, y],
                "a_priority": {x: float(a[x]), y: float(a[y])},
                "b_priority": {x: float(b[x]), y: float(b[y])},
                "label": explanation,
                "status": "POTENTIAL_CONFLICT",
            })

    return {
        "vector": "V2",
        "status": "ESTIMATED" if rho is not None else "UNKNOWN",
        "spearman": rho,
        "common_values": common,
        "pairwise_alignment": pair_rows,
        "top_alignments": top_alignments,
        "value_gaps": value_gaps,
        "conflict_zones": conflict_zones,
        "provenance": _provenance(
            "Model-derived ranked Values alignment and heuristic conflict mapping",
            {"a": dict(a), "b": dict(b)},
        ),
    }


def _role_class(role_a: str, role_b: str, overrides: Mapping[tuple[str, str], Any] | None) -> str:
    if overrides:
        value = overrides.get((role_a, role_b))
        if value is None:
            value = overrides.get((role_b, role_a))
        if value is not None:
            return str(value)
    pair = frozenset((role_a, role_b))
    if pair in ROLE_COMPETITION_DEFAULTS:
        return ROLE_COMPETITION_DEFAULTS[pair]
    if pair in ROLE_SYNERGY_DEFAULTS:
        return ROLE_SYNERGY_DEFAULTS[pair]
    return "NEUTRAL"


def compatibility_v3(
    roles_a: set[str] | list[str],
    roles_b: set[str] | list[str],
    synergy: Mapping[tuple[str, str], Any] | None = None,
) -> dict[str, Any]:
    rows = []
    for role_a in sorted(set(roles_a)):
        for role_b in sorted(set(roles_b)):
            classification = _role_class(role_a, role_b, synergy)
            rows.append({"role_a": role_a, "role_b": role_b, "interaction": classification})

    return {
        "vector": "V3",
        "status": "ESTIMATED" if rows else "UNKNOWN",
        "role_pairs": rows,
        "synergies": [x for x in rows if x["interaction"] in {"SYNERGY", "COMPLEMENT"}],
        "competition": [x for x in rows if x["interaction"] == "COMPETITION"],
        "coverage_a": sorted(set(roles_a)),
        "coverage_b": sorted(set(roles_b)),
        "provenance": _provenance(
            "Model-derived role interaction matrix",
            {"roles_a": sorted(set(roles_a)), "roles_b": sorted(set(roles_b))},
        ),
    }


def scenarios_and_interventions(
    v1: Mapping[str, Any],
    v2: Mapping[str, Any],
    v3: Mapping[str, Any],
    *,
    decision_buffer_threshold: float = 3.0,
) -> list[dict[str, Any]]:
    scenarios: list[dict[str, Any]] = []

    tempo_gap = v1.get("dimensions", {}).get("tempo", {}).get("absolute_delta")
    if tempo_gap is not None and tempo_gap >= decision_buffer_threshold:
        scenarios.append({
            "scenario": "DECISION_SPEED_MISMATCH",
            "trigger": {"tempo_absolute_delta": tempo_gap, "threshold": decision_buffer_threshold},
            "intervention": "24-hour decision buffer",
            "rationale": "Reduce escalation from asymmetric decision tempo before irreversible commitments",
            "provenance_tag": "DRV",
        })

    if v3.get("competition"):
        scenarios.append({
            "scenario": "ROLE_COMPETITION",
            "trigger": {"competitive_pairs": v3["competition"]},
            "intervention": "explicit role ownership and tie-break protocol",
            "rationale": "Separate decision ownership from execution support",
            "provenance_tag": "DRV",
        })

    if v2.get("conflict_zones"):
        scenarios.append({
            "scenario": "VALUE_TENSION",
            "trigger": {"conflict_zones": v2["conflict_zones"]},
            "intervention": "write explicit trade-off rules before high-stakes decisions",
            "rationale": "Make value trade-offs explicit rather than inferring intent",
            "provenance_tag": "DRV",
        })

    return scenarios


def compatibility_report(
    bio_a: Mapping[str, float],
    bio_b: Mapping[str, float],
    values_a: Mapping[str, float],
    values_b: Mapping[str, float],
    roles_a: list[str] | set[str],
    roles_b: list[str] | set[str],
    synergy: Mapping[tuple[str, str], Any] | None = None,
) -> dict[str, Any]:
    v1 = compatibility_v1(bio_a, bio_b)
    v2 = compatibility_v2(values_a, values_b)
    v3 = compatibility_v3(roles_a, roles_b, synergy)
    scenarios = scenarios_and_interventions(v1, v2, v3)
    return {
        "version": VERSION,
        "v1": v1,
        "v2": v2,
        "v3": v3,
        "scenarios": scenarios,
        "authoritative_scalar": False,
        "scientific_status": "MODEL_DERIVED_NOT_VALIDATED",
        "provenance_tag": "DRV",
        "provenance": _provenance(
            "Three-vector compatibility report; no authoritative scalar",
            {"v1": v1, "v2": v2, "v3": v3, "scenarios": scenarios},
        ),
    }


# Backward-compatible helper retained for existing callers.
def compatibility(
    a: Mapping[str, float],
    b: Mapping[str, float],
    synergy: Mapping[tuple[str, str], Any] | None = None,
) -> dict[str, Any]:
    return compatibility_report(a, b, {}, {}, set(), set(), synergy)


__all__ = [
    "compatibility",
    "compatibility_v1",
    "compatibility_v2",
    "compatibility_v3",
    "compatibility_report",
    "scenarios_and_interventions",
    "spearman",
]
