from cte.evidence_graph import register_node, register_edge
from cte.graph_registry import build_registry
from cte.reporting import register_spec, ReportService

def _service():
    g=build_registry()
    d=register_node("d","DATASET","d","DRV","1",{})
    a=register_node("a","ANALYSIS","a","DRV","1",{})
    r=register_node("r","RESULT","r","DRV","1",{"qc_status":"PASS","validated_descriptive_result":True})
    for n in (d,a,r): g.add_node(n)
    g.add_edge(register_edge("ed",a,d,"ANALYZED_FROM"))
    g.add_edge(register_edge("er",a,r,"RESULTS_IN"))
    g.register_claim("c1","r","REGISTERED","DESCRIPTIVE_RESULT","DRV",{})
    s=ReportService(g)
    s.specs["rs"]=register_spec("rs","Test")
    return s

def test_publish_requires_qc():
    s=_service()
    s.create("rr","rs","study-1",["r"])
    try: s.publish("rr")
    except ValueError as e: assert "QC_PASSED" in str(e)
    else: assert False

def test_source_manifest_is_preserved():
    s=_service()
    r=s.create("rr","rs","study-1",["r"])
    assert r.source_artifacts==("r",)
    assert r.source_manifest_hash



def test_publish_endpoint_maps_snapshot_conflict_to_http_409(monkeypatch):
    from fastapi import FastAPI, HTTPException
    from cte.persistence import SQLiteRuntimeStore, SnapshotConflictError
    from cte.reporting_api import install_reporting_api

    app = FastAPI()
    service = install_reporting_api(app, build_registry(), SQLiteRuntimeStore(":memory:"))

    def conflict(_report_id):
        raise SnapshotConflictError("snapshot concurrent update conflict")

    monkeypatch.setattr(service, "publish", conflict)
    endpoint = next(
        route.endpoint for route in app.routes
        if getattr(route, "path", None) == "/reports/{report_id}/publish"
    )
    try:
        endpoint("report-1")
    except HTTPException as exc:
        assert exc.status_code == 409
        assert "concurrent update conflict" in exc.detail
    else:
        raise AssertionError("snapshot conflict must map to HTTP 409")
