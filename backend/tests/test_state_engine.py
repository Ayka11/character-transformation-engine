from cte.assessment import build_profile
from cte.state_engine import derive_daily_state

def profile(rows):
    return build_profile(rows, source_id="test", source_version="1")

def test_complete_p1_profile_derives_state():
    p = profile([
        {"item_id":"P1.sleep_quality","value":8,"observation_id":"o1"},
        {"item_id":"P1.recovery_index","value":7,"observation_id":"o2"},
        {"item_id":"P1.physical_activity","value":6,"observation_id":"o3"},
        {"item_id":"P1.metabolic_stability","value":8,"observation_id":"o4"},
        {"item_id":"P1.subjective_stress","value":2,"observation_id":"o5"},
        {"item_id":"P1.subjective_energy","value":8,"observation_id":"o6"},
    ])
    d = derive_daily_state(p)
    assert d.missing == ()
    assert d.state.subjective_energy == 8

def test_missing_p1_measurement_remains_unknown():
    p = profile([
        {"item_id":"P1.recovery_index","value":7,"observation_id":"o1"},
        {"item_id":"P1.subjective_stress","value":2,"observation_id":"o2"},
        {"item_id":"P1.subjective_energy","value":8,"observation_id":"o3"},
    ])
    d = derive_daily_state(p)
    assert "sleep_quality" in d.missing
    assert d.state.sleep_quality is None
