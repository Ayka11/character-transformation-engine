from dataclasses import dataclass
from typing import Any, Mapping
from ..provenance import content_hash

@dataclass(frozen=True)
class StateSnapshot:
    snapshot_id: str
    character_id: str
    sequence: int
    state: dict[str, Any]
    state_hash: str
    parent_snapshot_id: str | None = None
    source_execution_id: str | None = None
    schema_version: str = "1.0"
    canonicalization_version: str = "1.0"

    @classmethod
    def capture(cls, snapshot_id, character_id, sequence, state, *, parent_snapshot_id=None, source_execution_id=None, schema_version="1.0", canonicalization_version="1.0"):
        payload=dict(state)
        return cls(snapshot_id, character_id, sequence, payload, content_hash(payload), parent_snapshot_id, source_execution_id, schema_version, canonicalization_version)

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
        missing=tuple(sorted(k for k in expected if k not in changed))
        return StateDiff(before.state_hash, after.state_hash, changed, unchanged, unexpected, forbidden_changes, missing)
