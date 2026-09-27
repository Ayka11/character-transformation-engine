import tempfile
from pathlib import Path
from cte.persistence import SQLiteRuntimeStore

def test_snapshot_is_durable_and_immutable():
    with tempfile.TemporaryDirectory() as d:
        path=str(Path(d)/"runtime.sqlite3")
        first=SQLiteRuntimeStore(path)
        first.put_snapshot("graph","node-1",{"x":1},"1")
        second=SQLiteRuntimeStore(path)
        assert second.get_snapshot("graph","node-1").payload=={"x":1}
        try:
            second.put_snapshot("graph","node-1",{"x":2},"1")
        except ValueError as e:
            assert "immutable" in str(e)
        else:
            assert False

def test_event_append_is_durable():
    with tempfile.TemporaryDirectory() as d:
        store=SQLiteRuntimeStore(str(Path(d)/"runtime.sqlite3"))
        store.append_event("e1","orchestrator","START",{"x":1},input_hash="i")
        reopened=SQLiteRuntimeStore(store.path)
        assert reopened.list_events("orchestrator")[0]["event_id"]=="e1"
