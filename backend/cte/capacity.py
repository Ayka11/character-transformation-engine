from .models import DailyState, CapacityResult
from .provenance import derived_provenance
VERSION="2.1.0"

def compute_capacity(state: DailyState)->CapacityResult:
    required={"energy":state.subjective_energy,"stress":state.subjective_stress,"recovery":state.recovery_index}
    missing=[k for k,v in required.items() if v is None]
    if missing:
        return CapacityResult(None,"A",True,derived_provenance("capacity.engine",VERSION,required,"Required input missing"),"UNKNOWN capacity: "+", ".join(missing),required)
    cap=0.5*float(state.subjective_energy)+0.3*(float(state.recovery_index)/10.0)-0.5*float(state.subjective_stress)
    if state.subjective_stress>=8 or cap<3: level,blocked="A",True
    elif cap<4: level,blocked="B",False
    elif cap<6: level,blocked="C",False
    elif cap<8: level,blocked="D",False
    else: level,blocked="E",False
    return CapacityResult(cap,level,blocked,derived_provenance("capacity.engine",VERSION,required),f"C_cap={cap:.4f}; level={level}; safety_block={blocked}",required)
