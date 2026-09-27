"""FastAPI adapter for V1.8 integrated platform orchestration."""
from __future__ import annotations
from dataclasses import asdict
from fastapi import HTTPException
from pydantic import BaseModel, Field
from .orchestrator import OrchestratorService

class ExecutionCreateInput(BaseModel):
    execution_id:str
    correlation_id:str
    input_payload:dict=Field(default_factory=dict)
    required_stages:list[str]|None=None

class StageInput(BaseModel):
    stage_name:str
    state:str
    input_hash:str|None=None
    output_hash:str|None=None
    module_version:str|None=None
    provenance_record_id:str|None=None
    reason:str|None=None
    metadata:dict=Field(default_factory=dict)

class EventInput(BaseModel):
    execution_id:str
    event_type:str
    input_hash:str
    output_hash:str|None=None
    provenance_record_id:str
    payload:dict=Field(default_factory=dict)

class ModuleInput(BaseModel):
    module_id:str
    version:str
    contract_version:str
    status:str="ACTIVE"

class SchemaInput(BaseModel):
    schema_id:str
    version:str
    compatibility_policy:str

class RuleInput(BaseModel):
    rule_id:str
    version:str
    provenance_class:str
    status:str="REGISTERED"

class RouteInput(BaseModel):
    module_id:str
    stage_name:str

class BlockInput(BaseModel):
    rule_id:str
    reason:str

class ResumeInput(BaseModel):
    resolved:bool

class FailureInput(BaseModel):
    failure_code:str
    rationale:str

def install_orchestrator_api(app):
    service=OrchestratorService()

    @app.post("/orchestrator/executions")
    def create_execution(p:ExecutionCreateInput):
        try:return asdict(service.create_execution(p.execution_id,p.correlation_id,p.input_payload,p.required_stages))
        except ValueError as e:raise HTTPException(400,str(e))

    @app.post("/orchestrator/executions/{execution_id}/start")
    def start_execution(execution_id:str):
        try:return asdict(service.start(execution_id))
        except ValueError as e:raise HTTPException(400,str(e))

    @app.post("/orchestrator/executions/{execution_id}/stages")
    def advance_stage(execution_id:str,p:StageInput):
        try:return asdict(service.advance_stage(execution_id,p.stage_name,p.state,input_hash=p.input_hash,output_hash=p.output_hash,module_version=p.module_version,provenance_record_id=p.provenance_record_id,reason=p.reason,metadata=p.metadata))
        except ValueError as e:raise HTTPException(400,str(e))

    @app.post("/orchestrator/events")
    def append_event(p:EventInput):
        try:
            return asdict(service.append_event(p.execution_id,p.event_type,p.input_hash,p.output_hash,p.provenance_record_id,p.payload))
        except ValueError as e:
            raise HTTPException(400,str(e))

    @app.get("/orchestrator/executions/{execution_id}")
    def get_execution(execution_id:str):
        try:return asdict(service._get(execution_id))
        except ValueError as e:raise HTTPException(404,str(e))

    @app.get("/orchestrator/executions/{execution_id}/events")
    def get_events(execution_id:str):
        try:return {"execution_id":execution_id,"events":[asdict(e) for e in service._get(execution_id).events]}
        except ValueError as e:raise HTTPException(404,str(e))

    @app.post("/orchestrator/modules/register")
    def register_module(p:ModuleInput):
        try:return asdict(service.register_module(p.module_id,p.version,p.contract_version,p.status))
        except ValueError as e:raise HTTPException(400,str(e))

    @app.post("/orchestrator/schemas/register")
    def register_schema(p:SchemaInput):
        try:return asdict(service.register_schema(p.schema_id,p.version,p.compatibility_policy))
        except ValueError as e:raise HTTPException(400,str(e))

    @app.post("/orchestrator/rules/register")
    def register_rule(p:RuleInput):
        try:return asdict(service.register_rule(p.rule_id,p.version,p.provenance_class,p.status))
        except ValueError as e:raise HTTPException(400,str(e))

    @app.post("/orchestrator/route")
    def route_execution(execution_id:str,p:RouteInput):
        try:return service.route(execution_id,p.module_id,p.stage_name)
        except ValueError as e:raise HTTPException(400,str(e))

    @app.post("/orchestrator/block")
    def block_execution(execution_id:str,p:BlockInput):
        try:return asdict(service.block(execution_id,p.rule_id,p.reason))
        except ValueError as e:raise HTTPException(400,str(e))

    @app.post("/orchestrator/resume")
    def resume_execution(execution_id:str,p:ResumeInput):
        try:return asdict(service.resume(execution_id,p.resolved))
        except ValueError as e:raise HTTPException(400,str(e))

    @app.post("/orchestrator/complete")
    def complete_execution(execution_id:str):
        try:return asdict(service.complete(execution_id))
        except ValueError as e:raise HTTPException(400,str(e))

    @app.post("/orchestrator/fail")
    def fail_execution(execution_id:str,p:FailureInput):
        try:return asdict(service.fail(execution_id,p.failure_code,p.rationale))
        except ValueError as e:raise HTTPException(400,str(e))

    @app.get("/orchestrator/executions/{execution_id}/provenance")
    def execution_provenance(execution_id:str):
        try:return service.provenance(execution_id)
        except ValueError as e:raise HTTPException(404,str(e))

    return service
