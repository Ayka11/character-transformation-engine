from cte.result_node import build_result, graph_node

def test_result_is_graph_ready_but_not_evidence():
    r=build_result(result_id="r1",analysis_id="a1",manifest_id="m1",analysis_spec_id="v1.3-paired",qc_status="PASS",n=4,estimate=1.75,ci95_low=1.0,ci95_high=2.5)
    n=graph_node(r)
    assert n["node_type"]=="RESULT"
    assert n["provenance_class"]=="DRV"
    assert n["metadata_json"]["manifest_id"]=="m1"
