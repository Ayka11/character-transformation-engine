from cte.intervention_engine import InterventionService

def _service():
    class R: nodes={}
    return InterventionService(R())

def test_only_active_registered_rule_can_be_assigned():
    s=_service()
    s.register_rule_from_fields("r","Rule","MDL","1.0",["P3"],[],["capacity"],{}, {},status="ACTIVE")
    a=s.assign("a","u","r","P3",{"capacity":4},"C","PASS","PASS")
    assert a.safety_gate_status=="PASS"

def test_unknown_inputs_hold_assignment():
    s=_service()
    s.register_rule_from_fields("r","Rule","MDL","1.0",["P3"],[],["capacity"],{}, {},status="ACTIVE")
    a=s.assign("a","u","r","P3",{"capacity":None},"C","PASS","UNKNOWN")
    assert a.safety_gate_status=="HOLD"

def test_blocked_assignment_cannot_create_session():
    s=_service()
    s.register_rule_from_fields("r","Rule","MDL","1.0",["P3"],[],["capacity"],{}, {},status="ACTIVE")
    a=s.assign("a","u","r","P3",{"capacity":4},"C","BLOCK","PASS")
    try: s.create_session("a","s",{"load":"standard"})
    except ValueError as e: assert "blocked" in str(e)
    else: assert False

def test_missing_measurement_is_explicit():
    s=_service()
    s.register_rule_from_fields("r","Rule","MDL","1.0",["P3"],[],["capacity"],{}, {},status="ACTIVE")
    s.assign("a","u","r","P3",{"capacity":4},"C","PASS","PASS")
    s.create_session("a","s",{"load":"standard"})
    m=s.record_measurement("s","trait",missing_reason="not_collected")
    assert m["missing_reason"]=="not_collected"

def test_safety_block_forces_stop_adaptation():
    s=_service()
    s.register_rule_from_fields("r","Rule","MDL","1.0",["P3"],[],["capacity"],{}, {},status="ACTIVE")
    s.assign("a","u","r","P3",{"capacity":4},"C","PASS","PASS")
    x=s.adapt("a","ad1","C","IMPROVED","BLOCK",{"capacity":4})
    assert x.decision=="STOP" and x.next_level=="A"

def test_contraindication_blocks_assignment():
    s=_service()
    s.register_rule_from_fields("r","Rule","MDL","1.0",["P3"],["blocked_state"],["capacity"],{}, {},status="ACTIVE")
    a=s.assign("a","u","r","P3",{"capacity":4},"C","PASS","PASS",context_flags={"blocked_state"})
    assert a.safety_gate_status=="BLOCK"

def test_hold_assignment_cannot_create_session():
    s=_service()
    s.register_rule_from_fields("r","Rule","MDL","1.0",["P3"],[],["capacity"],{}, {},status="ACTIVE")
    s.assign("a","u","r","P3",{"capacity":4},"C","PASS","UNKNOWN")
    try:
        s.create_session("a","s",{"load":"standard"})
    except ValueError as e:
        assert "not executable" in str(e)
    else:
        assert False

def test_session_execution_uses_transformation_runtime():
    from cte.orchestrator import OrchestratorService
    from cte.contracts.transformation import TransformationContract
    from cte.persistence import SQLiteRuntimeStore
    store=SQLiteRuntimeStore(":memory:")
    o=OrchestratorService(store)
    o.create_execution("ie1","c",{},["SAFETY_GATE","INTERVENTION"])
    o.start("ie1")
    o.advance_stage("ie1","SAFETY_GATE","PASSED",metadata={"safety_status":"PASS"})
    class R: nodes={}
    s=InterventionService(R(),store)
    s.register_rule_from_fields("r","Rule","MDL","1.0",["P3"],[],["capacity"],{}, {},status="ACTIVE")
    a=s.assign("a","u","r","P3",{"capacity":4},"C","PASS","PASS",execution_id="ie1")
    s.create_session("a","s",{"load":"standard"})
    result=s.execute_session_transformation("s","u1",1,{"tempo":5},
        TransformationContract("t1","1",expected_changes={"tempo":6}),
        lambda state:{**state,"tempo":6})
    assert result.result.status=="VALIDATED"
    assert result.certificate is not None
    assert s.assignments["a"].sessions["s"].completion_status=="COMPLETED"

def test_session_execution_rejects_noop_and_marks_failed():
    from cte.orchestrator import OrchestratorService
    from cte.contracts.transformation import TransformationContract
    from cte.persistence import SQLiteRuntimeStore
    store=SQLiteRuntimeStore(":memory:")
    o=OrchestratorService(store)
    o.create_execution("ie2","c",{},["SAFETY_GATE","INTERVENTION"])
    o.start("ie2")
    o.advance_stage("ie2","SAFETY_GATE","PASSED",metadata={"safety_status":"PASS"})
    class R: nodes={}
    s=InterventionService(R(),store)
    s.register_rule_from_fields("r","Rule","MDL","1.0",["P3"],[],["capacity"],{}, {},status="ACTIVE")
    s.assign("a","u","r","P3",{"capacity":4},"C","PASS","PASS",execution_id="ie2")
    s.create_session("a","s",{"load":"standard"})
    result=s.execute_session_transformation("s","u1",1,{"tempo":5},
        TransformationContract("t1","1",expected_changes={"tempo":6}),
        lambda state:state)
    assert result.result.failure_code=="NO_STATE_CHANGE"
    assert s.assignments["a"].sessions["s"].completion_status=="FAILED"
