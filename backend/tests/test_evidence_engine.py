from cte.evidence_engine import register_criteria

def test_evidence_criteria_requires_rule():
    try:
        register_criteria("ec","claim",rule_ids=[],acceptance_rules={})
    except ValueError:
        assert True
    else:
        assert False

def test_evidence_criteria_is_not_evidence():
    x=register_criteria("ec","claim",rule_ids=["R1"],acceptance_rules={})
    assert x.provenance.tag.value=="DRV"
