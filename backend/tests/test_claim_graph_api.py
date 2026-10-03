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


def test_claim_subgraph_and_upstream_nodes_have_canonical_order():
    def make_graph(node_order, edge_order):
        g = build_registry()
        definitions = {
            "dataset-z": register_node("dataset-z", "DATASET", "dataset-z", "DRV", "1", {}),
            "analysis": register_node("analysis", "ANALYSIS", "analysis", "DRV", "1", {}),
            "result": register_node("result", "RESULT", "result", "DRV", "1", {}),
            "dataset-a": register_node("dataset-a", "DATASET", "dataset-a", "DRV", "1", {}),
            "claim": register_node("claim", "CLAIM", "claim", "DRV", "1", {}),
        }
        for node_id in node_order:
            g.add_node(definitions[node_id])
        edges = {
            "z-dataset": register_edge(
                "z-dataset", definitions["analysis"], definitions["dataset-z"], "ANALYZED_FROM",
            ),
            "a-dataset": register_edge(
                "a-dataset", definitions["analysis"], definitions["dataset-a"], "ANALYZED_FROM",
            ),
            "analysis-result": register_edge(
                "analysis-result", definitions["analysis"], definitions["result"], "RESULTS_IN",
            ),
            "result-claim": register_edge(
                "result-claim", definitions["result"], definitions["claim"], "SUPPORTS",
            ),
        }
        for edge_id in edge_order:
            g.add_edge(edges[edge_id])
        return g

    first = make_graph(
        ["dataset-z", "analysis", "result", "dataset-a", "claim"],
        ["z-dataset", "analysis-result", "result-claim", "a-dataset"],
    )
    second = make_graph(
        ["claim", "dataset-a", "result", "analysis", "dataset-z"],
        ["a-dataset", "result-claim", "analysis-result", "z-dataset"],
    )

    expected_nodes = ["analysis", "claim", "dataset-a", "dataset-z", "result"]
    expected_edges = ["a-dataset", "analysis-result", "result-claim", "z-dataset"]
    for graph in (first, second):
        nodes, edges = graph.claim_subgraph("claim")
        assert [node.node_id for node in nodes] == expected_nodes
        assert [edge.edge_id for edge in edges] == expected_edges
        assert [node.node_id for node in graph._upstream_nodes("result")] == [
            "analysis", "dataset-a", "dataset-z",
        ]
