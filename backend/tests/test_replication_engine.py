from cte.replication_engine import evaluate_outcome, register_run, register_spec

def _run():
    s=register_spec("s","claim","outcome",{"effect_compatibility_rule":"relative_20pct"})
    return register_run("r",s,source_result_node_id="result",independent_study_id="study",
                        dataset_manifest_id="manifest",protocol_hash="ph",input_hash="ih",independent=True)

def test_replication_replicated_when_all_registered_dimensions_match():
    out=evaluate_outcome(_run(),source_estimate=1,target_estimate=1.1,source_effect_size=.5,
                         target_effect_size=.55,source_ci_low=.1,source_ci_high=.9,
                         target_ci_low=.2,target_ci_high=.8,protocol_fidelity=True,
                         measurement_fidelity=True,outcome_definition=True,data_quality=True)
    assert out.overall_outcome=="REPLICATED"

def test_replication_unknown_data_is_not_estimable():
    out=evaluate_outcome(_run(),source_estimate=1,target_estimate=None,source_effect_size=None,
                         target_effect_size=None)
    assert out.overall_outcome=="NOT_ESTIMABLE"

def test_non_independent_run_is_blocked():
    s=register_spec("s2","claim","outcome")
    try:
        register_run("r2",s,source_result_node_id="result",independent_study_id="study",
                     dataset_manifest_id="manifest",protocol_hash="ph",input_hash="ih",independent=False)
    except ValueError:
        assert True
    else:
        assert False


def test_replication_can_be_replicated_without_unregistered_ci_requirement():
    out=evaluate_outcome(_run(),source_estimate=1,target_estimate=1.1,source_effect_size=.5,
                         target_effect_size=.55,protocol_fidelity=True,
                         measurement_fidelity=True,outcome_definition=True,data_quality=True)
    assert out.overall_outcome=="REPLICATED"
