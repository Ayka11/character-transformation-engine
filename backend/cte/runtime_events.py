from dataclasses import dataclass
from .provenance import Provenance, ProvenanceTag, content_hash

@dataclass(frozen=True)
class RuntimeEvent:
    event_id: str
    event_type: str
    execution_id: str
    payload: dict
    provenance: Provenance

def make_event(event_id: str, event_type: str, execution_id: str, payload: dict) -> RuntimeEvent:
    return RuntimeEvent(event_id, event_type, execution_id, payload, Provenance(ProvenanceTag.DRV, 'cte.runtime', '2.1.0', content_hash(payload), 'runtime event; not empirical evidence'))

def lineage_descriptor(event: RuntimeEvent) -> dict:
    return {'event_id': event.event_id, 'execution_id': event.execution_id, 'event_type': event.event_type, 'provenance_tag': event.provenance.tag.value, 'input_hash': event.provenance.input_hash}
