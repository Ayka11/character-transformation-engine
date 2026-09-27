from cte.evidence_graph import register_node, register_edge
from cte.graph_registry import build_registry
from cte.reporting import SECTION_CODES, ReportService, register_spec as register_report_spec
from cte.orchestrator import OrchestratorService

def test_v19_synthetic_end_to_end_contract():
    graph=build_registry()
    dataset=register_node("dataset","DATASET","dataset","DRV","1",{})
    analysis=register_node("analysis","ANALYSIS","analysis","DRV","1",{})
    protocol=register_node("assoc-protocol","PROTOCOL","assoc-protocol","DRV","1",{"design_type":"ASSOCIATIONAL"})
    result=register_node("result","RESULT","result","DRV","1",{"qc_status":"PASS","validated_descriptive_result":True})
    replication=register_node("rep","REPLICATION","rep","DRV","1",{"independent":True,"criteria_registered":True,"assessment_status":"REPLICATED"})
    generalization=register_node("gen","GENERALIZATION","gen","DRV","1",{"run_status":"COMPLETED","result_status":"GENERALIZABLE","target_population_context":"declared-target"})
    criteria=register_node("criteria","PROTOCOL","criteria","DRV","1",{"kind":"EVIDENCE_CRITERIA","claim_id":"c4","rule_ids":["E1"]})
    for n in (dataset,analysis,protocol,result,replication,generalization,criteria): graph.add_node(n)
    graph.add_edge(register_edge("e1",analysis,dataset,"ANALYZED_FROM"))
    graph.add_edge(register_edge("e2",analysis,result,"RESULTS_IN"))
    graph.add_edge(register_edge("e3",analysis,protocol,"USES_PROTOCOL"))
    graph.add_edge(register_edge("e4",replication,result,"REPLICATES"))
    graph.add_edge(register_edge("e5",generalization,result,"GENERALIZES"))
    graph.add_edge(register_edge("e6",analysis,criteria,"USES_PROTOCOL"))

    graph.register_claim("c0",None,"HYPOTHESIS","REGISTERED","HYP",{})
    graph.register_claim("c1","result","REGISTERED","DESCRIPTIVE_RESULT","DRV",{},previous_claim_id="c0")
    graph.register_claim("c2","result","DESCRIPTIVE_RESULT","ASSOCIATIONAL_RESULT","DRV",{},previous_claim_id="c1")
    graph.register_claim("c3","result","ASSOCIATIONAL_RESULT","REPLICATED_RESULT","DRV",{},previous_claim_id="c2")
    graph.register_claim("c4","result","REPLICATED_RESULT","GENERALIZED_RESULT","DRV",{},previous_claim_id="c3")
    graph.register_claim("c5","result","GENERALIZED_RESULT","EVIDENCE_SUPPORTED","EVD",{},previous_claim_id="c4")

    reports=ReportService(graph)
    reports.specs["rs"]=register_report_spec("rs","Synthetic V1.9")
    report=reports.create("report","rs","study",["dataset","analysis","result","c5"])
    for i,code in enumerate(SECTION_CODES):
        reports.add_section("report",code,{"section":code},["result"],i)
    reports.bind_claim("report","c5")
    assert reports.qc_run("report")["status"]=="QC_PASSED"
    assert reports.publish("report").status=="PUBLISHED"

    orch=OrchestratorService()
    execution=orch.create_execution("execution","corr",{"fixture":"NON_EVIDENCE_TEST_FIXTURE"},["INTAKE","ASSESSMENT","SAFETY_GATE","REPORT"])
    orch.start("execution")
    orch.advance_stage("execution","INTAKE","PASSED",input_hash="i1",output_hash="o1",module_version="2.1",provenance_record_id="p1")
    orch.advance_stage("execution","ASSESSMENT","PASSED",input_hash="i2",output_hash="o2",module_version="2.1",provenance_record_id="p2")
    orch.advance_stage("execution","SAFETY_GATE","SKIPPED",reason="synthetic research-only fixture")
    orch.advance_stage("execution","REPORT","PASSED",input_hash="i4",output_hash=report.report_output_hash,module_version="1.6",provenance_record_id="p4")
    assert orch.complete("execution").state=="COMPLETED"
