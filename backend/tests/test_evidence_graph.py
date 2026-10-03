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


def test_register_node_rejects_missing_identity_fields_and_non_object_metadata():
    import pytest

    invalid_cases = [
        ({"node_id": ""}, "node_id must be a non-empty string"),
        ({"node_type": None}, "node_type must be a non-empty string"),
        ({"entity_id": " "}, "entity_id must be a non-empty string"),
        ({"provenance_class": None}, "provenance_class must be a non-empty string"),
        ({"version": ""}, "version must be a non-empty string"),
        ({"metadata": None}, "node metadata must be an object"),
        ({"metadata": []}, "node metadata must be an object"),
    ]
    for override, message in invalid_cases:
        values = {
            "node_id": "valid-node",
            "node_type": "DATASET",
            "entity_id": "entity",
            "provenance_class": "DRV",
            "version": "1",
            "metadata": {},
        }
        values.update(override)
        with pytest.raises(ValueError, match=message):
            register_node(**values)


def test_register_edge_rejects_invalid_boundary_inputs():
    import pytest

    source = register_node("edge-source", "ANALYSIS", "source", "DRV", "1", {})
    target = register_node("edge-target", "DATASET", "target", "DRV", "1", {})
    invalid_cases = [
        ("", source, target, "ANALYZED_FROM", "", "edge_id must be a non-empty string"),
        ("e", None, target, "ANALYZED_FROM", "", "edge endpoints must be registered graph nodes"),
        ("e", source, None, "ANALYZED_FROM", "", "edge endpoints must be registered graph nodes"),
        ("e", source, target, None, "", "edge_type must be a non-empty string"),
        ("e", source, target, "ANALYZED_FROM", None, "edge rationale must be a string"),
    ]
    for edge_id, from_node, to_node, edge_type, rationale, message in invalid_cases:
        with pytest.raises(ValueError, match=message):
            register_edge(edge_id, from_node, to_node, edge_type, rationale=rationale)
