from pathlib import Path
from tempfile import TemporaryDirectory
from cte.evidence_graph import register_node, register_edge
from cte.graph_registry import build_registry
from cte.intervention_engine import InterventionService
from cte.persistence import SQLiteRuntimeStore
from cte.reporting import ReportService, register_spec

def _graph(store):
    g=build_registry(store)
    d=register_node("d","DATASET","d","DRV","1",{})
    a=register_node("a","ANALYSIS","a","DRV","1",{})
    r=register_node("r","RESULT","r","DRV","1",{"qc_status":"PASS","validated_descriptive_result":True})
    for n in (d,a,r): g.add_node(n)
    g.add_edge(register_edge("ed",a,d,"ANALYZED_FROM"))
    g.add_edge(register_edge("er",a,r,"RESULTS_IN"))
    return g

def test_report_execution_id_requires_registered_orchestrator_execution():
    with TemporaryDirectory() as d:
        store=SQLiteRuntimeStore(str(Path(d)/"runtime.sqlite3"))
        service=ReportService(_graph(store),store)
        service.register_spec(register_spec("rs","Test"))
        try:
            service.create("rr","rs","study",["r"],execution_id="missing")
        except ValueError as e:
            assert "orchestrator" in str(e)
        else:
            assert False

def test_intervention_execution_id_requires_registered_orchestrator_execution():
    with TemporaryDirectory() as d:
        store=SQLiteRuntimeStore(str(Path(d)/"runtime.sqlite3"))
        service=InterventionService(_graph(store),store)
        service.register_rule_from_fields("rule","Rule","MDL","1.0",["P3"],[],["capacity"],{}, {},status="ACTIVE")
        try:
            service.assign("a","u","rule","P3",{"capacity":4},"C","PASS","PASS",execution_id="missing")
        except ValueError as e:
            assert "orchestrator" in str(e)
        else:
            assert False
