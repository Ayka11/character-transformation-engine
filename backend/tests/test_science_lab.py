from cte.evidence_graph import register_node
from cte.graph_registry import build_registry
from cte.orchestrator import OrchestratorService
from cte.persistence import SQLiteRuntimeStore
from cte.research_e2e import ResearchE2ECoordinator
from cte.research_execution import ResearchService
from cte.science_lab import ScienceLabService


def make_lab(tmp_path):
    db=str(tmp_path/"lab.sqlite3")
    store=SQLiteRuntimeStore(db)
    registry=build_registry(store)
    research=ResearchService(registry,store)
    orchestrator=OrchestratorService(store)
    coordinator=ResearchE2ECoordinator(orchestrator,research,registry)
    return ScienceLabService(registry,store,research,coordinator)


def e2e_payload(execution_id):
    return {
        "execution_id":execution_id,
        "correlation_id":execution_id+":corr",
        "observations":[
            {"item_id":"P1.sleep_quality","value":8,"observation_id":execution_id+":sleep"},
            {"item_id":"P1.recovery_index","value":8,"observation_id":execution_id+":recovery"},
            {"item_id":"P1.physical_activity","value":7,"observation_id":execution_id+":activity"},
            {"item_id":"P1.metabolic_stability","value":8,"observation_id":execution_id+":metabolic"},
            {"item_id":"P1.subjective_stress","value":2,"observation_id":execution_id+":stress"},
            {"item_id":"P1.subjective_energy","value":8,"observation_id":execution_id+":energy"},
        ],
        "study":{
            "study_id":execution_id+":study","study_code":execution_id,"title":"Lab Study",
            "research_question":"Does scenario change outcome?","hypothesis_ids":["H1"],
            "design_type":"SYNTHETIC","protocol_version":"1.2","preregistration_ref":"lab",
            "population_definition":{"synthetic":True},"inclusion_criteria":{},
            "exclusion_criteria":{},"primary_outcomes":["value"],"secondary_outcomes":[]
        },
        "protocol":{
            "protocol_id":execution_id+":protocol","version":"1.2",
            "design":{"type":"SYNTHETIC"},"measurement_schedule":{"frequency":"once"},
            "analysis_plan":{"primary":"mean"}
        },
        "experiment":{
            "experiment_id":execution_id+":experiment","experiment_code":"E1",
            "intervention_spec":{"scenario":execution_id},"comparator_spec":None,
            "randomization_spec":None,"blinding_spec":None,"duration_days":1,
            "measurement_schedule":{"frequency":"once"},"analysis_plan":{"primary":"mean"},
            "seed":42,"software_version":"2.3"
        },
        "arm":{
            "arm_id":execution_id+":arm","arm_code":"I","arm_type":"INTERVENTION",
            "intervention":{"scenario":execution_id},"target_level":"B","sample_target":1
        },
        "participant":{
            "participant_id":execution_id+":participant","external_participant_code":"P1",
            "eligibility_status":"ELIGIBLE","consent_status":"CONSENTED",
            "enrollment_date":"2026-09-27","withdrawal_date":None,
            "demographic_snapshot":{"synthetic":True},"baseline_snapshot_id":None
        },
        "assignment":{
            "assignment_id":execution_id+":assignment",
            "participant_id":execution_id+":participant",
            "arm_id":execution_id+":arm","assignment_method":"SYNTHETIC",
            "randomization_seed":42,"status":"ACTIVE"
        },
        "trial":{
            "trial_id":execution_id+":trial","participant_id":execution_id+":participant",
            "arm_id":execution_id+":arm","trial_number":1,
            "trial_time":"2026-09-27T12:00:00+00:00","task_id":"synthetic-task",
            "condition":{"scenario":execution_id},"stimulus":None,
            "response":{"rt":500},"outcome":{"value":7.0},"duration_ms":500,
            "validity_status":"VALID","raw_payload":{"value":7.0}
        },
        "requested_trait":None,"blockers":{},"recovery_indices":[8,8,8]
    }


def test_matrix_scenario_run_and_report_bundle(tmp_path):
    lab=make_lab(tmp_path)
    matrix=lab.register_matrix(
        matrix_id="m1",study_id="study-root",name="Experiment Matrix",
        primary_outcome="value",design={"type":"scenario_matrix"}
    )
    scenario=lab.register_scenario(
        scenario_id="s1",matrix_id=matrix.matrix_id,name="Baseline",
        description="Baseline scenario",conditions={"dose":0},
        expected_outcomes=["value"],independent=True
    )
    run=lab.run_scenario(matrix_id="m1",scenario_id="s1",
                          payload=e2e_payload("m1-s1-run"))
    assert run.status=="COMPLETED"
    assert run.result_ids
    bundle=lab.report_bundle("m1")
    assert bundle["matrix"]["matrix_id"]=="m1"
    assert bundle["scenario_runs"][0]["execution_id"]=="m1-s1-run"
    assert bundle["provenance"]["tag"]=="EXP"


def test_lab_replication_and_generalization_are_explicit(tmp_path):
    lab=make_lab(tmp_path)
    matrix=lab.register_matrix(
        matrix_id="m1",study_id="study-root",name="Matrix",
        primary_outcome="value",design={"type":"scenario_matrix"}
    )
    lab.register_scenario(
        scenario_id="s1",matrix_id="m1",name="Baseline",
        description="Baseline",conditions={},expected_outcomes=["value"]
    )
    run=lab.run_scenario(matrix_id="m1",scenario_id="s1",
                          payload=e2e_payload("m1-s1-run"))
    result_id=run.result_ids[0]
    claim_id="c-lab"
    claim=lab.registry.register_claim(
        claim_id,result_id,"REGISTERED","DESCRIPTIVE_RESULT","EXP",
        {"execution_id":run.execution_id}
    )
    rep=lab.register_replication_assessment(
        matrix_id="m1",assessment_id="rep1",
        replication_spec_id="rep-spec",source_claim_id=claim_id,
        primary_outcome_id="value",source_result_id=result_id,
        independent_study_id="rep-study",dataset_manifest_id="rep-manifest",
        protocol_hash="p",input_hash="i",source_estimate=7.0,
        target_estimate=7.1,source_effect_size=1.0,target_effect_size=1.02,
        protocol_fidelity=True,measurement_fidelity=True,
        outcome_definition=True,data_quality=True
    )
    assert rep.status=="REPLICATED"
    gen=lab.register_generalization_assessment(
        matrix_id="m1",assessment_id="gen1",
        generalization_spec_id="gen-spec",source_claim_id=claim_id,
        source_result_id=result_id,source_population={"synthetic":True},
        target_population={"synthetic":True},source_context={"x":"a"},
        target_context={"x":"b"},dataset_manifest_id="gen-manifest",
        source_estimate=7.0,transported_estimate=6.9,transport_error=0.05,
        dimensions={
            "population":"LOW","context":"LOW","task":"LOW",
            "measurement":"LOW","intervention":"LOW","time":"LOW",
            "data_quality":"LOW"
        }
    )
    assert gen.status=="GENERALIZABLE"
    validation=lab.claim_validation("m1")
    assert any(x["claim_id"]==claim_id for x in validation["claims"])


def test_lab_descriptive_statistics_is_explicitly_non_inferential(tmp_path):
    lab=make_lab(tmp_path)
    matrix=lab.register_matrix(
        matrix_id="m1",study_id="study-root",name="Matrix",
        primary_outcome="value",design={"type":"scenario_matrix"}
    )
    lab.register_scenario(
        scenario_id="s1",matrix_id="m1",name="Baseline",
        description="Baseline",conditions={},expected_outcomes=["value"]
    )
    run=lab.run_scenario(matrix_id="m1",scenario_id="s1",
                          payload=e2e_payload("m1-s1-run"))
    stats=lab.descriptive_statistics("m1")
    assert stats["completed_runs"]==1
    assert stats["descriptive_estimate_mean"]==7.0
    assert stats["scientific_status"]=="DESCRIPTIVE_ONLY_MODEL_DERIVED_RUNTIME"


def test_factorial_scenario_generator_is_deterministic_and_bounded(tmp_path):
    lab=make_lab(tmp_path)
    matrix=lab.register_matrix(
        matrix_id="m1",study_id="study-root",name="Factor Matrix",
        primary_outcome="value",design={"type":"factorial"}
    )
    scenarios=lab.generate_scenarios(
        matrix_id=matrix.matrix_id,
        factors={"dose":[0,1],"tempo":["slow","fast"]},
        max_scenarios=8,
        name_prefix="Scenario"
    )
    assert len(scenarios)==4
    assert [s.scenario_id for s in scenarios]==[
        "m1:scenario:001","m1:scenario:002","m1:scenario:003","m1:scenario:004"
    ]
    assert scenarios[0].conditions=={"dose":0,"tempo":"slow"}
    assert all(s.independent is False for s in scenarios)


def test_factorial_scenario_generator_rejects_explosion(tmp_path):
    lab=make_lab(tmp_path)
    lab.register_matrix(
        matrix_id="m1",study_id="study-root",name="Factor Matrix",
        primary_outcome="value",design={"type":"factorial"}
    )
    try:
        lab.generate_scenarios(
            matrix_id="m1",
            factors={"a":[1,2,3,4],"b":[1,2,3,4]},
            max_scenarios=8
        )
    except ValueError as e:
        assert "max is 8" in str(e)
    else:
        assert False
