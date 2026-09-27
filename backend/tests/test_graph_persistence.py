from pathlib import Path
from tempfile import TemporaryDirectory
from cte.evidence_graph import register_node, register_edge
from cte.graph_registry import build_registry
from cte.persistence import SQLiteRuntimeStore

def test_graph_nodes_edges_and_claim_audit_survive_restart():
    with TemporaryDirectory() as d:
        store=SQLiteRuntimeStore(str(Path(d)/"runtime.sqlite3"))
        g=build_registry(store)
        dataset=register_node("d","DATASET","d","DRV","1",{})
        analysis=register_node("a","ANALYSIS","a","DRV","1",{})
        result=register_node("r","RESULT","r","DRV","1",{"qc_status":"PASS","validated_descriptive_result":True})
        for n in (dataset,analysis,result): g.add_node(n)
        g.add_edge(register_edge("ed",analysis,dataset,"ANALYZED_FROM"))
        g.add_edge(register_edge("er",analysis,result,"RESULTS_IN"))
        claim=g.register_claim("c","r","REGISTERED","DESCRIPTIVE_RESULT","DRV",{})
        g2=build_registry(SQLiteRuntimeStore(str(Path(d)/"runtime.sqlite3")))
        assert {"d","a","r","c"} <= set(g2.nodes)
        assert {"ed","er","c:supports:r"} <= set(g2.edges)
        assert any(e.edge_id=="c:supports:r" for e in g2.claim_audit("c"))

def test_contradiction_and_inference_rules_survive_restart():
    with TemporaryDirectory() as d:
        path=str(Path(d)/"runtime.sqlite3")
        g=build_registry(SQLiteRuntimeStore(path))
        claim=register_node("c","CLAIM","c","DRV","1",{"state":"REGISTERED","result_id":"r"})
        result=register_node("r","RESULT","r","DRV","1",{})
        for n in (claim,result): g.add_node(n)
        g.register_contradiction_set("cx","c",["r"],"CONFLICT")
        g.register_inference_block("ib","MODEL_OUTPUT","EVIDENCE_SUPPORTED","blocked","MODEL","RULE")
        g2=build_registry(SQLiteRuntimeStore(path))
        assert "cx" in g2.contradiction_sets
        assert "ib" in g2.inference_blocks
