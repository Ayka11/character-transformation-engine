"""Executable V1.8 platform orchestrator.

Model-derived implementation of the repository's orchestration contract; not empirically validated.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from .provenance import content_hash
from .persistence import SQLiteRuntimeStore

LIFECYCLE=("INTAKE","PROFILE","ASSESSMENT","STATE_ESTIMATION","CAPACITY","RULE_ELIGIBILITY",
           "SAFETY_GATE","INTERVENTION","MEASUREMENT","QC","ANALYSIS","CLAIM",
           "REPLICATION","GENERALIZATION","REPORT","ADAPTATION","AUDIT")
EXECUTION_STATES=("CREATED","RUNNING","PAUSED","BLOCKED","COMPLETED","FAILED","CANCELLED")
STAGE_STATES=("PENDING","RUNNING","PASSED","BLOCKED","FAILED","SKIPPED")

@dataclass(frozen=True)
class OrchestratorEvent:
    event_id:str
    execution_id:str
    event_type:str
    input_hash:str
    output_hash:str|None
    provenance_record_id:str
    payload:dict
    sequence:int
    immutable_hash:str

@dataclass
class StageRecord:
    stage_name:str
    state:str="PENDING"
    input_hash:str|None=None
    output_hash:str|None=None
    module_version:str|None=None
    provenance_record_id:str|None=None
    reason:str|None=None
    metadata:dict=field(default_factory=dict)

@dataclass
class Execution:
    execution_id:str
    correlation_id:str
    state:str="CREATED"
    required_stages:tuple[str,...]=()
    stages:dict[str,StageRecord]=field(default_factory=dict)
    events:list[OrchestratorEvent]=field(default_factory=list)
    input_hash:str=""
    output_hash:str|None=None

@dataclass(frozen=True)
class ModuleRegistration:
    module_id:str
    version:str
    contract_version:str
    status:str
    immutable_hash:str

@dataclass(frozen=True)
class SchemaRegistration:
    schema_id:str
    version:str
    compatibility_policy:str
    immutable_hash:str

@dataclass(frozen=True)
class RuleRegistration:
    rule_id:str
    version:str
    provenance_class:str
    status:str
    immutable_hash:str

class OrchestratorService:
    def __init__(self, store: SQLiteRuntimeStore | None = None):
        self.store=store
        self.executions:dict[str,Execution]={}
        self.modules:dict[str,ModuleRegistration]={}
        self.schemas:dict[str,SchemaRegistration]={}
        self.rules:dict[str,RuleRegistration]={}
        self._hydrate()

    def create_execution(self,execution_id:str,correlation_id:str,input_payload:dict,
                         required_stages:list[str]|None=None)->Execution:
        if execution_id in self.executions: raise ValueError("execution already registered")
        stages=tuple(required_stages or ("INTAKE","PROFILE","ASSESSMENT","STATE_ESTIMATION","CAPACITY","RULE_ELIGIBILITY","SAFETY_GATE"))
        invalid=set(stages)-set(LIFECYCLE)
        if invalid: raise ValueError("unsupported lifecycle stage: "+",".join(sorted(invalid)))
        execution=Execution(execution_id,correlation_id,"CREATED",stages,
                            {name:StageRecord(name) for name in LIFECYCLE},
                            input_hash=content_hash(input_payload))
        self.executions[execution_id]=execution
        self.append_event(execution_id,"EXECUTION_CREATED",execution.input_hash,None,
                          f"{execution_id}:create",{"required_stages":list(stages)})
        return execution

    def start(self,execution_id:str,input_valid:bool=True)->Execution:
        e=self._get(execution_id)
        if e.state!="CREATED": raise ValueError("execution must be CREATED")
        if not input_valid: raise ValueError("input_valid guard failed")
        e.state="RUNNING"
        self.append_event(execution_id,"EXECUTION_STARTED",e.input_hash,None,f"{execution_id}:start",{})
        return e

    def advance_stage(self,execution_id:str,stage_name:str,state:str, *,
                      input_hash:str|None=None,output_hash:str|None=None,module_version:str|None=None,
                      provenance_record_id:str|None=None,reason:str|None=None,metadata:dict|None=None)->StageRecord:
        e=self._get(execution_id)
        if e.state!="RUNNING": raise ValueError("execution must be RUNNING")
        if stage_name not in LIFECYCLE: raise ValueError("unsupported lifecycle stage")
        if state not in STAGE_STATES: raise ValueError("unsupported stage state")
        stage=e.stages[stage_name]
        if stage.state not in {"PENDING","RUNNING"}: raise ValueError("stage is already terminal")
        md=dict(metadata or {})
        if state=="RUNNING" and stage.state=="PENDING":
            if stage_name in e.required_stages:
                idx=list(e.required_stages).index(stage_name)
                prior=list(e.required_stages)[:idx]
                incomplete=[name for name in prior if e.stages[name].state not in {"PASSED","SKIPPED"}]
                if incomplete:
                    raise ValueError("upstream required stages not terminal: "+",".join(incomplete))
        if state=="PASSED":
            if md.get("unknown_required_input"): raise ValueError("unknown required input cannot produce PASSED stage")
            if stage_name in e.required_stages:
                idx=list(e.required_stages).index(stage_name)
                prior=list(e.required_stages)[:idx]
                blocked=[name for name in prior if e.stages[name].state in {"BLOCKED","FAILED"}]
                if blocked:
                    raise ValueError("blocked or failed upstream stage prevents PASSED: "+",".join(blocked))
            safety=e.stages["SAFETY_GATE"]
            if stage_name!="SAFETY_GATE" and "SAFETY_GATE" in e.required_stages:
                if safety.state=="BLOCKED" or safety.metadata.get("safety_status")=="BLOCK":
                    idx=list(e.required_stages).index(stage_name)
                    safety_idx=list(e.required_stages).index("SAFETY_GATE")
                    if idx>safety_idx:
                        raise ValueError("safety gate blocks downstream PASSED stage")
            if stage_name=="CLAIM" and md.get("claim_state")=="EVIDENCE_SUPPORTED" and not md.get("claim_gate_passed",False):
                raise ValueError("orchestrator cannot promote claim to EVIDENCE_SUPPORTED without claim gate")
        if state=="SKIPPED" and not reason:
            raise ValueError("SKIPPED requires reason")
        if state=="BLOCKED" and not reason:
            raise ValueError("BLOCKED requires reason")
        if state=="FAILED" and not md.get("failure_code"):
            raise ValueError("FAILED requires failure_code")
        if stage.state=="PENDING" and state=="RUNNING":
            stage.state="RUNNING"
        else:
            stage.state=state
        stage.input_hash=input_hash; stage.output_hash=output_hash; stage.module_version=module_version
        stage.provenance_record_id=provenance_record_id; stage.reason=reason; stage.metadata=md
        event_type=f"STAGE_{stage.state}"
        self.append_event(execution_id,event_type,input_hash or e.input_hash,output_hash,
                          provenance_record_id or f"{execution_id}:{stage_name}",{"stage":stage_name,"reason":reason,"metadata":md})
        if state=="BLOCKED": e.state="BLOCKED"
        if state=="FAILED": e.state="FAILED"
        return stage

    def pause(self,execution_id:str,reason:str)->Execution:
        e=self._get(execution_id)
        if e.state!="RUNNING" or not reason: raise ValueError("pause requires RUNNING execution and resumable reason")
        e.state="PAUSED"
        self.append_event(execution_id,"EXECUTION_PAUSED",e.input_hash,None,f"{execution_id}:pause",{"reason":reason})
        return e

    def block(self,execution_id:str,rule_id:str,reason:str)->Execution:
        e=self._get(execution_id)
        if e.state!="RUNNING": raise ValueError("execution must be RUNNING")
        if not rule_id or not reason: raise ValueError("blocking rule and rationale are required")
        e.state="BLOCKED"
        self.append_event(execution_id,"EXECUTION_BLOCKED",e.input_hash,None,f"{execution_id}:block",{"rule_id":rule_id,"reason":reason})
        return e

    def resume(self,execution_id:str,resolved:bool)->Execution:
        e=self._get(execution_id)
        if e.state not in {"PAUSED","BLOCKED"} or not resolved: raise ValueError("resume condition is not satisfied")
        if e.state=="BLOCKED":
            for stage in e.stages.values():
                if stage.state=="BLOCKED":
                    stage.state="RUNNING"
                    stage.reason="blocking condition resolved; stage resumed"
        e.state="RUNNING"
        self.append_event(execution_id,"EXECUTION_RESUMED",e.input_hash,None,f"{execution_id}:resume",{"resolved":True})
        return e

    def fail(self,execution_id:str,failure_code:str,rationale:str)->Execution:
        e=self._get(execution_id)
        if e.state!="RUNNING": raise ValueError("execution must be RUNNING")
        e.state="FAILED"
        self.append_event(execution_id,"EXECUTION_FAILED",e.input_hash,None,f"{execution_id}:failure",{"failure_code":failure_code,"rationale":rationale})
        return e

    def complete(self,execution_id:str)->Execution:
        e=self._get(execution_id)
        if e.state!="RUNNING": raise ValueError("execution must be RUNNING")
        for name in e.required_stages:
            stage=e.stages[name]
            if stage.state not in {"PASSED","SKIPPED"}:
                raise ValueError(f"required stage not terminal-passed-or-skipped: {name}")
            if stage.state=="SKIPPED" and not stage.reason:
                raise ValueError(f"skipped stage requires reason: {name}")
        e.output_hash=content_hash({name:(e.stages[name].output_hash,e.stages[name].state) for name in e.required_stages})
        e.state="COMPLETED"
        self.append_event(execution_id,"EXECUTION_COMPLETED",e.input_hash,e.output_hash,f"{execution_id}:complete",{})
        return e

    def append_event(self,execution_id,event_type,input_hash,output_hash,provenance_record_id,payload)->OrchestratorEvent:
        e=self._get(execution_id)
        seq=len(e.events)+1
        body={"event_id":f"{execution_id}:event:{seq}","execution_id":execution_id,"event_type":event_type,
              "input_hash":input_hash,"output_hash":output_hash,"provenance_record_id":provenance_record_id,
              "payload":payload,"sequence":seq}
        event=OrchestratorEvent(body["event_id"],execution_id,event_type,input_hash,output_hash,
                                provenance_record_id,payload,seq,content_hash(body))
        e.events.append(event)
        return event

    def register_module(self,module_id,version,contract_version,status="ACTIVE"):
        if module_id in self.modules: raise ValueError("module already registered")
        item=ModuleRegistration(module_id,version,contract_version,status,
                                content_hash({"module_id":module_id,"version":version,"contract_version":contract_version,"status":status}))
        self.modules[module_id]=item
        return item

    def register_schema(self,schema_id,version,compatibility_policy):
        if schema_id in self.schemas: raise ValueError("schema already registered")
        item=SchemaRegistration(schema_id,version,compatibility_policy,
                                content_hash({"schema_id":schema_id,"version":version,"compatibility_policy":compatibility_policy}))
        self.schemas[schema_id]=item
        return item

    def register_rule(self,rule_id,version,provenance_class,status="REGISTERED"):
        if rule_id in self.rules: raise ValueError("rule already registered")
        if provenance_class not in {"EVD","MDL","HYP","RPT","DRV"}: raise ValueError("unsupported rule provenance")
        item=RuleRegistration(rule_id,version,provenance_class,status,
                               content_hash({"rule_id":rule_id,"version":version,"provenance_class":provenance_class,"status":status}))
        self.rules[rule_id]=item
        return item

    def route(self,execution_id,module_id,stage_name)->dict:
        e=self._get(execution_id)
        module=self.modules.get(module_id)
        if module is None or module.status!="ACTIVE": raise ValueError("module is not ACTIVE")
        if stage_name not in LIFECYCLE: raise ValueError("unsupported lifecycle stage")
        self.append_event(execution_id,"ROUTED",e.input_hash,None,f"{execution_id}:route:{stage_name}",
                          {"module_id":module_id,"module_version":module.version,"stage":stage_name})
        return {"execution_id":execution_id,"module_id":module_id,"module_version":module.version,"stage":stage_name}

    def provenance(self,execution_id)->dict:
        e=self._get(execution_id)
        artifacts=[]
        for stage in e.stages.values():
            if stage.input_hash or stage.output_hash:
                artifacts.append({"stage":stage.stage_name,"input_hash":stage.input_hash,"output_hash":stage.output_hash,
                                  "module_version":stage.module_version,"provenance_record_id":stage.provenance_record_id})
        return {"execution_id":execution_id,"input_hash":e.input_hash,"output_hash":e.output_hash,
                "artifacts":artifacts,"events":[asdict_event(x) for x in e.events]}

    def _get(self,execution_id):
        if execution_id not in self.executions: raise ValueError("execution is not registered")
        return self.executions[execution_id]

def asdict_event(event):
    return {"event_id":event.event_id,"execution_id":event.execution_id,"event_type":event.event_type,
            "input_hash":event.input_hash,"output_hash":event.output_hash,
            "provenance_record_id":event.provenance_record_id,"payload":event.payload,
            "sequence":event.sequence,"immutable_hash":event.immutable_hash}
