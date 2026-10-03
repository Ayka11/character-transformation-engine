from fastapi.testclient import TestClient

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
