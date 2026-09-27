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
