from cte.evidence_graph import register_node, register_edge
from cte.graph_registry import build_registry
from cte.reporting import SECTION_CODES, ReportService, register_spec

def _service():
    g=build_registry()
    d=register_node("d","DATASET","d","DRV","1",{})
    a=register_node("a","ANALYSIS","a","DRV","1",{})
    r=register_node("r","RESULT","r","DRV","1",{"qc_status":"PASS","validated_descriptive_result":True})
    for n in (d,a,r): g.add_node(n)
    g.add_edge(register_edge("ed",a,d,"ANALYZED_FROM"))
    g.add_edge(register_edge("er",a,r,"RESULTS_IN"))
    g.register_claim("c1","r","REGISTERED","DESCRIPTIVE_RESULT","DRV",{"validated_descriptive_result":True})
    return ReportService(g)

def test_report_requires_source_artifacts_and_all_sections_for_publish():
    s=_service()
    s.specs["rs"]=register_spec("rs","Test")
    run=s.create("rr","rs","study-1",["r"])
    s.add_section("rr","LIMITATIONS_BOUNDARIES",{},["r"],12)
    qc=s.qc_run("rr")
    assert qc["status"]=="QC_FAILED"

def test_report_claim_binding_preserves_claim_language_rule():
    s=_service()
    s.specs["rs"]=register_spec("rs","Test")
    s.create("rr","rs","study-1",["r"])
    b=s.bind_claim("rr","c1")
    assert b.claim_status=="DESCRIPTIVE_RESULT"
    assert b.allowed_language_rule_id=="DESCRIPTIVE_STATUS"

def test_full_report_lifecycle_reaches_immutable_published_state():
    s=_service()
    s.specs["rs"]=register_spec("rs","Test")
    run=s.create("rr","rs","study-1",["r"])
    for i,code in enumerate(SECTION_CODES):
        s.add_section("rr",code,{"section":code},["r"],i)
    s.bind_claim("rr","c1")
    qc=s.qc_run("rr")
    assert qc["status"]=="QC_PASSED"
    published=s.publish("rr")
    assert published.status=="PUBLISHED"
    assert published.report_output_hash
    try:
        s.add_section("rr","EXECUTIVE_SUMMARY",{},["r"],0)
    except ValueError as e:
        assert "immutable" in str(e)
    else:
        assert False


def test_report_qc_fails_closed_when_section_source_node_is_missing():
    from cte.reporting import SECTION_CODES

    service = _service()
    service.specs["rs"] = register_spec("rs", "Missing source test")
    service.create("rr-missing-source", "rs", "study-1", ["r"])
    for ordinal, code in enumerate(SECTION_CODES):
        service.add_section("rr-missing-source", code, {"section": code}, ["r"], ordinal)

    # Simulate a damaged/reduced graph after report registration. QC must
    # report the missing lineage as a blocker instead of raising KeyError.
    del service.registry.nodes["r"]
    result = service.qc_run("rr-missing-source")

    assert result["status"] == "QC_FAILED"
    assert "SOURCE_MANIFEST" in result["blocking_checks"]
    assert "PROVENANCE" in result["blocking_checks"]
