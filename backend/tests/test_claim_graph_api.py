from cte.evidence_graph import register_node, register_edge
from cte.graph_registry import build_registry

def test_claim_subgraph_contains_prior_claim_result_and_analysis():
    g=build_registry()
    d=register_node("d","DATASET","d","DRV","1",{})
    a=register_node("a","ANALYSIS","a","DRV","1",{})
    r=register_node("r","RESULT","r","DRV","1",{"qc_status":"PASS","validated_descriptive_result":True})
    for n in (d,a,r): g.add_node(n)
    g.add_edge(register_edge("ed",a,d,"ANALYZED_FROM"))
    g.add_edge(register_edge("er",a,r,"RESULTS_IN"))
    c1=g.register_claim("c1","r","REGISTERED","DESCRIPTIVE_RESULT","DRV",{})
    c2=g.register_claim("c2","r","DESCRIPTIVE_RESULT","ASSOCIATIONAL_RESULT","DRV",{},previous_claim_id="c1")
    nodes,edges=g.claim_subgraph("c2")
    ids={n.node_id for n in nodes}
    assert {"c2","c1","r","a","d"} <= ids
    assert any(e.edge_type=="DERIVED_FROM" for e in edges)
    assert any(e.edge_type=="SUPPORTS" for e in edges)

def test_claim_audit_records_node_and_edge_events():
    g=build_registry()
    r=register_node("r","RESULT","r","DRV","1",{"qc_status":"PASS","validated_descriptive_result":True})
    a=register_node("a","ANALYSIS","a","DRV","1",{})
    d=register_node("d","DATASET","d","DRV","1",{})
    g.add_node(r); g.add_node(a); g.add_node(d)
    g.add_edge(register_edge("ed",a,d,"ANALYZED_FROM"))
    g.add_edge(register_edge("er",a,r,"RESULTS_IN"))
    g.register_claim("c1","r","REGISTERED","DESCRIPTIVE_RESULT","DRV",{})
    events=g.claim_audit("c1")
    assert any(e.operation=="NODE_REGISTERED" and e.node_id=="c1" for e in events)
    assert any(e.operation=="EDGE_REGISTERED" and e.edge_id=="c1:supports:r" for e in events)
