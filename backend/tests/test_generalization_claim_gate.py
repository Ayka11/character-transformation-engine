from cte.evidence_graph import register_node, register_edge
from cte.graph_registry import build_registry

def _generalized_graph():
    g=build_registry()
    d=register_node("d","DATASET","d","DRV","1",{})
    a=register_node("a","ANALYSIS","a","DRV","1",{})
    r=register_node("r","RESULT","r","DRV","1",{"qc_status":"PASS","validated_descriptive_result":True})
    rep=register_node("rep","REPLICATION","rep","DRV","1",{"independent":True,"criteria_registered":True,"assessment_status":"REPLICATED"})
    gen=register_node("gen","GENERALIZATION","gen","DRV","1",{"run_status":"COMPLETED","result_status":"GENERALIZABLE","target_population_context":{"site":"B"}})
    for n in (d,a,r,rep,gen): g.add_node(n)
    g.add_edge(register_edge("ed",a,d,"ANALYZED_FROM"))
    g.add_edge(register_edge("er",a,r,"RESULTS_IN"))
    g.add_edge(register_edge("rp",rep,r,"REPLICATES"))
    g.add_edge(register_edge("ge",gen,r,"GENERALIZES"))
    return g

def test_generalized_claim_requires_successful_replication_and_generalization():
    g=_generalized_graph()
    g.register_claim("c1","r","REGISTERED","DESCRIPTIVE_RESULT","DRV",{})
    g.register_claim("c2","r","DESCRIPTIVE_RESULT","ASSOCIATIONAL_RESULT","DRV",{},previous_claim_id="c1")
    g.register_claim("c3","r","ASSOCIATIONAL_RESULT","REPLICATED_RESULT","DRV",{},previous_claim_id="c2")
    c4=g.register_claim("c4","r","REPLICATED_RESULT","GENERALIZED_RESULT","DRV",{},previous_claim_id="c3")
    assert c4.metadata["state"]=="GENERALIZED_RESULT"

def test_generalized_claim_blocks_unsuccessful_transport():
    g=_generalized_graph()
    g.nodes["gen"]=register_node("gen","GENERALIZATION","gen","DRV","1",{"run_status":"COMPLETED","result_status":"NOT_GENERALIZABLE","target_population_context":{"site":"B"}})
    try:
        g.register_claim("c","r","REPLICATED_RESULT","GENERALIZED_RESULT","DRV",{})
    except ValueError as e:
        assert "generalization_run" in str(e)
    else:
        assert False

def test_evidence_supported_requires_claim_bound_evidence_criteria():
    from cte.evidence_graph import register_node, register_edge
    g=_generalized_graph()
    criteria=register_node("ec","PROTOCOL","ec","DRV","1",{"kind":"EVIDENCE_CRITERIA","claim_id":"c3","rule_ids":["E1"]})
    g.add_node(criteria)
    g.add_edge(register_edge("epc",g.nodes["a"],criteria,"USES_PROTOCOL"))
    g.register_claim("c1","r","REGISTERED","DESCRIPTIVE_RESULT","DRV",{})
    g.register_claim("c2","r","DESCRIPTIVE_RESULT","ASSOCIATIONAL_RESULT","DRV",{},previous_claim_id="c1")
    g.register_claim("c3","r","ASSOCIATIONAL_RESULT","REPLICATED_RESULT","DRV",{},previous_claim_id="c2")
    try:
        g.register_claim("c4","r","REPLICATED_RESULT","EVIDENCE_SUPPORTED","EVD",{},previous_claim_id="c3")
    except ValueError as e:
        assert "registered_evidence_criteria" in str(e)
    else:
        assert False

def test_evidence_supported_opens_for_matching_prior_claim_and_criteria():
    from cte.evidence_graph import register_node, register_edge
    g=_generalized_graph()
    criteria=register_node("ec2","PROTOCOL","ec2","DRV","1",{"kind":"EVIDENCE_CRITERIA","claim_id":"c3","rule_ids":["E1"]})
    g.add_node(criteria)
    g.add_edge(register_edge("epc2",g.nodes["a"],criteria,"USES_PROTOCOL"))
    g.register_claim("c1","r","REGISTERED","DESCRIPTIVE_RESULT","DRV",{})
    g.register_claim("c2","r","DESCRIPTIVE_RESULT","ASSOCIATIONAL_RESULT","DRV",{},previous_claim_id="c1")
    g.register_claim("c3","r","ASSOCIATIONAL_RESULT","REPLICATED_RESULT","DRV",{},previous_claim_id="c2")
    c4=g.register_claim("c4","r","REPLICATED_RESULT","EVIDENCE_SUPPORTED","EVD",{},previous_claim_id="c3")
    assert c4.metadata["state"]=="EVIDENCE_SUPPORTED"
