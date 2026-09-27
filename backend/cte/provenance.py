from dataclasses import dataclass
from enum import Enum
from typing import Any
import hashlib, json

class ProvenanceTag(str, Enum):
    EVD="EVD"; MDL="MDL"; HYP="HYP"; RPT="RPT"; DRV="DRV"; OBS="OBS"; EXT="EXT"; EXP="EXP"

@dataclass(frozen=True)
class Provenance:
    tag: ProvenanceTag
    source_id: str
    source_version: str
    input_hash: str | None = None
    note: str | None = None

def content_hash(value: Any) -> str:
    payload=json.dumps(value,sort_keys=True,separators=(",",":"),default=str).encode()
    return hashlib.sha256(payload).hexdigest()

def derived_provenance(source_id: str, source_version: str, inputs: Any, note: str|None=None) -> Provenance:
    return Provenance(ProvenanceTag.DRV,source_id,source_version,content_hash(inputs),note)
