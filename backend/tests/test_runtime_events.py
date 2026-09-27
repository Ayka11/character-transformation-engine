from cte.runtime_events import make_event, lineage_descriptor

def test_runtime_event_is_derived_and_traceable():
    event=make_event('evt-1','OUTCOME_EVALUATED','exec-1',{'delta':1.0})
    assert event.provenance.tag.value=='DRV'
    assert lineage_descriptor(event)['execution_id']=='exec-1'
    assert lineage_descriptor(event)['input_hash']
