from cte.longitudinal import longitudinal_change

def test_absolute_and_relative_change():
    r=longitudinal_change([2,4],[3,6])
    assert r.n==2
    assert r.absolute_change==1.5
    assert r.relative_change==0.5

def test_missing_pairs_are_not_imputed():
    r=longitudinal_change([2,None,4],[3,5,6])
    assert r.n==2
    assert "sensitivity" in " ".join(r.limitations)

def test_zero_baseline_relative_change_unknown():
    r=longitudinal_change([0,0],[1,2])
    assert r.relative_change is None
