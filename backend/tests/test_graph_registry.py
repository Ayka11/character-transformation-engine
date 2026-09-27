from cte.evidence_graph import register_edge, register_node
from cte.graph_registry import build_registry

def test_result_requires_analysis_and_dataset_lineage():
    g=build_registry()
    d=register_node("d","DATASET","d","DRV","1",{})
    a=register_node("a","ANALYSIS","a","DRV","1",{})
    r=register_node("r","RESULT","r","DRV","1",{})
    g.add_node(d); g.add_node(a); g.add_node(r)
    g.add_edge(register_edge("e1",d,a,"ANALYZED_FROM"))
    g.add_edge(register_edge("e2",a,r,"RESULTS_IN"))
    g.require_lineage_for_result("r")

def test_orphan_result_is_blocked():
    g=build_registry()
    g.add_node(register_node("r","RESULT","r","DRV","1",{}))
    try:
        g.require_lineage_for_result("r")
        assert False
    except ValueError:
        assert True

def test_immutable_node_conflict_is_blocked():
    g=build_registry()
    g.add_node(register_node("r","RESULT","r","DRV","1",{"x":1}))
    try:
        g.add_node(register_node("r","RESULT","r","DRV","1",{"x":2}))
        assert False
    except ValueError:
        assert True

from cte.evidence_graph import register_node, register_edge

def test_claim_upstream_types_are_derived_from_registered_graph():
    g=build_registry()
    d=register_node("d2","DATASET","d2","DRV","1",{})
    a=register_node("a2","ANALYSIS","a2","DRV","1",{})
    r=register_node("r2","RESULT","r2","DRV","1",{})
    rep=register_node("rep2","REPLICATION","rep2","DRV","1",{})
    gen=register_node("gen2","GENERALIZATION","gen2","DRV","1",{})
    for n in (d,a,r,rep,gen): g.add_node(n)
    g.add_edge(register_edge("x1",d,a,"ANALYZED_FROM"))
    g.add_edge(register_edge("x2",a,r,"RESULTS_IN"))
    g.add_edge(register_edge("x3",rep,r,"REPLICATES"))
    g.add_edge(register_edge("x4",gen,r,"GENERALIZES"))
    assert g.claim_upstream_types("r2") == {"RESULT","ANALYSIS","DATASET","REPLICATION","GENERALIZATION"}
