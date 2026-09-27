from cte.outcome import AdaptationAction, ResponseClass, evaluate_outcome

def test_improvement_continues():
    r=evaluate_outcome(5,6)
    assert r.response==ResponseClass.IMPROVED
    assert r.adaptation==AdaptationAction.CONTINUE

def test_decline_reduces_load():
    r=evaluate_outcome(7,6)
    assert r.response==ResponseClass.DECLINED
    assert r.adaptation==AdaptationAction.REDUCE

def test_missing_data_stays_unknown():
    r=evaluate_outcome(5,None)
    assert r.response==ResponseClass.UNKNOWN
    assert r.adaptation==AdaptationAction.COLLECT_DATA

def test_safety_overrides_outcome():
    r=evaluate_outcome(2,9,safety_block=True)
    assert r.adaptation==AdaptationAction.STOP
