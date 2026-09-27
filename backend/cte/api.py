from dataclasses import asdict
from fastapi import FastAPI
from pydantic import BaseModel, Field
from .models import DailyState
from .capacity import compute_capacity
from .compatibility import compatibility_v1, compatibility_v2, compatibility_v3
from .catalog import ADAPTIVE_LEVELS, MASTER_MATRIX, MATRIX_VERSION, SPRINT_TEMPLATE
from .assessment import build_profile
from .state_engine import derive_daily_state
from .trait_graph import TraitGraph
from .intervention import plan_bio_reset, plan_21_day_sprint
from .sprint import start_sprint, record_day
from .outcome import evaluate_outcome
from .runtime_events import make_event, lineage_descriptor
from .analysis import descriptive
from .longitudinal import longitudinal_change
from .registered_analysis import lock_manifest, paired_effect
from .result_node import build_result, graph_node
from .evidence_graph import register_node, register_edge
from .graph_registry import build_registry
from .claim_gate import validate_claim_transition
from .replication import register_replication, register_generalization
from .replication_engine import ReplicationRun as EngineReplicationRun, register_spec, register_run, evaluate_outcome as evaluate_replication_outcome

app = FastAPI(title="Character Transformation Engine", version="2.1.0")
GRAPH_REGISTRY = build_registry()
REPLICATION_SPECS = {}
REPLICATION_RUNS = {}

class StateInput(BaseModel):
    sleep_quality: float | None = Field(None, ge=0, le=10)
    recovery_index: float | None = Field(None, ge=0, le=10)
    physical_activity: float | None = Field(None, ge=0, le=10)
    metabolic_stability: float | None = Field(None, ge=0, le=10)
    subjective_stress: float | None = Field(None, ge=0, le=10)
    subjective_energy: float | None = Field(None, ge=0, le=10)

class CompatibilityInput(BaseModel):
    bio_a: dict[str, float] = Field(default_factory=dict)
    bio_b: dict[str, float] = Field(default_factory=dict)
    values_a: dict[str, float] = Field(default_factory=dict)
    values_b: dict[str, float] = Field(default_factory=dict)
    roles_a: list[str] = Field(default_factory=list)
    roles_b: list[str] = Field(default_factory=list)
    synergy: dict[str, float] = Field(default_factory=dict)

class ObservationInput(BaseModel):
    item_id: str
    value: float = Field(ge=0, le=10)
    observation_id: str

class AssessmentInput(BaseModel):
    observations: list[ObservationInput]
    source_id: str = "assessment.api"
    source_version: str = "1.0"

class InterventionInput(AssessmentInput):
    requested_trait: str
    blockers: dict[str, float] = Field(default_factory=dict)
    supporting_bio_habit: str = "consistent recovery routine"
    daily_action: str = "one deliberate pause before a response"

class SprintStartInput(BaseModel):
    sprint_id: str
    target_trait: str
    supporting_bio_habit: str
    daily_action: str

class ClaimGateInput(BaseModel):
    result_id: str
    current_state: str
    target_level: str
    provenance_class: str = "DRV"

class ClaimInput(BaseModel):
    claim_id: str
    result_id: str | None = None
    current_state: str
    target_state: str
    provenance_class: str = "DRV"
    metadata: dict = Field(default_factory=dict)
    previous_claim_id: str | None = None

class ReplicationSpecInput(BaseModel):
    replication_spec_id: str
    source_claim_id: str
    primary_outcome_id: str
    criteria: dict = Field(default_factory=dict)

class ReplicationRunInput(BaseModel):
    replication_run_id: str
    replication_spec_id: str
    source_result_node_id: str
    independent_study_id: str
    dataset_manifest_id: str
    protocol_hash: str
    input_hash: str
    independent: bool

class ReplicationOutcomeInput(BaseModel):
    replication_run_id: str
    source_estimate: float | None = None
    target_estimate: float | None = None
    source_effect_size: float | None = None
    target_effect_size: float | None = None
    source_ci_low: float | None = None
    source_ci_high: float | None = None
    target_ci_low: float | None = None
    target_ci_high: float | None = None
    effect_tolerance: float = Field(0.20, ge=0)
    protocol_fidelity: bool | None = None
    measurement_fidelity: bool | None = None
    outcome_definition: bool | None = None
    data_quality: bool | None = None

class ReplicationInput(BaseModel):
    replication_id: str
    source_result_id: str
    independent: bool = False
    criteria_registered: bool = False
    status: str = "REGISTERED"

class GeneralizationInput(BaseModel):
    generalization_id: str
    source_result_id: str
    run_status: str
    target_population_context: str

class NodeInput(BaseModel):
    node_id: str
    node_type: str
    entity_id: str
    provenance_class: str = "DRV"
    version: str = "2.1.0"
    metadata: dict = Field(default_factory=dict)

class GraphEdgeInput(BaseModel):
    edge_id: str
    from_node_id: str
    from_node_type: str
    to_node_id: str
    to_node_type: str
    edge_type: str
    rationale: str = ""

class RegisteredPairedInput(BaseModel):
    result_id: str = "result-1"
    analysis_id: str = "analysis-1"
    baseline: list[float | None]
    current: list[float | None]
    manifest_id: str
    analysis_spec_id: str

class LongitudinalInput(BaseModel):
    baseline: list[float | None]
    current: list[float | None]

class AnalysisInput(BaseModel):
    values: list[float | None]
    ids: list[str] | None = None

class OutcomeInput(BaseModel):
    execution_id: str = "runtime-outcome"
    baseline: float | None = Field(None, ge=0, le=10)
    current: float | None = Field(None, ge=0, le=10)
    tolerance: float = Field(0.25, ge=0)
    safety_block: bool = False

class SprintDayInput(BaseModel):
    sprint_id: str
    target_trait: str
    supporting_bio_habit: str
    daily_action: str
    current_day: int
    status: str = "ACTIVE"
    day: int
    action_completed: bool
    outcome: float | None = Field(None, ge=0, le=10)
    state: StateInput

GRAPH = TraitGraph({
    "P3.pause_capacity": ["P3.impulse_control"],
    "P3.impulse_control": ["P5.discipline_consistency"],
    "P3.cognitive_reappraisal": ["P3.reflection_depth"],
    "P3.attention_regulation": ["P3.pause_capacity"],
})

@app.get("/health")
def health():
    return {"status":"ok","version":"2.1.0","scientific_status":"implementation_baseline"}

@app.get("/matrix")
def matrix_catalog():
    return {"version":MATRIX_VERSION,"items":[asdict(item) for item in MASTER_MATRIX],"adaptive_levels":ADAPTIVE_LEVELS,"sprint_template":SPRINT_TEMPLATE}

def _profile(p: AssessmentInput):
    return build_profile([row.model_dump() for row in p.observations], source_id=p.source_id, source_version=p.source_version)

@app.post("/assessment/profile")
def assessment_profile(p: AssessmentInput):
    profile=_profile(p)
    return {"source_id":profile.source_id,"source_version":profile.source_version,"measurements":[asdict(m) for m in profile.measurements]}

@app.post("/runtime/state-capacity")
def runtime_state_capacity(p: AssessmentInput):
    profile=_profile(p)
    derived=derive_daily_state(profile)
    capacity=compute_capacity(derived.state)
    return {"source_id":profile.source_id,"source_version":profile.source_version,"state":asdict(derived.state),"missing_state_inputs":list(derived.missing),"capacity":asdict(capacity),"adaptive_level":ADAPTIVE_LEVELS[capacity.level]}

@app.post("/runtime/intervention")
def runtime_intervention(p: InterventionInput):
    profile=_profile(p)
    state=derive_daily_state(profile).state
    bio_reset=plan_bio_reset(state,p.requested_trait,GRAPH,p.blockers)
    sprint=plan_21_day_sprint(state,p.requested_trait,GRAPH,p.blockers,p.supporting_bio_habit,p.daily_action)
    return {"bio_reset":asdict(bio_reset),"sprint":asdict(sprint)}

@app.post("/runtime/sprint/start")
def runtime_sprint_start(p: SprintStartInput):
    return asdict(start_sprint(p.sprint_id,p.target_trait,p.supporting_bio_habit,p.daily_action))

@app.post("/runtime/sprint/day")
def runtime_sprint_day(p: SprintDayInput):
    state=DailyState(**p.state.model_dump())
    sprint=type("SprintStateAdapter",(),{})()
    sprint.sprint_id=p.sprint_id
    sprint.target_trait=p.target_trait
    sprint.duration_days=21
    sprint.current_day=p.current_day
    sprint.status=p.status
    sprint.supporting_bio_habit=p.supporting_bio_habit
    sprint.daily_action=p.daily_action
    return asdict(record_day(sprint,p.day,p.action_completed,p.outcome,state))

@app.post("/replication/specs")
def replication_spec_register(p: ReplicationSpecInput):
    spec=register_spec(p.replication_spec_id,p.source_claim_id,p.primary_outcome_id,p.criteria)
    if p.replication_spec_id in REPLICATION_SPECS:
        raise ValueError("replication spec already registered")
    REPLICATION_SPECS[p.replication_spec_id]=spec
    GRAPH_REGISTRY.add_node(register_node(spec.replication_spec_id,"PROTOCOL",spec.replication_spec_id,spec.provenance.tag.value,"1.5",{"kind":"REPLICATION_SPEC","source_claim_id":spec.source_claim_id,"primary_outcome_id":spec.primary_outcome_id,"criteria":spec.criteria}))
    return asdict(spec)

@app.post("/replication/runs")
def replication_run_register(p: ReplicationRunInput):
    spec=REPLICATION_SPECS.get(p.replication_spec_id)
    if spec is None:
        raise ValueError("replication_spec_id must reference a registered replication spec")
    source=GRAPH_REGISTRY.nodes.get(p.source_result_node_id)
    if source is None or source.node_type!="RESULT":
        raise ValueError("source_result_node_id must reference a registered RESULT")
    run=register_run(p.replication_run_id,spec,source_result_node_id=p.source_result_node_id,independent_study_id=p.independent_study_id,dataset_manifest_id=p.dataset_manifest_id,protocol_hash=p.protocol_hash,input_hash=p.input_hash,independent=p.independent)
    if p.replication_run_id in REPLICATION_RUNS:
        raise ValueError("replication run already registered")
    REPLICATION_RUNS[p.replication_run_id]=run
    node=register_node(run.replication_run_id,"REPLICATION",run.replication_run_id,run.provenance.tag.value,"1.5",{"source_result_id":run.source_result_node_id,"replication_spec_id":run.replication_spec_id,"independent":p.independent,"criteria_registered":True,"status":run.status,"independent_study_id":run.independent_study_id,"dataset_manifest_id":run.dataset_manifest_id,"protocol_hash":run.protocol_hash,"input_hash":run.input_hash})
    GRAPH_REGISTRY.add_node(node)
    GRAPH_REGISTRY.add_edge(register_edge(f"{node.node_id}:replicates:{source.node_id}",node,source,"REPLICATES",rationale="registered V1.5 replication run"))
    return {"run":asdict(run),"graph_node":asdict(node)}

@app.post("/replication/runs/{replication_run_id}/outcomes")
def replication_outcome_register(replication_run_id: str,p: ReplicationOutcomeInput):
    if p.replication_run_id != replication_run_id:
        raise ValueError("path and payload replication_run_id mismatch")
    run=REPLICATION_RUNS.get(replication_run_id)
    if run is None:
        raise ValueError("replication run is not registered")
    result=evaluate_replication_outcome(run,source_estimate=p.source_estimate,target_estimate=p.target_estimate,source_effect_size=p.source_effect_size,target_effect_size=p.target_effect_size,source_ci_low=p.source_ci_low,source_ci_high=p.source_ci_high,target_ci_low=p.target_ci_low,target_ci_high=p.target_ci_high,effect_tolerance=p.effect_tolerance,protocol_fidelity=p.protocol_fidelity,measurement_fidelity=p.measurement_fidelity,outcome_definition=p.outcome_definition,data_quality=p.data_quality)
    assessment_id=f"{replication_run_id}:assessment:{result.overall_outcome}"
    node=register_node(assessment_id,"REPLICATION",assessment_id,result.provenance.tag.value,"1.5",{"source_result_id":run.source_result_node_id,"replication_run_id":run.replication_run_id,"independent":True,"criteria_registered":True,"status":result.overall_outcome,"assessment_status":result.overall_outcome})
    GRAPH_REGISTRY.add_node(node)
    GRAPH_REGISTRY.add_edge(register_edge(f"{assessment_id}:replicates:{run.source_result_node_id}",node,GRAPH_REGISTRY.nodes[run.source_result_node_id],"REPLICATES",rationale="V1.5 replication outcome assessment"))
    return {"outcome":asdict(result),"assessment_graph_node":asdict(node)}

@app.post("/validation/replication/register")
def validation_replication(p: ReplicationInput):
    if p.source_result_id not in GRAPH_REGISTRY.nodes or GRAPH_REGISTRY.nodes[p.source_result_id].node_type!="RESULT":
        raise ValueError("source_result_id must reference a registered RESULT")
    record=register_replication(p.replication_id,p.source_result_id,independent=p.independent,criteria_registered=p.criteria_registered,status=p.status)
    node=register_node(p.replication_id,"REPLICATION",p.replication_id,record.provenance.tag.value,"2.1.0",{"source_result_id":p.source_result_id,"independent":record.independent,"criteria_registered":record.criteria_registered,"status":record.status})
    GRAPH_REGISTRY.add_node(node)
    GRAPH_REGISTRY.add_edge(register_edge(f"{p.replication_id}:replicates:{p.source_result_id}",node,GRAPH_REGISTRY.nodes[p.source_result_id],"REPLICATES",rationale="registered replication record"))
    return {"record":asdict(record),"graph_node":asdict(node)}

@app.post("/validation/generalization/register")
def validation_generalization(p: GeneralizationInput):
    if p.source_result_id not in GRAPH_REGISTRY.nodes or GRAPH_REGISTRY.nodes[p.source_result_id].node_type!="RESULT":
        raise ValueError("source_result_id must reference a registered RESULT")
    record=register_generalization(p.generalization_id,p.source_result_id,run_status=p.run_status,target_population_context=p.target_population_context)
    node=register_node(p.generalization_id,"GENERALIZATION",p.generalization_id,record.provenance.tag.value,"2.1.0",{"source_result_id":p.source_result_id,"run_status":record.run_status,"target_population_context":record.target_population_context})
    GRAPH_REGISTRY.add_node(node)
    GRAPH_REGISTRY.add_edge(register_edge(f"{p.generalization_id}:generalizes:{p.source_result_id}",node,GRAPH_REGISTRY.nodes[p.source_result_id],"GENERALIZES",rationale="registered generalization record"))
    return {"record":asdict(record),"graph_node":asdict(node)}

@app.post("/graph/claim-gate")
def graph_claim_gate(p: ClaimGateInput):
    upstream=GRAPH_REGISTRY.claim_upstream_types(p.result_id)
    return validate_claim_transition(p.current_state,p.target_level,upstream,p.provenance_class)

@app.post("/graph/claim")
def graph_claim(p: ClaimInput):
    claim=GRAPH_REGISTRY.register_claim(p.claim_id,p.result_id,p.current_state,p.target_state,p.provenance_class,p.metadata,p.previous_claim_id)
    return {"claim":asdict(claim),"supported_result_id":claim.metadata.get("result_id") if p.result_id is None else p.result_id}

@app.get("/graph/lineage/{node_id}")
def graph_lineage(node_id: str):
    if node_id not in GRAPH_REGISTRY.nodes:
        raise ValueError("node is not registered")
    nodes=GRAPH_REGISTRY._upstream_nodes(node_id) if GRAPH_REGISTRY.nodes[node_id].node_type=="RESULT" else []
    return {"node_id":node_id,"node_type":GRAPH_REGISTRY.nodes[node_id].node_type,"upstream_nodes":[asdict(n) for n in nodes]}

@app.post("/graph/register-node")
def graph_register_node(p: NodeInput):
    node=register_node(p.node_id,p.node_type,p.entity_id,p.provenance_class,p.version,p.metadata)
    return asdict(GRAPH_REGISTRY.add_node(node))

@app.post("/graph/edge")
def graph_edge(p: GraphEdgeInput):
    source=GRAPH_REGISTRY.nodes.get(p.from_node_id)
    target=GRAPH_REGISTRY.nodes.get(p.to_node_id)
    if source is None or target is None:
        raise ValueError("edge requires pre-registered nodes")
    if source.node_type != p.from_node_type or target.node_type != p.to_node_type:
        raise ValueError("edge node type does not match registered node")
    edge=GRAPH_REGISTRY.add_edge(register_edge(p.edge_id,source,target,p.edge_type,rationale=p.rationale))
    if target.node_type=="RESULT":
        GRAPH_REGISTRY.require_lineage_for_result(target.node_id)
    return asdict(edge)

@app.post("/validation/paired")
def validation_paired(p: RegisteredPairedInput):
    manifest=lock_manifest(p.baseline,p.current,manifest_id=p.manifest_id,analysis_spec_id=p.analysis_spec_id)
    result=paired_effect(p.baseline,p.current,manifest)
    node=build_result(result_id=p.result_id,analysis_id=p.analysis_id,manifest_id=manifest.manifest_id,analysis_spec_id=manifest.analysis_spec_id,qc_status="PASS" if result.status.startswith("ESTIMABLE") else result.status,n=result.n,estimate=result.mean_change,ci95_low=result.ci95_low,ci95_high=result.ci95_high)
    dataset=register_node(manifest.manifest_id,"DATASET",manifest.manifest_id,"DRV",manifest.analysis_spec_id,{"values_hash":manifest.values_hash,"n_total":manifest.n_total,"n_complete":manifest.n_complete,"missing":manifest.missing})
    analysis=register_node(p.analysis_id,"ANALYSIS",p.analysis_id,"DRV",manifest.analysis_spec_id,{"manifest_id":manifest.manifest_id,"analysis_spec_id":manifest.analysis_spec_id})
    result_graph=register_node(node.result_id,"RESULT",node.result_id,node.provenance.tag.value,node.analysis_spec_id,graph_node(node)["metadata_json"])
    GRAPH_REGISTRY.add_node(dataset); GRAPH_REGISTRY.add_node(analysis); GRAPH_REGISTRY.add_node(result_graph)
    GRAPH_REGISTRY.add_edge(register_edge(f"{p.analysis_id}:dataset:{manifest.manifest_id}",analysis,dataset,"ANALYZED_FROM",rationale="registered analysis manifest"))
    GRAPH_REGISTRY.add_edge(register_edge(f"{p.analysis_id}:result:{p.result_id}",analysis,result_graph,"RESULTS_IN",rationale="registered analysis result"))
    GRAPH_REGISTRY.require_lineage_for_result(p.result_id)
    return {"manifest": asdict(manifest), "result": asdict(result), "graph_node": graph_node(node), "graph_lineage": sorted(GRAPH_REGISTRY.claim_upstream_types(p.result_id))}

@app.post("/validation/longitudinal")
def validation_longitudinal(p: LongitudinalInput):
    return asdict(longitudinal_change(p.baseline, p.current))

@app.post("/validation/descriptive")
def validation_descriptive(p: AnalysisInput):
    result=descriptive(p.values, ids=p.ids)
    return asdict(result)

@app.post("/runtime/outcome")
def runtime_outcome(p: OutcomeInput):
    result=evaluate_outcome(p.baseline, p.current, tolerance=p.tolerance, safety_block=p.safety_block)
    outcome=asdict(result)
    event=make_event(f"{p.execution_id}:outcome", "OUTCOME_EVALUATED", p.execution_id, outcome)
    return {"outcome": outcome, "lineage": lineage_descriptor(event)}

@app.post("/runtime/capacity")
def runtime_capacity(p: StateInput):
    return asdict(compute_capacity(DailyState(**p.model_dump())))

@app.post("/compatibility")
def compatibility(p: CompatibilityInput):
    s={(k.split("|")[0],k.split("|")[1]):v for k,v in p.synergy.items() if "|" in k}
    return {"v1":compatibility_v1(p.bio_a,p.bio_b),"v2":compatibility_v2(p.values_a,p.values_b),"v3":compatibility_v3(set(p.roles_a),set(p.roles_b),s),"authoritative_scalar":False}
