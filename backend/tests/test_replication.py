from cte.replication import register_generalization, register_replication

def test_replication_record_carries_gate_flags():
    x=register_replication("rep","result",independent=True,criteria_registered=True)
    assert x.independent and x.criteria_registered

def test_generalization_requires_target_context():
    try:
        register_generalization("gen","result",run_status="COMPLETED",target_population_context=" ")
    except ValueError:
        assert True
    else:
        assert False
