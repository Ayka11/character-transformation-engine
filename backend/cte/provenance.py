from dataclasses import dataclass, fields, is_dataclass
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

def json_safe(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {field.name: json_safe(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value

def content_hash(value: Any) -> str:
    payload=json.dumps(json_safe(value),sort_keys=True,separators=(',',':')).encode()
    return hashlib.sha256(payload).hexdigest()

def derived_provenance(source_id: str, source_version: str, inputs: Any, note: str|None=None) -> Provenance:
    return Provenance(ProvenanceTag.DRV,source_id,source_version,content_hash(inputs),note)
