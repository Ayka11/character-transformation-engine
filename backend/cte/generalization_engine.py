"""Executable V1.5 generalization/transport comparison engine.

Model-derived implementation of the repository V1.5 contract; not empirically validated.
"""
from __future__ import annotations
from dataclasses import dataclass
from .provenance import Provenance, ProvenanceTag, content_hash

@dataclass(frozen=True)
class GeneralizationSpec:
    generalization_spec_id:str
    source_claim_id:str
    source_population:dict
    target_population:dict
    source_context:dict
    target_context:dict
    transport_dimensions:list[str]
    acceptance_rules:dict
    version:str
    provenance:Provenance

def register_spec(generalization_spec_id:str, source_claim_id:str, *,
                  source_population:dict, target_population:dict,
                  source_context:dict, target_context:dict,
                  transport_dimensions:list[str]|None=None,
                  acceptance_rules:dict|None=None,
                  version:str="1.5")->GeneralizationSpec:
    if not target_context:
        raise ValueError("target_context is required")
    dims=transport_dimensions or ["population","context","task","measurement","intervention","time","data_quality"]
    rules=dict(acceptance_rules or {})
    payload={"generalization_spec_id":generalization_spec_id,"source_claim_id":source_claim_id,
             "source_population":source_population,"target_population":target_population,
             "source_context":source_context,"target_context":target_context,
             "transport_dimensions":dims,"acceptance_rules":rules,"version":version}
    return GeneralizationSpec(generalization_spec_id,source_claim_id,source_population,target_population,
        source_context,target_context,dims,rules,version,
        Provenance(ProvenanceTag.DRV,"cte.generalization.spec","1.5",content_hash(payload),
                   "Registered transport specification; not empirical validation"))

@dataclass(frozen=True)
class GeneralizationRun:
    generalization_run_id:str
    generalization_spec_id:str
    source_result_node_id:str
    dataset_manifest_id:str
    transport_analysis_version:str
    input_hash:str
    status:str
    provenance:Provenance

def register_run(generalization_run_id:str,spec:GeneralizationSpec, *,
                 source_result_node_id:str,dataset_manifest_id:str,
                 transport_analysis_version:str,input_hash:str)->GeneralizationRun:
    payload={"generalization_run_id":generalization_run_id,"generalization_spec_id":spec.generalization_spec_id,
             "source_result_node_id":source_result_node_id,"dataset_manifest_id":dataset_manifest_id,
             "transport_analysis_version":transport_analysis_version,"input_hash":input_hash}
    return GeneralizationRun(generalization_run_id,spec.generalization_spec_id,source_result_node_id,
        dataset_manifest_id,transport_analysis_version,input_hash,"REGISTERED",
        Provenance(ProvenanceTag.DRV,"cte.generalization.run","1.5",content_hash(payload),
                   "Registered transport run; not empirical validation"))

@dataclass(frozen=True)
class GeneralizationResult:
    generalization_run_id:str
    source_estimate:float|None
    transported_estimate:float|None
    transport_error:float|None
    ci_low:float|None
    ci_high:float|None
    heterogeneity_statistic:float|None
    heterogeneity_p_value:float|None
    result_status:str
    rationale:str
    provenance:Provenance

def evaluate(run:GeneralizationRun, *, source_estimate:float|None, transported_estimate:float|None,
             ci_low:float|None=None, ci_high:float|None=None,
             transport_error:float|None=None,
             heterogeneity_statistic:float|None=None,
             heterogeneity_p_value:float|None=None,
             dimensions:dict[str,str]|None=None,
             max_transport_error:float=0.20,
             max_heterogeneity:float|None=None)->GeneralizationResult:
    dims=dimensions or {}
    unknown=[k for k in ("population","context","task","measurement","intervention","time","data_quality") if dims.get(k) in (None,"UNKNOWN")]
    failures=[k for k,v in dims.items() if v=="HIGH"]
    if transport_error is None or source_estimate is None or transported_estimate is None:
        status="NOT_ESTIMABLE"
    elif failures or abs(transport_error)>max_transport_error:
        status="NOT_GENERALIZABLE"
    elif max_heterogeneity is not None and heterogeneity_statistic is not None and heterogeneity_statistic>max_heterogeneity:
        status="LIMITED_GENERALIZABILITY"
    elif unknown:
        status="LIMITED_GENERALIZABILITY"
    else:
        status="GENERALIZABLE"
    rationale="high_transport="+(",".join(failures) or "none")+"; unknown="+(",".join(unknown) or "none")
    payload={"run":run.generalization_run_id,"status":status,"transport_error":transport_error,
             "heterogeneity_statistic":heterogeneity_statistic,"dimensions":dims}
    return GeneralizationResult(run.generalization_run_id,source_estimate,transported_estimate,transport_error,
        ci_low,ci_high,heterogeneity_statistic,heterogeneity_p_value,status,rationale,
        Provenance(ProvenanceTag.DRV,"cte.generalization.result","1.5",content_hash(payload),
                   "Transport result; not empirical validation"))
