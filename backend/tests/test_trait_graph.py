from cte.trait_graph import TraitGraph

def test_downstream_and_bottleneck():
    g=TraitGraph({"social_courage":["evaluation_fear"],"evaluation_fear":["avoidance"]})
    assert "avoidance" in g.downstream("social_courage")
    assert g.find_intervention_target("social_courage",{"evaluation_fear":0.2,"avoidance":0.8})=="evaluation_fear"
