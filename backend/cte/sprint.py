"""Executable 21-day sprint state machine."""
from __future__ import annotations
from dataclasses import dataclass
from .models import DailyState
from .capacity import compute_capacity

@dataclass(frozen=True)
class SprintDayResult:
    day: int
    status: str
    action_completed: bool
    outcome: float | None
    capacity: float | None
    safety_block: bool
    next_action: str
    reason: str

@dataclass(frozen=True)
class SprintState:
    sprint_id: str
    target_trait: str
    duration_days: int
    current_day: int
    status: str
    supporting_bio_habit: str
    daily_action: str

def start_sprint(sprint_id: str, target_trait: str, supporting_bio_habit: str, daily_action: str) -> SprintState:
    return SprintState(sprint_id, target_trait, 21, 0, "ACTIVE", supporting_bio_habit, daily_action)

def record_day(state: SprintState, day: int, action_completed: bool, outcome: float | None, daily_state: DailyState) -> SprintDayResult:
    if state.status != "ACTIVE":
        raise ValueError("Sprint is not active")
    if day != state.current_day + 1:
        raise ValueError("Daily records must be sequential")
    if not 1 <= day <= state.duration_days:
        raise ValueError("Day must be within sprint duration")
    capacity = compute_capacity(daily_state)
    if capacity.safety_block:
        return SprintDayResult(day, "PAUSED_SAFETY", action_completed, outcome, capacity.capacity, True, "pause_and_recover", "Safety gate overrides sprint progression")
    if outcome is None:
        return SprintDayResult(day, "RECORDED_NO_OUTCOME", action_completed, None, capacity.capacity, False, "collect_outcome", "Outcome measurement is missing")
    if day == state.duration_days:
        return SprintDayResult(day, "COMPLETED", action_completed, outcome, capacity.capacity, False, "final_review", "21-day sprint completed")
    if not action_completed:
        return SprintDayResult(day, "ADAPT_ACTION", False, outcome, capacity.capacity, False, "reduce_or_reframe_action", "Action was not completed; adaptation is required")
    return SprintDayResult(day, "CONTINUE", True, outcome, capacity.capacity, False, "next_day", "Continue with next daily cycle")
