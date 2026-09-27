from cte.evidence_graph import register_node, register_edge
from cte.graph_registry import build_registry

def _replicated_graph():
    g=build_registry()
    d=register_node("d","DATASET","d","DRV","1",{})
    a=register_node("a","ANALYSIS","a","DRV","1",{})
    r=register_node("r","RESULT","r","DRV","1",{"qc_status":"PASS"})
    rep=register_node("rep","REPLICATION","rep","DRV","1",{"independent":True,"criteria_registered":True})
    for n in (d,a,r,rep): g.add_node(n)
    g.add_edge(register_edge("ed",a,d,"ANALYZED_FROM"))
    g.add_edge(register_edge("er",a,r,"RESULTS_IN"))
    g.add_edge(register_edge("rp",rep,r,"REPLICATES"))
    return g

def test_replicated_claim_requires_graph_replication():
    g=_replicated_graph()
    g.register_claim("c1","r","REGISTERED","DESCRIPTIVE_RESULT","DRV",{})
    c2=g.register_claim("c2","r","DESCRIPTIVE_RESULT","ASSOCIATIONAL_RESULT","DRV",{},previous_claim_id="c1")
    c3=g.register_claim("c3","r","ASSOCIATIONAL_RESULT","REPLICATED_RESULT","DRV",{},previous_claim_id="c2")
    assert c3.metadata["state"]=="REPLICATED_RESULT"

def test_replication_without_independence_cannot_promote():
    g=_replicated_graph()
    g.nodes["rep"]=register_node("rep","REPLICATION","rep","DRV","1",{"independent":False,"criteria_registered":True})
    try:
        g.register_claim("c1","r","ASSOCIATIONAL_RESULT","REPLICATED_RESULT","DRV",{})
    except ValueError as e:
        assert "independent_replication" in str(e)
    else:
        assert False
