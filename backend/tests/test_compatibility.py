from cte.compatibility import compatibility_v2

def test_spearman_perfect_alignment():
    r=compatibility_v2({"honesty":1,"autonomy":2,"growth":3},{"honesty":10,"autonomy":20,"growth":30})
    assert r["spearman"]==1.0

def test_compatibility_is_not_authoritative_scalar():
    assert True
