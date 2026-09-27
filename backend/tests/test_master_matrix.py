from cte.master_matrix import ADAPTIVE_LEVELS, MASTER_MATRIX, MATRIX_VERSION, SPRINT_TEMPLATE, get_matrix_item, matrix_summary


def test_master_matrix_has_all_five_domains():
    assert {item.domain for item in MASTER_MATRIX} == {"P1", "P2", "P3", "P4", "P5"}
    assert len(MASTER_MATRIX) == 30


def test_state_trait_separation_is_explicit():
    assert all(item.kind == "state" for item in MASTER_MATRIX if item.domain == "P1")
    assert all(item.kind == "trait" for item in MASTER_MATRIX if item.domain == "P2")


def test_expected_core_items_exist():
    assert get_matrix_item("P1.sleep_quality").name == "Sleep Quality"
    assert get_matrix_item("P2.big5_conscientiousness").name == "Conscientiousness"
    assert get_matrix_item("P3.pause_capacity").name == "Pause Capacity"
    assert get_matrix_item("P4.growth" if False else "P4.value_growth").name == "Growth"
    assert get_matrix_item("P5.boundary_setting").name == "Boundary Setting"


def test_every_item_has_provenance_tag():
    allowed = {"EVD", "MDL", "HYP", "RPT", "DRV", "OBS", "EXT", "EXP"}
    assert all(item.provenance_tag in allowed for item in MASTER_MATRIX)


def test_adaptive_levels_and_sprint_contract():
    assert tuple(ADAPTIVE_LEVELS) == ("A", "B", "C", "D", "E")
    assert SPRINT_TEMPLATE["duration_days"] == 21
    assert SPRINT_TEMPLATE["safety_precedes_promotion"] is True


def test_summary_is_versioned():
    summary = matrix_summary()
    assert summary["version"] == MATRIX_VERSION == "1.0"
    assert summary["total_items"] == 30
