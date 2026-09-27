"""Runtime state derivation from an AssessmentProfile.

State derivation is deliberately conservative: absent measurements remain UNKNOWN.
No missing value is silently imputed.
"""
from __future__ import annotations
from dataclasses import dataclass
from .assessment import AssessmentProfile
from .models import DailyState

@dataclass(frozen=True)
class StateDerivation:
    state: DailyState
    missing: tuple[str, ...]

_MAP = {
    "P1.sleep_quality": "sleep_quality",
    "P1.recovery_index": "recovery_index",
    "P1.physical_activity": "physical_activity",
    "P1.metabolic_stability": "metabolic_stability",
    "P1.subjective_stress": "subjective_stress",
    "P1.subjective_energy": "subjective_energy",
}

def derive_daily_state(profile: AssessmentProfile) -> StateDerivation:
    values = profile.values()
    kwargs = {field: values.get(item_id) for item_id, field in _MAP.items()}
    missing = tuple(field for field, value in kwargs.items() if value is None)
    return StateDerivation(DailyState(**kwargs), missing)
