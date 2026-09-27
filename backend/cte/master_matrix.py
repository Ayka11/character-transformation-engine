"""Canonical Master Matrix V1.0 catalog used by the executable CTE baseline.

The catalog is intentionally declarative. It describes constructs and measurement
contracts; it does not claim that any model-derived rule is empirically validated.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


Domain = Literal["P1", "P2", "P3", "P4", "P5"]
MeasurementKind = Literal["state", "trait", "modeled", "value", "behavior"]


@dataclass(frozen=True)
class MatrixItem:
    id: str
    domain: Domain
    name: str
    kind: MeasurementKind
    scale: str
    direction: str
    provenance_tag: str
    notes: str = ""


MATRIX_VERSION = "1.0"

P1_ITEMS = (
    MatrixItem("P1.sleep_quality", "P1", "Sleep Quality", "state", "0-10", "higher_is_better", "OBS"),
    MatrixItem("P1.recovery_index", "P1", "Recovery Index", "state", "0-10", "higher_is_better", "OBS"),
    MatrixItem("P1.physical_activity", "P1", "Physical Activity", "state", "0-10", "higher_is_better", "OBS"),
    MatrixItem("P1.metabolic_stability", "P1", "Metabolic/Glycemic Stability", "state", "0-10", "higher_is_better", "OBS"),
    MatrixItem("P1.subjective_stress", "P1", "Subjective Stress", "state", "0-10", "higher_is_worse", "OBS"),
    MatrixItem("P1.subjective_energy", "P1", "Subjective Energy", "state", "0-10", "higher_is_better", "OBS"),
)

P2_ITEMS = tuple(
    MatrixItem(f"P2.big5_{trait.lower()}", "P2", trait, "trait", "0-10", "higher_is_trait_level", "OBS")
    for trait in ("Openness", "Conscientiousness", "Extraversion", "Agreeableness", "Neuroticism")
)

P3_ITEMS = (
    MatrixItem("P3.impulse_control", "P3", "Impulse Control", "modeled", "0-10", "higher_is_better", "OBS"),
    MatrixItem("P3.pause_capacity", "P3", "Pause Capacity", "modeled", "0-10", "higher_is_better", "OBS"),
    MatrixItem("P3.cognitive_reappraisal", "P3", "Cognitive Reappraisal", "modeled", "0-10", "higher_is_better", "OBS"),
    MatrixItem("P3.attention_regulation", "P3", "Attention Regulation", "modeled", "0-10", "higher_is_better", "OBS"),
    MatrixItem("P3.reflection_depth", "P3", "Reflection Depth", "modeled", "0-10", "higher_is_better", "OBS"),
)

P4_ITEMS = tuple(
    MatrixItem(
        f"P4.value_{value.lower()}",
        "P4",
        value,
        "value",
        "0-10",
        "higher_is_importance",
        "OBS",
    )
    for value in (
        "Honesty", "Autonomy", "Achievement", "Security", "Growth",
        "Compassion", "Justice", "Family", "Freedom", "Order",
    )
)

P5_ITEMS = (
    MatrixItem("P5.discipline_consistency", "P5", "Discipline & Consistency", "behavior", "0-10", "higher_is_better", "OBS"),
    MatrixItem("P5.social_courage_assertiveness", "P5", "Social Courage & Assertiveness", "behavior", "0-10", "higher_is_better", "OBS"),
    MatrixItem("P5.boundary_setting", "P5", "Boundary Setting", "behavior", "0-10", "higher_is_better", "OBS"),
    MatrixItem("P5.adaptability", "P5", "Adaptability", "behavior", "0-10", "higher_is_better", "OBS"),
)

MASTER_MATRIX = P1_ITEMS + P2_ITEMS + P3_ITEMS + P4_ITEMS + P5_ITEMS

ADAPTIVE_LEVELS = {
    "A": {"name": "Recovery", "promotion_gate": "capacity_and_safety"},
    "B": {"name": "Stabilization", "promotion_gate": "capacity_and_safety"},
    "C": {"name": "Training", "promotion_gate": "capacity_and_safety"},
    "D": {"name": "Challenge", "promotion_gate": "capacity_and_safety"},
    "E": {"name": "Integration", "promotion_gate": "capacity_and_safety"},
}

SPRINT_TEMPLATE = {
    "duration_days": 21,
    "required": ["target_trait", "supporting_bio_habit", "daily_action", "metrics", "safety"],
    "safety_precedes_promotion": True,
}

def get_matrix_item(item_id: str) -> MatrixItem:
    for item in MASTER_MATRIX:
        if item.id == item_id:
            return item
    raise KeyError(item_id)


def matrix_summary() -> dict:
    return {
        "version": MATRIX_VERSION,
        "domains": {d: sum(1 for item in MASTER_MATRIX if item.domain == d) for d in ("P1", "P2", "P3", "P4", "P5")},
        "total_items": len(MASTER_MATRIX),
        "adaptive_levels": ADAPTIVE_LEVELS,
        "sprint_template": SPRINT_TEMPLATE,
    }
