from cte.contracts.transformation import TransformationContract
from cte.persistence import SQLiteRuntimeStore
from cte.state_snapshot_store import StateSnapshotStore
from cte.transformation_ledger import TransformationLedger
from cte.transformation_provenance import TransformationProvenanceBinder
from cte.transformation_runtime import TransformationExecutor


def test_transformation_provenance_binds_validated_execution():
    db=SQLiteRuntimeStore(":memory:")
    snapshots=StateSnapshotStore(db)
    ledger=TransformationLedger(db)
    executor=TransformationExecutor(snapshots,ledger)
    execution=executor.execute(
        "prov-1","c1",1,{"tempo":5},
        TransformationContract("protocol-1","1",expected_changes={"tempo":6}),
        lambda state: {"tempo":6},
    )
    bound=TransformationProvenanceBinder(db).bind_execution("prov-1")
    assert execution.result.status=="VALIDATED"
    assert bound["validated"] is True
    assert bound["status"]=="VALIDATED"
    assert bound["ledger_id"]
    assert bound["certificate_id"]
    assert bound["integrity_status"]=="PASS"
    assert bound["before_snapshot_id"]
    assert bound["after_snapshot_id"]


def test_transformation_provenance_does_not_promote_missing_execution():
    db=SQLiteRuntimeStore(":memory:")
    bound=TransformationProvenanceBinder(db).bind_execution("missing-execution")
    assert bound["validated"] is False
    assert bound["status"]=="MISSING"
    assert "TRANSFORMATION_LEDGER_ENTRY_MISSING" in bound["issues"]

def test_science_lab_lineage_can_reach_transformation_node():
    from cte.graph_registry import GraphRegistry
    from cte.provenance import Provenance, ProvenanceTag
    from cte.science_lab import ScienceLabService

    db=SQLiteRuntimeStore(":memory:")
    registry=GraphRegistry(db)
    binder=TransformationProvenanceBinder(db)
    from cte.transformation_runtime import TransformationExecutor
    executor=TransformationExecutor(StateSnapshotStore(db), TransformationLedger(db))
    executor.execute(
        "lineage-1","c1",1,{"tempo":5},
        TransformationContract("protocol-1","1",expected_changes={"tempo":6}),
        lambda state: {"tempo":6},
    )
    transformation=binder.bind_execution("lineage-1")
    registry.add_node(__import__("cte.evidence_graph",fromlist=["register_node"]).register_node(
        "transformation:lineage-1","TRANSFORMATION","lineage-1","EXP","1.0",transformation
    ))
    registry.add_node(__import__("cte.evidence_graph",fromlist=["register_node"]).register_node(
        "scenario:lineage-1","ANALYSIS","scenario:lineage-1","EXP","1.0",
        {"execution_id":"lineage-1"}
    ))
    registry.add_edge(__import__("cte.evidence_graph",fromlist=["register_edge"]).register_edge(
        "scenario:lineage-1:transformation",
        registry.nodes["scenario:lineage-1"],
        registry.nodes["transformation:lineage-1"],
        "DERIVED_FROM",
        rationale="test lineage"
    ))
    registry.add_node(__import__("cte.evidence_graph",fromlist=["register_node"]).register_node(
        "result:lineage-1","RESULT","result:lineage-1","EXP","1.0",{}
    ))
    registry.add_edge(__import__("cte.evidence_graph",fromlist=["register_edge"]).register_edge(
        "scenario:lineage-1:result",
        registry.nodes["scenario:lineage-1"],
        registry.nodes["result:lineage-1"],
        "DERIVED_FROM",
        rationale="test result lineage"
    ))
    registry.register_claim(
        "claim:lineage-1","result:lineage-1","REGISTERED","DESCRIPTIVE_RESULT","EXP",
        {"execution_id":"lineage-1"}
    )
    nodes,edges=registry.claim_subgraph("claim:lineage-1")
    assert "transformation:lineage-1" in {n.node_id for n in nodes}


def test_science_lab_report_exposes_transformation_provenance_without_promotion():
    from cte.science_lab import ScienceLabService

    db=SQLiteRuntimeStore(":memory:")
    binder=TransformationProvenanceBinder(db)
    registry=__import__("cte.graph_registry",fromlist=["GraphRegistry"]).GraphRegistry(db)

    # A missing execution is deliberately not promoted to validated evidence.
    tp=binder.bind_execution("report-missing")
    assert tp["validated"] is False

    service=object.__new__(ScienceLabService)
    service.store=db
    service.registry=registry
    service.matrices={
        "m1": __import__("cte.science_lab",fromlist=["ExperimentMatrix"]).ExperimentMatrix(
            "m1","study-1","Matrix","outcome",{},("s1",),"ACTIVE","hash"
        )
    }
    service.scenarios={
        "s1": __import__("cte.science_lab",fromlist=["ScenarioDefinition"]).ScenarioDefinition(
            "s1","m1","Scenario","desc",{},("outcome",),True,"hash"
        )
    }
    service.runs={}
    service.replication_assessments={}
    service.generalization_assessments={}
    service.claim_validation=lambda matrix_id: []
    service.descriptive_statistics=lambda matrix_id: {
        "scenario_count": 1, "run_count": 0, "completed_runs": 0,
        "descriptive_estimate_mean": None
    }

    bundle=service.report_bundle("m1")
    assert bundle["transformation_provenance"]["run_count"] == 0
    assert bundle["transformation_provenance"]["all_runs_validated"] is False


def test_corrupted_transformation_provenance_cannot_support_claim():
    from cte.graph_registry import GraphRegistry
    from cte.science_lab import ScienceLabService, ScenarioRun

    db=SQLiteRuntimeStore(":memory:")
    registry=GraphRegistry(db)
    service=object.__new__(ScienceLabService)
    service.store=db
    service.registry=registry
    service.matrices={}
    service.scenarios={}
    service.runs={}
    service.replication_assessments={}
    service.generalization_assessments={}

    from cte.provenance import Provenance, ProvenanceTag
    run=ScenarioRun(
        "run-corrupt","m1","s1","exec-corrupt","COMPLETED",("result-corrupt",),
        {"outcome":1.0},"PASS","hash",
        Provenance(ProvenanceTag.EXP,"test","1","hash","test"),
        {
            "execution_id":"exec-corrupt",
            "validated":True,
            "integrity_status":"FAIL",
            "ledger_id":"forged-ledger",
            "certificate_id":"forged-cert",
            "issues":["CERTIFICATE_HASH_MISMATCH"],
        },
    )
    service.runs[run.run_id]=run
    registry.add_node(__import__("cte.evidence_graph",fromlist=["register_node"]).register_node(
        "result-corrupt","RESULT","result-corrupt","EXP","1",{}
    ))
    registry.register_claim(
        "claim-corrupt","result-corrupt","REGISTERED","DESCRIPTIVE_RESULT","EXP",
        {"execution_id":"exec-corrupt"}
    )
    service.matrices["m1"]=__import__("cte.science_lab",fromlist=["ExperimentMatrix"]).ExperimentMatrix(
        "m1","study","Matrix","outcome",{},("s1",),"ACTIVE","hash"
    )
    service.scenarios["s1"]=__import__("cte.science_lab",fromlist=["ScenarioDefinition"]).ScenarioDefinition(
        "s1","m1","Scenario","desc",{},("outcome",),True,"hash"
    )
    claims=service.claim_validation("m1")
    assert claims["claims"][0]["transformation_support"]["status"]=="NOT_VALIDATED"
    assert claims["claims"][0]["transformation_support"]["integrity_status"]=="FAIL"
