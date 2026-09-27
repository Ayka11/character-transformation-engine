from cte.evidence_graph import register_node, register_edge
from cte.graph_registry import build_registry

def test_edge_requires_registered_endpoints():
    g=build_registry()
    a=register_node("a","ANALYSIS","a","DRV","1",{})
    r=register_node("r","RESULT","r","DRV","1",{})
    g.add_node(a)
    try:
        g.add_edge(register_edge("e",a,r,"RESULTS_IN"))
    except ValueError as e:
        assert "unknown node" in str(e)
    else:
        assert False

def test_registered_node_metadata_is_available_to_claim_gate():
    g=build_registry()
    p=register_node("p","PROTOCOL","p","DRV","1",{"design_type":"INTERVENTION"})
    g.add_node(p)
    assert g.nodes["p"].metadata["design_type"]=="INTERVENTION"
