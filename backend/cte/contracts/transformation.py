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

    @classmethod
    def failed(cls, code: str, details: dict[str, Any] | None = None, *, before_snapshot_id: str = "", after_snapshot_id: str = ""):
        return cls("FAILED", code, before_snapshot_id, after_snapshot_id, "", "", (), False, details or {})

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

@dataclass(frozen=True)
class TransformationCertificate:
    certificate_id: str
    execution_id: str
    contract_id: str
    contract_version: str
    before_snapshot_id: str
    after_snapshot_id: str
    before_hash: str
    after_hash: str
    changed_fields: tuple[str, ...]
    certificate_hash: str

    @classmethod
    def issue(cls, execution_id: str, contract, result: TransformationResult):
        if result.status != "VALIDATED" or not result.certificate_eligible:
            raise ValueError("certificate requires a validated transformation")
        payload={"execution_id":execution_id,"contract_id":contract.contract_id,"contract_version":contract.version,
                 "before_snapshot_id":result.before_snapshot_id,"after_snapshot_id":result.after_snapshot_id,
                 "before_hash":result.before_hash,"after_hash":result.after_hash,"changed_fields":list(result.changed_fields)}
        from ..provenance import content_hash
        return cls(content_hash(payload), execution_id, contract.contract_id, contract.version,
                   result.before_snapshot_id,result.after_snapshot_id,result.before_hash,result.after_hash,
                   result.changed_fields,content_hash(payload))
