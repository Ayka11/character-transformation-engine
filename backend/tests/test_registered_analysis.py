from cte.registered_analysis import lock_manifest, paired_effect

def test_manifest_locks_input_hash():
    m=lock_manifest([1,2,3],[2,3,5],manifest_id="m1",analysis_spec_id="v1.3-paired")
    assert m.n_complete==3
    assert m.values_hash

def test_hash_mismatch_is_blocked():
    m=lock_manifest([1,2],[2,3],manifest_id="m1",analysis_spec_id="v1.3-paired")
    try:
        paired_effect([1,2],[2,4],m)
        assert False
    except ValueError:
        assert True

def test_paired_effect_ci():
    m=lock_manifest([1,2,3,4],[2,4,4,7],manifest_id="m2",analysis_spec_id="v1.3-paired")
    r=paired_effect([1,2,3,4],[2,4,4,7],m)
    assert r.n==4
    assert r.mean_change==1.75
    assert r.ci95_low < r.mean_change < r.ci95_high
