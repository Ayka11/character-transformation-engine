"""Executable V1.9 integrity smoke runner.

Runs deterministic contract checks in-process without requiring pytest.
This is a test harness, not scientific validation.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from .evidence_graph import register_node, register_edge
from .graph_registry import build_registry
from .orchestrator import OrchestratorService
from .persistence import SQLiteRuntimeStore
from .reporting import SECTION_CODES, ReportService, register_spec as register_report_spec

@dataclass(frozen=True)
class IntegrityCheck:
    check_id:str
    status:str
    message:str

def _check(check_id,fn):
    try:
        fn()
        return IntegrityCheck(check_id,"PASS","contract check passed")
    except Exception as exc:
        return IntegrityCheck(check_id,"FAIL",str(exc))

def run_v19_integrity_suite() -> dict:
    checks=[]
    def provenance_hash():
        n1=register_node("n","RESULT","n","DRV","1",{"x":1})
        n2=register_node("n","RESULT","n","DRV","1",{"x":2})
        if n1.immutable_hash==n2.immutable_hash: raise AssertionError("hash did not change")
    checks.append(_check("PROVENANCE_HASHING",provenance_hash))

    def graph_lineage():
        g=build_registry()
        d=register_node("d","DATASET","d","DRV","1",{})
        a=register_node("a","ANALYSIS","a","DRV","1",{})
        r=register_node("r","RESULT","r","DRV","1",{"qc_status":"PASS","validated_descriptive_result":True})
        for n in (d,a,r): g.add_node(n)
        g.add_edge(register_edge("ed",a,d,"ANALYZED_FROM"))
        g.add_edge(register_edge("er",a,r,"RESULTS_IN"))
        g.require_lineage_for_result("r")
    checks.append(_check("RESULT_LINEAGE",graph_lineage))

    def claim_guard():
        g=build_registry()
        d=register_node("d","DATASET","d","DRV","1",{})
        a=register_node("a","ANALYSIS","a","DRV","1",{})
        r=register_node("r","RESULT","r","DRV","1",{"qc_status":"PASS","validated_descriptive_result":True})
        rep=register_node("rep","REPLICATION","rep","DRV","1",{"independent":True,"criteria_registered":True,"assessment_status":"REPLICATED"})
        gen=register_node("gen","GENERALIZATION","gen","DRV","1",{"run_status":"COMPLETED","result_status":"GENERALIZABLE","target_population_context":"target"})
        crit=register_node("crit","PROTOCOL","crit","DRV","1",{"kind":"EVIDENCE_CRITERIA","claim_id":"c4"})
        for n in (d,a,r,rep,gen,crit): g.add_node(n)
        g.add_edge(register_edge("ed",a,d,"ANALYZED_FROM")); g.add_edge(register_edge("er",a,r,"RESULTS_IN"))
        g.add_edge(register_edge("rp",rep,r,"REPLICATES")); g.add_edge(register_edge("ge",gen,r,"GENERALIZES"))
        g.add_edge(register_edge("ec",a,crit,"USES_PROTOCOL"))
        g.register_claim("c0",None,"HYPOTHESIS","REGISTERED","HYP",{})
        g.register_claim("c1","r","REGISTERED","DESCRIPTIVE_RESULT","DRV",{},previous_claim_id="c0")
        g.register_claim("c2","r","DESCRIPTIVE_RESULT","ASSOCIATIONAL_RESULT","DRV",{},previous_claim_id="c1")
        g.register_claim("c3","r","ASSOCIATIONAL_RESULT","REPLICATED_RESULT","DRV",{},previous_claim_id="c2")
        g.register_claim("c4","r","REPLICATED_RESULT","GENERALIZED_RESULT","DRV",{},previous_claim_id="c3")
    checks.append(_check("CLAIM_PROMOTION_GATES",claim_guard))

    def report_publish():
        g=build_registry()
        d=register_node("d","DATASET","d","DRV","1",{})
        a=register_node("a","ANALYSIS","a","DRV","1",{})
        r=register_node("r","RESULT","r","DRV","1",{"qc_status":"PASS","validated_descriptive_result":True})
        for n in (d,a,r): g.add_node(n)
        g.add_edge(register_edge("ed",a,d,"ANALYZED_FROM")); g.add_edge(register_edge("er",a,r,"RESULTS_IN"))
        g.register_claim("c0","r","REGISTERED","DESCRIPTIVE_RESULT","DRV",{})
        service=ReportService(g); service.specs["rs"]=register_report_spec("rs","Integrity")
        service.create("rep","rs","study",["d","a","r"])
        for i,code in enumerate(SECTION_CODES): service.add_section("rep",code,{"section":code},["r"],i)
        service.bind_claim("rep","c0")
        if service.qc_run("rep")["status"]!="QC_PASSED": raise AssertionError("report QC did not pass")
        if service.publish("rep").status!="PUBLISHED": raise AssertionError("report did not publish")
    checks.append(_check("REPORT_QC_PUBLISH",report_publish))

    def orchestrator():
        with __import__("tempfile").TemporaryDirectory() as d:
            path=f"{d}/runtime.sqlite3"
            o=OrchestratorService(SQLiteRuntimeStore(path))
            o.create_execution("x","c",{"fixture":"NON_EVIDENCE_TEST_FIXTURE"},["INTAKE"])
            o.start("x")
            o.advance_stage("x","INTAKE","PASSED",input_hash="i",output_hash="o",module_version="1.8",provenance_record_id="p")
            o.complete("x")
            if OrchestratorService(SQLiteRuntimeStore(path)).executions["x"].state!="COMPLETED":
                raise AssertionError("completion did not persist")
    checks.append(_check("ORCHESTRATOR_PERSISTENCE",orchestrator))

    passed=sum(1 for c in checks if c.status=="PASS")
    failed=len(checks)-passed
    return {"suite":"V1.9_INTEGRITY_SYNTHETIC","status":"PASS" if failed==0 else "FAIL",
            "passed":passed,"failed":failed,"checks":[asdict(c) for c in checks],
            "scientific_status":"NOT_VALIDATION"}
