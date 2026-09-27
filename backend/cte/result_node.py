"""Canonical validation RESULT boundary.

A result is a graph-ready derived object. It is not itself a claim or evidence.
"""
from __future__ import annotations
from dataclasses import dataclass
from .provenance import Provenance, ProvenanceTag, content_hash

@dataclass(frozen=True)
class ResultNode:
    result_id: str
    analysis_id: str
    manifest_id: str
    analysis_spec_id: str
    qc_status: str
    n: int
    estimate: float | None
    ci95_low: float | None
    ci95_high: float | None
    provenance: Provenance

def build_result(*, result_id: str, analysis_id: str, manifest_id: str, analysis_spec_id: str, qc_status: str, n: int, estimate: float | None, ci95_low: float | None, ci95_high: float | None) -> ResultNode:
    payload={"result_id":result_id,"analysis_id":analysis_id,"manifest_id":manifest_id,"analysis_spec_id":analysis_spec_id,"qc_status":qc_status,"n":n,"estimate":estimate,"ci95_low":ci95_low,"ci95_high":ci95_high}
    return ResultNode(result_id,analysis_id,manifest_id,analysis_spec_id,qc_status,n,estimate,ci95_low,ci95_high,Provenance(ProvenanceTag.DRV,"cte.result","2.1.0",content_hash(payload),"Graph-ready result; not evidence or claim"))

def graph_node(result: ResultNode) -> dict:
    return {"node_id":result.result_id,"node_type":"RESULT","entity_id":result.result_id,"provenance_class":result.provenance.tag.value,"version":result.analysis_spec_id,"immutable_hash":result.provenance.input_hash,"metadata_json":{"analysis_id":result.analysis_id,"manifest_id":result.manifest_id,"qc_status":result.qc_status,"n":result.n,"estimate":result.estimate,"ci95_low":result.ci95_low,"ci95_high":result.ci95_high}}
