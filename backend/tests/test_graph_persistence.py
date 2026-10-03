from pathlib import Path
from tempfile import TemporaryDirectory
from cte.evidence_graph import register_node, register_edge
from cte.graph_registry import build_registry
from cte.persistence import SQLiteRuntimeStore

def test_graph_nodes_edges_and_claim_audit_survive_restart():
    with TemporaryDirectory() as d:
        store=SQLiteRuntimeStore(str(Path(d)/"runtime.sqlite3"))
        g=build_registry(store)
        dataset=register_node("d","DATASET","d","DRV","1",{})
        analysis=register_node("a","ANALYSIS","a","DRV","1",{})
        result=register_node("r","RESULT","r","DRV","1",{"qc_status":"PASS","validated_descriptive_result":True})
        for n in (dataset,analysis,result): g.add_node(n)
        g.add_edge(register_edge("ed",analysis,dataset,"ANALYZED_FROM"))
        g.add_edge(register_edge("er",analysis,result,"RESULTS_IN"))
        claim=g.register_claim("c","r","REGISTERED","DESCRIPTIVE_RESULT","DRV",{})
        g2=build_registry(SQLiteRuntimeStore(str(Path(d)/"runtime.sqlite3")))
        assert {"d","a","r","c"} <= set(g2.nodes)
        assert {"ed","er","c:supports:r"} <= set(g2.edges)
        assert any(e.edge_id=="c:supports:r" for e in g2.claim_audit("c"))

def test_contradiction_and_inference_rules_survive_restart():
    with TemporaryDirectory() as d:
        path=str(Path(d)/"runtime.sqlite3")
        g=build_registry(SQLiteRuntimeStore(path))
        claim=register_node("c","CLAIM","c","DRV","1",{"state":"REGISTERED","result_id":"r"})
        result=register_node("r","RESULT","r","DRV","1",{})
        for n in (claim,result): g.add_node(n)
        g.register_contradiction_set("cx","c",["r"],"CONFLICT")
        g.register_inference_block("ib","MODEL_OUTPUT","EVIDENCE_SUPPORTED","blocked","MODEL","RULE")
        g2=build_registry(SQLiteRuntimeStore(path))
        assert "cx" in g2.contradiction_sets
        assert "ib" in g2.inference_blocks


def test_graph_recovery_rejects_semantically_tampered_node_even_with_rehashed_snapshot():
    import json
    import pytest
    from cte.provenance import content_hash

    with TemporaryDirectory() as d:
        path = str(Path(d) / "runtime.sqlite3")
        store = SQLiteRuntimeStore(path)
        graph = build_registry(store)
        graph.add_node(register_node("integrity-node", "DATASET", "entity", "DRV", "1", {"x": 1}))

        with store._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM runtime_snapshots WHERE namespace=? AND key=?",
                ("graph.node", "integrity-node"),
            ).fetchone()
            payload = json.loads(row[0])
            payload["metadata"]["x"] = 2
            payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            conn.execute(
                "UPDATE runtime_snapshots SET payload_json=?, payload_hash=? WHERE namespace=? AND key=?",
                (payload_json, content_hash(payload), "graph.node", "integrity-node"),
            )
            conn.commit()

        with pytest.raises(ValueError, match="evidence graph node integrity failure: integrity-node"):
            build_registry(SQLiteRuntimeStore(path))


def test_graph_recovery_rejects_edge_with_missing_endpoint():
    import json
    import pytest
    from cte.provenance import content_hash

    with TemporaryDirectory() as d:
        path = str(Path(d) / "runtime.sqlite3")
        store = SQLiteRuntimeStore(path)
        graph = build_registry(store)
        source = register_node("integrity-source", "ANALYSIS", "source", "DRV", "1", {})
        target = register_node("integrity-target", "RESULT", "target", "DRV", "1", {})
        graph.add_node(source)
        graph.add_node(target)
        graph.add_edge(register_edge("integrity-edge", source, target, "RESULTS_IN"))

        with store._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM runtime_snapshots WHERE namespace=? AND key=?",
                ("graph.edge", "integrity-edge"),
            ).fetchone()
            payload = json.loads(row[0])
            payload["to_node_id"] = "missing-target"
            payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            conn.execute(
                "UPDATE runtime_snapshots SET payload_json=?, payload_hash=? WHERE namespace=? AND key=?",
                (payload_json, content_hash(payload), "graph.edge", "integrity-edge"),
            )
            conn.commit()

        with pytest.raises(ValueError, match="evidence graph edge references missing node: integrity-edge"):
            build_registry(SQLiteRuntimeStore(path))
