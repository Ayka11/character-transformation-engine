from cte.graph_registry import build_registry
from cte.persistence import SQLiteRuntimeStore
from cte.research_execution import ResearchService


def make_service(tmp_path):
    return ResearchService(build_registry(SQLiteRuntimeStore(str(tmp_path / "runtime.sqlite3"))),
                            SQLiteRuntimeStore(str(tmp_path / "runtime.sqlite3")))


def test_research_execution_pipeline_and_provenance(tmp_path):
    s=make_service(tmp_path)
    study=s.register_study(
        study_id="study-1",study_code="S1",title="Test Study",
        research_question="Does intervention change outcome?",
        hypothesis_ids=["H1"],design_type="RANDOMIZED",
        protocol_version="1.2",preregistration_ref="prereg-1",
        population_definition={"age":"adult"},inclusion_criteria={"consent":True},
        exclusion_criteria={},primary_outcomes=["value"]
    )
    protocol=s.register_protocol(
        protocol_id="protocol-1",study_id=study.study_id,version="1.2",
        design={"type":"RANDOMIZED"},measurement_schedule={"frequency":"daily"},
        analysis_plan={"primary":"mean"}
    )
    experiment=s.create_experiment(
        experiment_id="exp-1",study_id="study-1",experiment_code="E1",
        intervention_spec={"name":"intervention"},comparator_spec={"name":"control"},
        randomization_spec={"seeded":True},blinding_spec=None,duration_days=7,
        measurement_schedule={"frequency":"daily"},analysis_plan={"primary":"mean"},
        seed=42,software_version="2.2",protocol_id=protocol.protocol_id
    )
    arm=s.register_arm(arm_id="arm-i",experiment_id="exp-1",arm_code="I",
                       arm_type="INTERVENTION",intervention={"dose":"standard"},
                       target_level="C",sample_target=1)
    s.register_arm(arm_id="arm-c",experiment_id="exp-1",arm_code="C",
                   arm_type="CONTROL",intervention=None,target_level=None,sample_target=1)
    p=s.enroll_participant(
        participant_id="p1",study_id="study-1",external_participant_code="P001",
        eligibility_status="ELIGIBLE",consent_status="CONSENTED",
        enrollment_date="2026-09-27",withdrawal_date=None,
        demographic_snapshot={"age":40},baseline_snapshot_id=None
    )
    assignment=s.assign_participant(
        assignment_id="as-1",participant_id=p.participant_id,arm_id=arm.arm_id,
        assignment_method="SEEDED_RANDOM",randomization_seed=42
    )
    assert assignment.status=="ACTIVE"
    s.ingest_trial(
        trial_id="t1",experiment_id="exp-1",participant_id="p1",arm_id="arm-i",
        trial_number=1,trial_time="2026-09-27T10:00:00+00:00",task_id="task-1",
        condition={"condition":"baseline"},stimulus=None,response={"rt":500},
        outcome={"value":7.0},duration_ms=500,validity_status="VALID",
        raw_payload={"value":7.0}
    )
    qc=s.run_qc(qc_run_id="qc-1",study_id="study-1",experiment_id="exp-1")
    assert qc.passed
    manifest=s.create_manifest(dataset_manifest_id="manifest-1",experiment_id="exp-1")
    analysis,results=s.run_analysis(
        analysis_run_id="analysis-1",study_id="study-1",experiment_id="exp-1",
        qc_run_id=qc.qc_run_id,dataset_manifest_id=manifest.dataset_manifest_id,
        analysis_version="1.2.0",statistical_plan={"primary":"mean"},
        dataset_definition={"filter":"VALID"},model_specification={"estimator":"MEAN"},
        random_seed=42
    )
    assert analysis.status=="COMPLETED"
    assert results[0].estimate==7.0
    assert s.registry.nodes["analysis-1"].node_type=="ANALYSIS"
    assert s.registry.nodes[results[0].result_id].node_type=="RESULT"
    provenance=s.study_provenance("study-1")
    assert provenance["node_count"]>=5
    assert any(e["edge_type"]=="ANALYZED_FROM" for e in provenance["edges"])


def test_qc_blocks_analysis_until_pending_trials_are_resolved(tmp_path):
    s=make_service(tmp_path)
    s.register_study(
        study_id="study-1",study_code="S1",title="Test",
        research_question="RQ",hypothesis_ids=[],design_type="OBSERVATIONAL",
        protocol_version="1.2",preregistration_ref=None,population_definition={},
        inclusion_criteria={},exclusion_criteria={},primary_outcomes=["value"]
    )
    p=s.register_protocol(protocol_id="protocol-1",study_id="study-1",version="1.2",
                          design={},measurement_schedule={},analysis_plan={})
    s.create_experiment(experiment_id="exp-1",study_id="study-1",experiment_code="E1",
                        intervention_spec={},comparator_spec=None,randomization_spec=None,
                        blinding_spec=None,duration_days=None,measurement_schedule={},
                        analysis_plan={},seed=None,software_version="2.2",protocol_id=p.protocol_id)
    s.enroll_participant(participant_id="p1",study_id="study-1",external_participant_code="P1",
                         eligibility_status="ELIGIBLE",consent_status="CONSENTED",
                         enrollment_date=None,withdrawal_date=None,demographic_snapshot=None,
                         baseline_snapshot_id=None)
    s.ingest_trial(trial_id="t1",experiment_id="exp-1",participant_id="p1",arm_id=None,
                   trial_number=1,trial_time="2026-09-27T10:00:00+00:00",task_id="task",
                   condition={},stimulus=None,response=None,outcome={"value":1},
                   duration_ms=None,validity_status="PENDING",raw_payload={"value":1})
    qc=s.run_qc(qc_run_id="qc-1",study_id="study-1",experiment_id="exp-1")
    assert qc.passed is False
    try:
        s.run_analysis(analysis_run_id="a1",study_id="study-1",experiment_id="exp-1",
                       qc_run_id="qc-1",dataset_manifest_id="missing",
                       analysis_version="1.2",statistical_plan={},dataset_definition={},
                       model_specification={})
    except ValueError as e:
        assert "PASSED QC" in str(e)
    else:
        assert False


def test_research_state_and_trial_are_durable(tmp_path):
    db=str(tmp_path / "runtime.sqlite3")
    store=SQLiteRuntimeStore(db)
    s=ResearchService(build_registry(store),store)
    s.register_study(
        study_id="study-1",study_code="S1",title="Test",
        research_question="RQ",hypothesis_ids=[],design_type="OBSERVATIONAL",
        protocol_version="1.2",preregistration_ref=None,population_definition={},
        inclusion_criteria={},exclusion_criteria={},primary_outcomes=["value"]
    )
    p=s.register_protocol(protocol_id="protocol-1",study_id="study-1",version="1.2",
                          design={},measurement_schedule={},analysis_plan={})
    s.create_experiment(experiment_id="exp-1",study_id="study-1",experiment_code="E1",
                        intervention_spec={},comparator_spec=None,randomization_spec=None,
                        blinding_spec=None,duration_days=None,measurement_schedule={},
                        analysis_plan={},seed=None,software_version="2.2",protocol_id=p.protocol_id)
    s.enroll_participant(participant_id="p1",study_id="study-1",external_participant_code="P1",
                         eligibility_status="ELIGIBLE",consent_status="CONSENTED",
                         enrollment_date=None,withdrawal_date=None,demographic_snapshot=None,
                         baseline_snapshot_id=None)
    s.ingest_trial(trial_id="t1",experiment_id="exp-1",participant_id="p1",arm_id=None,
                   trial_number=1,trial_time="2026-09-27T10:00:00+00:00",task_id="task",
                   condition={},stimulus=None,response=None,outcome={"value":1},
                   duration_ms=None,validity_status="VALID",raw_payload={"value":1})
    s2=ResearchService(build_registry(SQLiteRuntimeStore(db)),SQLiteRuntimeStore(db))
    assert "study-1" in s2.studies
    assert "exp-1" in s2.experiments
    assert "p1" in s2.participants
    assert "t1" in s2.trials
