from cte.compatibility import compatibility_report, compatibility_v1, compatibility_v2, compatibility_v3

def test_v1_reports_named_deltas_and_missing_dimensions():
    r=compatibility_v1(
        {"tempo":8,"energy":7,"reactivity":3,"recovery":6},
        {"tempo":5,"energy":9,"reactivity":6,"recovery":4},
    )
    assert r["status"]=="ESTIMATED"
    assert r["dimensions"]["tempo"]["delta"]==3
    assert r["dimensions"]["energy"]["absolute_delta"]==2
    assert r["dimensions"]["reactivity"]["delta"]==-3
    assert r["dimensions"]["recovery"]["delta"]==2
    assert r["provenance"].tag.value=="DRV"

def test_v1_can_use_master_matrix_aliases():
    r=compatibility_v1(
        {"subjective_energy":8,"recovery_index":6},
        {"subjective_energy":7,"recovery_index":5},
    )
    assert r["dimensions"]["energy"]["delta"]==1
    assert r["dimensions"]["recovery"]["delta"]==1
    assert "tempo" in r["missing_a"]

def test_spearman_perfect_alignment_and_value_map():
    r=compatibility_v2(
        {"Honesty":1,"Autonomy":2,"Growth":3},
        {"Honesty":10,"Autonomy":20,"Growth":30},
    )
    assert r["spearman"]==1.0
    assert len(r["top_alignments"])==3
    assert len(r["value_gaps"])==3

def test_value_conflict_zone_is_explicitly_heuristic():
    r=compatibility_v2(
        {"Order":9,"Autonomy":2},
        {"Order":8,"Autonomy":3},
    )
    assert r["conflict_zones"][0]["status"]=="POTENTIAL_CONFLICT"
    assert r["provenance"].tag.value=="DRV"

def test_v3_identifies_synergy_and_competition_without_scalar():
    r=compatibility_v3({"Leader"},{"Strategist","Leader"})
    assert any(x["interaction"]=="SYNERGY" for x in r["synergies"])
    assert any(x["interaction"]=="COMPETITION" for x in r["competition"])

def test_report_contains_three_vectors_and_scenarios():
    r=compatibility_report(
        {"tempo":8,"energy":7,"reactivity":3,"recovery":6},
        {"tempo":4,"energy":7,"reactivity":4,"recovery":6},
        {"Order":9,"Autonomy":2},
        {"Order":8,"Autonomy":3},
        ["Leader"],
        ["Leader"],
    )
    assert set(r)=={"version","v1","v2","v3","scenarios","authoritative_scalar","scientific_status","provenance_tag","provenance"}
    assert r["authoritative_scalar"] is False
    assert any(s["intervention"]=="24-hour decision buffer" for s in r["scenarios"])
    assert any(s["scenario"]=="ROLE_COMPETITION" for s in r["scenarios"])
