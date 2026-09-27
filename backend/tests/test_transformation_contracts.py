from cte.contracts.state import StateSnapshot, StateDiffEngine
from cte.contracts.transformation import TransformationContract, validate_transition

def test_state_snapshot_hash_is_stable():
    a=StateSnapshot.capture("s1","c1",1,{"tempo":5,"recovery":8})
    b=StateSnapshot.capture("s2","c1",2,{"recovery":8,"tempo":5})
    assert a.state_hash==b.state_hash

def test_diff_detects_expected_change():
    before=StateSnapshot.capture("s1","c1",1,{"tempo":5,"recovery":8})
    after=StateSnapshot.capture("s2","c1",2,{"tempo":6,"recovery":8})
    diff=StateDiffEngine.compare(before,after,expected={"tempo":6})
    assert diff.state_changed and "tempo" in diff.changed and not diff.unexpected and not diff.missing_expected

def test_required_transformation_with_no_change_fails():
    before=StateSnapshot.capture("s1","c1",1,{"tempo":5})
    after=StateSnapshot.capture("s2","c1",2,{"tempo":5})
    diff=StateDiffEngine.compare(before,after,expected={"tempo":6})
    result=validate_transition(TransformationContract("t1","1",expected_changes={"tempo":6}),diff,before_snapshot_id="s1",after_snapshot_id="s2")
    assert result.status=="FAILED" and result.failure_code=="NO_STATE_CHANGE" and not result.certificate_eligible

def test_forbidden_change_fails():
    before=StateSnapshot.capture("s1","c1",1,{"tempo":5,"recovery":8})
    after=StateSnapshot.capture("s2","c1",2,{"tempo":6,"recovery":7})
    diff=StateDiffEngine.compare(before,after,expected={"tempo":6},forbidden={"recovery"})
    result=validate_transition(TransformationContract("t1","1",expected_changes={"tempo":6},forbidden_changes=("recovery",)),diff,before_snapshot_id="s1",after_snapshot_id="s2")
    assert result.status=="FAILED" and result.failure_code=="UNEXPECTED_CHANGE"
