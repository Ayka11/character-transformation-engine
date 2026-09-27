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
