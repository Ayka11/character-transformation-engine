from cte.models import DailyState
from cte.sprint import start_sprint, record_day

def state(**overrides):
    base=dict(sleep_quality=8,recovery_index=8,physical_activity=7,metabolic_stability=8,subjective_stress=2,subjective_energy=8)
    base.update(overrides)
    return DailyState(**base)

def test_day_one_continues_when_completed():
    s=start_sprint("s1","P3.pause_capacity","sleep routine","pause before response")
    r=record_day(s,1,True,7.0,state())
    assert r.status=="CONTINUE"

def test_safety_overrides_progression():
    s=start_sprint("s1","P3.pause_capacity","sleep routine","pause")
    r=record_day(s,1,True,7.0,state(subjective_stress=9))
    assert r.status=="PAUSED_SAFETY"
    assert r.next_action=="pause_and_recover"

def test_missing_outcome_does_not_infer_success():
    s=start_sprint("s1","P3.pause_capacity","sleep routine","pause")
    r=record_day(s,1,True,None,state())
    assert r.status=="RECORDED_NO_OUTCOME"

def test_nonsequential_day_rejected():
    s=start_sprint("s1","P3.pause_capacity","sleep routine","pause")
    try:
        record_day(s,2,True,7.0,state())
        assert False
    except ValueError:
        assert True
