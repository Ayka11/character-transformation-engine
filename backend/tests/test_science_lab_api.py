from uuid import uuid4

from fastapi.testclient import TestClient

from cte.api import app


def test_science_lab_api_matrix_run_statistics_cycle():
    client=TestClient(app)
    suffix=uuid4().hex[:10]
    matrix_id="api-matrix-"+suffix
    scenario_id="api-scenario-"+suffix
    execution_id="api-execution-"+suffix

    matrix=client.post(
        "/science-lab/matrices",
        json={
            "matrix_id":matrix_id,
            "study_id":"api-study-"+suffix,
            "name":"API Matrix",
            "primary_outcome":"value",
            "design":{"type":"scenario_matrix"}
        }
    )
    assert matrix.status_code==200

    scenario=client.post(
        f"/science-lab/matrices/{matrix_id}/scenarios",
        json={
            "scenario_id":scenario_id,
            "name":"Baseline",
            "description":"API baseline",
            "conditions":{"dose":0},
            "expected_outcomes":["value"],
            "independent":True
        }
    )
    assert scenario.status_code==200

    payload={
        "execution_id":execution_id,
        "correlation_id":execution_id+":corr",
        "observations":[
            {"item_id":"P1.sleep_quality","value":8,"observation_id":execution_id+":sleep"},
            {"item_id":"P1.recovery_index","value":8,"observation_id":execution_id+":recovery"},
            {"item_id":"P1.physical_activity","value":7,"observation_id":execution_id+":activity"},
            {"item_id":"P1.metabolic_stability","value":8,"observation_id":execution_id+":metabolic"},
            {"item_id":"P1.subjective_stress","value":2,"observation_id":execution_id+":stress"},
            {"item_id":"P1.subjective_energy","value":8,"observation_id":execution_id+":energy"}
        ],
        "study":{
            "study_id":execution_id+":study","study_code":execution_id,
            "title":"API E2E Study","research_question":"RQ","hypothesis_ids":["H1"],
            "design_type":"SYNTHETIC","protocol_version":"1.2",
            "preregistration_ref":"synthetic","population_definition":{"synthetic":True},
            "inclusion_criteria":{},"exclusion_criteria":{},
            "primary_outcomes":["value"],"secondary_outcomes":[]
        },
        "protocol":{
            "protocol_id":execution_id+":protocol","version":"1.2",
            "design":{"type":"SYNTHETIC"},"measurement_schedule":{"frequency":"once"},
            "analysis_plan":{"primary":"mean"}
        },
        "experiment":{
            "experiment_id":execution_id+":experiment","experiment_code":"E1",
            "intervention_spec":{"name":"baseline"},"comparator_spec":None,
            "randomization_spec":None,"blinding_spec":None,"duration_days":1,
            "measurement_schedule":{"frequency":"once"},"analysis_plan":{"primary":"mean"},
            "seed":42,"software_version":"2.3"
        },
        "arm":{
            "arm_id":execution_id+":arm","arm_code":"I","arm_type":"INTERVENTION",
            "intervention":{"name":"baseline"},"target_level":"B","sample_target":1
        },
        "participant":{
            "participant_id":execution_id+":participant",
            "external_participant_code":"P1","eligibility_status":"ELIGIBLE",
            "consent_status":"CONSENTED","enrollment_date":"2026-09-27",
            "withdrawal_date":None,"demographic_snapshot":{"synthetic":True},
            "baseline_snapshot_id":None
        },
        "assignment":{
            "assignment_id":execution_id+":assignment",
            "participant_id":execution_id+":participant",
            "arm_id":execution_id+":arm","assignment_method":"SYNTHETIC",
            "randomization_seed":42,"status":"ACTIVE"
        },
        "trial":{
            "trial_id":execution_id+":trial",
            "participant_id":execution_id+":participant",
            "arm_id":execution_id+":arm","trial_number":1,
            "trial_time":"2026-09-27T12:00:00+00:00","task_id":"api-task",
            "condition":{"scenario":"baseline"},"stimulus":None,
            "response":{"rt":500},"outcome":{"value":7},
            "duration_ms":500,"validity_status":"VALID","raw_payload":{"value":7}
        },
        "requested_trait":None,
        "blockers":{},
        "recovery_indices":[8,8,8]
    }

    run=client.post(
        f"/science-lab/matrices/{matrix_id}/scenarios/{scenario_id}/run",
        json={"payload":payload}
    )
    assert run.status_code==200
    assert run.json()["status"]=="COMPLETED"

    stats=client.get(f"/science-lab/matrices/{matrix_id}/statistics")
    assert stats.status_code==200
    assert stats.json()["completed_runs"]==1
    assert stats.json()["descriptive_estimate_mean"]==7.0

    bundle=client.get(f"/science-lab/matrices/{matrix_id}/report")
    assert bundle.status_code==200
    assert bundle.json()["matrix"]["matrix_id"]==matrix_id
