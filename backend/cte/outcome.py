"""Outcome and adaptation runtime.

Outcome classification is descriptive/model-driven; it is not an efficacy claim.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

class ResponseClass(str, Enum):
    IMPROVED="IMPROVED"
    STABLE="STABLE"
    DECLINED="DECLINED"
    UNKNOWN="UNKNOWN"

class AdaptationAction(str, Enum):
    CONTINUE="CONTINUE"
    INTENSIFY="INTENSIFY"
    REDUCE="REDUCE"
    REPLACE="REPLACE"
    STOP="STOP"
    COLLECT_DATA="COLLECT_DATA"

@dataclass(frozen=True)
class OutcomeResult:
    baseline: float | None
    current: float | None
    delta: float | None
    response: ResponseClass
    adaptation: AdaptationAction
    reason: str

def evaluate_outcome(baseline: float | None, current: float | None, *, tolerance: float = 0.25, safety_block: bool = False) -> OutcomeResult:
    if safety_block:
        return OutcomeResult(baseline, current, None if baseline is None or current is None else current-baseline, ResponseClass.UNKNOWN, AdaptationAction.STOP, "Safety block overrides outcome progression")
    if baseline is None or current is None:
        return OutcomeResult(baseline, current, None, ResponseClass.UNKNOWN, AdaptationAction.COLLECT_DATA, "Baseline or current outcome is missing")
    delta=current-baseline
    if delta > tolerance:
        return OutcomeResult(baseline,current,delta,ResponseClass.IMPROVED,AdaptationAction.CONTINUE,"Measured change exceeds tolerance in positive direction")
    if delta < -tolerance:
        return OutcomeResult(baseline,current,delta,ResponseClass.DECLINED,AdaptationAction.REDUCE,"Measured change exceeds tolerance in negative direction")
    return OutcomeResult(baseline,current,delta,ResponseClass.STABLE,AdaptationAction.CONTINUE,"Change remains within tolerance")
