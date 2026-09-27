from cte.evidence_graph import register_node, register_edge
from cte.graph_registry import build_registry

def test_unresolved_contradiction_opens_contradicted_state():
    g=build_registry()
    r=register_node("r","RESULT","r","DRV","1",{"qc_status":"PASS"})
    a=register_node("a","ANALYSIS","a","DRV","1",{})
    d=register_node("d","DATASET","d","DRV","1",{})
    for n in (r,a,d): g.add_node(n)
    g.add_edge(register_edge("ed",a,d,"ANALYZED_FROM"))
    g.add_edge(register_edge("er",a,r,"RESULTS_IN"))
    g.register_claim("c1","r","REGISTERED","DESCRIPTIVE_RESULT","DRV",{})
    g.register_contradiction_set("cx","c1",["r"],"MATERIAL_RESULT_CONFLICT","UNRESOLVED")
    c2=g.register_claim("c2","r","DESCRIPTIVE_RESULT","CONTRADICTED","DRV",{},previous_claim_id="c1")
    assert c2.metadata["state"]=="CONTRADICTED"

def test_indeterminate_requires_registered_insufficient_information():
    g=build_registry()
    r=register_node("r","RESULT","r","DRV","1",{"qc_status":"NOT_ESTIMABLE","insufficient_information":True})
    a=register_node("a","ANALYSIS","a","DRV","1",{})
    d=register_node("d","DATASET","d","DRV","1",{})
    for n in (r,a,d): g.add_node(n)
    g.add_edge(register_edge("ed",a,d,"ANALYZED_FROM"))
    g.add_edge(register_edge("er",a,r,"RESULTS_IN"))
    g.register_claim("c1","r","REGISTERED","INDETERMINATE","DRV",{})
    assert g.nodes["c1"].metadata["state"]=="INDETERMINATE"

def test_inference_block_prevents_model_output_evidence_transition():
    g=build_registry()
    r=register_node("r","RESULT","r","DRV","1",{"qc_status":"PASS","inference_type":"MODEL_OUTPUT"})
    a=register_node("a","ANALYSIS","a","DRV","1",{})
    d=register_node("d","DATASET","d","DRV","1",{})
    for n in (r,a,d): g.add_node(n)
    g.add_edge(register_edge("ed",a,d,"ANALYZED_FROM"))
    g.add_edge(register_edge("er",a,r,"RESULTS_IN"))
    g.register_inference_block("ib","MODEL_OUTPUT","EVIDENCE_SUPPORTED","model output to evidence","MODEL_OUTPUT_REQUIRES_EVIDENCE","V1.4-BLOCK")
    try:
        g.register_claim("c","r","GENERALIZED_RESULT","EVIDENCE_SUPPORTED","EVD",{})
    except ValueError as e:
        assert "V1.4-BLOCK" in str(e)
    else:
        assert False
