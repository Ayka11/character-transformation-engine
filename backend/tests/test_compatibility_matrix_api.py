from fastapi.testclient import TestClient
from hashlib import sha256
from json import dumps

from cte.api import app

client = TestClient(app)


def test_canonical_compatibility_endpoint_accepts_registered_p1_to_p5_ids():
    response = client.post("/compatibility/v2/canonical", json={
        "profile_a": {"P1.sleep_quality": 7, "P2.big5_openness": 6, "P3.impulse_control": 5, "P4.value_order": 8, "P5.adaptability": 4},
        "profile_b": {"P1.sleep_quality": 6, "P2.big5_openness": 5, "P3.impulse_control": 4, "P4.value_autonomy": 7, "P5.adaptability": 5},
        "roles_a": ["Leader"], "roles_b": ["Strategist"], "contexts": ["work"],
    })
    assert response.status_code == 200
    payload = response.json()
    assert payload["scientific_status"] == "IMPLEMENTATION_BASELINE"
    assert payload["authoritative_scalar"] is False
    contract = payload["input_contract"]
    assert contract["domains_supported"] == ["P1", "P2", "P3", "P4", "P5"]
    assert {item["domain"] for item in contract["profile_a_provenance"]} == {"P1", "P2", "P3", "P4", "P5"}
    assert payload["contexts"] == ["work"]


def test_canonical_compatibility_endpoint_rejects_unknown_ids_with_422():
    response = client.post("/compatibility/v2/canonical", json={"profile_a": {"P4.value_not_registered": 5}, "profile_b": {}})
    assert response.status_code == 422
    assert "not a registered Master Matrix item" in response.json()["detail"]


def test_canonical_compatibility_endpoint_rejects_bad_numeric_values_with_422():
    for invalid in (True, "5", 11, -1):
        response = client.post("/compatibility/v2/canonical", json={"profile_a": {"P1.sleep_quality": invalid}, "profile_b": {}})
        assert response.status_code == 422


def test_canonical_compatibility_endpoint_keeps_missing_data_unknown():
    response = client.post("/compatibility/v2/canonical", json={"profile_a": {"P1.sleep_quality": 7}, "profile_b": {"P1.recovery_index": 5}})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "PARTIAL"
    assert all(row["status"] == "UNKNOWN" for row in payload["rows"])


def test_legacy_compatibility_endpoint_remains_available():
    response = client.post("/compatibility", json={
        "bio_a": {"tempo": 8, "energy": 7, "reactivity": 3, "recovery": 6},
        "bio_b": {"tempo": 6, "energy": 7, "reactivity": 4, "recovery": 5},
        "values_a": {"Order": 8, "Autonomy": 3}, "values_b": {"Order": 7, "Autonomy": 4},
        "roles_a": ["Leader"], "roles_b": ["Strategist"],
    })
    assert response.status_code == 200
    payload = response.json()
    assert {"v1", "v2", "v3", "authoritative_scalar"} <= set(payload)


def test_canonical_endpoint_exposes_result_semantics_and_context_boundary():
    response = client.post("/compatibility/v2/canonical", json={
        "profile_a": {"P1.sleep_quality": 7},
        "profile_b": {"P1.sleep_quality": 5},
        "contexts": ["work"],
    })
    assert response.status_code == 200
    semantics = response.json()["result_semantics"]
    assert semantics["interpretation"] == "DESCRIPTIVE_ONLY"
    assert semantics["context_semantics"] == "ANNOTATION_ONLY"
    assert semantics["descriptive_row_count"] == 1
    assert semantics["heuristic_row_count"] == 0


def test_canonical_endpoint_exposes_heuristic_rule_catalog():
    response = client.post("/compatibility/v2/canonical", json={
        "profile_a": {"P4.value_order": 8, "P4.value_autonomy": 3},
        "profile_b": {"P4.value_order": 7, "P4.value_autonomy": 4},
    })
    assert response.status_code == 200
    payload = response.json()
    tension = next(row for row in payload["rows"] if row["kind"] == "VALUE_TENSION")
    rule = payload["rule_catalog"][tension["rule_id"]]
    assert rule["validation_status"] == "UNVALIDATED_HEURISTIC"
    assert rule["requires_human_review"] is True
    assert rule["context_sensitive"] is False


def test_canonical_endpoint_identifies_exact_rule_catalog_version_and_hash():
    response = client.post("/compatibility/v2/canonical", json={
        "profile_a": {"P4.value_order": 8, "P4.value_autonomy": 3},
        "profile_b": {"P4.value_order": 7, "P4.value_autonomy": 4},
    })
    assert response.status_code == 200
    payload = response.json()
    assert payload["rule_catalog_version"] == "1.0.0"
    assert len(payload["rule_catalog_hash"]) == 64
    assert payload["rule_catalog_hash"] == payload["rule_catalog_hash"].lower()
    canonical = dumps(payload["rule_catalog"], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    expected_hash = sha256(canonical.encode("utf-8")).hexdigest()
    assert payload["rule_catalog_hash"] == expected_hash



def test_rule_catalog_fingerprint_is_independent_of_assessment_inputs():
    first = client.post("/compatibility/v2/canonical", json={
        "profile_a": {"P4.value_order": 8, "P4.value_autonomy": 3},
        "profile_b": {"P4.value_order": 7, "P4.value_autonomy": 4},
        "roles_a": ["Leader"], "roles_b": ["Strategist"], "contexts": ["work"],
    })
    second = client.post("/compatibility/v2/canonical", json={
        "profile_a": {"P1.sleep_quality": 6},
        "profile_b": {"P1.sleep_quality": 2},
        "roles_a": ["Artist"], "roles_b": ["Mediator"], "contexts": ["family"],
    })
    assert first.status_code == second.status_code == 200
    first_payload, second_payload = first.json(), second.json()
    assert first_payload["rule_catalog"] == second_payload["rule_catalog"]
    assert first_payload["rule_catalog_hash"] == second_payload["rule_catalog_hash"]
