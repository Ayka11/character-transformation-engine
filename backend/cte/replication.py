"""Registered replication and generalization runtime records."""
from __future__ import annotations
from dataclasses import dataclass
from .provenance import Provenance, ProvenanceTag, content_hash

@dataclass(frozen=True)
class ReplicationRecord:
    replication_id: str
    source_result_id: str
    independent: bool
    criteria_registered: bool
    status: str
    provenance: Provenance

def register_replication(replication_id: str, source_result_id: str, *,
                         independent: bool, criteria_registered: bool,
                         status: str="REGISTERED") -> ReplicationRecord:
    payload={"replication_id":replication_id,"source_result_id":source_result_id,
             "independent":independent,"criteria_registered":criteria_registered,"status":status}
    return ReplicationRecord(
        replication_id,source_result_id,independent,criteria_registered,status,
        Provenance(ProvenanceTag.DRV,"cte.replication","2.1.0",content_hash(payload),
                   "Registered replication record; not empirical validation")
    )

@dataclass(frozen=True)
class GeneralizationRecord:
    generalization_id: str
    source_result_id: str
    run_status: str
    target_population_context: str
    provenance: Provenance

def register_generalization(generalization_id: str, source_result_id: str, *,
                            run_status: str, target_population_context: str) -> GeneralizationRecord:
    if not target_population_context.strip():
        raise ValueError("target_population_context is required")
    payload={"generalization_id":generalization_id,"source_result_id":source_result_id,
             "run_status":run_status,"target_population_context":target_population_context}
    return GeneralizationRecord(
        generalization_id,source_result_id,run_status,target_population_context,
        Provenance(ProvenanceTag.DRV,"cte.generalization","2.1.0",content_hash(payload),
                   "Registered generalization record; not empirical validation")
    )
