from cte.evidence_graph import register_edge, register_node

def test_result_edge_is_typed():
    a=register_node("a1","ANALYSIS","a1","DRV","1",{})
    r=register_node("r1","RESULT","r1","DRV","1",{})
    e=register_edge("e1",a,r,"RESULTS_IN")
    assert e.edge_type=="RESULTS_IN"

def test_result_edge_wrong_direction_is_blocked():
    r=register_node("r1","RESULT","r1","DRV","1",{})
    a=register_node("a1","ANALYSIS","a1","DRV","1",{})
    try:
        register_edge("e1",r,a,"RESULTS_IN")
        assert False
    except ValueError:
        assert True

def test_invalid_node_type_is_blocked():
    try:
        register_node("x","UNKNOWN","x","DRV","1",{})
        assert False
    except ValueError:
        assert True
