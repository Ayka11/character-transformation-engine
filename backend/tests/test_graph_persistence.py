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

        restored = build_registry(SQLiteRuntimeStore(path))
        assert "integrity-edge" in restored.edges
        assert restored.integrity_errors == [
            "evidence graph edge references missing node: integrity-edge"
        ]


def test_result_lineage_fails_closed_when_analysis_node_is_missing():
    from dataclasses import replace
    import pytest

    graph = build_registry()
    result = register_node("lineage-result", "RESULT", "result", "DRV", "1", {})
    analysis = register_node("lineage-analysis", "ANALYSIS", "analysis", "DRV", "1", {})
    graph.add_node(result)
    edge = register_edge("lineage-result-edge", analysis, result, "RESULTS_IN")
    graph.edges[edge.edge_id] = replace(edge, from_node_id="missing-analysis")

    with pytest.raises(ValueError, match="RESULT lineage references missing ANALYSIS node"):
        graph.require_lineage_for_result("lineage-result")


def test_result_lineage_fails_closed_when_dataset_node_is_missing():
    from dataclasses import replace
    import pytest

    graph = build_registry()
    dataset = register_node("lineage-dataset", "DATASET", "dataset", "DRV", "1", {})
    analysis = register_node("lineage-analysis", "ANALYSIS", "analysis", "DRV", "1", {})
    result = register_node("lineage-result", "RESULT", "result", "DRV", "1", {})
    for node in (analysis, result):
        graph.add_node(node)
    result_edge = register_edge("lineage-result-edge", analysis, result, "RESULTS_IN")
    dataset_edge = register_edge("lineage-dataset-edge", analysis, dataset, "ANALYZED_FROM")
    graph.add_edge(result_edge)
    graph.edges[dataset_edge.edge_id] = replace(dataset_edge, to_node_id="missing-dataset")

    with pytest.raises(ValueError, match="ANALYSIS lineage references missing source node"):
        graph.require_lineage_for_result("lineage-result")




def test_node_replay_repairs_audit_event_after_partial_write(monkeypatch):
    with TemporaryDirectory() as d:
        store = SQLiteRuntimeStore(str(Path(d) / "runtime.sqlite3"))
        graph = build_registry(store)
        node = register_node("retry-node", "DATASET", "entity", "DRV", "1", {})
        original = store.append_event
        failed = {"once": False}

        def fail_once(*args, **kwargs):
            if not failed["once"]:
                failed["once"] = True
                raise OSError("simulated audit event failure")
            return original(*args, **kwargs)

        monkeypatch.setattr(store, "append_event", fail_once)
        try:
            graph.add_node(node)
        except OSError:
            pass
        else:
            raise AssertionError("first audit append should fail")

        assert store.list_events("graph") == []
        graph.add_node(node)
        events = store.list_events("graph")
        assert len([e for e in events if e["event_type"] == "NODE_REGISTERED"]) == 1
        assert len([e for e in graph.audit_events if e.node_id == "retry-node"]) == 1


def test_edge_replay_repairs_audit_event_after_partial_write(monkeypatch):
    with TemporaryDirectory() as d:
        store = SQLiteRuntimeStore(str(Path(d) / "runtime.sqlite3"))
        graph = build_registry(store)
        source = register_node("retry-source", "ANALYSIS", "source", "DRV", "1", {})
        target = register_node("retry-target", "RESULT", "target", "DRV", "1", {})
        graph.add_node(source)
        graph.add_node(target)
        edge = register_edge("retry-edge", source, target, "RESULTS_IN")
        original = store.append_event
        failed = {"once": False}

        def fail_once(*args, **kwargs):
            if not failed["once"]:
                failed["once"] = True
                raise OSError("simulated audit event failure")
            return original(*args, **kwargs)

        monkeypatch.setattr(store, "append_event", fail_once)
        try:
            graph.add_edge(edge)
        except OSError:
            pass
        else:
            raise AssertionError("first audit append should fail")

        assert not any(
            e["event_type"] == "EDGE_REGISTERED" for e in store.list_events("graph")
        )
        graph.add_edge(edge)
        events = store.list_events("graph")
        assert len([e for e in events if e["event_type"] == "EDGE_REGISTERED"]) == 1
        assert len([e for e in graph.audit_events if e.edge_id == "retry-edge"]) == 1
