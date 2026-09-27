from dataclasses import dataclass
from typing import Any
from ..provenance import content_hash

@dataclass(frozen=True)
class StateSnapshot:
    snapshot_id: str
    character_id: str
    sequence: int
    state: dict[str, Any]
    state_hash: str
    lineage_hash: str
    parent_snapshot_id: str | None = None
    source_execution_id: str | None = None
    schema_version: str = "1.0"
    canonicalization_version: str = "1.0"

    @classmethod
    def capture(cls, snapshot_id, character_id, sequence, state, *, parent_snapshot_id=None, source_execution_id=None, schema_version="1.0", canonicalization_version="1.0"):
        payload=dict(state)
        state_hash=content_hash(payload)
        lineage_hash=content_hash({"parent_snapshot_id":parent_snapshot_id,"state_hash":state_hash,"source_execution_id":source_execution_id,"schema_version":schema_version,"canonicalization_version":canonicalization_version})
        return cls(snapshot_id, character_id, sequence, payload, state_hash, lineage_hash, parent_snapshot_id, source_execution_id, schema_version, canonicalization_version)

@dataclass(frozen=True)
class StateDiff:
    before_hash: str
    after_hash: str
    changed: dict
    unchanged: dict
    unexpected: dict
    forbidden: dict
    missing_expected: tuple
    @property
    def state_changed(self): return self.before_hash != self.after_hash

class StateDiffEngine:
    @staticmethod
    def compare(before, after, *, expected=None, allowed=None, forbidden=None):
        expected=dict(expected or {})
        allowed=set(allowed or ()) | set(expected)
        forbidden=set(forbidden or ())
        changed={}; unchanged={}
        for key in sorted(set(before.state)|set(after.state)):
            bv=before.state.get(key); av=after.state.get(key)
            if bv==av: unchanged[key]=av
            else: changed[key]={"before":bv,"after":av}
        unexpected={k:v for k,v in changed.items() if allowed and k not in allowed}
        forbidden_changes={k:v for k,v in changed.items() if k in forbidden}
        # An expected transformation is satisfied only when the field changes
        # to the declared target value. A changed field with the wrong value
        # must therefore enter validation/rollback rather than being accepted.
        missing=tuple(sorted(k for k, expected_value in expected.items()
                              if k not in changed or after.state.get(k) != expected_value))
        return StateDiff(before.state_hash, after.state_hash, changed, unchanged, unexpected, forbidden_changes, missing)
