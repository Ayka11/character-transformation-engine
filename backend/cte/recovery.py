"""V1.0 recovery / detox protocol runtime.

This module operationalizes the safety and recovery portions of Master Matrix V1.0.
Rules are model-derived (DRV) and are not presented as clinical or empirically
validated conclusions. Trait measurements are never overwritten by compromised
state flags.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from .capacity import compute_capacity
from .models import DailyState
from .provenance import Provenance, derived_provenance, content_hash

VERSION = "1.0"

RECOVERY_THRESHOLD = 4.0  # Master Matrix scale is 0-10; 40% == 4.0
RECOVERY_STREAK_DAYS = 3
HIGH_STRESS_THRESHOLD = 8.0
LOW_CAPACITY_THRESHOLD = 3.0
MICRO_ACTION_MIN_SECONDS = 5
MICRO_ACTION_MAX_SECONDS = 30


@dataclass(frozen=True)
class RecoveryGate:
    status: str
    level: str
    safety_block: bool
    capacity: float | None
    compromised_state: bool
    trigger_reasons: tuple[str, ...]
    provenance: Provenance
    inputs: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class RecoveryPlan:
    mode: str
    sprint_status: str
    level: str
    stimulus_restriction: str
    micro_action_seconds: tuple[int, int]
    exclude_cognitively_costly_tests: bool
    actions: tuple[str, ...]
    reason: str
    provenance: Provenance


@dataclass(frozen=True)
class StateTraitIsolation:
    current_state: str
    trait_profile_mutable: bool
    trait_values_untouched: bool
    reason: str
    provenance: Provenance


@dataclass(frozen=True)
class BioResetDecision:
    triggered: bool
    consecutive_low_recovery_days: int
    sprint_status: str
    reason: str
    provenance: Provenance
    observed_recovery: tuple[float | None, ...]


def evaluate_recovery_gate(state: DailyState) -> RecoveryGate:
    capacity = compute_capacity(state)
    reasons: list[str] = []
    if state.subjective_stress is not None and state.subjective_stress >= HIGH_STRESS_THRESHOLD:
        reasons.append("subjective_stress>=8")
    if capacity.capacity is not None and capacity.capacity < LOW_CAPACITY_THRESHOLD:
        reasons.append("capacity<3")
    if capacity.level == "A":
        reasons.append("capacity_level=A")

    compromised = bool(reasons)
    status = "RECOVERY_REQUIRED" if compromised else "CAPACITY_AVAILABLE"
    prov = derived_provenance(
        "recovery.gate",
        VERSION,
        {"state": state, "capacity": capacity.capacity, "level": capacity.level, "reasons": reasons},
        "Model-derived Level A safety gate; not empirically validated",
    )
    return RecoveryGate(
        status=status,
        level="A" if compromised else capacity.level,
        safety_block=compromised or capacity.safety_block,
        capacity=capacity.capacity,
        compromised_state=compromised,
        trigger_reasons=tuple(reasons),
        provenance=prov,
        inputs={
            "subjective_stress": state.subjective_stress,
            "recovery_index": state.recovery_index,
            "capacity": capacity.capacity,
        },
    )


def evaluate_bio_reset(
    recovery_indices: list[float | None],
    *,
    threshold: float = RECOVERY_THRESHOLD,
    streak_days: int = RECOVERY_STREAK_DAYS,
) -> BioResetDecision:
    if streak_days < 1:
        raise ValueError("streak_days must be >= 1")
    if threshold < 0:
        raise ValueError("threshold must be >= 0")

    recent = tuple(recovery_indices[-streak_days:])
    low_days = 0
    for value in reversed(recent):
        if value is None or value >= threshold:
            break
        low_days += 1

    triggered = low_days >= streak_days
    reason = (
        f"Recovery remained below {threshold:g}/10 for {streak_days} consecutive days"
        if triggered
        else f"Bio Reset requires {streak_days} consecutive days below {threshold:g}/10"
    )
    prov = derived_provenance(
        "recovery.bio_reset",
        VERSION,
        {"recovery_indices": recovery_indices, "threshold": threshold, "streak_days": streak_days},
        "Model-derived consecutive-low-recovery trigger; not empirically validated",
    )
    return BioResetDecision(
        triggered=triggered,
        consecutive_low_recovery_days=low_days,
        sprint_status="PAUSED" if triggered else "ACTIVE",
        reason=reason,
        provenance=prov,
        observed_recovery=recent,
    )


def build_recovery_plan(state: DailyState, *, bio_reset_triggered: bool = False) -> RecoveryPlan:
    gate = evaluate_recovery_gate(state)
    recovery_required = gate.compromised_state or bio_reset_triggered
    if recovery_required:
        mode = "BIO_RESET_DETOX"
        sprint_status = "PAUSED"
        level = "A"
        reason = "Safety gate requires recovery before trait challenge"
    else:
        mode = "RECOVERY_AVAILABLE"
        sprint_status = "ACTIVE"
        level = gate.level
        reason = "No Level A recovery trigger is active"

    prov = derived_provenance(
        "recovery.plan",
        VERSION,
        {"gate": gate, "bio_reset_triggered": bio_reset_triggered},
        "Model-derived recovery protocol; not a clinical detox recommendation",
    )
    return RecoveryPlan(
        mode=mode,
        sprint_status=sprint_status,
        level=level,
        stimulus_restriction=(
            "RESTRICT_INCOMING_STIMULI" if recovery_required else "STANDARD"
        ),
        micro_action_seconds=(MICRO_ACTION_MIN_SECONDS, MICRO_ACTION_MAX_SECONDS),
        exclude_cognitively_costly_tests=recovery_required,
        actions=(
            "reduce_incoming_stimuli",
            "use_micro_actions_only",
            "prioritize_basic_recovery",
            "pause_trait_challenge",
            "reassess_daily_state",
        ) if recovery_required else (
            "maintain_recovery_routine",
            "reassess_daily_state",
        ),
        reason=reason,
        provenance=prov,
    )


def isolate_compromised_state_from_traits(
    current_state: str = "compromised",
    *,
    trait_values_untouched: bool = True,
) -> StateTraitIsolation:
    if current_state not in {"normal", "compromised", "unknown"}:
        raise ValueError("unsupported current_state")
    prov = derived_provenance(
        "recovery.trait_isolation",
        VERSION,
        {"current_state": current_state, "trait_values_untouched": trait_values_untouched},
        "State/trait separation invariant",
    )
    return StateTraitIsolation(
        current_state=current_state,
        trait_profile_mutable=False,
        trait_values_untouched=trait_values_untouched,
        reason="Compromised CURRENT STATE must not be written back as low P2-P5 TRAIT",
        provenance=prov,
    )
