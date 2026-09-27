from cte.intervention import plan_bio_reset, plan_21_day_sprint
from cte.models import DailyState
from cte.trait_graph import TraitGraph

GRAPH = TraitGraph({"P3.pause_capacity":["P3.impulse_control"],"P3.impulse_control":["P5.discipline_consistency"]})

def state(**overrides):
    base=dict(sleep_quality=8,recovery_index=8,physical_activity=7,metabolic_stability=8,subjective_stress=2,subjective_energy=8)
    base.update(overrides)
    return DailyState(**base)

def test_bio_reset_is_recovery_first_when_safety_blocks():
    result=plan_bio_reset(state(subjective_stress=9),"P3.pause_capacity",GRAPH,{"P3.pause_capacity":3,"P3.impulse_control":2})
    assert result.allowed is False
    assert result.level=="A"
    assert "prioritize_recovery" in result.actions

def test_sprint_selects_graph_target():
    result=plan_21_day_sprint(state(),"P3.pause_capacity",GRAPH,{"P3.pause_capacity":5,"P3.impulse_control":2,"P5.discipline_consistency":6},"consistent sleep schedule","practice a 10-second pause before one response")
    assert result.allowed is True
    assert result.target_trait=="P3.impulse_control"
    assert result.duration_days==21

def test_sprint_cannot_start_without_target():
    result=plan_21_day_sprint(state(),"P3.pause_capacity",GRAPH,{},"sleep","pause")
    assert result.allowed is False
