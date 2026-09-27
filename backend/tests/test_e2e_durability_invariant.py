from cte.contracts.transformation import TransformationContract
from cte.graph_registry import GraphRegistry
from cte.persistence import SQLiteRuntimeStore
from cte.provenance import Provenance, ProvenanceTag
from cte.runtime_backup import build_backup, restore_backup, validate_backup
from cte.science_lab import ExperimentMatrix, ScenarioDefinition, ScenarioRun, ScienceLabService
from cte.state_snapshot_store import StateSnapshotStore
from cte.transformation_ledger import TransformationLedger
from cte.transformation_provenance import TransformationProvenanceBinder
from cte.transformation_runtime import TransformationExecutor
from cte.evidence_graph import register_edge, register_node


def _service(store, registry):
    service = object.__new__(ScienceLabService)
    service.registry = registry
    service.store = store
    service.research = None
    service.coordinator = None
    service.transformation_provenance = TransformationProvenanceBinder(store)
    service.matrices = {}
    service.scenarios = {}
    service.runs = {}
    service.replication_assessments = {}
    service.generalization_assessments = {}
    service._hydrate()
    return service


def test_transformation_science_lab_claim_report_survive_backup_restore():
    source = SQLiteRuntimeStore(":memory:")
    registry = GraphRegistry.empty(source)
    executor = TransformationExecutor(
        StateSnapshotStore(source), TransformationLedger(source)
    )
    execution = executor.execute(
        "e2e-durable-1",
        "character-e2e-1",
        1,
        {"tempo": 5},
        TransformationContract(
            "protocol-e2e",
            "1",
            expected_changes={"tempo": 6},
        ),
        lambda state: {"tempo": 6},
    )
    tp = TransformationProvenanceBinder(source).bind_execution("e2e-durable-1")
    assert execution.result.status == "VALIDATED"
    assert tp["validated"] is True
    assert tp["integrity_status"] == "PASS"

    matrix = ExperimentMatrix(
        "e2e-matrix", "study-e2e", "Durability", "outcome",
        {}, ("e2e-scenario",), "ACTIVE", "matrix-hash",
    )
    scenario = ScenarioDefinition(
        "e2e-scenario", "e2e-matrix", "Scenario", "Durability scenario",
        {}, ("outcome",), True, "scenario-hash",
    )
    service = object.__new__(ScienceLabService)
    service.registry = registry
    service.store = source
    service.research = None
    service.coordinator = None
    service.transformation_provenance = TransformationProvenanceBinder(source)
    service.matrices = {"e2e-matrix": matrix}
    service.scenarios = {"e2e-scenario": scenario}
    service.replication_assessments = {}
    service.generalization_assessments = {}
    service.runs = {
        "e2e-run": ScenarioRun(
            "e2e-run", "e2e-matrix", "e2e-scenario", "e2e-durable-1",
            "COMPLETED", ("e2e-result",), {"outcome": 6.0}, "PASS",
            "output-hash",
            Provenance(
                ProvenanceTag.EXP, "e2e", "1", "run-input-hash",
                "durability test",
            ),
            tp,
        )
    }
    service._put("science_lab.matrix", "e2e-matrix", {
        "matrix_id": matrix.matrix_id, "study_id": matrix.study_id,
        "name": matrix.name, "primary_outcome": matrix.primary_outcome,
        "design": matrix.design, "scenario_ids": list(matrix.scenario_ids),
        "status": matrix.status, "immutable_hash": matrix.immutable_hash,
    })
    service._put("science_lab.scenario", "e2e-scenario", {
        "scenario_id": scenario.scenario_id, "matrix_id": scenario.matrix_id,
        "name": scenario.name, "description": scenario.description,
        "conditions": scenario.conditions,
        "expected_outcomes": list(scenario.expected_outcomes),
        "independent": scenario.independent,
        "immutable_hash": scenario.immutable_hash,
    })
    service._put("science_lab.run", "e2e-run", {
        "run_id": "e2e-run", "matrix_id": "e2e-matrix",
        "scenario_id": "e2e-scenario", "execution_id": "e2e-durable-1",
        "status": "COMPLETED", "result_ids": ["e2e-result"],
        "estimate_by_outcome": {"outcome": 6.0}, "safety_status": "PASS",
        "output_hash": "output-hash", "transformation_provenance": tp,
        "provenance_tag": "EXP", "source": "e2e", "version": "1",
        "provenance_input_hash": "run-input-hash",
        "provenance_note": "durability test",
    })

    registry.add_node(register_node(
        "e2e-dataset", "DATASET", "e2e-dataset", "EXP", "1",
        {"kind": "DATASET"},
    ))
    registry.add_node(register_node(
        "e2e-analysis", "ANALYSIS", "e2e-analysis", "EXP", "1",
        {"kind": "ANALYSIS"},
    ))
    registry.add_node(register_node(
        "e2e-result", "RESULT", "e2e-result", "EXP", "1",
        {"qc_status": "PASS", "validated_descriptive_result": True},
    ))
    registry.add_edge(register_edge(
        "e2e-analysis:dataset", registry.nodes["e2e-dataset"],
        registry.nodes["e2e-analysis"], "ANALYZED_FROM", rationale="dataset",
    ))
    registry.add_edge(register_edge(
        "e2e-result:analysis", registry.nodes["e2e-analysis"],
        registry.nodes["e2e-result"], "RESULTS_IN", rationale="analysis",
    ))
    registry.add_node(register_node(
        "e2e-transformation", "TRANSFORMATION", "e2e-durable-1", "EXP", "2.3.0",
        {"validated": True, "ledger_id": tp["ledger_id"],
         "certificate_id": tp["certificate_id"]},
    ))
    registry.add_node(register_node(
        "e2e-run-node", "ANALYSIS", "e2e-run", "EXP", "2.3.0",
        {"execution_id": "e2e-durable-1"},
    ))
    registry.add_edge(register_edge(
        "e2e-run:transformation", registry.nodes["e2e-run-node"],
        registry.nodes["e2e-transformation"], "DERIVED_FROM", rationale="run",
    ))
    registry.register_claim(
        "e2e-claim", "e2e-result", "HYPOTHESIS", "REGISTERED",
        "EXP", {"execution_id": "e2e-durable-1"},
    )

    before = service.report_bundle("e2e-matrix")
    assert before["claim_validation"]["claims"][0]["transformation_support"]["status"] == "VALIDATED"
    assert before["transformation_provenance"]["validated_run_count"] == 1
    assert before["provenance"]["scientific_status"] == "IMPLEMENTATION_BASELINE"

    backup = build_backup(source)
    validate_backup(backup)
    target = SQLiteRuntimeStore(":memory:")
    restore_backup(target, backup)

    after_service = _service(target, GraphRegistry.empty(target))
    after = after_service.report_bundle("e2e-matrix")

    assert after["provenance"]["input_hash"] == before["provenance"]["input_hash"]
    assert after["claim_validation"] == before["claim_validation"]
    assert after["transformation_provenance"] == before["transformation_provenance"]
    assert after["scenario_runs"] == before["scenario_runs"]
    assert after["claim_validation"]["claims"][0]["transformation_support"]["ledger_id"] == tp["ledger_id"]
    assert after["claim_validation"]["claims"][0]["transformation_support"]["certificate_id"] == tp["certificate_id"]

    restored_tp = TransformationProvenanceBinder(target).bind_execution("e2e-durable-1")
    assert restored_tp["validated"] is True
    assert restored_tp["integrity_status"] == "PASS"
    assert restored_tp["ledger_id"] == tp["ledger_id"]
    assert restored_tp["certificate_id"] == tp["certificate_id"]
