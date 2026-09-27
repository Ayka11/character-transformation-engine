from cte.capacity import compute_capacity
from cte.models import DailyState

def test_missing_capacity_inputs_are_unknown():
    r=compute_capacity(DailyState(5,None,5,5,3,7))
    assert r.capacity is None and r.level=="A" and r.safety_block

def test_high_stress_forces_level_a():
    r=compute_capacity(DailyState(5,8,5,5,8,10))
    assert r.level=="A" and r.safety_block

def test_capacity_formula_and_level():
    r=compute_capacity(DailyState(5,10,5,5,2,10))
    assert round(r.capacity,4)==4.3
    assert r.level=="C"
