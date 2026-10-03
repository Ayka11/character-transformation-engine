from cte.evidence_graph import register_node, register_edge
from cte.graph_registry import build_registry

def _result_graph():
    g=build_registry()
    d=register_node("d","DATASET","d","DRV","1",{"values_hash":"x"})
    a=register_node("a","ANALYSIS","a","DRV","1",{"design_type":"ASSOCIATIONAL"})
    r=register_node("r","RESULT","r","DRV","1",{"qc_status":"PASS"})
    p=register_node("p","PROTOCOL","p","DRV","1",{"design_type":"ASSOCIATIONAL"})
    for n in (d,a,r,p): g.add_node(n)
    g.add_edge(register_edge("ed",a,d,"ANALYZED_FROM"))
    g.add_edge(register_edge("er",a,r,"RESULTS_IN"))
    g.add_edge(register_edge("ep",p,a,"USES_PROTOCOL"))
    return g

def test_claim_registration_creates_support_edge():
    g=_result_graph()
    claim=g.register_claim("c1","r","REGISTERED","ASSOCIATIONAL_RESULT","DRV",{})
    assert claim.node_type=="CLAIM"
    assert any(e.from_node_id=="r" and e.to_node_id=="c1" and e.edge_type=="SUPPORTS" for e in g.edges.values())

def test_claim_transition_history_is_immutable_and_linked():
    g=_result_graph()
    rep=register_node("rep-history","REPLICATION","rep-history","DRV","1",{"independent":True,"criteria_registered":True})
    g.add_node(rep)
    g.add_edge(register_edge("rep-history-edge",rep,g.nodes["r"],"REPLICATES"))
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

def test_non_initial_claim_cannot_fabricate_current_state():
    g=_result_graph()
    g.register_claim("c0",None,"HYPOTHESIS","REGISTERED","HYP",{})
    try:
        g.register_claim("c1","r","DESCRIPTIVE_RESULT","ASSOCIATIONAL_RESULT","DRV",{},previous_claim_id="c0")
    except ValueError as e:
        assert "current_state does not match" in str(e)
    else:
        assert False



def test_claim_registration_replay_repairs_missing_support_edge_after_restart(monkeypatch):
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from cte.persistence import SQLiteRuntimeStore

    with TemporaryDirectory() as d:
        path = str(Path(d) / "runtime.sqlite3")
        graph = build_registry(SQLiteRuntimeStore(path))
        dataset = register_node("replay-dataset", "DATASET", "d", "DRV", "1", {"values_hash": "x"})
        analysis = register_node("replay-analysis", "ANALYSIS", "a", "DRV", "1", {"design_type": "ASSOCIATIONAL"})
        result = register_node("r", "RESULT", "r", "DRV", "1", {"qc_status": "PASS"})
        protocol = register_node("replay-protocol", "PROTOCOL", "p", "DRV", "1", {"design_type": "ASSOCIATIONAL"})
        for node in (dataset, analysis, result, protocol):
            graph.add_node(node)
        graph.add_edge(register_edge("replay-ed", analysis, dataset, "ANALYZED_FROM"))
        graph.add_edge(register_edge("replay-er", analysis, result, "RESULTS_IN"))
        graph.add_edge(register_edge("replay-ep", protocol, analysis, "USES_PROTOCOL"))

        original_add_edge = graph.add_edge

        def fail_support_edge_once(edge):
            if edge.edge_type == "SUPPORTS" and edge.to_node_id == "replay-claim":
                raise OSError("simulated interruption before support edge write")
            return original_add_edge(edge)

        monkeypatch.setattr(graph, "add_edge", fail_support_edge_once)
        try:
            graph.register_claim("replay-claim", "r", "REGISTERED", "ASSOCIATIONAL_RESULT", "DRV", {})
        except OSError as exc:
            assert "support edge write" in str(exc)
        else:
            raise AssertionError("support edge creation should fail once")

        assert "replay-claim" in graph.nodes
        assert graph.store.get_snapshot("graph.node", "replay-claim") is not None
        assert graph.store.get_snapshot("graph.edge", "replay-claim:supports:r") is None

        recovered = build_registry(SQLiteRuntimeStore(path))
        assert "replay-claim" in recovered.nodes
        assert "replay-claim:supports:r" not in recovered.edges

        claim = recovered.register_claim(
            "replay-claim", "r", "REGISTERED", "ASSOCIATIONAL_RESULT", "DRV", {},
        )
        assert claim.node_id == "replay-claim"
        assert "replay-claim:supports:r" in recovered.edges
        assert len([event for event in recovered.store.list_events("graph")
                    if event["event_type"] == "EDGE_REGISTERED"
                    and event["payload"].get("edge_id") == "replay-claim:supports:r"]) == 1
