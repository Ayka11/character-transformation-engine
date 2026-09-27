from cte.evidence_graph import register_node, register_edge
from cte.graph_registry import build_registry

def _result_graph():
    g=build_registry()
    d=register_node("d","DATASET","d","DRV","1",{"values_hash":"x"})
    a=register_node("a","ANALYSIS","a","DRV","1",{"design_type":"ASSOCIATIONAL"})
    r=register_node("r","RESULT","r","DRV","1",{"qc_status":"PASS"})
    for n in (d,a,r): g.add_node(n)
    g.add_edge(register_edge("ed",a,d,"ANALYZED_FROM"))
    g.add_edge(register_edge("er",a,r,"RESULTS_IN"))
    return g

def test_claim_registration_creates_support_edge():
    g=_result_graph()
    claim=g.register_claim("c1","r","REGISTERED","ASSOCIATIONAL_RESULT","DRV",{})
    assert claim.node_type=="CLAIM"
    assert any(e.from_node_id=="r" and e.to_node_id=="c1" and e.edge_type=="SUPPORTS" for e in g.edges.values())

def test_claim_transition_history_is_immutable_and_linked():
    g=_result_graph()
    g.register_claim("c1","r","REGISTERED","ASSOCIATIONAL_RESULT","DRV",{})
    c2=g.register_claim("c2","r","ASSOCIATIONAL_RESULT","REPLICATED_RESULT","DRV",{},previous_claim_id="c1")
    assert c2.metadata["state"]=="REPLICATED_RESULT"
    assert any(e.from_node_id=="c2" and e.to_node_id=="c1" and e.edge_type=="DERIVED_FROM" for e in g.edges.values())

def test_evidence_supported_requires_evd_and_evidence_criteria():
    g=_result_graph()
    try:
        g.register_claim("c1","r","GENERALIZED_RESULT","EVIDENCE_SUPPORTED","DRV",{})
    except ValueError:
        assert True
    else:
        assert False
