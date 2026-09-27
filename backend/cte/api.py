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

app = FastAPI(title="Character Transformation Engine", version="2.1.0")

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

@app.post("/runtime/capacity")
def runtime_capacity(p: StateInput):
    return asdict(compute_capacity(DailyState(**p.model_dump())))

@app.post("/compatibility")
def compatibility(p: CompatibilityInput):
    s={(k.split("|")[0],k.split("|")[1]):v for k,v in p.synergy.items() if "|" in k}
    return {"v1":compatibility_v1(p.bio_a,p.bio_b),"v2":compatibility_v2(p.values_a,p.values_b),"v3":compatibility_v3(set(p.roles_a),set(p.roles_b),s),"authoritative_scalar":False}
