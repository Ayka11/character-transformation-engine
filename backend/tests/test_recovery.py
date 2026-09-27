from cte.models import DailyState
from cte.recovery import (
    evaluate_recovery_gate,
    evaluate_bio_reset,
    build_recovery_plan,
    isolate_compromised_state_from_traits,
)

def state(**overrides):
    base=dict(
        sleep_quality=8,
        recovery_index=8,
        physical_activity=7,
        metabolic_stability=8,
        subjective_stress=2,
        subjective_energy=8,
    )
    base.update(overrides)
    return DailyState(**base)

def test_high_stress_forces_recovery_level_a():
    result=evaluate_recovery_gate(state(subjective_stress=8))
    assert result.level=="A"
    assert result.safety_block
    assert result.compromised_state
    assert "subjective_stress>=8" in result.trigger_reasons

def test_low_capacity_forces_recovery_level_a():
    result=evaluate_recovery_gate(state(subjective_energy=6,subjective_stress=4,recovery_index=0))
    assert result.level=="A"
    assert result.safety_block
    assert "capacity<3" in result.trigger_reasons or "capacity_level=A" in result.trigger_reasons

def test_three_consecutive_days_below_40_percent_trigger_bio_reset():
    result=evaluate_bio_reset([3.9,3.5,3.0])
    assert result.triggered
    assert result.consecutive_low_recovery_days==3
    assert result.sprint_status=="PAUSED"

def test_nonconsecutive_low_recovery_does_not_trigger():
    result=evaluate_bio_reset([3.0,5.0,3.0,3.0])
    assert result.triggered is False

def test_missing_recovery_breaks_the_consecutive_streak():
    result=evaluate_bio_reset([3.0,None,3.0,3.0])
    assert result.triggered is False

def test_recovery_plan_uses_5_to_30_second_micro_action_window():
    result=build_recovery_plan(state(subjective_stress=9))
    assert result.mode=="BIO_RESET_DETOX"
    assert result.sprint_status=="PAUSED"
    assert result.level=="A"
    assert result.micro_action_seconds==(5,30)
    assert result.exclude_cognitively_costly_tests
    assert "reduce_incoming_stimuli" in result.actions

def test_compromised_state_is_separate_from_traits():
    result=isolate_compromised_state_from_traits("compromised")
    assert result.current_state=="compromised"
    assert result.trait_profile_mutable is False
    assert result.trait_values_untouched
    assert "must not be written back" in result.reason
