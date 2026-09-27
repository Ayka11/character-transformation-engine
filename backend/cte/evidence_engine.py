"""Registered evidence-criteria runtime for V1.4 evidence support."""
from __future__ import annotations
from dataclasses import dataclass
from .provenance import Provenance, ProvenanceTag, content_hash

@dataclass(frozen=True)
class EvidenceCriteria:
    criteria_id:str
    claim_id:str
    rule_ids:tuple[str,...]
    acceptance_rules:dict
    version:str
    provenance:Provenance

def register_criteria(criteria_id:str, claim_id:str, *,
                      rule_ids:list[str], acceptance_rules:dict,
                      version:str="1.4")->EvidenceCriteria:
    if not rule_ids:
        raise ValueError("at least one evidence criterion rule is required")
    payload={"criteria_id":criteria_id,"claim_id":claim_id,
             "rule_ids":rule_ids,"acceptance_rules":acceptance_rules,"version":version}
    return EvidenceCriteria(criteria_id,claim_id,tuple(rule_ids),dict(acceptance_rules),version,
        Provenance(ProvenanceTag.DRV,"cte.evidence.criteria","1.4",content_hash(payload),
                   "Registered evidence criteria; not evidence itself"))
