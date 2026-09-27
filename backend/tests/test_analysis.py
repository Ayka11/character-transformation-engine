from cte.analysis import QCStatus, descriptive, qc_values

def test_complete_values_pass_qc():
    assert qc_values([1,2,3],["a","b","c"]).status==QCStatus.PASS

def test_missing_values_are_not_silently_imputed():
    assert qc_values([1,None,3],["a","b","c"]).status==QCStatus.NOT_ESTIMABLE

def test_duplicate_ids_fail_qc():
    assert qc_values([1,2],["a","a"]).status==QCStatus.FAIL

def test_descriptive_result_has_derived_provenance():
    r=descriptive([2,4,6])
    assert r.mean==4
    assert r.provenance.tag.value=="DRV"
