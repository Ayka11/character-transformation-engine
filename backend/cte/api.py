import os
from dataclasses import asdict
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from pydantic import BaseModel, Field
from .models import DailyState
from .capacity import compute_capacity
from .compatibility import compatibility_report
from .recovery import evaluate_recovery_gate, evaluate_bio_reset, build_recovery_plan, isolate_compromised_state_from_traits
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
from .replication_engine import ReplicationRun as EngineReplicationRun, register_spec as register_replication_spec, register_run as register_replication_run, evaluate_outcome as evaluate_replication_outcome
from .generalization_engine import register_spec as register_generalization_spec, register_run as register_generalization_run, evaluate as evaluate_generalization
from .evidence_engine import register_criteria
from .reporting_api import install_reporting_api
from .intervention_api import install_intervention_api
from .orchestrator_api import install_orchestrator_api
from .integrity_runner import run_v19_integrity_suite
from .research_api import install_research_api
from .science_lab_api import install_science_lab_api
from .persistence import SQLiteRuntimeStore, build_runtime_store

app = FastAPI(title="Character Transformation Engine", version="2.1.0")

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/science-lab/assets", StaticFiles(directory=str(FRONTEND_DIR)), name="science-lab-assets")

    @app.get("/science-lab/ui", include_in_schema=False)
    def science_lab_ui():
        return FileResponse(FRONTEND_DIR / "index.html")

RUNTIME_DB_PATH = os.getenv("CTE_RUNTIME_DB", "data/cte-runtime.sqlite3")
RUNTIME_STORE = build_runtime_store(RUNTIME_DB_PATH)
GRAPH_REGISTRY = build_registry(RUNTIME_STORE)
REPLICATION_SPECS = {}
REPLICATION_RUNS = {}
GENERALIZATION_SPECS = {}
GENERALIZATION_RUNS = {}
EVIDENCE_CRITERIA = {}

def _hydrate_research_runtime():
    from .provenance import Provenance, ProvenanceTag
    from .replication_engine import ReplicationSpec, ReplicationRun as EngineReplicationRun
    from .generalization_engine import GeneralizationSpec, GeneralizationRun as EngineGeneralizationRun
    for node in GRAPH_REGISTRY.nodes.values():
        md=node.metadata or {}
        if node.node_type=="PROTOCOL" and md.get("kind")=="REPLICATION_SPEC":
            REPLICATION_SPECS[node.node_id]=ReplicationSpec(
                node.node_id,md.get("source_claim_id",""),md.get("primary_outcome_id",""),
                md.get("criteria",{}),node.version,
                Provenance(ProvenanceTag(node.provenance_class),"cte.replication.spec",node.version,node.immutable_hash)
            )
        elif node.node_type=="REPLICATION":
            run_id=node.node_id
            REPLICATION_RUNS[run_id]=EngineReplicationRun(
                run_id,md.get("replication_spec_id",""),md.get("source_result_id",""),
                md.get("independent_study_id",""),md.get("dataset_manifest_id",""),
                md.get("protocol_hash",""),md.get("input_hash",""),md.get("status","REGISTERED"),
                Provenance(ProvenanceTag(node.provenance_class),"cte.replication.run",node.version,node.immutable_hash)
            )
        elif node.node_type=="PROTOCOL" and md.get("kind")=="GENERALIZATION_SPEC":
            GENERALIZATION_SPECS[node.node_id]=GeneralizationSpec(
                node.node_id,md.get("source_claim_id",""),{}, {},{}, md.get("target_context",{}),
                md.get("transport_dimensions",[]),md.get("acceptance_rules",{}),node.version,
                Provenance(ProvenanceTag(node.provenance_class),"cte.generalization.spec",node.version,node.immutable_hash)
            )
        elif node.node_type=="GENERALIZATION":
            run_id=node.node_id
            GENERALIZATION_RUNS[run_id]=EngineGeneralizationRun(
                run_id,md.get("generalization_spec_id",""),md.get("source_result_id",""),
                md.get("dataset_manifest_id",""),md.get("transport_analysis_version","1.5"),
                md.get("input_hash",""),md.get("run_status","REGISTERED"),
                Provenance(ProvenanceTag(node.provenance_class),"cte.generalization.run",node.version,node.immutable_hash)
            )

_hydrate_research_runtime()

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

class RecoveryWindowInput(BaseModel):
    recovery_indices: list[float | None]
    threshold: float = Field(4.0, ge=0)
    streak_days: int = Field(3, ge=1)

class RecoveryPlanInput(BaseModel):
    state: StateInput
    bio_reset_triggered: bool = False

class StateTraitIsolationInput(BaseModel):
    current_state: str = "compromised"
    trait_values_untouched: bool = True

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

class InferenceBlockInput(BaseModel):
    inference_block_id: str
    from_node_type: str
    to_claim_level: str
    blocked_inference: str
    reason_code: str
    rule_id: str

class ContradictionInput(BaseModel):
    contradiction_set_id: str
    claim_id: str
    node_ids: list[str]
    contradiction_type: str
    resolution_status: str = "UNRESOLVED"
    resolution_note: str | None = None

class EvidenceCriteriaInput(BaseModel):
    criteria_id: str
    claim_id: str
    analysis_id: str
    rule_ids: list[str]
    acceptance_rules: dict = Field(default_factory=dict)

class GeneralizationSpecInput(BaseModel):
    generalization_spec_id: str
    source_claim_id: str
    source_population: dict
    target_population: dict
    source_context: dict
    target_context: dict
    transport_dimensions: list[str] = Field(default_factory=list)
    acceptance_rules: dict = Field(default_factory=dict)

class GeneralizationRunInput(BaseModel):
    generalization_run_id: str
    generalization_spec_id: str
    source_result_node_id: str
    dataset_manifest_id: str
    transport_analysis_version: str = "1.5"
    input_hash: str

class GeneralizationResultInput(BaseModel):
    generalization_run_id: str
    source_estimate: float | None = None
    transported_estimate: float | None = None
    transport_error: float | None = None
    ci_low: float | None = None
    ci_high: float | None = None
    heterogeneity_statistic: float | None = None
    heterogeneity_p_value: float | None = None
    dimensions: dict[str,str] = Field(default_factory=dict)
    max_transport_error: float = Field(0.20, ge=0)
    max_heterogeneity: float | None = Field(None, ge=0)

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
    recovery_indices: list[float | None] = Field(default_factory=list)

GRAPH = TraitGraph({
    "P3.pause_capacity": ["P3.impulse_control"],
    "P3.impulse_control": ["P5.discipline_consistency"],
    "P3.cognitive_reappraisal": ["P3.reflection_depth"],
    "P3.attention_regulation": ["P3.pause_capacity"],
})

@app.get("/health")
def health():
    return {"status":"ok","version":"2.1.0","scientific_status":"implementation_baseline","runtime_persistence":{"backend":"postgresql" if RUNTIME_STORE.__class__.__name__=="PostgreSQLRuntimeStore" else "sqlite","path":getattr(RUNTIME_STORE,"dsn",RUNTIME_DB_PATH)},"ci_workflow":"backend-tests"}

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
    return asdict(record_day(sprint,p.day,p.action_completed,p.outcome,state,p.recovery_indices or None))

@app.post("/replication/specs")
def replication_spec_register(p: ReplicationSpecInput):
    spec=register_replication_spec(p.replication_spec_id,p.source_claim_id,p.primary_outcome_id,p.criteria)
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
    run=register_replication_run(p.replication_run_id,spec,source_result_node_id=p.source_result_node_id,independent_study_id=p.independent_study_id,dataset_manifest_id=p.dataset_manifest_id,protocol_hash=p.protocol_hash,input_hash=p.input_hash,independent=p.independent)
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

@app.post("/generalization/specs")
def generalization_spec_register(p: GeneralizationSpecInput):
    spec=register_generalization_spec(p.generalization_spec_id,p.source_claim_id,
        source_population=p.source_population,target_population=p.target_population,
        source_context=p.source_context,target_context=p.target_context,
        transport_dimensions=p.transport_dimensions or None,acceptance_rules=p.acceptance_rules)
    if p.generalization_spec_id in GENERALIZATION_SPECS:
        raise ValueError("generalization spec already registered")
    GENERALIZATION_SPECS[p.generalization_spec_id]=spec
    GRAPH_REGISTRY.add_node(register_node(spec.generalization_spec_id,"PROTOCOL",spec.generalization_spec_id,spec.provenance.tag.value,"1.5",{"kind":"GENERALIZATION_SPEC","source_claim_id":spec.source_claim_id,"target_context":spec.target_context,"acceptance_rules":spec.acceptance_rules}))
    return asdict(spec)

@app.post("/generalization/runs")
def generalization_run_register(p: GeneralizationRunInput):
    spec=GENERALIZATION_SPECS.get(p.generalization_spec_id)
    if spec is None:
        raise ValueError("generalization_spec_id must reference a registered generalization spec")
    source=GRAPH_REGISTRY.nodes.get(p.source_result_node_id)
    if source is None or source.node_type!="RESULT":
        raise ValueError("source_result_node_id must reference a registered RESULT")
    run=register_generalization_run(p.generalization_run_id,spec,source_result_node_id=p.source_result_node_id,dataset_manifest_id=p.dataset_manifest_id,transport_analysis_version=p.transport_analysis_version,input_hash=p.input_hash)
    GENERALIZATION_RUNS[p.generalization_run_id]=run
    node=register_node(run.generalization_run_id,"GENERALIZATION",run.generalization_run_id,run.provenance.tag.value,"1.5",{"source_result_id":run.source_result_node_id,"generalization_spec_id":run.generalization_spec_id,"dataset_manifest_id":run.dataset_manifest_id,"run_status":run.status})
    GRAPH_REGISTRY.add_node(node)
    GRAPH_REGISTRY.add_edge(register_edge(f"{node.node_id}:generalizes:{source.node_id}",node,source,"GENERALIZES",rationale="registered V1.5 generalization run"))
    return {"run":asdict(run),"graph_node":asdict(node)}

@app.post("/generalization/runs/{generalization_run_id}/results")
def generalization_result_register(generalization_run_id: str,p: GeneralizationResultInput):
    if p.generalization_run_id != generalization_run_id:
        raise ValueError("path and payload generalization_run_id mismatch")
    run=GENERALIZATION_RUNS.get(generalization_run_id)
    if run is None:
        raise ValueError("generalization run is not registered")
    result=evaluate_generalization(run,source_estimate=p.source_estimate,transported_estimate=p.transported_estimate,transport_error=p.transport_error,ci_low=p.ci_low,ci_high=p.ci_high,heterogeneity_statistic=p.heterogeneity_statistic,heterogeneity_p_value=p.heterogeneity_p_value,dimensions=p.dimensions,max_transport_error=p.max_transport_error,max_heterogeneity=p.max_heterogeneity)
    assessment_id=f"{generalization_run_id}:assessment:{result.result_status}"
    node=register_node(assessment_id,"GENERALIZATION",assessment_id,result.provenance.tag.value,"1.5",{"source_result_id":run.source_result_node_id,"generalization_run_id":run.generalization_run_id,"run_status":"COMPLETED" if result.result_status=="GENERALIZABLE" else "LIMITED","result_status":result.result_status,"target_population_context":GENERALIZATION_SPECS[run.generalization_spec_id].target_population})
    GRAPH_REGISTRY.add_node(node)
    GRAPH_REGISTRY.add_edge(register_edge(f"{assessment_id}:generalizes:{run.source_result_node_id}",node,GRAPH_REGISTRY.nodes[run.source_result_node_id],"GENERALIZES",rationale="V1.5 generalization result assessment"))
    return {"result":asdict(result),"assessment_graph_node":asdict(node)}

@app.post("/validation/generalization/register")
def validation_generalization(p: GeneralizationInput):
    if p.source_result_id not in GRAPH_REGISTRY.nodes or GRAPH_REGISTRY.nodes[p.source_result_id].node_type!="RESULT":
        raise ValueError("source_result_id must reference a registered RESULT")
    record=register_generalization(p.generalization_id,p.source_result_id,run_status=p.run_status,target_population_context=p.target_population_context)
    node=register_node(p.generalization_id,"GENERALIZATION",p.generalization_id,record.provenance.tag.value,"2.1.0",{"source_result_id":p.source_result_id,"run_status":record.run_status,"target_population_context":record.target_population_context})
    GRAPH_REGISTRY.add_node(node)
    GRAPH_REGISTRY.add_edge(register_edge(f"{p.generalization_id}:generalizes:{p.source_result_id}",node,GRAPH_REGISTRY.nodes[p.source_result_id],"GENERALIZES",rationale="registered generalization record"))
    return {"record":asdict(record),"graph_node":asdict(node)}

@app.post("/graph/inference-blocks")
def graph_inference_block(p: InferenceBlockInput):
    return asdict(GRAPH_REGISTRY.register_inference_block(
        p.inference_block_id,p.from_node_type,p.to_claim_level,
        p.blocked_inference,p.reason_code,p.rule_id
    ))

@app.post("/graph/contradictions")
def graph_contradiction(p: ContradictionInput):
    return asdict(GRAPH_REGISTRY.register_contradiction_set(
        p.contradiction_set_id,p.claim_id,p.node_ids,p.contradiction_type,
        p.resolution_status,p.resolution_note
    ))

@app.post("/graph/evidence-criteria")
def graph_evidence_criteria(p: EvidenceCriteriaInput):
    if p.criteria_id in EVIDENCE_CRITERIA:
        raise ValueError("evidence criteria already registered")
    analysis=GRAPH_REGISTRY.nodes.get(p.analysis_id)
    if analysis is None or analysis.node_type!="ANALYSIS":
        raise ValueError("analysis_id must reference a registered ANALYSIS")
    claim=GRAPH_REGISTRY.nodes.get(p.claim_id)
    if claim is None or claim.node_type!="CLAIM":
        raise ValueError("claim_id must reference a registered CLAIM")
    criteria=register_criteria(p.criteria_id,p.claim_id,rule_ids=p.rule_ids,acceptance_rules=p.acceptance_rules)
    EVIDENCE_CRITERIA[p.criteria_id]=criteria
    node=register_node(p.criteria_id,"PROTOCOL",p.criteria_id,criteria.provenance.tag.value,criteria.version,
                       {"kind":"EVIDENCE_CRITERIA","claim_id":criteria.claim_id,
                        "rule_ids":list(criteria.rule_ids),"acceptance_rules":criteria.acceptance_rules})
    GRAPH_REGISTRY.add_node(node)
    GRAPH_REGISTRY.add_edge(register_edge(f"{analysis.node_id}:evidence-criteria:{node.node_id}",
                                          analysis,node,"USES_PROTOCOL",
                                          rationale="registered evidence criteria linked to analysis"))
    return {"criteria":asdict(criteria),"graph_node":asdict(node)}

@app.post("/graph/claim-gate")
def graph_claim_gate(p: ClaimGateInput):
    upstream=GRAPH_REGISTRY.claim_upstream_types(p.result_id)
    return validate_claim_transition(p.current_state,p.target_level,upstream,p.provenance_class)

@app.post("/graph/claim")
def graph_claim(p: ClaimInput):
    claim=GRAPH_REGISTRY.register_claim(p.claim_id,p.result_id,p.current_state,p.target_state,p.provenance_class,p.metadata,p.previous_claim_id)
    return {"claim":asdict(claim),"supported_result_id":claim.metadata.get("result_id") if p.result_id is None else p.result_id}

@app.get("/graph/claims/{claim_id}")
def graph_claim_subgraph(claim_id: str):
    nodes,edges=GRAPH_REGISTRY.claim_subgraph(claim_id)
    return {"claim_id":claim_id,"nodes":[asdict(n) for n in nodes],"edges":[asdict(e) for e in edges]}

@app.get("/graph/claims/{claim_id}/lineage")
def graph_claim_lineage(claim_id: str):
    nodes,edges=GRAPH_REGISTRY.claim_subgraph(claim_id)
    return {"claim_id":claim_id,"nodes":[asdict(n) for n in nodes],"edges":[asdict(e) for e in edges]}

@app.get("/graph/claims/{claim_id}/support")
def graph_claim_support(claim_id: str):
    nodes,edges=GRAPH_REGISTRY.claim_subgraph(claim_id)
    allowed={"SUPPORTS","REPLICATES","GENERALIZES","QUALIFIES","CONTRADICTS","LIMITS","BLOCKS"}
    return {"claim_id":claim_id,"edges":[asdict(e) for e in edges if e.edge_type in allowed]}

@app.get("/graph/audit/{claim_id}")
def graph_claim_audit(claim_id: str):
    return {"claim_id":claim_id,"events":[asdict(e) for e in GRAPH_REGISTRY.claim_audit(claim_id)]}

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
    role_overrides={(k.split("|")[0],k.split("|")[1]):v for k,v in p.synergy.items() if "|" in k}
    return compatibility_report(
        p.bio_a,p.bio_b,p.values_a,p.values_b,
        set(p.roles_a),set(p.roles_b),role_overrides
    )

@app.post("/runtime/recovery-gate")
def runtime_recovery_gate(p: StateInput):
    state=DailyState(**p.model_dump())
    return asdict(evaluate_recovery_gate(state))

@app.post("/runtime/bio-reset")
def runtime_bio_reset(p: RecoveryWindowInput):
    return asdict(evaluate_bio_reset(
        p.recovery_indices,threshold=p.threshold,streak_days=p.streak_days
    ))

@app.post("/runtime/recovery-plan")
def runtime_recovery_plan(p: RecoveryPlanInput):
    state=DailyState(**p.state.model_dump())
    return asdict(build_recovery_plan(state,bio_reset_triggered=p.bio_reset_triggered))

@app.post("/runtime/state-trait-isolation")
def runtime_state_trait_isolation(p: StateTraitIsolationInput):
    return asdict(isolate_compromised_state_from_traits(
        p.current_state,trait_values_untouched=p.trait_values_untouched
    ))


REPORT_SERVICE = install_reporting_api(app, GRAPH_REGISTRY)


INTERVENTION_SERVICE = install_intervention_api(app, GRAPH_REGISTRY, RUNTIME_STORE)


ORCHESTRATOR_SERVICE = install_orchestrator_api(app, RUNTIME_STORE)

RESEARCH_SERVICE = install_research_api(app, GRAPH_REGISTRY, RUNTIME_STORE, ORCHESTRATOR_SERVICE)
SCIENCE_LAB_SERVICE = install_science_lab_api(app, GRAPH_REGISTRY, RUNTIME_STORE, RESEARCH_SERVICE.e2e_coordinator)


@app.post("/integrity/v1.9/run")
def integrity_v19_run():
    return run_v19_integrity_suite()
