"""Executable V1.5 replication comparison engine.

Model-derived implementation of the repository's V1.5 contract; not empirically validated.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import isfinite
from .provenance import Provenance, ProvenanceTag, content_hash

DIMENSIONS=("protocol_fidelity","measurement_fidelity","outcome_definition","direction","effect_compatibility","data_quality")
STATUSES=("MATCH","COMPATIBLE","DEVIATION","UNKNOWN","NOT_APPLICABLE")

@dataclass(frozen=True)
class ReplicationSpec:
    replication_spec_id:str
    source_claim_id:str
    primary_outcome_id:str
    criteria:dict
    version:str
    provenance:Provenance

def register_spec(replication_spec_id:str, source_claim_id:str, primary_outcome_id:str,
                  criteria:dict|None=None, version:str="1.5")->ReplicationSpec:
    c=dict(criteria or {})
    payload={"replication_spec_id":replication_spec_id,"source_claim_id":source_claim_id,
             "primary_outcome_id":primary_outcome_id,"criteria":c,"version":version}
    return ReplicationSpec(replication_spec_id,source_claim_id,primary_outcome_id,c,version,
        Provenance(ProvenanceTag.DRV,"cte.replication.spec","1.5",content_hash(payload),
                   "Registered replication criteria; not empirical validation"))

@dataclass(frozen=True)
class ReplicationRun:
    replication_run_id:str
    replication_spec_id:str
    source_result_node_id:str
    independent_study_id:str
    dataset_manifest_id:str
    protocol_hash:str
    input_hash:str
    status:str
    provenance:Provenance

def register_run(replication_run_id:str, spec:ReplicationSpec, *,
                 source_result_node_id:str, independent_study_id:str,
                 dataset_manifest_id:str, protocol_hash:str, input_hash:str,
                 independent:bool)->ReplicationRun:
    if not independent:
        raise ValueError("independence is required for replication")
    payload={"replication_run_id":replication_run_id,"replication_spec_id":spec.replication_spec_id,
             "source_result_node_id":source_result_node_id,"independent_study_id":independent_study_id,
             "dataset_manifest_id":dataset_manifest_id,"protocol_hash":protocol_hash,"input_hash":input_hash,
             "independent":independent}
    return ReplicationRun(replication_run_id,spec.replication_spec_id,source_result_node_id,
        independent_study_id,dataset_manifest_id,protocol_hash,input_hash,"REGISTERED",
        Provenance(ProvenanceTag.DRV,"cte.replication.run","1.5",content_hash(payload),
                   "Registered independent replication run; not empirical validation"))

@dataclass(frozen=True)
class ReplicationOutcome:
    replication_run_id:str
    source_estimate:float|None
    target_estimate:float|None
    source_effect_size:float|None
    target_effect_size:float|None
    source_ci_low:float|None
    source_ci_high:float|None
    target_ci_low:float|None
    target_ci_high:float|None
    direction_compatible:bool|None
    effect_compatible:bool|None
    interval_rule_met:bool|None
    overall_outcome:str
    rationale:str
    provenance:Provenance

def _direction(a:float|None,b:float|None)->bool|None:
    if a is None or b is None: return None
    if a==0 or b==0: return a==b
    return (a>0)==(b>0)

def _effect(a:float|None,b:float|None,tol:float)->bool|None:
    if a is None or b is None: return None
    scale=max(abs(a),abs(b),1.0)
    return abs(a-b) <= tol*scale

def _interval(low1:float|None,high1:float|None,low2:float|None,high2:float|None)->bool|None:
    if None in (low1,high1,low2,high2): return None
    return max(low1,low2) <= min(high1,high2)

def evaluate_outcome(run:ReplicationRun, *, source_estimate:float|None, target_estimate:float|None,
                     source_effect_size:float|None, target_effect_size:float|None,
                     source_ci_low:float|None=None, source_ci_high:float|None=None,
                     target_ci_low:float|None=None, target_ci_high:float|None=None,
                     effect_tolerance:float=0.20,
                     protocol_fidelity:bool|None=None, measurement_fidelity:bool|None=None,
                     outcome_definition:bool|None=None, data_quality:bool|None=None)->ReplicationOutcome:
    checks={"direction":_direction(source_effect_size,target_effect_size),
            "effect":_effect(source_effect_size,target_effect_size,effect_tolerance),
            "interval":_interval(source_ci_low,source_ci_high,target_ci_low,target_ci_high),
            "protocol":protocol_fidelity,"measurement":measurement_fidelity,
            "outcome":outcome_definition,"data_quality":data_quality}
    unknown=[k for k,v in checks.items() if v is None]
    failed=[k for k,v in checks.items() if v is False]
    if failed:
        overall="NOT_REPLICATED"
    elif unknown:
        overall="NOT_ESTIMABLE" if len(unknown)>=len(checks) else "PARTIAL"
    else:
        overall="REPLICATED"
    rationale="failed="+(",".join(failed) or "none")+"; unknown="+(",".join(unknown) or "none")
    payload={"run":run.replication_run_id,"checks":checks,"overall":overall,"rationale":rationale}
    return ReplicationOutcome(run.replication_run_id,source_estimate,target_estimate,source_effect_size,
        target_effect_size,source_ci_low,source_ci_high,target_ci_low,target_ci_high,
        checks["direction"],checks["effect"],checks["interval"],overall,rationale,
        Provenance(ProvenanceTag.DRV,"cte.replication.outcome","1.5",content_hash(payload),
                   "Replication comparison; not empirical validation"))
