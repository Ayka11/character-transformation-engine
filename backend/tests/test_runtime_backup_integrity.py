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


def test_adversarial_lineage_damage_blocks_transformation_backed_claim():
    from cte.contracts.transformation import TransformationContract
    from cte.evidence_graph import register_edge, register_node
    from cte.graph_registry import GraphRegistry
    from cte.science_lab import ExperimentMatrix, ScenarioDefinition, ScenarioRun, ScienceLabService
    from cte.provenance import Provenance, ProvenanceTag
    from cte.state_snapshot_store import StateSnapshotStore
    from cte.transformation_ledger import TransformationLedger
    from cte.transformation_provenance import TransformationProvenanceBinder
    from cte.transformation_runtime import TransformationExecutor

    db = SQLiteRuntimeStore(":memory:")
    registry = GraphRegistry.empty(db)
    execution = TransformationExecutor(
        StateSnapshotStore(db), TransformationLedger(db)
    ).execute(
        "attack-exec", "attack-character", 1, {"tempo": 5},
        TransformationContract("attack-contract", "1", expected_changes={"tempo": 6}),
        lambda state: {"tempo": 6},
    )
    assert execution.result.status == "VALIDATED"
    tp = TransformationProvenanceBinder(db).bind_execution("attack-exec")

    matrix = ExperimentMatrix("attack-matrix", "attack-study", "Attack", "outcome", {}, ("attack-scenario",), "ACTIVE", "matrix")
    scenario = ScenarioDefinition("attack-scenario", "attack-matrix", "Scenario", "Attack", {}, ("outcome",), True, "scenario")
    service = object.__new__(ScienceLabService)
    service.store = db
    service.registry = registry
    service.research = None
    service.coordinator = None
    service.transformation_provenance = TransformationProvenanceBinder(db)
    service.matrices = {"attack-matrix": matrix}
    service.scenarios = {"attack-scenario": scenario}
    service.runs = {
        "attack-run": ScenarioRun(
            "attack-run", "attack-matrix", "attack-scenario", "attack-exec",
            "COMPLETED", ("attack-result",), {"outcome": 6.0}, "PASS", "output",
            Provenance(ProvenanceTag.EXP, "attack", "1", "input", "test"), tp,
        )
    }
    service.replication_assessments = {}
    service.generalization_assessments = {}

    registry.add_node(register_node(
        "attack-dataset", "DATASET", "attack-dataset", "EXP", "1", {"kind": "DATASET"},
    ))
    registry.add_node(register_node(
        "attack-analysis", "ANALYSIS", "attack-analysis", "EXP", "1", {"kind": "ANALYSIS"},
    ))
    registry.add_node(register_node(
        "attack-result", "RESULT", "attack-result", "EXP", "1",
        {"qc_status": "PASS", "validated_descriptive_result": True},
    ))
    registry.add_node(register_node(
        "attack-transform", "TRANSFORMATION", "attack-exec", "EXP", "1",
        {"execution_id": "attack-exec", "ledger_id": tp["ledger_id"], "certificate_id": tp["certificate_id"]},
    ))
    registry.add_edge(register_edge(
        "attack-analysis:dataset", registry.nodes["attack-analysis"],
        registry.nodes["attack-dataset"], "ANALYZED_FROM",
    ))
    registry.add_edge(register_edge(
        "attack-result:analysis", registry.nodes["attack-analysis"],
        registry.nodes["attack-result"], "RESULTS_IN",
    ))
    registry.add_node(register_node(
        "attack-run-node", "ANALYSIS", "attack-run", "EXP", "1",
        {"execution_id": "attack-exec"},
    ))
    registry.add_edge(register_edge(
        "attack-run:transform", registry.nodes["attack-run-node"],
        registry.nodes["attack-transform"], "DERIVED_FROM",
    ))
    registry.add_edge(register_edge(
        "attack-run:result", registry.nodes["attack-run-node"],
        registry.nodes["attack-result"], "DERIVED_FROM",
    ))
    registry.register_claim(
        "attack-claim", "attack-result", "HYPOTHESIS", "REGISTERED", "EXP",
        {"execution_id": "attack-exec"},
    )

    def support():
        return service.claim_validation("attack-matrix")["claims"][0]["transformation_support"]

    assert support()["status"] == "VALIDATED"

    # Attack 1: remove the transformation graph node.
    registry.nodes.pop("attack-transform")
    assert support()["status"] == "VALIDATED"
    # Graph lineage is damaged, but the durable transformation source is still valid.
    # Claim validation must therefore remain provenance-valid while graph-specific
    # validation is separately inspectable.
    assert "attack-transform" not in {n.node_id for n in registry.claim_subgraph("attack-claim")[0]}

    # Attack 2: destroy the durable ledger. This must invalidate transformation support.
    ledger_id = tp["ledger_id"]
    with db._connect() as conn:\n        conn.execute("DELETE FROM runtime_snapshots WHERE namespace=? AND key=?", ("transformation.ledger", ledger_id))\n        conn.commit()
    damaged = support()
    assert damaged["status"] == "NOT_VALIDATED"
    assert damaged["integrity_status"] != "PASS"
    assert "TRANSFORMATION_LEDGER_ENTRY_MISSING" in damaged["issues"]

    # Attack 3: a forged graph node cannot restore trusted validation.
    registry.nodes["attack-transform"] = register_node(
        "attack-transform", "TRANSFORMATION", "attack-exec", "EXP", "1",
        {"execution_id": "attack-exec", "validated": True,
         "ledger_id": "forged-ledger", "certificate_id": "forged-certificate"},
    )
    forged = support()
    assert forged["status"] == "NOT_VALIDATED"
    assert forged["ledger_id"] is None or forged["ledger_id"] != "forged-ledger"
