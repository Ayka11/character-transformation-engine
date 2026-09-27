"""FastAPI adapter for V1.7 decision and intervention runtime."""
from __future__ import annotations
from dataclasses import asdict
from fastapi import HTTPException
from pydantic import BaseModel, Field
from .intervention_engine import InterventionService

class InterventionRuleInput(BaseModel):
    rule_id:str
    rule_name:str
    provenance_class:str
    rule_version:str
    eligible_domains:list[str]
    contraindications:list[str]=Field(default_factory=list)
    required_inputs:list[str]=Field(default_factory=list)
    decision_logic:dict=Field(default_factory=dict)
    evidence_scope:dict=Field(default_factory=dict)
    status:str="REGISTERED"

class InterventionAssignInput(BaseModel):
    assignment_id:str
    user_id:str
    rule_id:str
    domain:str
    required_inputs:dict=Field(default_factory=dict)
    current_level:str
    safety_status:str
    data_quality_status:str
    source_assessment_id:str|None=None
    source_claim_ids:list[str]=Field(default_factory=list)

class InterventionSessionInput(BaseModel):
    session_id:str
    planned_load:dict=Field(default_factory=dict)

class InterventionMeasurementInput(BaseModel):
    metric_id:str
    value_numeric:float|None=None
    value_text:str|None=None
    missing_reason:str|None=None

class InterventionResponseInput(BaseModel):
    response_dimension:str
    baseline_value:float|None=None
    post_value:float|None=None
    safety_status:str="PASS"

class InterventionAdaptInput(BaseModel):
    adaptation_id:str
    prior_level:str
    response_status:str
    safety_status:str
    input_snapshot:dict=Field(default_factory=dict)

class ResearchLinkInput(BaseModel):
    relation:str
    result_node_id:str|None=None
    claim_id:str|None=None

def install_intervention_api(app, graph_registry):
    service=InterventionService(graph_registry)

    @app.post("/interventions/rules")
    def create_rule(p:InterventionRuleInput):
        try:
            rule=service.register_rule_from_fields(p.rule_id,p.rule_name,p.provenance_class,p.rule_version,
                p.eligible_domains,p.contraindications,p.required_inputs,p.decision_logic,p.evidence_scope,p.status)
            node=graph_registry.nodes.get(rule.rule_id)
            if node is None:
                from .evidence_graph import register_node
                node=graph_registry.add_node(register_node(
                    rule.rule_id,"PROTOCOL",rule.rule_id,rule.provenance_class,rule.rule_version,
                    {"kind":"INTERVENTION_RULE","rule_name":rule.rule_name,"eligible_domains":list(rule.eligible_domains),
                     "required_inputs":list(rule.required_inputs),"status":rule.status}
                ))
            return {"rule":asdict(rule),"graph_node":asdict(node)}
        except ValueError as e:
            raise HTTPException(400,str(e))

    @app.post("/interventions/assign")
    def assign(p:InterventionAssignInput):
        try:
            return asdict(service.assign(p.assignment_id,p.user_id,p.rule_id,p.domain,p.required_inputs,p.current_level,
                p.safety_status,p.data_quality_status,p.source_assessment_id,p.source_claim_ids))
        except ValueError as e:
            raise HTTPException(400,str(e))

    @app.post("/interventions/{assignment_id}/sessions")
    def create_session(assignment_id:str,p:InterventionSessionInput):
        try: return asdict(service.create_session(assignment_id,p.session_id,p.planned_load))
        except ValueError as e: raise HTTPException(400,str(e))

    @app.post("/interventions/sessions/{session_id}/measurements")
    def measurement(session_id:str,p:InterventionMeasurementInput):
        try: return service.record_measurement(session_id,p.metric_id,p.value_numeric,p.value_text,p.missing_reason)
        except ValueError as e: raise HTTPException(400,str(e))

    @app.post("/interventions/sessions/{session_id}/response")
    def response(session_id:str,p:InterventionResponseInput):
        try: return service.record_response(session_id,p.response_dimension,p.baseline_value,p.post_value,p.safety_status)
        except ValueError as e: raise HTTPException(400,str(e))

    @app.post("/interventions/{assignment_id}/adapt")
    def adapt(assignment_id:str,p:InterventionAdaptInput):
        try: return asdict(service.adapt(assignment_id,p.adaptation_id,p.prior_level,p.response_status,p.safety_status,p.input_snapshot))
        except ValueError as e: raise HTTPException(400,str(e))

    @app.get("/interventions/{assignment_id}")
    def get_assignment(assignment_id:str):
        assignment=service.assignments.get(assignment_id)
        if assignment is None: raise HTTPException(404,"assignment is not registered")
        return asdict(assignment)

    @app.post("/interventions/sessions/{session_id}/research-link")
    def research_link(session_id:str,p:ResearchLinkInput):
        try: return service.research_link(session_id,p.relation,p.result_node_id,p.claim_id)
        except ValueError as e: raise HTTPException(400,str(e))

    @app.get("/interventions/{assignment_id}/audit")
    def audit(assignment_id:str):
        assignment=service.assignments.get(assignment_id)
        if assignment is None: raise HTTPException(404,"assignment is not registered")
        return {"assignment_id":assignment_id,"events":assignment.audit}

    return service
