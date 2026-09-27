from cte.claim_gate import validate_claim_transition

def test_descriptive_claim_requires_result():
    assert validate_claim_transition("REGISTERED","DESCRIPTIVE_RESULT",{"RESULT"})["allowed"]

def test_intervention_requires_protocol():
    try: validate_claim_transition("DESCRIPTIVE_RESULT","INTERVENTION_RESULT",{"RESULT"})
    except ValueError as e: assert "PROTOCOL" in str(e)
    else: assert False

def test_generalized_requires_replication_and_generalization():
    try: validate_claim_transition("REPLICATED_RESULT","GENERALIZED_RESULT",{"RESULT","REPLICATION"})
    except ValueError as e: assert "GENERALIZATION" in str(e)
    else: assert False

def test_evidence_supported_requires_evd():
    try: validate_claim_transition("GENERALIZED_RESULT","EVIDENCE_SUPPORTED",{"RESULT","REPLICATION","GENERALIZATION"},"DRV")
    except ValueError: assert True
    else: assert False
