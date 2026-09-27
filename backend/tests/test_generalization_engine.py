from cte.generalization_engine import evaluate, register_run, register_spec

def _run():
    s=register_spec("gs","claim",source_population={"n":1},target_population={"n":2},
                    source_context={"site":"A"},target_context={"site":"B"})
    return register_run("gr",s,source_result_node_id="result",dataset_manifest_id="manifest",
                        transport_analysis_version="1.5",input_hash="ih")

def test_generalization_generalizable_when_declared_dimensions_are_low_or_unknown_free():
    out=evaluate(_run(),source_estimate=1,transported_estimate=1.05,transport_error=.05,
                 dimensions={k:"LOW" for k in ["population","context","task","measurement","intervention","time","data_quality"]})
    assert out.result_status=="GENERALIZABLE"

def test_generalization_high_transport_blocks():
    out=evaluate(_run(),source_estimate=1,transported_estimate=1.1,transport_error=.05,
                 dimensions={"population":"HIGH"})
    assert out.result_status=="NOT_GENERALIZABLE"

def test_generalization_missing_estimate_is_not_estimable():
    out=evaluate(_run(),source_estimate=None,transported_estimate=None)
    assert out.result_status=="NOT_ESTIMABLE"
