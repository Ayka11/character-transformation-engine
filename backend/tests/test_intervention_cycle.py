from cte.intervention_engine import InterventionService

def test_full_intervention_cycle():
    class R: nodes={}
    s=InterventionService(R())
    s.register_rule_from_fields("r","Rule","MDL","1.0",["P3"],[],["capacity"],{}, {},status="ACTIVE")
    a=s.assign("a","u","r","P3",{"capacity":4},"C","PASS","PASS")
    session=s.create_session("a","s",{"load":"standard"})
    m=s.record_measurement("s","trait",value_numeric=5)
    response=s.record_response("s","TARGET_TRAIT",4,6)
    decision=s.adapt("a","ad1","C",response["response_status"],"PASS",{"capacity":4,"response":response["response_status"]})
    assert session.completion_status=="PLANNED"
    assert m["value_numeric"]==5
    assert response["response_status"]=="IMPROVED"
    assert decision.decision=="ADJUST"

def test_research_link_is_not_evidence():
    class R: nodes={}
    s=InterventionService(R())
    s.register_rule_from_fields("r","Rule","MDL","1.0",["P3"],[],["capacity"],{}, {},status="ACTIVE")
    s.assign("a","u","r","P3",{"capacity":4},"C","PASS","PASS")
    s.create_session("a","s",{})
    x=s.research_link("s","GENERATES_OBSERVATION",result_node_id="result")
    assert x["runtime_observation_is_evidence"] is False
