from cte.assessment import build_measurement, build_profile

def test_observation_becomes_measurement_with_provenance():
    m = build_measurement("P1.sleep_quality", 7.5, source_id="assessment.demo", source_version="1.0", observation_id="obs-001")
    assert m.measurement_id == "obs-001:P1.sleep_quality"
    assert m.provenance.tag.value == "OBS"
    assert m.provenance.input_hash

def test_profile_keeps_domains_separate():
    profile = build_profile([
        {"item_id": "P1.sleep_quality", "value": 7, "observation_id": "o1"},
        {"item_id": "P2.big5_conscientiousness", "value": 8, "observation_id": "o2"},
        {"item_id": "P5.discipline_consistency", "value": 6, "observation_id": "o3"},
    ], source_id="assessment.demo", source_version="1.0")
    assert len(profile.by_domain("P1")) == 1
    assert len(profile.by_domain("P2")) == 1
    assert len(profile.by_domain("P5")) == 1

def test_out_of_range_is_rejected():
    try:
        build_measurement("P1.sleep_quality", 11, source_id="x", source_version="1", observation_id="o")
        assert False
    except ValueError:
        assert True

def test_unknown_item_is_rejected():
    try:
        build_measurement("P9.unknown", 5, source_id="x", source_version="1", observation_id="o")
        assert False
    except KeyError:
        assert True
