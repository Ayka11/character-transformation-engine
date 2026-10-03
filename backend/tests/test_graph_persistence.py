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


def test_contradiction_set_replay_after_restart_normalizes_node_ids():
    with TemporaryDirectory() as d:
        path = str(Path(d) / "runtime.sqlite3")
        store = SQLiteRuntimeStore(path)
        graph = build_registry(store)
        claim = register_node("replay-claim", "CLAIM", "claim", "DRV", "1", {})
        evidence = register_node("replay-evidence", "DATASET", "evidence", "DRV", "1", {})
        graph.add_node(claim)
        graph.add_node(evidence)
        original = graph.register_contradiction_set(
            "replay-contradiction", claim.node_id, [evidence.node_id], "CONFLICT"
        )

        restored = build_registry(SQLiteRuntimeStore(path))
        recovered = restored.contradiction_sets["replay-contradiction"]
        assert recovered.node_ids == (evidence.node_id,)
        replayed = restored.register_contradiction_set(
            "replay-contradiction", claim.node_id, [evidence.node_id], "CONFLICT"
        )

        assert replayed == recovered == original
        assert len([
            event for event in restored.audit_events
            if event.contradiction_set_id == "replay-contradiction"
        ]) == 1


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
        assert "retry-node" not in graph.nodes
        assert not any(e.node_id == "retry-node" for e in graph.audit_events)
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
        assert "retry-edge" not in graph.edges
        assert not any(e.edge_id == "retry-edge" for e in graph.audit_events)
        graph.add_edge(edge)
        events = store.list_events("graph")
        assert len([e for e in events if e["event_type"] == "EDGE_REGISTERED"]) == 1
        assert len([e for e in graph.audit_events if e.edge_id == "retry-edge"]) == 1


def test_graph_recovery_repairs_missing_node_audit_event_after_restart(monkeypatch):
    with TemporaryDirectory() as d:
        path = str(Path(d) / "runtime.sqlite3")
        store = SQLiteRuntimeStore(path)
        graph = build_registry(store)
        node = register_node("restart-retry-node", "DATASET", "entity", "DRV", "1", {})
        original = store.append_event

        def fail_node_event(event_id, namespace, event_type, payload, *args, **kwargs):
            if event_type == "NODE_REGISTERED" and payload.get("node_id") == node.node_id:
                raise OSError("simulated process interruption after snapshot write")
            return original(event_id, namespace, event_type, payload, *args, **kwargs)

        monkeypatch.setattr(store, "append_event", fail_node_event)
        try:
            graph.add_node(node)
        except OSError:
            pass
        else:
            raise AssertionError("first audit append should fail")

        assert store.list_events("graph") == []
        recovered = build_registry(SQLiteRuntimeStore(path))
        events = SQLiteRuntimeStore(path).list_events("graph")
        assert "restart-retry-node" in recovered.nodes
        assert len([e for e in events if e["event_type"] == "NODE_REGISTERED"
                    and e["payload"].get("node_id") == "restart-retry-node"]) == 1
        assert len([e for e in recovered.audit_events if e.node_id == "restart-retry-node"]) == 1


def test_graph_recovery_repairs_missing_edge_audit_event_after_restart(monkeypatch):
    with TemporaryDirectory() as d:
        path = str(Path(d) / "runtime.sqlite3")
        store = SQLiteRuntimeStore(path)
        graph = build_registry(store)
        source = register_node("restart-retry-source", "ANALYSIS", "source", "DRV", "1", {})
        target = register_node("restart-retry-target", "RESULT", "target", "DRV", "1", {})
        graph.add_node(source)
        graph.add_node(target)
        edge = register_edge("restart-retry-edge", source, target, "RESULTS_IN")
        original = store.append_event

        def fail_edge_event(event_id, namespace, event_type, payload, *args, **kwargs):
            if event_type == "EDGE_REGISTERED" and payload.get("edge_id") == edge.edge_id:
                raise OSError("simulated process interruption after snapshot write")
            return original(event_id, namespace, event_type, payload, *args, **kwargs)

        monkeypatch.setattr(store, "append_event", fail_edge_event)
        try:
            graph.add_edge(edge)
        except OSError:
            pass
        else:
            raise AssertionError("first audit append should fail")

        assert not any(e["event_type"] == "EDGE_REGISTERED"
                       and e["payload"].get("edge_id") == edge.edge_id
                       for e in store.list_events("graph"))
        recovered = build_registry(SQLiteRuntimeStore(path))
        events = SQLiteRuntimeStore(path).list_events("graph")
        assert edge.edge_id in recovered.edges
        assert len([e for e in events if e["event_type"] == "EDGE_REGISTERED"
                    and e["payload"].get("edge_id") == edge.edge_id]) == 1
        assert len([e for e in recovered.audit_events if e.edge_id == edge.edge_id]) == 1


def test_failed_node_audit_write_does_not_publish_node_in_memory(monkeypatch):
    with TemporaryDirectory() as d:
        store = SQLiteRuntimeStore(str(Path(d) / "runtime.sqlite3"))
        graph = build_registry(store)
        node = register_node("atomic-memory-node", "DATASET", "entity", "DRV", "1", {})
        original = store.append_event

        def fail_node_event(event_id, namespace, event_type, payload, *args, **kwargs):
            if event_type == "NODE_REGISTERED" and payload.get("node_id") == node.node_id:
                raise OSError("simulated audit event failure")
            return original(event_id, namespace, event_type, payload, *args, **kwargs)

        monkeypatch.setattr(store, "append_event", fail_node_event)
        import pytest
        with pytest.raises(OSError, match="simulated audit event failure"):
            graph.add_node(node)
        assert node.node_id not in graph.nodes
        assert not any(e.node_id == node.node_id for e in graph.audit_events)
        assert store.get_snapshot("graph.node", node.node_id) is not None
        assert not any(e["payload"].get("node_id") == node.node_id
                       for e in store.list_events("graph"))


def test_failed_edge_audit_write_does_not_publish_edge_in_memory(monkeypatch):
    with TemporaryDirectory() as d:
        store = SQLiteRuntimeStore(str(Path(d) / "runtime.sqlite3"))
        graph = build_registry(store)
        source = register_node("atomic-memory-source", "ANALYSIS", "source", "DRV", "1", {})
        target = register_node("atomic-memory-target", "RESULT", "target", "DRV", "1", {})
        graph.add_node(source)
        graph.add_node(target)
        edge = register_edge("atomic-memory-edge", source, target, "RESULTS_IN")
        original = store.append_event

        def fail_edge_event(event_id, namespace, event_type, payload, *args, **kwargs):
            if event_type == "EDGE_REGISTERED" and payload.get("edge_id") == edge.edge_id:
                raise OSError("simulated audit event failure")
            return original(event_id, namespace, event_type, payload, *args, **kwargs)

        monkeypatch.setattr(store, "append_event", fail_edge_event)
        import pytest
        with pytest.raises(OSError, match="simulated audit event failure"):
            graph.add_edge(edge)
        assert edge.edge_id not in graph.edges
        assert not any(e.edge_id == edge.edge_id for e in graph.audit_events)
        assert store.get_snapshot("graph.edge", edge.edge_id) is not None
        assert not any(e["payload"].get("edge_id") == edge.edge_id
                       for e in store.list_events("graph"))



def test_contradiction_set_replay_completes_edges_after_partial_failure(monkeypatch):
    import pytest

    with TemporaryDirectory() as d:
        store = SQLiteRuntimeStore(str(Path(d) / "runtime.sqlite3"))
        graph = build_registry(store)
        claim = register_node("retry-contradiction-claim", "CLAIM", "claim", "DRV", "1", {})
        evidence_a = register_node("retry-contradiction-a", "DATASET", "a", "DRV", "1", {})
        evidence_b = register_node("retry-contradiction-b", "DATASET", "b", "DRV", "1", {})
        for node in (claim, evidence_a, evidence_b):
            graph.add_node(node)

        original_add_edge = graph.add_edge
        failed = {"once": False}

        def fail_second_edge_once(edge):
            if edge.edge_id.endswith(f":{evidence_b.node_id}:{claim.node_id}") and not failed["once"]:
                failed["once"] = True
                raise OSError("simulated interruption during contradiction edge creation")
            return original_add_edge(edge)

        monkeypatch.setattr(graph, "add_edge", fail_second_edge_once)
        with pytest.raises(OSError, match="simulated interruption"):
            graph.register_contradiction_set(
                "retry-contradiction-set", claim.node_id,
                [evidence_a.node_id, evidence_b.node_id], "CONFLICT",
            )

        assert "retry-contradiction-set" in graph.contradiction_sets
        assert "retry-contradiction-set:contradicts:retry-contradiction-a:retry-contradiction-claim" in graph.edges
        assert "retry-contradiction-set:contradicts:retry-contradiction-b:retry-contradiction-claim" not in graph.edges

        monkeypatch.setattr(graph, "add_edge", original_add_edge)
        replayed = graph.register_contradiction_set(
            "retry-contradiction-set", claim.node_id,
            [evidence_a.node_id, evidence_b.node_id], "CONFLICT",
        )
        assert replayed.contradiction_set_id == "retry-contradiction-set"
        assert "retry-contradiction-set:contradicts:retry-contradiction-a:retry-contradiction-claim" in graph.edges
        assert "retry-contradiction-set:contradicts:retry-contradiction-b:retry-contradiction-claim" in graph.edges
        assert len([e for e in store.list_events("graph")
                    if e["event_type"] == "EDGE_REGISTERED"
                    and e["payload"].get("edge_id", "").startswith("retry-contradiction-set:")]) == 2


def test_inference_block_replay_recovers_after_snapshot_write_then_error(monkeypatch):
    import pytest

    with TemporaryDirectory() as d:
        store = SQLiteRuntimeStore(str(Path(d) / "runtime.sqlite3"))
        graph = build_registry(store)
        original_put_snapshot = store.put_snapshot
        failed = {"once": False}

        def persist_then_fail(namespace, key, payload, version):
            result = original_put_snapshot(namespace, key, payload, version)
            if namespace == "graph.inference" and key == "retry-inference-block" and not failed["once"]:
                failed["once"] = True
                raise OSError("simulated interruption after inference snapshot write")
            return result

        monkeypatch.setattr(store, "put_snapshot", persist_then_fail)
        with pytest.raises(OSError, match="after inference snapshot"):
            graph.register_inference_block(
                "retry-inference-block", "MODEL_OUTPUT", "EVIDENCE_SUPPORTED",
                "blocked", "MODEL", "RULE-1",
            )
        assert "retry-inference-block" not in graph.inference_blocks
        assert store.get_snapshot("graph.inference", "retry-inference-block") is not None

        recovered = graph.register_inference_block(
            "retry-inference-block", "MODEL_OUTPUT", "EVIDENCE_SUPPORTED",
            "blocked", "MODEL", "RULE-1",
        )
        assert recovered.inference_block_id in graph.inference_blocks
        assert graph.register_inference_block(
            "retry-inference-block", "MODEL_OUTPUT", "EVIDENCE_SUPPORTED",
            "blocked", "MODEL", "RULE-1",
        ) == recovered

        with pytest.raises(ValueError, match="immutable inference block conflict"):
            graph.register_inference_block(
                "retry-inference-block", "MODEL_OUTPUT", "EVIDENCE_SUPPORTED",
                "different blocked inference", "MODEL", "RULE-1",
            )



def test_graph_recovery_rejects_semantically_tampered_contradiction_even_with_rehashed_snapshot():
    import json
    import pytest
    from cte.provenance import content_hash

    with TemporaryDirectory() as d:
        path = str(Path(d) / "runtime.sqlite3")
        store = SQLiteRuntimeStore(path)
        graph = build_registry(store)
        claim = register_node("tamper-contradiction-claim", "CLAIM", "claim", "DRV", "1", {})
        evidence = register_node("tamper-contradiction-evidence", "DATASET", "evidence", "DRV", "1", {})
        graph.add_node(claim)
        graph.add_node(evidence)
        graph.register_contradiction_set(
            "tamper-contradiction", claim.node_id, [evidence.node_id], "CONFLICT",
        )

        with store._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM runtime_snapshots WHERE namespace=? AND key=?",
                ("graph.contradiction", "tamper-contradiction"),
            ).fetchone()
            payload = json.loads(row[0])
            payload["contradiction_type"] = "ALTERED"
            payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            conn.execute(
                "UPDATE runtime_snapshots SET payload_json=?, payload_hash=? WHERE namespace=? AND key=?",
                (payload_json, content_hash(payload), "graph.contradiction", "tamper-contradiction"),
            )
            conn.commit()

        with pytest.raises(ValueError, match="evidence graph contradiction integrity failure: tamper-contradiction"):
            build_registry(SQLiteRuntimeStore(path))


def test_graph_recovery_rejects_semantically_tampered_inference_even_with_rehashed_snapshot():
    import json
    import pytest
    from cte.provenance import content_hash

    with TemporaryDirectory() as d:
        path = str(Path(d) / "runtime.sqlite3")
        store = SQLiteRuntimeStore(path)
        graph = build_registry(store)
        graph.register_inference_block(
            "tamper-inference", "MODEL_OUTPUT", "EVIDENCE_SUPPORTED",
            "blocked", "MODEL", "RULE-1",
        )

        with store._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM runtime_snapshots WHERE namespace=? AND key=?",
                ("graph.inference", "tamper-inference"),
            ).fetchone()
            payload = json.loads(row[0])
            payload["reason_code"] = "ALTERED"
            payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            conn.execute(
                "UPDATE runtime_snapshots SET payload_json=?, payload_hash=? WHERE namespace=? AND key=?",
                (payload_json, content_hash(payload), "graph.inference", "tamper-inference"),
            )
            conn.commit()

        with pytest.raises(ValueError, match="evidence graph inference integrity failure: tamper-inference"):
            build_registry(SQLiteRuntimeStore(path))



def test_graph_recovery_repairs_missing_rule_audit_events():
    with TemporaryDirectory() as d:
        path = str(Path(d) / "runtime.sqlite3")
        store = SQLiteRuntimeStore(path)
        graph = build_registry(store)
        claim = register_node("audit-rule-claim", "CLAIM", "claim", "DRV", "1", {})
        evidence = register_node("audit-rule-evidence", "DATASET", "evidence", "DRV", "1", {})
        graph.add_node(claim)
        graph.add_node(evidence)
        graph.register_contradiction_set(
            "audit-rule-contradiction", claim.node_id, [evidence.node_id], "CONFLICT",
        )
        graph.register_inference_block(
            "audit-rule-inference", "MODEL_OUTPUT", "EVIDENCE_SUPPORTED",
            "blocked", "MODEL", "RULE-1",
        )

        with store._connect() as conn:
            conn.execute("DELETE FROM runtime_events WHERE event_id IN (?, ?)", (
                "graph:contradiction:audit-rule-contradiction",
                "graph:inference:audit-rule-inference",
            ))
            conn.commit()

        recovered = build_registry(SQLiteRuntimeStore(path))
        events = SQLiteRuntimeStore(path).list_events("graph")
        contradiction_events = [
            event for event in events
            if event["event_type"] == "CONTRADICTION_SET_REGISTERED"
            and event["payload"].get("contradiction_set_id") == "audit-rule-contradiction"
        ]
        inference_events = [
            event for event in events
            if event["event_type"] == "INFERENCE_BLOCK_REGISTERED"
            and event["payload"].get("inference_block_id") == "audit-rule-inference"
        ]
        assert len(contradiction_events) == 1
        assert len(inference_events) == 1
        assert any(event.contradiction_set_id == "audit-rule-contradiction"
                   for event in recovered.audit_events)
        assert any(event.inference_block_id == "audit-rule-inference"
                   for event in recovered.audit_events)
        assert any(event.claim_id == claim.node_id
                   and event.operation == "CONTRADICTION_SET_REGISTERED"
                   for event in recovered.claim_audit(claim.node_id))



def test_graph_recovery_recreates_missing_contradiction_edges_after_restart(monkeypatch):
    with TemporaryDirectory() as d:
        path = str(Path(d) / "runtime.sqlite3")
        store = SQLiteRuntimeStore(path)
        graph = build_registry(store)
        claim = register_node("recover-contradiction-claim", "CLAIM", "claim", "DRV", "1", {})
        evidence = register_node("recover-contradiction-evidence", "DATASET", "evidence", "DRV", "1", {})
        graph.add_node(claim)
        graph.add_node(evidence)

        original_add_edge = graph.add_edge

        def fail_contradiction_edge_once(edge):
            if edge.edge_type == "CONTRADICTS":
                raise OSError("simulated interruption before contradiction edge write")
            return original_add_edge(edge)

        monkeypatch.setattr(graph, "add_edge", fail_contradiction_edge_once)
        try:
            graph.register_contradiction_set(
                "recover-contradiction-set", claim.node_id, [evidence.node_id], "CONFLICT",
            )
        except OSError as exc:
            assert "contradiction edge write" in str(exc)
        else:
            raise AssertionError("contradiction edge creation should fail")

        edge_id = "recover-contradiction-set:contradicts:recover-contradiction-evidence:recover-contradiction-claim"
        assert store.get_snapshot("graph.contradiction", "recover-contradiction-set") is not None
        assert store.get_snapshot("graph.edge", edge_id) is None

        recovered = build_registry(SQLiteRuntimeStore(path))
        events = SQLiteRuntimeStore(path).list_events("graph")
        assert edge_id in recovered.edges
        assert SQLiteRuntimeStore(path).get_snapshot("graph.edge", edge_id) is not None
        assert len([event for event in events
                    if event["event_type"] == "EDGE_REGISTERED"
                    and event["payload"].get("edge_id") == edge_id]) == 1
        assert len([event for event in recovered.audit_events if event.edge_id == edge_id]) == 1



def test_graph_recovery_rejects_tampered_edge_relation_status_even_with_rehashed_snapshot():
    import json
    import pytest
    from cte.provenance import content_hash

    with TemporaryDirectory() as d:
        path = str(Path(d) / "runtime.sqlite3")
        store = SQLiteRuntimeStore(path)
        graph = build_registry(store)
        source = register_node("tamper-status-source", "ANALYSIS", "source", "DRV", "1", {})
        target = register_node("tamper-status-target", "RESULT", "target", "DRV", "1", {})
        graph.add_node(source)
        graph.add_node(target)
        graph.add_edge(register_edge("tamper-status-edge", source, target, "RESULTS_IN"))

        with store._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM runtime_snapshots WHERE namespace=? AND key=?",
                ("graph.edge", "tamper-status-edge"),
            ).fetchone()
            payload = json.loads(row[0])
            payload["relation_status"] = "RETRACTED"
            payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            conn.execute(
                "UPDATE runtime_snapshots SET payload_json=?, payload_hash=? WHERE namespace=? AND key=?",
                (payload_json, content_hash(payload), "graph.edge", "tamper-status-edge"),
            )
            conn.commit()

        with pytest.raises(ValueError, match="evidence graph edge integrity failure: tamper-status-edge"):
            build_registry(SQLiteRuntimeStore(path))



def test_graph_recovery_rejects_tampered_node_provenance_even_with_rehashed_snapshot():
    import json
    import pytest
    from cte.provenance import content_hash

    with TemporaryDirectory() as d:
        path = str(Path(d) / "runtime.sqlite3")
        store = SQLiteRuntimeStore(path)
        graph = build_registry(store)
        graph.add_node(register_node(
            "tamper-envelope-node", "DATASET", "entity", "DRV", "1", {"x": 1},
        ))

        with store._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM runtime_snapshots WHERE namespace=? AND key=?",
                ("graph.node", "tamper-envelope-node"),
            ).fetchone()
            payload = json.loads(row[0])
            payload["provenance_class"] = "OBS"
            payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            conn.execute(
                "UPDATE runtime_snapshots SET payload_json=?, payload_hash=? WHERE namespace=? AND key=?",
                (payload_json, content_hash(payload), "graph.node", "tamper-envelope-node"),
            )
            conn.commit()

        with pytest.raises(ValueError, match="evidence graph node envelope integrity failure: tamper-envelope-node"):
            build_registry(SQLiteRuntimeStore(path))


def test_graph_recovery_accepts_legacy_node_snapshot_without_envelope_hash():
    import json
    from cte.provenance import content_hash

    with TemporaryDirectory() as d:
        path = str(Path(d) / "runtime.sqlite3")
        store = SQLiteRuntimeStore(path)
        graph = build_registry(store)
        graph.add_node(register_node(
            "legacy-envelope-node", "DATASET", "entity", "DRV", "1", {"x": 1},
        ))

        with store._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM runtime_snapshots WHERE namespace=? AND key=?",
                ("graph.node", "legacy-envelope-node"),
            ).fetchone()
            payload = json.loads(row[0])
            payload.pop("envelope_hash", None)
            payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            conn.execute(
                "UPDATE runtime_snapshots SET payload_json=?, payload_hash=? WHERE namespace=? AND key=?",
                (payload_json, content_hash(payload), "graph.node", "legacy-envelope-node"),
            )
            conn.commit()

        recovered = build_registry(SQLiteRuntimeStore(path))
        assert "legacy-envelope-node" in recovered.nodes
        assert recovered.nodes["legacy-envelope-node"].envelope_hash is None



def test_add_node_rejects_forged_envelope_before_persistence():
    from dataclasses import replace
    import pytest

    with TemporaryDirectory() as d:
        store = SQLiteRuntimeStore(str(Path(d) / "runtime.sqlite3"))
        graph = build_registry(store)
        original = register_node("forged-envelope-node", "DATASET", "entity", "DRV", "1", {})
        forged = replace(original, provenance_class="OBS")

        with pytest.raises(ValueError, match="immutable node conflict"):
            graph.add_node(forged)

        assert "forged-envelope-node" not in graph.nodes
        assert store.get_snapshot("graph.node", "forged-envelope-node") is None


def test_add_edge_rejects_noncanonical_status_before_persistence():
    from dataclasses import replace
    import pytest

    with TemporaryDirectory() as d:
        store = SQLiteRuntimeStore(str(Path(d) / "runtime.sqlite3"))
        graph = build_registry(store)
        source = register_node("forged-edge-source", "ANALYSIS", "source", "DRV", "1", {})
        target = register_node("forged-edge-target", "RESULT", "target", "DRV", "1", {})
        graph.add_node(source)
        graph.add_node(target)
        original = register_edge("forged-edge", source, target, "RESULTS_IN")
        forged = replace(original, relation_status="RETRACTED")

        with pytest.raises(ValueError, match="immutable edge conflict"):
            graph.add_edge(forged)

        assert "forged-edge" not in graph.edges
        assert store.get_snapshot("graph.edge", "forged-edge") is None



def test_graph_recovery_rejects_snapshot_version_column_mismatch():
    import pytest

    with TemporaryDirectory() as d:
        path = str(Path(d) / "runtime.sqlite3")
        store = SQLiteRuntimeStore(path)
        graph = build_registry(store)
        graph.add_node(register_node("envelope-version-node", "DATASET", "entity", "DRV", "1", {}))

        with store._connect() as conn:
            conn.execute(
                "UPDATE runtime_snapshots SET version=? WHERE namespace=? AND key=?",
                ("2", "graph.node", "envelope-version-node"),
            )
            conn.commit()

        with pytest.raises(ValueError, match="evidence graph node snapshot envelope failure: envelope-version-node"):
            build_registry(SQLiteRuntimeStore(path))


def test_graph_recovery_rejects_snapshot_storage_hash_mismatch():
    import pytest

    with TemporaryDirectory() as d:
        path = str(Path(d) / "runtime.sqlite3")
        store = SQLiteRuntimeStore(path)
        graph = build_registry(store)
        graph.add_node(register_node("storage-hash-node", "DATASET", "entity", "DRV", "1", {}))

        with store._connect() as conn:
            conn.execute(
                "UPDATE runtime_snapshots SET payload_hash=? WHERE namespace=? AND key=?",
                ("incorrect-storage-hash", "graph.node", "storage-hash-node"),
            )
            conn.commit()

        with pytest.raises(ValueError, match="evidence graph node storage hash failure: storage-hash-node"):
            build_registry(SQLiteRuntimeStore(path))



def test_graph_recovery_rejects_tampered_contradiction_envelope_metadata():
    import json
    import pytest
    from cte.provenance import content_hash

    with TemporaryDirectory() as d:
        path = str(Path(d) / "runtime.sqlite3")
        store = SQLiteRuntimeStore(path)
        graph = build_registry(store)
        claim = register_node("envelope-contradiction-claim", "CLAIM", "claim", "DRV", "1", {})
        evidence = register_node("envelope-contradiction-evidence", "DATASET", "evidence", "DRV", "1", {})
        graph.add_node(claim)
        graph.add_node(evidence)
        graph.register_contradiction_set(
            "envelope-contradiction", claim.node_id, [evidence.node_id], "CONFLICT",
        )

        with store._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM runtime_snapshots WHERE namespace=? AND key=?",
                ("graph.contradiction", "envelope-contradiction"),
            ).fetchone()
            payload = json.loads(row[0])
            payload["version"] = "9"
            payload["provenance_class"] = "OBS"
            payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            conn.execute(
                "UPDATE runtime_snapshots SET version=?, payload_json=?, payload_hash=? WHERE namespace=? AND key=?",
                ("9", payload_json, content_hash(payload), "graph.contradiction", "envelope-contradiction"),
            )
            conn.commit()

        with pytest.raises(ValueError, match="evidence graph contradiction snapshot envelope failure: envelope-contradiction"):
            build_registry(SQLiteRuntimeStore(path))


def test_claim_registration_retry_preserves_in_memory_claim_after_edge_failure(monkeypatch):
    with TemporaryDirectory() as d:
        store = SQLiteRuntimeStore(str(Path(d) / "runtime.sqlite3"))
        graph = build_registry(store)
        dataset = register_node("claim-retry-dataset", "DATASET", "dataset", "DRV", "1", {})
        analysis = register_node("claim-retry-analysis", "ANALYSIS", "analysis", "DRV", "1", {})
        result = register_node(
            "claim-retry-result", "RESULT", "result", "DRV", "1",
            {"qc_status": "PASS", "validated_descriptive_result": True},
        )
        for node in (dataset, analysis, result):
            graph.add_node(node)
        graph.add_edge(register_edge("claim-retry-analyzed-from", analysis, dataset, "ANALYZED_FROM"))
        graph.add_edge(register_edge("claim-retry-results-in", analysis, result, "RESULTS_IN"))

        original_add_edge = graph.add_edge
        failed = {"once": False}

        def fail_first_edge(edge):
            if not failed["once"]:
                failed["once"] = True
                raise OSError("simulated derived-edge failure")
            return original_add_edge(edge)

        monkeypatch.setattr(graph, "add_edge", fail_first_edge)
        try:
            graph.register_claim(
                "claim-retry-claim", "claim-retry-result",
                "REGISTERED", "DESCRIPTIVE_RESULT", "DRV", {},
            )
        except OSError:
            pass
        else:
            raise AssertionError("first derived-edge write should fail")

        # The claim snapshot/event may already be durable. Keep the in-memory
        # node so an immediate retry can repair its missing derived edge.
        assert "claim-retry-claim" in graph.nodes
        assert store.get_snapshot("graph.node", "claim-retry-claim") is not None

        claim = graph.register_claim(
            "claim-retry-claim", "claim-retry-result",
            "REGISTERED", "DESCRIPTIVE_RESULT", "DRV", {},
        )
        assert claim.node_id == "claim-retry-claim"
        assert "claim-retry-claim:supports:claim-retry-result" in graph.edges
        assert store.get_snapshot(
            "graph.edge", "claim-retry-claim:supports:claim-retry-result"
        ) is not None


def test_graph_recovery_repairs_missing_contradiction_audit_event_after_restart(monkeypatch):
    import pytest

    with TemporaryDirectory() as d:
        path = str(Path(d) / "runtime.sqlite3")
        store = SQLiteRuntimeStore(path)
        graph = build_registry(store)
        claim = register_node("restart-rule-claim", "CLAIM", "claim", "DRV", "1", {})
        evidence = register_node("restart-rule-evidence", "DATASET", "evidence", "DRV", "1", {})
        graph.add_node(claim)
        graph.add_node(evidence)
        original = store.append_event

        def fail_rule_event(event_id, namespace, event_type, payload, *args, **kwargs):
            if event_type == "CONTRADICTION_SET_REGISTERED":
                raise OSError("simulated contradiction audit failure")
            return original(event_id, namespace, event_type, payload, *args, **kwargs)

        monkeypatch.setattr(store, "append_event", fail_rule_event)
        with pytest.raises(OSError, match="contradiction audit failure"):
            graph.register_contradiction_set(
                "restart-rule-set", claim.node_id, [evidence.node_id], "CONFLICT",
            )

        assert store.get_snapshot("graph.contradiction", "restart-rule-set") is not None
        assert not any(
            event["event_type"] == "CONTRADICTION_SET_REGISTERED"
            for event in store.list_events("graph")
        )

        recovered_store = SQLiteRuntimeStore(path)
        recovered = build_registry(recovered_store)
        events = recovered_store.list_events("graph")
        assert "restart-rule-set" in recovered.contradiction_sets
        assert len([
            event for event in events
            if event["event_type"] == "CONTRADICTION_SET_REGISTERED"
            and event["payload"].get("contradiction_set_id") == "restart-rule-set"
        ]) == 1
        assert len([
            event for event in recovered.audit_events
            if event.contradiction_set_id == "restart-rule-set"
        ]) == 1


def test_graph_recovery_repairs_missing_inference_audit_event_after_restart(monkeypatch):
    import pytest

    with TemporaryDirectory() as d:
        path = str(Path(d) / "runtime.sqlite3")
        store = SQLiteRuntimeStore(path)
        graph = build_registry(store)
        original = store.append_event

        def fail_rule_event(event_id, namespace, event_type, payload, *args, **kwargs):
            if event_type == "INFERENCE_BLOCK_REGISTERED":
                raise OSError("simulated inference audit failure")
            return original(event_id, namespace, event_type, payload, *args, **kwargs)

        monkeypatch.setattr(store, "append_event", fail_rule_event)
        with pytest.raises(OSError, match="inference audit failure"):
            graph.register_inference_block(
                "restart-inference-block", "MODEL_OUTPUT", "EVIDENCE_SUPPORTED",
                "block inference", "MODEL", "RULE-1",
            )

        assert store.get_snapshot("graph.inference", "restart-inference-block") is not None
        assert not any(
            event["event_type"] == "INFERENCE_BLOCK_REGISTERED"
            for event in store.list_events("graph")
        )

        recovered_store = SQLiteRuntimeStore(path)
        recovered = build_registry(recovered_store)
        events = recovered_store.list_events("graph")
        assert "restart-inference-block" in recovered.inference_blocks
        assert len([
            event for event in events
            if event["event_type"] == "INFERENCE_BLOCK_REGISTERED"
            and event["payload"].get("inference_block_id") == "restart-inference-block"
        ]) == 1
        assert len([
            event for event in recovered.audit_events
            if event.inference_block_id == "restart-inference-block"
        ]) == 1


def test_graph_recovery_rejects_orphaned_audit_event():
    import pytest

    with TemporaryDirectory() as d:
        path = str(Path(d) / "runtime.sqlite3")
        store = SQLiteRuntimeStore(path)
        store.append_event(
            "graph:node:missing-node", "graph", "NODE_REGISTERED",
            {"node_id": "missing-node", "payload_hash": "not-backed-by-a-snapshot", "claim_id": None},
            provenance_record_id="1",
        )

        with pytest.raises(ValueError, match="orphan graph audit event: graph:node:missing-node"):
            build_registry(SQLiteRuntimeStore(path))


def test_graph_recovery_rejects_audit_event_type_mismatch():
    import pytest

    with TemporaryDirectory() as d:
        path = str(Path(d) / "runtime.sqlite3")
        store = SQLiteRuntimeStore(path)
        graph = build_registry(store)
        graph.add_node(register_node("event-type-node", "DATASET", "entity", "DRV", "1", {}))

        with store._connect() as conn:
            conn.execute(
                "UPDATE runtime_events SET event_type=? WHERE event_id=?",
                ("EDGE_REGISTERED", "graph:node:event-type-node"),
            )
            conn.commit()

        with pytest.raises(ValueError, match="graph audit event type mismatch: graph:node:event-type-node"):
            build_registry(SQLiteRuntimeStore(path))


def test_contradiction_requirements_reject_missing_evidence_after_recovery():
    import pytest

    with TemporaryDirectory() as d:
        path = str(Path(d) / "runtime.sqlite3")
        store = SQLiteRuntimeStore(path)
        graph = build_registry(store)
        claim = register_node(
            "missing-evidence-claim", "CLAIM", "claim", "DRV", "1",
            {"state": "HYPOTHESIS"},
        )
        evidence = register_node(
            "missing-evidence-dataset", "DATASET", "dataset", "DRV", "1", {},
        )
        graph.add_node(claim)
        graph.add_node(evidence)
        graph.register_contradiction_set(
            "missing-evidence-set", claim.node_id, [evidence.node_id], "CONFLICT",
        )

        # Simulate loss of the evidence snapshot without leaving an orphan
        # node event, so this test isolates the contradiction gate invariant.
        with store._connect() as conn:
            conn.execute(
                "DELETE FROM runtime_snapshots WHERE namespace=? AND key=?",
                ("graph.node", evidence.node_id),
            )
            conn.execute(
                "DELETE FROM runtime_events WHERE event_id=?",
                (f"graph:node:{evidence.node_id}",),
            )
            conn.commit()

        recovered = build_registry(SQLiteRuntimeStore(path))
        assert any(
            error == f"contradiction set references missing node: missing-evidence-set:{evidence.node_id}"
            for error in recovered.integrity_errors
        )
        with pytest.raises(
            ValueError,
            match=f"contradiction set references missing node: missing-evidence-set:{evidence.node_id}",
        ):
            recovered.contradiction_requirements({claim.node_id})
        with pytest.raises(
            ValueError,
            match=f"contradiction set references missing node: missing-evidence-set:{evidence.node_id}",
        ):
            recovered.indeterminate_requirements({claim.node_id}, None)


def test_graph_recovery_validates_audit_stream_before_repairing_derived_edges():
    import pytest

    with TemporaryDirectory() as d:
        path = str(Path(d) / "runtime.sqlite3")
        store = SQLiteRuntimeStore(path)
        graph = build_registry(store)
        claim = register_node("validate-first-claim", "CLAIM", "claim", "DRV", "1", {})
        evidence = register_node("validate-first-evidence", "DATASET", "evidence", "DRV", "1", {})
        graph.add_node(claim)
        graph.add_node(evidence)
        graph.register_contradiction_set(
            "validate-first-set", claim.node_id, [evidence.node_id], "CONFLICT"
        )
        derived_edge_id = f"validate-first-set:contradicts:{evidence.node_id}:{claim.node_id}"

        # Simulate a crash after the contradiction snapshot/event persisted but
        # before its derived edge snapshot was durable, then corrupt the event
        # stream independently. Recovery must reject the stream before writing
        # the derived edge back into the database.
        with store._connect() as conn:
            conn.execute(
                "DELETE FROM runtime_snapshots WHERE namespace=? AND key=?",
                ("graph.edge", derived_edge_id),
            )
            conn.commit()
        store.append_event(
            "graph:node:unrecognized-orphan",
            "graph",
            "NODE_REGISTERED",
            {"node_id": "unrecognized-orphan", "payload_hash": "invalid", "claim_id": None},
        )

        with pytest.raises(ValueError, match="orphan graph audit event: graph:node:unrecognized-orphan"):
            build_registry(SQLiteRuntimeStore(path))

        assert SQLiteRuntimeStore(path).get_snapshot("graph.edge", derived_edge_id) is None


def test_graph_recovery_rejects_tampered_audit_payload_before_edge_repair():
    import json
    import pytest

    with TemporaryDirectory() as d:
        path = str(Path(d) / "runtime.sqlite3")
        store = SQLiteRuntimeStore(path)
        graph = build_registry(store)
        claim = register_node("audit-payload-claim", "CLAIM", "claim", "DRV", "1", {})
        evidence = register_node("audit-payload-evidence", "DATASET", "evidence", "DRV", "1", {})
        graph.add_node(claim)
        graph.add_node(evidence)
        graph.register_contradiction_set(
            "audit-payload-set", claim.node_id, [evidence.node_id], "CONFLICT"
        )
        derived_edge_id = f"audit-payload-set:contradicts:{evidence.node_id}:{claim.node_id}"
        event_id = f"graph:edge:{derived_edge_id}"

        with store._connect() as conn:
            conn.execute(
                "DELETE FROM runtime_snapshots WHERE namespace=? AND key=?",
                ("graph.edge", derived_edge_id),
            )
            row = conn.execute(
                "SELECT payload_json FROM runtime_events WHERE event_id=?", (event_id,)
            ).fetchone()
            payload = json.loads(row[0])
            payload["payload_hash"] = "tampered"
            conn.execute(
                "UPDATE runtime_events SET payload_json=? WHERE event_id=?",
                (json.dumps(payload, sort_keys=True, separators=(",", ":")), event_id),
            )
            conn.commit()

        with pytest.raises(ValueError, match=f"graph audit event content mismatch: {event_id}"):
            build_registry(SQLiteRuntimeStore(path))

        assert SQLiteRuntimeStore(path).get_snapshot("graph.edge", derived_edge_id) is None


def test_inference_block_rejects_invalid_rule_definitions():
    import pytest

    invalid_cases = [
        ("inference_block_id", "", "inference_block_id must be a non-empty string"),
        ("from_node_type", "   ", "from_node_type must be a non-empty string"),
        ("to_claim_level", "NOT_A_CLAIM_LEVEL", "unsupported inference block claim level"),
        ("blocked_inference", "", "blocked_inference must be a non-empty string"),
        ("reason_code", None, "reason_code must be a non-empty string"),
        ("rule_id", " ", "rule_id must be a non-empty string"),
    ]
    for field_name, invalid_value, message in invalid_cases:
        graph = build_registry()
        values = {
            "inference_block_id": "invalid-inference-rule",
            "from_node_type": "MODEL_OUTPUT",
            "to_claim_level": "EVIDENCE_SUPPORTED",
            "blocked_inference": "Do not infer evidence support from model output",
            "reason_code": "MODEL_ONLY",
            "rule_id": "RULE-1",
        }
        values[field_name] = invalid_value
        with pytest.raises(ValueError, match=message):
            graph.register_inference_block(**values)
        assert "invalid-inference-rule" not in graph.inference_blocks


def test_contradiction_set_rejects_malformed_inputs():
    import pytest

    invalid_cases = [
        ("contradiction_set_id", "", "contradiction_set_id must be a non-empty string"),
        ("claim_id", None, "claim_id must be a non-empty string"),
        ("contradiction_type", " ", "contradiction_type must be a non-empty string"),
        ("node_ids", [], "contradiction set requires at least one node"),
        ("node_ids", "evidence", "contradiction set requires at least one node"),
        ("node_ids", ["evidence", "evidence"], "contradiction set node IDs must be unique"),
        ("node_ids", [None], "contradiction set node IDs must be non-empty strings"),
        ("resolution_status", "UNKNOWN", "unsupported contradiction resolution status"),
        ("resolution_note", 42, "contradiction resolution note must be a string"),
    ]
    for field_name, invalid_value, message in invalid_cases:
        graph = build_registry()
        values = {
            "contradiction_set_id": "invalid-contradiction-set",
            "claim_id": "claim",
            "node_ids": ["evidence"],
            "contradiction_type": "CONFLICT",
        }
        values[field_name] = invalid_value
        with pytest.raises(ValueError, match=message):
            graph.register_contradiction_set(**values)
        assert "invalid-contradiction-set" not in graph.contradiction_sets



def test_graph_recovery_rejects_semantically_invalid_contradiction_snapshot_with_rehashed_envelopes():
    import json
    import pytest
    from cte.provenance import content_hash

    with TemporaryDirectory() as d:
        path = str(Path(d) / "runtime.sqlite3")
        store = SQLiteRuntimeStore(path)
        graph = build_registry(store)
        claim = register_node("recovery-rule-claim", "CLAIM", "claim", "DRV", "1", {})
        evidence = register_node("recovery-rule-evidence", "DATASET", "evidence", "DRV", "1", {})
        graph.add_node(claim)
        graph.add_node(evidence)
        graph.register_contradiction_set(
            "recovery-invalid-contradiction", claim.node_id, [evidence.node_id], "CONFLICT"
        )

        with store._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM runtime_snapshots WHERE namespace=? AND key=?",
                ("graph.contradiction", "recovery-invalid-contradiction"),
            ).fetchone()
            payload = json.loads(row[0])
            payload["resolution_status"] = ["UNKNOWN"]
            canonical_payload = {
                "contradiction_set_id": payload["contradiction_set_id"],
                "claim_id": payload["claim_id"],
                "node_ids": payload["node_ids"],
                "contradiction_type": payload["contradiction_type"],
                "resolution_status": payload["resolution_status"],
                "resolution_note": payload["resolution_note"],
            }
            payload["immutable_hash"] = content_hash(canonical_payload)
            payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            conn.execute(
                "UPDATE runtime_snapshots SET payload_json=?, payload_hash=? WHERE namespace=? AND key=?",
                (payload_json, content_hash(payload), "graph.contradiction", "recovery-invalid-contradiction"),
            )
            conn.commit()

        with pytest.raises(
            ValueError,
            match="evidence graph contradiction status invalid: recovery-invalid-contradiction",
        ):
            build_registry(SQLiteRuntimeStore(path))


def test_graph_recovery_rejects_semantically_invalid_inference_snapshot_with_rehashed_envelopes():
    import json
    import pytest
    from cte.provenance import content_hash

    with TemporaryDirectory() as d:
        path = str(Path(d) / "runtime.sqlite3")
        store = SQLiteRuntimeStore(path)
        graph = build_registry(store)
        graph.register_inference_block(
            "recovery-invalid-inference", "MODEL_OUTPUT", "EVIDENCE_SUPPORTED",
            "Do not infer evidence support from model output", "MODEL_ONLY", "RULE-1"
        )

        with store._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM runtime_snapshots WHERE namespace=? AND key=?",
                ("graph.inference", "recovery-invalid-inference"),
            ).fetchone()
            payload = json.loads(row[0])
            payload["to_claim_level"] = "NOT_A_CLAIM_LEVEL"
            canonical_payload = {
                "inference_block_id": payload["inference_block_id"],
                "from_node_type": payload["from_node_type"],
                "to_claim_level": payload["to_claim_level"],
                "blocked_inference": payload["blocked_inference"],
                "reason_code": payload["reason_code"],
                "rule_id": payload["rule_id"],
            }
            payload["immutable_hash"] = content_hash(canonical_payload)
            payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            conn.execute(
                "UPDATE runtime_snapshots SET payload_json=?, payload_hash=? WHERE namespace=? AND key=?",
                (payload_json, content_hash(payload), "graph.inference", "recovery-invalid-inference"),
            )
            conn.commit()

        with pytest.raises(
            ValueError,
            match="evidence graph inference claim level invalid: recovery-invalid-inference",
        ):
            build_registry(SQLiteRuntimeStore(path))



def test_concurrent_node_registration_keeps_one_audit_entry():
    from concurrent.futures import ThreadPoolExecutor

    with TemporaryDirectory() as d:
        store = SQLiteRuntimeStore(str(Path(d) / "runtime.sqlite3"))
        graph = build_registry(store)
        node = register_node("concurrent-node", "DATASET", "entity", "DRV", "1", {"k": [1, 2]})

        with ThreadPoolExecutor(max_workers=8) as pool:
            registered = list(pool.map(lambda _: graph.add_node(node), range(24)))

        assert all(item.node_id == "concurrent-node" for item in registered)
        assert len([event for event in store.list_events("graph")
                    if event["event_type"] == "NODE_REGISTERED"]) == 1
        assert len([event for event in graph.audit_events
                    if event.node_id == "concurrent-node"]) == 1


def test_graph_node_metadata_matches_json_shape_after_restart():
    with TemporaryDirectory() as d:
        path = str(Path(d) / "runtime.sqlite3")
        store = SQLiteRuntimeStore(path)
        graph = build_registry(store)
        node = register_node(
            "json-normalized-metadata", "DATASET", "entity", "DRV", "1",
            {1: {"values": (1, 2)}},
        )

        graph.add_node(node)
        expected = {"1": {"values": [1, 2]}}
        assert graph.nodes["json-normalized-metadata"].metadata == expected
        snapshot = store.get_snapshot("graph.node", "json-normalized-metadata")
        assert snapshot is not None
        assert snapshot.payload["metadata"] == expected

        restored = build_registry(SQLiteRuntimeStore(path))
        assert restored.nodes["json-normalized-metadata"].metadata == expected


def test_graph_node_metadata_is_detached_from_caller_after_registration():
    import pytest

    with TemporaryDirectory() as d:
        path = str(Path(d) / "runtime.sqlite3")
        store = SQLiteRuntimeStore(path)
        graph = build_registry(store)
        metadata = {"nested": {"values": [1, 2]}}
        node = register_node("detached-metadata", "DATASET", "entity", "DRV", "1", metadata)

        graph.add_node(node)
        metadata["nested"]["values"].append(3)

        # Registered node metadata is deeply immutable, including nested lists,
        # whether accessed through the original node or the registry.
        with pytest.raises(TypeError, match="registered graph metadata is immutable"):
            node.metadata["nested"]["values"].append(4)
        with pytest.raises(TypeError, match="registered graph metadata is immutable"):
            graph.nodes["detached-metadata"].metadata["nested"]["values"].append(5)
        with pytest.raises(TypeError, match="registered graph metadata is immutable"):
            graph.nodes["detached-metadata"].metadata["new"] = "tamper"

        expected = {"nested": {"values": [1, 2]}}
        assert graph.nodes["detached-metadata"].metadata == expected
        snapshot = store.get_snapshot("graph.node", "detached-metadata")
        assert snapshot is not None
        assert snapshot.payload["metadata"] == expected

        restored = build_registry(SQLiteRuntimeStore(path))
        assert restored.nodes["detached-metadata"].metadata == expected
        with pytest.raises(TypeError, match="registered graph metadata is immutable"):
            restored.nodes["detached-metadata"].metadata["nested"]["values"].append(6)
