from cte.claim_state_machine import validate_transition

def test_v14_valid_transition():
    out=validate_transition("REGISTERED","ASSOCIATIONAL_RESULT",{"registered_analysis","valid_result","association_design"})
    assert out["allowed"]

def test_v14_blocks_direct_evidence_supported():
    try: validate_transition("REGISTERED","EVIDENCE_SUPPORTED",set())
    except ValueError: assert True
    else: assert False

def test_v14_requires_generalization():
    try: validate_transition("REPLICATED_RESULT","GENERALIZED_RESULT",{"generalization_run"})
    except ValueError as e: assert "target_population_context" in str(e)
    else: assert False

def test_v14_terminal_states_have_explicit_requirements():
    assert validate_transition("GENERALIZED_RESULT","INDETERMINATE",{"insufficient_or_conflicting_information"})["allowed"]
    assert validate_transition("GENERALIZED_RESULT","CONTRADICTED",{"unresolved_material_contradiction"})["allowed"]
