from cte.orchestrator import OrchestratorService

def test_execution_lifecycle_and_completion():
    o=OrchestratorService()
    e=o.create_execution("x","c",{"input":1},["INTAKE","SAFETY_GATE"])
    o.start("x")
    o.advance_stage("x","INTAKE","PASSED",input_hash="i",output_hash="o",module_version="1",provenance_record_id="p")
    o.advance_stage("x","SAFETY_GATE","SKIPPED",reason="not required for this research-only run")
    out=o.complete("x")
    assert out.state=="COMPLETED" and out.output_hash

def test_unknown_required_input_cannot_pass():
    o=OrchestratorService()
    o.create_execution("x","c",{},["ASSESSMENT"])
    o.start("x")
    try: o.advance_stage("x","ASSESSMENT","PASSED",metadata={"unknown_required_input":True})
    except ValueError: assert True
    else: assert False

def test_unsafe_intervention_cannot_pass():
    o=OrchestratorService()
    o.create_execution("x","c",{},["SAFETY_GATE","INTERVENTION"])
    o.start("x")
    o.advance_stage("x","SAFETY_GATE","BLOCKED",reason="safety constraint",metadata={"safety_status":"BLOCK"})
    try: o.advance_stage("x","INTERVENTION","PASSED")
    except ValueError: assert True
    else: assert False

def test_claim_evidence_promotion_requires_claim_gate():
    o=OrchestratorService()
    o.create_execution("x","c",{},["CLAIM"])
    o.start("x")
    try: o.advance_stage("x","CLAIM","PASSED",metadata={"claim_state":"EVIDENCE_SUPPORTED","claim_gate_passed":False})
    except ValueError: assert True
    else: assert False

def test_blocked_upstream_stage_prevents_downstream_pass():
    o=OrchestratorService()
    o.create_execution("x","c",{},["SAFETY_GATE","INTERVENTION"])
    o.start("x")
    o.advance_stage("x","SAFETY_GATE","BLOCKED",reason="constraint",metadata={"safety_status":"BLOCK"})
    try:
        o.advance_stage("x","INTERVENTION","RUNNING")
    except ValueError:
        assert True
    else:
        assert False

def test_downstream_stage_cannot_start_before_required_upstream():
    o=OrchestratorService()
    o.create_execution("x","c",{},["INTAKE","PROFILE"])
    o.start("x")
    try:
        o.advance_stage("x","PROFILE","RUNNING")
    except ValueError as e:
        assert "upstream" in str(e)
    else:
        assert False

def test_blocked_execution_can_resume_stage_after_resolution():
    o=OrchestratorService()
    o.create_execution("x","c",{},["SAFETY_GATE"])
    o.start("x")
    o.advance_stage("x","SAFETY_GATE","BLOCKED",reason="temporary",metadata={})
    o.resume("x",True)
    assert o.executions["x"].state=="RUNNING"
    assert o.executions["x"].stages["SAFETY_GATE"].state=="RUNNING"


def test_validated_transformation_transition_passes():
    from cte.contracts.state import StateSnapshot
    from cte.contracts.transformation import TransformationContract
    o=OrchestratorService()
    o.create_execution("tx","c",{},["INTERVENTION"])
    o.start("tx")
    before=StateSnapshot.capture("s1","c",1,{"tempo":5},source_execution_id="tx")
    after=StateSnapshot.capture("s2","c",2,{"tempo":6},parent_snapshot_id="s1",source_execution_id="tx")
    result=o.validate_transformation_transition("tx",TransformationContract("t1","1",expected_changes={"tempo":6}),before,after)
    assert result.status=="VALIDATED"
    assert result.certificate_eligible
    assert o.executions["tx"].state=="RUNNING"

def test_no_state_change_fails_execution_and_forbids_certificate():
    from cte.contracts.state import StateSnapshot
    from cte.contracts.transformation import TransformationContract
    o=OrchestratorService()
    o.create_execution("tx","c",{},["INTERVENTION"])
    o.start("tx")
    before=StateSnapshot.capture("s1","c",1,{"tempo":5},source_execution_id="tx")
    after=StateSnapshot.capture("s2","c",2,{"tempo":5},parent_snapshot_id="s1",source_execution_id="tx")
    result=o.validate_transformation_transition("tx",TransformationContract("t1","1",expected_changes={"tempo":6}),before,after)
    assert result.status=="FAILED"
    assert result.failure_code=="NO_STATE_CHANGE"
    assert not result.certificate_eligible
    assert o.executions["tx"].state=="FAILED"

def test_orchestrator_intervention_uses_validated_transformation_runtime():
    from cte.contracts.transformation import TransformationContract
    o=OrchestratorService()
    o.create_execution("tx2","c",{},["SAFETY_GATE","INTERVENTION"])
    o.start("tx2")
    o.advance_stage("tx2","SAFETY_GATE","PASSED",metadata={"safety_status":"PASS"})
    result=o.execute_transformation(
        "tx2","character-1",1,{"tempo":5},
        TransformationContract("t1","1",expected_changes={"tempo":6}),
        lambda state:{**state,"tempo":6},
    )
    assert result.result.status=="VALIDATED"
    assert result.certificate is not None
    assert o.executions["tx2"].stages["INTERVENTION"].state=="PASSED"

def test_orchestrator_blocks_intervention_without_safety_pass():
    from cte.contracts.transformation import TransformationContract
    o=OrchestratorService()
    o.create_execution("tx3","c",{},["SAFETY_GATE","INTERVENTION"])
    o.start("tx3")
    o.advance_stage("tx3","SAFETY_GATE","BLOCKED",reason="safety",metadata={"safety_status":"BLOCK"})
    try:
        o.execute_transformation(
            "tx3","character-1",1,{"tempo":5},
            TransformationContract("t1","1",expected_changes={"tempo":6}),
            lambda state:{**state,"tempo":6},
        )
    except ValueError as exc:
        assert "safety gate" in str(exc)
    else:
        assert False


def test_completion_rejects_intervention_without_validated_certificate():
    o=OrchestratorService()
    o.create_execution("complete-block","c",{},["SAFETY_GATE","INTERVENTION"])
    o.start("complete-block")
    o.advance_stage("complete-block","SAFETY_GATE","PASSED",metadata={"safety_status":"PASS"})
    o.advance_stage("complete-block","INTERVENTION","PASSED",
                     input_hash="before",output_hash="after",
                     metadata={"transition_status":"EXECUTED"})
    try:
        o.complete("complete-block")
    except ValueError as exc:
        assert "VALIDATED" in str(exc)
    else:
        assert False


def test_completion_rejects_validated_intervention_without_certificate():
    o=OrchestratorService()
    o.create_execution("complete-cert","c",{},["INTERVENTION"])
    o.start("complete-cert")
    o.advance_stage("complete-cert","INTERVENTION","PASSED",
                     input_hash="before",output_hash="after",
                     metadata={"transition_status":"VALIDATED",
                               "before_snapshot_id":"b","after_snapshot_id":"a"})
    try:
        o.complete("complete-cert")
    except ValueError as exc:
        assert "certificate" in str(exc)
    else:
        assert False


def test_completion_accepts_runtime_validated_transformation():
    from cte.contracts.transformation import TransformationContract
    o=OrchestratorService()
    o.create_execution("complete-ok","c",{},["SAFETY_GATE","INTERVENTION"])
    o.start("complete-ok")
    o.advance_stage("complete-ok","SAFETY_GATE","PASSED",metadata={"safety_status":"PASS"})
    out=o.execute_transformation(
        "complete-ok","character-1",1,{"tempo":5},
        TransformationContract("t1","1",expected_changes={"tempo":6}),
        lambda state:{**state,"tempo":6},
    )
    assert out.result.status=="VALIDATED"
    done=o.complete("complete-ok")
    assert done.state=="COMPLETED"
