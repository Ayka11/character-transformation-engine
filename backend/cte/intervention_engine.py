"""Executable V1.7 decision and intervention runtime.

Model-derived implementation of the repository's V1.7 contract; not empirically validated.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from .provenance import content_hash
from .persistence import SQLiteRuntimeStore

LEVELS=("A","B","C","D","E")
DECISIONS=("CONTINUE","ADJUST","HOLD","DEESCALATE","STOP","INSUFFICIENT_DATA")
RULE_STATUSES=("DRAFT","REGISTERED","ACTIVE","SUSPENDED","RETIRED")

@dataclass(frozen=True)
class InterventionRule:
    rule_id:str
    rule_name:str
    provenance_class:str
    rule_version:str
    eligible_domains:tuple[str,...]
    contraindications:tuple[str,...]
    required_inputs:tuple[str,...]
    decision_logic:dict
    evidence_scope:dict
    status:str
    immutable_hash:str

@dataclass
class Assignment:
    assignment_id:str
    user_id:str
    rule_id:str
    rule_version:str
    selected_level:str
    source_assessment_id:str|None
    source_claim_ids:tuple[str,...]
    selection_reason:dict
    safety_gate_status:str
    status:str="ASSIGNED"
    sessions:dict[str,"Session"]=field(default_factory=dict)
    adaptations:list["AdaptationDecision"]=field(default_factory=list)
    audit:list[dict]=field(default_factory=list)
    links:list[dict]=field(default_factory=list)

@dataclass
class Session:
    session_id:str
    assignment_id:str
    planned_load:dict
    completion_status:str="PLANNED"
    executed_load:dict|None=None
    stop_reason:str|None=None
    measurements:dict[str,dict]=field(default_factory=dict)
    response:dict|None=None

@dataclass(frozen=True)
class AdaptationDecision:
    adaptation_id:str
    assignment_id:str
    prior_level:str
    next_level:str
    decision:str
    rule_id:str
    input_snapshot_hash:str
    explanation:str
    safety_status:str

class InterventionService:
    def __init__(self,registry,store:SQLiteRuntimeStore|None=None):
        self.registry=registry
        self.store=store
        self.rules:dict[str,InterventionRule]={}
        self.assignments:dict[str,Assignment]={}
        self._hydrate()

    def register_rule(self,rule:InterventionRule)->InterventionRule:
        if rule.rule_id in self.rules: raise ValueError("intervention rule already registered")
        if rule.status not in RULE_STATUSES: raise ValueError("unsupported intervention rule status")
        if rule.provenance_class not in {"EVD","MDL","HYP","RPT","DRV"}:
            raise ValueError("unsupported intervention rule provenance")
        self.rules[rule.rule_id]=rule
        return rule

    def register_rule_from_fields(self,rule_id,rule_name,provenance_class,rule_version,
                                   eligible_domains,contraindications,required_inputs,
                                   decision_logic,evidence_scope,status="REGISTERED"):
        payload={"rule_id":rule_id,"rule_name":rule_name,"provenance_class":provenance_class,
                 "rule_version":rule_version,"eligible_domains":eligible_domains,"contraindications":contraindications,
                 "required_inputs":required_inputs,"decision_logic":decision_logic,
                 "evidence_scope":evidence_scope,"status":status}
        return self.register_rule(InterventionRule(rule_id,rule_name,provenance_class,rule_version,
            tuple(eligible_domains),tuple(contraindications),tuple(required_inputs),
            dict(decision_logic),dict(evidence_scope),status,content_hash(payload)))

    def assign(self,assignment_id,user_id,rule_id,domain,required_inputs:dict,current_level:str,
               safety_status:str,data_quality_status:str,source_assessment_id=None,source_claim_ids=None,
               context_flags:set[str]|None=None)->Assignment:
        if assignment_id in self.assignments: raise ValueError("assignment already registered")
        rule=self.rules.get(rule_id)
        if rule is None: raise ValueError("rule is not registered")
        if rule.status!="ACTIVE": raise ValueError("intervention rule is not ACTIVE")
        if domain not in rule.eligible_domains: raise ValueError("rule is outside eligible domain scope")
        missing=[x for x in rule.required_inputs if required_inputs.get(x) is None]
        if missing: raise ValueError("required intervention inputs missing: "+",".join(missing))
        if current_level not in LEVELS: raise ValueError("unsupported capacity level")
        if safety_status not in {"PASS","HOLD","BLOCK"}: raise ValueError("unsupported safety gate status")
        if data_quality_status not in {"PASS","UNKNOWN","FAIL"}: raise ValueError("unsupported data quality status")
        flags=set(context_flags or ())
        contraindication_hit=bool(flags.intersection(rule.contraindications))
        if contraindication_hit:
            safety_status="BLOCK"
        if safety_status=="BLOCK" or data_quality_status=="FAIL":
            level=current_level; gate="BLOCK"
        elif safety_status=="HOLD" or data_quality_status=="UNKNOWN":
            level=current_level; gate="HOLD"
        else:
            level=current_level; gate="PASS"
        reason={"domain":domain,"missing_inputs":missing,"capacity_level":current_level,
                "safety_status":safety_status,"data_quality_status":data_quality_status,
                "contraindication_hit":contraindication_hit,"context_flags":sorted(flags)}
        assignment=Assignment(assignment_id,user_id,rule_id,rule.rule_version,level,source_assessment_id,
            tuple(source_claim_ids or ()),reason,gate)
        self.assignments[assignment_id]=assignment
        assignment.audit.append(self._audit("ASSIGNMENT_CREATED",assignment_id,reason))
        return assignment

    def create_session(self,assignment_id,session_id,planned_load):
        assignment=self.assignments.get(assignment_id)
        if assignment is None: raise ValueError("assignment is not registered")
        if session_id in assignment.sessions: raise ValueError("session already registered")
        if assignment.safety_gate_status=="BLOCK": raise ValueError("blocked assignment cannot create session")
        session=Session(session_id,assignment_id,dict(planned_load))
        assignment.sessions[session_id]=session
        assignment.audit.append(self._audit("SESSION_CREATED",assignment_id,{"session_id":session_id}))
        return session

    def record_measurement(self,session_id,metric_id, value_numeric=None, value_text=None, missing_reason=None):
        session,assignment=self._find_session(session_id)
        if value_numeric is None and value_text is None and not missing_reason:
            raise ValueError("measurement requires a value or explicit missing_reason")
        measurement={"metric_id":metric_id,"value_numeric":value_numeric,"value_text":value_text,
                     "missing_reason":missing_reason,"provenance_class":"OBS"}
        session.measurements[metric_id]=measurement
        assignment.audit.append(self._audit("MEASUREMENT_RECORDED",assignment.assignment_id,measurement))
        return measurement

    def record_response(self,session_id,response_dimension,baseline_value,post_value,safety_status="PASS"):
        session,assignment=self._find_session(session_id)
        if response_dimension not in {"TARGET_TRAIT","SUPPORTING_STATE","BEHAVIOR","SAFETY","ADHERENCE","CAPACITY"}:
            raise ValueError("unsupported response dimension")
        if safety_status=="BLOCK":
            status="DEGRADED"
        elif baseline_value is None or post_value is None:
            status="UNKNOWN"
        else:
            delta=post_value-baseline_value
            status="IMPROVED" if delta>0 else ("DEGRADED" if delta<0 else "STABLE")
        response={"response_dimension":response_dimension,"baseline_value":baseline_value,
                  "post_value":post_value,"change_value":None if baseline_value is None or post_value is None else post_value-baseline_value,
                  "response_status":status,"safety_status":safety_status}
        session.response=response
        assignment.audit.append(self._audit("RESPONSE_RECORDED",assignment.assignment_id,response))
        return response

    def adapt(self,assignment_id,adaptation_id,prior_level,response_status,safety_status,input_snapshot):
        assignment=self.assignments.get(assignment_id)
        if assignment is None: raise ValueError("assignment is not registered")
        if prior_level not in LEVELS: raise ValueError("unsupported prior level")
        if safety_status=="BLOCK":
            decision="STOP"; next_level="A"
        elif response_status=="UNKNOWN":
            decision="INSUFFICIENT_DATA"; next_level=prior_level
        elif response_status=="DEGRADED":
            decision="DEESCALATE"; next_level=LEVELS[max(0,LEVELS.index(prior_level)-1)]
        elif response_status=="IMPROVED":
            decision="ADJUST" if prior_level!="E" else "CONTINUE"
            next_level=LEVELS[min(4,LEVELS.index(prior_level)+1)] if decision=="ADJUST" else prior_level
        else:
            decision="CONTINUE"; next_level=prior_level
        snapshot_hash=content_hash(input_snapshot)
        item=AdaptationDecision(adaptation_id,assignment_id,prior_level,next_level,decision,
            assignment.rule_id,snapshot_hash,
            f"{decision} based on registered rule and recorded response.",
            "BLOCKED" if safety_status=="BLOCK" else ("UNKNOWN" if response_status=="UNKNOWN" else "SAFE"))
        assignment.adaptations.append(item)
        assignment.audit.append(self._audit("ADAPTATION_DECIDED",assignment_id,{"adaptation":item.decision,"next_level":next_level}))
        return item

    def research_link(self,session_id,relation,result_node_id=None,claim_id=None):
        session,assignment=self._find_session(session_id)
        if relation not in {"GENERATES_OBSERVATION","CONTRIBUTES_TO_ANALYSIS","SUPPORTS_CLAIM","LIMITS_CLAIM","CONTRADICTS_CLAIM"}:
            raise ValueError("unsupported research link relation")
        if relation in {"SUPPORTS_CLAIM","LIMITS_CLAIM","CONTRADICTS_CLAIM"} and not claim_id:
            raise ValueError("claim_id is required for claim relation")
        if result_node_id and (result_node_id not in self.registry.nodes or self.registry.nodes[result_node_id].node_type!="RESULT"):
            raise ValueError("result_node_id must reference a registered RESULT")
        if claim_id and (claim_id not in self.registry.nodes or self.registry.nodes[claim_id].node_type!="CLAIM"):
            raise ValueError("claim_id must reference a registered CLAIM")
        link={"session_id":session_id,"relation":relation,"research_result_node_id":result_node_id,"claim_id":claim_id,
              "runtime_observation_is_evidence":False}
        assignment.links.append(link)
        return link

    def _find_session(self,session_id):
        for assignment in self.assignments.values():
            if session_id in assignment.sessions: return assignment.sessions[session_id],assignment
        raise ValueError("session is not registered")

    @staticmethod
    def _audit(event_type,assignment_id,event):
        return {"event_type":event_type,"assignment_id":assignment_id,"event":event,
                "input_hash":content_hash(event),"actor_type":"SYSTEM"}
