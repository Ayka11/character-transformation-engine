from cte.graph_registry import build_registry
from cte.orchestrator import OrchestratorService
from cte.persistence import SQLiteRuntimeStore
from cte.research_e2e import ResearchE2ECoordinator
from cte.research_execution import ResearchService


def payload(execution_id="e2e-1", stress=2):
    return dict(
        execution_id=execution_id,
        correlation_id=f"{execution_id}:corr",
        observations=[
            {"item_id":"P1.sleep_quality","value":8,"observation_id":f"{execution_id}:sleep"},
            {"item_id":"P1.recovery_index","value":8,"observation_id":f"{execution_id}:recovery"},
            {"item_id":"P1.physical_activity","value":7,"observation_id":f"{execution_id}:activity"},
            {"item_id":"P1.metabolic_stability","value":8,"observation_id":f"{execution_id}:metabolic"},
            {"item_id":"P1.subjective_stress","value":stress,"observation_id":f"{execution_id}:stress"},
            {"item_id":"P1.subjective_energy","value":8,"observation_id":f"{execution_id}:energy"},
        ],
        study={
            "study_id":f"{execution_id}:study","study_code":execution_id,"title":"E2E Study",
            "research_question":"Does the intervention change the outcome?","hypothesis_ids":["H1"],
            "design_type":"SYNTHETIC","protocol_version":"1.2","preregistration_ref":"synthetic",
            "population_definition":{"synthetic":True},"inclusion_criteria":{},"exclusion_criteria":{},
            "primary_outcomes":["value"],"secondary_outcomes":[]
        },
        protocol={
            "protocol_id":f"{execution_id}:protocol","version":"1.2","design":{"type":"SYNTHETIC"},
            "measurement_schedule":{"frequency":"once"},"analysis_plan":{"primary":"mean"}
        },
        experiment={
            "experiment_id":f"{execution_id}:experiment","experiment_code":"E1",
            "intervention_spec":{"name":"synthetic"},"comparator_spec":None,
            "randomization_spec":None,"blinding_spec":None,"duration_days":1,
            "measurement_schedule":{"frequency":"once"},"analysis_plan":{"primary":"mean"},
            "seed":42,"software_version":"2.2"
        },
        arm={
            "arm_id":f"{execution_id}:arm","arm_code":"I","arm_type":"INTERVENTION",
            "intervention":{"name":"synthetic"},"target_level":"B","sample_target":1
        },
        participant={
            "participant_id":f"{execution_id}:participant","external_participant_code":"P1",
            "eligibility_status":"ELIGIBLE","consent_status":"CONSENTED",
            "enrollment_date":"2026-09-27","withdrawal_date":None,
            "demographic_snapshot":{"synthetic":True},"baseline_snapshot_id":None
        },
        assignment={
            "assignment_id":f"{execution_id}:assignment",
            "participant_id":f"{execution_id}:participant",
            "arm_id":f"{execution_id}:arm","assignment_method":"SYNTHETIC",
            "randomization_seed":42,"status":"ACTIVE"
        },
        trial={
            "trial_id":f"{execution_id}:trial",
            "participant_id":f"{execution_id}:participant",
            "arm_id":f"{execution_id}:arm","trial_number":1,
            "trial_time":"2026-09-27T12:00:00+00:00","task_id":"synthetic-task",
            "condition":{"condition":"baseline"},"stimulus":None,
            "response":{"rt":500},"outcome":{"value":7.0},
            "duration_ms":500,"validity_status":"VALID","raw_payload":{"value":7.0}
        },
        requested_trait=None,blockers={},recovery_indices=[8,8,8]
    )


def make_coordinator(tmp_path):
    store=SQLiteRuntimeStore(str(tmp_path/"runtime.sqlite3"))
    registry=build_registry(store)
    research=ResearchService(registry,store)
    orchestrator=OrchestratorService(store)
    return ResearchE2ECoordinator(orchestrator,research,registry)


def test_research_e2e_reaches_completed_and_links_claim(tmp_path):
    c=make_coordinator(tmp_path)
    result=c.run(**payload())
    assert result["status"]=="COMPLETED"
    assert result["execution"]["state"]=="COMPLETED"
    assert result["research"]["analysis"]["status"]=="COMPLETED"
    assert result["research"]["results"][0]["estimate"]==7.0
    assert result["research"]["claim"]["metadata"]["state"]=="DESCRIPTIVE_RESULT"
    assert result["provenance"]["execution_id"]=="e2e-1"
    assert len(result["provenance"]["events"])>=12


def test_research_e2e_blocks_on_level_a_safety_gate(tmp_path):
    c=make_coordinator(tmp_path)
    result=c.run(**payload(execution_id="e2e-blocked",stress=9))
    assert result["status"]=="BLOCKED"
    assert result["execution"]["state"]=="BLOCKED"
    assert result["safety_gate"]["level"]=="A"
    assert result["safety_gate"]["safety_block"] is True
