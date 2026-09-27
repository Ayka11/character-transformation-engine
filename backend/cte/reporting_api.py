"""FastAPI adapter for V1.6 scientific reporting."""
from __future__ import annotations
from dataclasses import asdict
from fastapi import HTTPException
from pydantic import BaseModel, Field
from .reporting import ReportService, register_spec

class ReportSpecInput(BaseModel):
    report_spec_id:str
    name:str
    version:str="1.6"
    section_order:list[str]|None=None
    rendering_rules:dict=Field(default_factory=dict)
    claim_language_rules:dict=Field(default_factory=dict)

class ReportCreateInput(BaseModel):
    report_run_id:str
    report_spec_id:str
    study_id:str
    source_artifacts:list[str]

class ReportSectionInput(BaseModel):
    section_code:str
    ordinal:int
    content:dict=Field(default_factory=dict)
    source_artifacts:list[str]
    derivation_rule_id:str="V1.6_RENDER"
    derivation_rule_version:str="1.6"
    evidence_status:str="INDETERMINATE"
    limitations:list[str]=Field(default_factory=list)

class ReportClaimInput(BaseModel):
    claim_id:str
    allowed_claim_status:str|None=None

class ReportDecisionInput(BaseModel):
    decision_id:str
    decision_type:str
    decision:str
    rule_id:str
    inputs:dict=Field(default_factory=dict)
    rationale:str

class ReportSupersedeInput(BaseModel):
    new_report_id:str

def install_reporting_api(app, graph_registry):
    service=ReportService(graph_registry)
    
    @app.post("/reports/specs")
    def create_spec(p:ReportSpecInput):
        if p.report_spec_id in service.specs:
            raise HTTPException(409,"report spec already registered")
        spec=register_spec(p.report_spec_id,p.name,p.version,p.section_order,p.rendering_rules,p.claim_language_rules)
        service.specs[p.report_spec_id]=spec
        return asdict(spec)

    @app.post("/reports")
    def create_report(p:ReportCreateInput):
        try:
            return asdict(service.create(p.report_run_id,p.report_spec_id,p.study_id,p.source_artifacts))
        except ValueError as e:
            raise HTTPException(400,str(e))

    @app.post("/reports/{report_id}/sections")
    def add_section(report_id:str,p:ReportSectionInput):
        try:
            sec=service.add_section(report_id,p.section_code,p.content,p.source_artifacts,p.ordinal,
                                    p.derivation_rule_id,p.derivation_rule_version,p.evidence_status,p.limitations)
            return asdict(sec)
        except ValueError as e:
            raise HTTPException(400,str(e))

    @app.post("/reports/{report_id}/claims")
    def bind_claim(report_id:str,p:ReportClaimInput):
        try:
            return asdict(service.bind_claim(report_id,p.claim_id,p.allowed_claim_status))
        except ValueError as e:
            raise HTTPException(400,str(e))

    @app.post("/reports/{report_id}/decisions")
    def add_decision(report_id:str,p:ReportDecisionInput):
        try:
            return service.add_decision(report_id,p.decision_id,p.decision_type,p.decision,p.rule_id,p.inputs,p.rationale)
        except ValueError as e:
            raise HTTPException(400,str(e))

    @app.post("/reports/{report_id}/qc")
    def report_qc(report_id:str):
        try:
            return service.qc_run(report_id)
        except ValueError as e:
            raise HTTPException(400,str(e))

    @app.get("/reports/{report_id}")
    def get_report(report_id:str):
        run=service.runs.get(report_id)
        if run is None: raise HTTPException(404,"report is not registered")
        return asdict(run)

    @app.get("/reports/{report_id}/provenance")
    def get_report_provenance(report_id:str):
        run=service.runs.get(report_id)
        if run is None: raise HTTPException(404,"report is not registered")
        return {"report_run_id":report_id,"source_artifacts":list(run.source_artifacts),
                "source_manifest_hash":run.source_manifest_hash,
                "sections":{k:list(v.source_artifacts) for k,v in run.sections.items()},
                "claim_bindings":{k:list(v.supporting_nodes)+list(v.limiting_nodes)+list(v.contradiction_nodes) for k,v in run.bindings.items()}}

    @app.post("/reports/{report_id}/publish")
    def publish_report(report_id:str):
        try:
            return asdict(service.publish(report_id))
        except ValueError as e:
            raise HTTPException(400,str(e))

    @app.post("/reports/{report_id}/supersede")
    def supersede_report(report_id:str,p:ReportSupersedeInput):
        try:
            return asdict(service.supersede(report_id,p.new_report_id))
        except ValueError as e:
            raise HTTPException(400,str(e))

    return service
