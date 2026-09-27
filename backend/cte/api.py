from dataclasses import asdict
from fastapi import FastAPI
from pydantic import BaseModel,Field
from .models import DailyState
from .capacity import compute_capacity
from .compatibility import compatibility_v1,compatibility_v2,compatibility_v3

app=FastAPI(title="Character Transformation Engine",version="2.1.0")
class StateInput(BaseModel):
    sleep_quality:float|None=Field(None,ge=0,le=10); recovery_index:float|None=Field(None,ge=0,le=10)
    physical_activity:float|None=Field(None,ge=0,le=10); metabolic_stability:float|None=Field(None,ge=0,le=10)
    subjective_stress:float|None=Field(None,ge=0,le=10); subjective_energy:float|None=Field(None,ge=0,le=10)
class CompatibilityInput(BaseModel):
    bio_a:dict[str,float]={}; bio_b:dict[str,float]={}; values_a:dict[str,float]={}; values_b:dict[str,float]={}
    roles_a:list[str]=[]; roles_b:list[str]=[]; synergy:dict[str,float]={}
@app.get("/health")
def health(): return {"status":"ok","version":"2.1.0","scientific_status":"implementation_baseline"}
@app.post("/runtime/capacity")
def runtime_capacity(p:StateInput): return asdict(compute_capacity(DailyState(**p.model_dump())))
@app.post("/compatibility")
def compatibility(p:CompatibilityInput):
    s={(k.split("|")[0],k.split("|")[1]):v for k,v in p.synergy.items() if "|" in k}
    return {"v1":compatibility_v1(p.bio_a,p.bio_b),"v2":compatibility_v2(p.values_a,p.values_b),"v3":compatibility_v3(set(p.roles_a),set(p.roles_b),s),"authoritative_scalar":False}
