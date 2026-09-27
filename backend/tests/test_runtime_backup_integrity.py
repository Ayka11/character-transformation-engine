import copy

import pytest

from cte.persistence import SQLiteRuntimeStore
from cte.runtime_backup import build_backup, restore_backup, validate_backup


def test_backup_manifest_rejects_tampered_snapshot_payload():
    store = SQLiteRuntimeStore(":memory:")
    store.put_snapshot("backup.integrity", "snapshot-1", {"value": 1}, "1.0")
    backup = build_backup(store)

    tampered = copy.deepcopy(backup)
    tampered["snapshots"][0]["payload"]["value"] = 999
    with pytest.raises(ValueError, match="manifest hash mismatch"):
        validate_backup(tampered)


def test_backup_manifest_rejects_tampered_event_payload():
    store = SQLiteRuntimeStore(":memory:")
    store.append_event(
        "backup-event-1",
        "backup.integrity",
        "CHECK",
        {"value": 1},
    )
    backup = build_backup(store)

    tampered = copy.deepcopy(backup)
    tampered["events"][0]["payload"]["value"] = 999
    with pytest.raises(ValueError, match="manifest hash mismatch"):
        validate_backup(tampered)


def test_restore_preflight_rejects_immutable_snapshot_conflict():
    source = SQLiteRuntimeStore(":memory:")
    source.put_snapshot("backup.integrity", "snapshot-1", {"value": 1}, "1.0")
    backup = build_backup(source)

    target = SQLiteRuntimeStore(":memory:")
    target.put_snapshot("backup.integrity", "snapshot-1", {"value": 2}, "1.0")
    with pytest.raises(ValueError, match="restore preflight conflict"):
        restore_backup(target, backup)


def test_restore_preflight_rejects_event_conflict():
    source = SQLiteRuntimeStore(":memory:")
    source.append_event("backup-event-2", "backup.integrity", "CHECK", {"value": 1})
    backup = build_backup(source)

    target = SQLiteRuntimeStore(":memory:")
    target.append_event("backup-event-2", "backup.integrity", "CHECK", {"value": 2})
    with pytest.raises(ValueError, match="restore preflight conflict"):
        restore_backup(target, backup)


def test_evidence_graph_claim_lineage_survives_backup_restore():
    from cte.contracts.transformation import TransformationContract
    from cte.evidence_graph import register_edge, register_node
    from cte.graph_registry import GraphRegistry
    from cte.state_snapshot_store import StateSnapshotStore
    from cte.transformation_ledger import TransformationLedger
    from cte.transformation_provenance import TransformationProvenanceBinder
    from cte.transformation_runtime import TransformationExecutor

    source = SQLiteRuntimeStore(":memory:")
    registry = GraphRegistry.empty(source)
    execution = TransformationExecutor(
        StateSnapshotStore(source), TransformationLedger(source)
    ).execute(
        "graph-durable", "graph-character", 1, {"tempo": 5},
        TransformationContract("graph-contract", "1", expected_changes={"tempo": 6}),
        lambda state: {"tempo": 6},
    )
    tp = TransformationProvenanceBinder(source).bind_execution("graph-durable")

    registry.add_node(register_node(
        "graph-dataset", "DATASET", "graph-dataset", "EXP", "1",
        {"kind": "DATASET"},
    ))
    registry.add_node(register_node(
        "graph-analysis", "ANALYSIS", "graph-analysis", "EXP", "1",
        {"kind": "ANALYSIS"},
    ))
    registry.add_node(register_node(
        "graph-result", "RESULT", "graph-result", "EXP", "1",
        {"qc_status": "PASS", "validated_descriptive_result": True},
    ))
    registry.add_node(register_node(
        "graph-transformation", "TRANSFORMATION", "graph-durable", "EXP", "1",
        {"execution_id": "graph-durable", "validated": True,
         "ledger_id": tp["ledger_id"], "certificate_id": tp["certificate_id"]},
    ))
    registry.add_edge(register_edge(
        "graph-analysis:dataset", registry.nodes["graph-analysis"],
        registry.nodes["graph-dataset"], "ANALYZED_FROM", rationale="dataset lineage",
    ))
    registry.add_edge(register_edge(
        "graph-result:analysis", registry.nodes["graph-analysis"],
        registry.nodes["graph-result"], "RESULTS_IN", rationale="result lineage",
    ))
    registry.add_node(register_node(
        "graph-run", "ANALYSIS", "graph-run", "EXP", "1",
        {"execution_id": "graph-durable"},
    ))
    registry.add_edge(register_edge(
        "graph-run:transformation", registry.nodes["graph-run"],
        registry.nodes["graph-transformation"], "DERIVED_FROM",
        rationale="transformation provenance",
    ))
    registry.add_edge(register_edge(
        "graph-run:result", registry.nodes["graph-run"],
        registry.nodes["graph-result"], "DERIVED_FROM",
        rationale="run result lineage",
    ))
    registry.register_claim(
        "graph-claim", "graph-result", "HYPOTHESIS", "REGISTERED",
        "EXP", {"execution_id": "graph-durable"},
    )

    before_nodes, before_edges = registry.claim_subgraph("graph-claim")
    before_audit = registry.claim_audit("graph-claim")
    before_ids = {n.node_id for n in before_nodes}
    before_edge_ids = {e.edge_id for e in before_edges}
    before_audit_fingerprint = [
        (e.operation, e.node_id, e.edge_id, e.claim_id, e.payload_hash)
        for e in before_audit
    ]

    assert {"graph-claim", "graph-result", "graph-analysis",
            "graph-dataset", "graph-run", "graph-transformation"} <= before_ids
    assert "graph-result:analysis" in before_edge_ids
    assert "graph-run:transformation" in before_edge_ids
    assert "graph-claim:supports:graph-result" in before_edge_ids

    backup = build_backup(source)
    validate_backup(backup)

    target = SQLiteRuntimeStore(":memory:")
    restore_backup(target, backup)
    restored = GraphRegistry.empty(target)

    after_nodes, after_edges = restored.claim_subgraph("graph-claim")
    after_audit = restored.claim_audit("graph-claim")
    after_ids = {n.node_id for n in after_nodes}
    after_edge_ids = {e.edge_id for e in after_edges}
    after_audit_fingerprint = [
        (e.operation, e.node_id, e.edge_id, e.claim_id, e.payload_hash)
        for e in after_audit
    ]

    assert after_ids == before_ids
    assert after_edge_ids == before_edge_ids
    assert after_audit_fingerprint == before_audit_fingerprint

    restored_claim = restored.nodes["graph-claim"]
    assert restored_claim.metadata["state"] == "REGISTERED"
    assert restored_claim.metadata["result_id"] == "graph-result"
    assert restored.nodes["graph-transformation"].metadata["ledger_id"] == tp["ledger_id"]
    assert restored.nodes["graph-transformation"].metadata["certificate_id"] == tp["certificate_id"]

    trusted = TransformationProvenanceBinder(target).bind_execution("graph-durable")
    assert execution.result.status == "VALIDATED"
    assert trusted["validated"] is True
    assert trusted["integrity_status"] == "PASS"
    assert trusted["ledger_id"] == tp["ledger_id"]
