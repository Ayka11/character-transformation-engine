from pathlib import Path
from tempfile import TemporaryDirectory
from cte.evidence_graph import register_node, register_edge
from cte.graph_registry import build_registry
from cte.persistence import SQLiteRuntimeStore
from cte.reporting import SECTION_CODES, ReportService, register_spec

def _graph(store):
    g=build_registry(store)
    d=register_node("d","DATASET","d","DRV","1",{})
    a=register_node("a","ANALYSIS","a","DRV","1",{})
    r=register_node("r","RESULT","r","DRV","1",{"qc_status":"PASS","validated_descriptive_result":True})
    for n in (d,a,r): g.add_node(n)
    g.add_edge(register_edge("ed",a,d,"ANALYZED_FROM"))
    g.add_edge(register_edge("er",a,r,"RESULTS_IN"))
    g.register_claim("c","r","REGISTERED","DESCRIPTIVE_RESULT","DRV",{})
    return g

def test_report_spec_and_snapshot_survive_restart():
    with TemporaryDirectory() as d:
        path=str(Path(d)/"runtime.sqlite3")
        store=SQLiteRuntimeStore(path)
        g=_graph(store)
        first=ReportService(g,store)
        first.register_spec(register_spec("rs","Durable"))
        first.create("rr","rs","study",["r"])
        for i,code in enumerate(SECTION_CODES):
            first.add_section("rr",code,{"section":code},["r"],i)
        first.bind_claim("rr","c")
        first.qc_run("rr")
        first.publish("rr")
        second=ReportService(build_registry(SQLiteRuntimeStore(path)),SQLiteRuntimeStore(path))
        assert "rs" in second.specs
        assert second.runs["rr"].status=="PUBLISHED"
        assert second.runs["rr"].report_output_hash
