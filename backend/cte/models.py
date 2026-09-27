from dataclasses import dataclass, field
from typing import Any
from .provenance import Provenance

@dataclass
class DailyState:
    sleep_quality: float|None
    recovery_index: float|None
    physical_activity: float|None
    metabolic_stability: float|None
    subjective_stress: float|None
    subjective_energy: float|None

@dataclass
class CapacityResult:
    capacity: float|None
    level: str
    safety_block: bool
    provenance: Provenance
    explanation: str
    inputs: dict[str,Any]=field(default_factory=dict)
