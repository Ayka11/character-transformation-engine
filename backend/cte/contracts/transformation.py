from dataclasses import dataclass, field
from typing import Any
from .errors import CTEErrorCode

@dataclass(frozen=True)
class TransformationContract:
    contract_id: str
    version: str
    required_state: dict[str, Any] = field(default_factory=dict)
    expected_changes: dict[str, Any] = field(default_factory=dict)
    allowed_changes: tuple[str, ...] = ()
    forbidden_changes: tuple[str, ...] = ()
    postconditions: tuple[dict[str, Any], ...] = ()
    reversible: bool = False
    idempotent: bool = False

@dataclass(frozen=True)
class TransformationResult:
    status: str
    failure_code: str | None
    before_snapshot_id: str
    after_snapshot_id: str
    before_hash: str
    after_hash: str
    changed_fields: tuple[str, ...]
    certificate_eligible: bool
    details: dict[str, Any] = field(default_factory=dict)

def validate_transition(contract, diff, *, before_snapshot_id="", after_snapshot_id=""):
    if contract.expected_changes and not diff.state_changed:
        return TransformationResult("FAILED", CTEErrorCode.NO_STATE_CHANGE.value, before_snapshot_id, after_snapshot_id, diff.before_hash, diff.after_hash, (), False, {"reason":"required transformation produced no state change"})
    if diff.forbidden:
        return TransformationResult("FAILED", CTEErrorCode.UNEXPECTED_CHANGE.value, before_snapshot_id, after_snapshot_id, diff.before_hash, diff.after_hash, tuple(diff.changed), False, {"forbidden":diff.forbidden})
    if diff.unexpected:
        return TransformationResult("FAILED", CTEErrorCode.UNEXPECTED_CHANGE.value, before_snapshot_id, after_snapshot_id, diff.before_hash, diff.after_hash, tuple(diff.changed), False, {"unexpected":diff.unexpected})
    if diff.missing_expected:
        return TransformationResult("FAILED", CTEErrorCode.VALIDATION_FAILED.value, before_snapshot_id, after_snapshot_id, diff.before_hash, diff.after_hash, tuple(diff.changed), False, {"missing_expected":diff.missing_expected})
    return TransformationResult("VALIDATED", None, before_snapshot_id, after_snapshot_id, diff.before_hash, diff.after_hash, tuple(sorted(diff.changed)), True, {})
