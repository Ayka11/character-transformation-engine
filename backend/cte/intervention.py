"""Safety-gated intervention planning."""
from __future__ import annotations
from dataclasses import dataclass
from .capacity import compute_capacity
from .models import DailyState
from .trait_graph import TraitGraph

@dataclass(frozen=True)
class BioResetPlan:
    allowed: bool
    level: str
    target: str | None
    actions: tuple[str, ...]
    reason: str

@dataclass(frozen=True)
class SprintPlan:
    allowed: bool
    duration_days: int
    target_trait: str | None
    supporting_bio_habit: str | None
    daily_action: str | None
    safety: str
    reason: str

def plan_bio_reset(state: DailyState, requested_trait: str, graph: TraitGraph, blockers: dict[str, float]) -> BioResetPlan:
    capacity = compute_capacity(state)
    target = graph.resolve_intervention_target(requested_trait, blockers)
    if capacity.safety_block:
        return BioResetPlan(False, capacity.level, target.selected_target, ("reduce_load","prioritize_recovery","reassess_missing_inputs"), "Safety gate active: recovery/stabilization precedes trait challenge")
    return BioResetPlan(True, capacity.level, target.selected_target, ("sleep_regularization","recovery_support","low_intensity_movement"), "Capacity permits a recovery-supporting intervention")

def plan_21_day_sprint(state: DailyState, requested_trait: str, graph: TraitGraph, blockers: dict[str, float], supporting_bio_habit: str, daily_action: str) -> SprintPlan:
    capacity = compute_capacity(state)
    target = graph.resolve_intervention_target(requested_trait, blockers)
    if capacity.safety_block or target.selected_target is None:
        return SprintPlan(False, 21, target.selected_target, None, None, "SAFETY_BLOCKED", "Sprint cannot start until safety gate clears and an eligible target exists")
    return SprintPlan(True, 21, target.selected_target, supporting_bio_habit, daily_action, "CAPACITY_ALLOWED", "Sprint is permitted by current capacity gate")
