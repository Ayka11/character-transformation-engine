from pathlib import Path
from tempfile import TemporaryDirectory

def test_research_registry_snapshots_are_restorable():
    from cte.evidence_graph import register_node
    from cte.graph_registry import build_registry
    from cte.persistence import SQLiteRuntimeStore
    with TemporaryDirectory() as d:
        path=str(Path(d)/"runtime.sqlite3")
        g=build_registry(SQLiteRuntimeStore(path))
        g.add_node(register_node("rs","PROTOCOL","rs","DRV","1",{"kind":"REPLICATION_SPEC","source_claim_id":"c","primary_outcome_id":"o","criteria":{"direction":"same"}}))
        g.add_node(register_node("rr","REPLICATION","rr","DRV","1",{"replication_spec_id":"rs","source_result_id":"result","independent_study_id":"study","dataset_manifest_id":"manifest","protocol_hash":"p","input_hash":"i","status":"REGISTERED"}))
        g2=build_registry(SQLiteRuntimeStore(path))
        assert g2.nodes["rs"].metadata["kind"]=="REPLICATION_SPEC"
        assert g2.nodes["rr"].metadata["replication_spec_id"]=="rs"
