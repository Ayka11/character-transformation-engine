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
    registry=GraphRegistry.empty(db)
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
        "dataset:lineage-1","DATASET","dataset:lineage-1","EXP","1.0",{}
    ))
    registry.add_edge(__import__("cte.evidence_graph",fromlist=["register_edge"]).register_edge(
        "scenario:lineage-1:dataset",
        registry.nodes["scenario:lineage-1"],
        registry.nodes["dataset:lineage-1"],
        "ANALYZED_FROM",
        rationale="test dataset lineage"
    ))
    registry.add_node(__import__("cte.evidence_graph",fromlist=["register_node"]).register_node(
        "result:lineage-1","RESULT","result:lineage-1","EXP","1.0",{"qc_status":"PASS","validated_descriptive_result":True}
    ))
    registry.add_edge(__import__("cte.evidence_graph",fromlist=["register_edge"]).register_edge(
        "scenario:lineage-1:result",
        registry.nodes["scenario:lineage-1"],
        registry.nodes["result:lineage-1"],
        "RESULTS_IN",
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
    registry=__import__("cte.graph_registry",fromlist=["GraphRegistry"]).GraphRegistry.empty(db)

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
    registry=GraphRegistry.empty(db)
    service=object.__new__(ScienceLabService)
    service.store=db
    service.registry=registry
    service.matrices={}
    service.scenarios={}
    service.runs={}
    service.replication_assessments={}
    service.transformation_provenance=TransformationProvenanceBinder(db)
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
        "dataset-corrupt","DATASET","dataset-corrupt","EXP","1",{}
    ))
    registry.add_node(__import__("cte.evidence_graph",fromlist=["register_node"]).register_node(
        "analysis-corrupt","ANALYSIS","analysis-corrupt","EXP","1",{}
    ))
    registry.add_edge(__import__("cte.evidence_graph",fromlist=["register_edge"]).register_edge(
        "analysis-corrupt:dataset",registry.nodes["analysis-corrupt"],
        registry.nodes["dataset-corrupt"],"ANALYZED_FROM",rationale="test dataset"
    ))
    registry.add_node(__import__("cte.evidence_graph",fromlist=["register_node"]).register_node(
        "result-corrupt","RESULT","result-corrupt","EXP","1",
        {"qc_status":"PASS","validated_descriptive_result":True}
    ))
    registry.add_edge(__import__("cte.evidence_graph",fromlist=["register_edge"]).register_edge(
        "analysis-corrupt:result",registry.nodes["analysis-corrupt"],
        registry.nodes["result-corrupt"],"RESULTS_IN",rationale="test result"
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


def test_transformation_provenance_survives_science_lab_reload_and_report_hash():
    from cte.graph_registry import GraphRegistry
    from cte.science_lab import ScienceLabService, ExperimentMatrix, ScenarioDefinition, ScenarioRun

    db=SQLiteRuntimeStore(":memory:")
    registry=GraphRegistry.empty(db)
    binder=TransformationProvenanceBinder(db)
    executor=TransformationExecutor(StateSnapshotStore(db), TransformationLedger(db))
    execution=executor.execute(
        "reload-1","character-1",1,{"tempo":5},
        TransformationContract("protocol-reload","1",expected_changes={"tempo":6}),
        lambda state: {"tempo":6},
    )
    tp=binder.bind_execution("reload-1")
    prov=__import__("cte.provenance",fromlist=["Provenance","ProvenanceTag"]).Provenance(
        __import__("cte.provenance",fromlist=["ProvenanceTag"]).ProvenanceTag.EXP,
        "test","1","hash","test"
    )
    matrix=ExperimentMatrix("reload-matrix","study","Reload","outcome",{},("scenario",),"ACTIVE","hash")
    scenario=ScenarioDefinition("scenario","reload-matrix","Scenario","desc",{},("outcome",),True,"hash")
    service=object.__new__(ScienceLabService)
    service.registry=registry
    service.store=db
    service.research=None
    service.coordinator=None
    service.transformation_provenance=TransformationProvenanceBinder(db)
    service.matrices={"reload-matrix":matrix}
    service.scenarios={"scenario":scenario}
    service.replication_assessments={}
    service.generalization_assessments={}
    service.runs={
        "reload-run": ScenarioRun(
            "reload-run","reload-matrix","scenario","reload-1","COMPLETED",
            ("result-reload",),{"outcome":6.0},"PASS","output",prov,tp
        )
    }
    bundle1=service.report_bundle("reload-matrix")
    assert bundle1["transformation_provenance"]["validated_run_count"] == 1
    assert bundle1["transformation_provenance"]["all_runs_validated"] is True
    assert bundle1["transformation_provenance"]["runs"][0]["certificate_id"] == execution.certificate.certificate_id

    registry2=GraphRegistry.empty(db)
    service2=object.__new__(ScienceLabService)
    service2.registry=registry2
    service2.store=db
    service2.research=None
    service2.coordinator=None
    service2.transformation_provenance=TransformationProvenanceBinder(db)
    service2.matrices={"reload-matrix":matrix}
    service2.scenarios={"scenario":scenario}
    service2.replication_assessments={}
    service2.generalization_assessments={}
    service2._put("science_lab.run","reload-run",{
        "run_id":"reload-run","matrix_id":"reload-matrix","scenario_id":"scenario",
        "execution_id":"reload-1","status":"COMPLETED","result_ids":["result-reload"],
        "estimate_by_outcome":{"outcome":6.0},"safety_status":"PASS","output_hash":"output",
        "transformation_provenance":tp,"provenance_tag":prov.tag.value,"source":prov.source_id,
        "version":prov.source_version,"provenance_input_hash":prov.input_hash,
        "provenance_note":prov.note,
    })
    service2.runs={}
    service2._hydrate()
    bundle2=service2.report_bundle("reload-matrix")
    assert bundle2["transformation_provenance"]["validated_run_count"] == 1
    assert bundle2["transformation_provenance"]["runs"][0]["ledger_id"] == tp["ledger_id"]
    assert bundle2["provenance"]["input_hash"] == bundle1["provenance"]["input_hash"]


def test_science_lab_does_not_trust_tampered_run_transformation_provenance():
    from cte.graph_registry import GraphRegistry
    from cte.science_lab import ExperimentMatrix, ScenarioDefinition, ScenarioRun, ScienceLabService
    from cte.evidence_graph import register_edge, register_node

    db = SQLiteRuntimeStore(":memory:")
    registry = GraphRegistry.empty(db)
    executor = TransformationExecutor(StateSnapshotStore(db), TransformationLedger(db))
    execution = executor.execute(
        "tamper-source", "character-tamper", 1, {"tempo": 5},
        TransformationContract("tamper-contract", "1", expected_changes={"tempo": 6}),
        lambda state: {"tempo": 6},
    )
    trusted = TransformationProvenanceBinder(db).bind_execution("tamper-source")
    service = object.__new__(ScienceLabService)
    service.store = db
    service.registry = registry
    service.research = None
    service.coordinator = None
    service.transformation_provenance = TransformationProvenanceBinder(db)
    service.matrices = {
        "m": ExperimentMatrix("m", "study", "M", "outcome", {}, ("s",), "ACTIVE", "hash")
    }
    service.scenarios = {
        "s": ScenarioDefinition("s", "m", "S", "S", {}, ("outcome",), True, "hash")
    }
    service.replication_assessments = {}
    service.generalization_assessments = {}
    service.runs = {
        "run": ScenarioRun(
            "run", "m", "s", "tamper-source", "COMPLETED", ("result",),
            {"outcome": 6.0}, "PASS", "output",
            Provenance(ProvenanceTag.EXP, "test", "1", "input", "test"),
            {
                **trusted,
                "validated": False,
                "integrity_status": "FAIL",
                "ledger_id": "forged-ledger",
                "certificate_id": "forged-certificate",
            },
        )
    }
    registry.add_node(register_node(
        "result", "RESULT", "result", "EXP", "1",
        {"qc_status": "PASS", "validated_descriptive_result": True},
    ))
    registry.add_node(register_node(
        "analysis", "ANALYSIS", "analysis", "EXP", "1", {"kind": "ANALYSIS"},
    ))
    registry.add_node(register_node(
        "dataset", "DATASET", "dataset", "EXP", "1", {"kind": "DATASET"},
    ))
    registry.add_edge(register_edge(
        "analysis:dataset", registry.nodes["dataset"], registry.nodes["analysis"],
        "ANALYZED_FROM", rationale="test",
    ))
    registry.add_edge(register_edge(
        "result:analysis", registry.nodes["analysis"], registry.nodes["result"],
        "RESULTS_IN", rationale="test",
    ))
    registry.register_claim(
        "claim", "result", "HYPOTHESIS", "REGISTERED", "EXP",
        {"execution_id": "tamper-source"},
    )

    claims = service.claim_validation("m")
    support = claims["claims"][0]["transformation_support"]
    assert support["status"] == "VALIDATED"
    assert support["integrity_status"] == "PASS"
    assert support["ledger_id"] == trusted["ledger_id"]
    assert support["ledger_id"] != "forged-ledger"

    report = service.report_bundle("m")
    assert report["transformation_provenance"]["validated_run_count"] == 1
    assert report["transformation_provenance"]["runs"][0]["ledger_id"] == trusted["ledger_id"]
    assert report["transformation_provenance"]["runs"][0]["certificate_id"] == trusted["certificate_id"]
    assert execution.result.status == "VALIDATED"
