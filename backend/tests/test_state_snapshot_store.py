from cte.contracts.state import StateSnapshot
from cte.persistence import SQLiteRuntimeStore
from cte.state_snapshot_store import StateSnapshotStore

def test_snapshot_store_roundtrip_and_lineage():
    store=StateSnapshotStore(SQLiteRuntimeStore(":memory:"))
    s0=StateSnapshot.capture("s0","c1",0,{"tempo":5})
    s1=StateSnapshot.capture("s1","c1",1,{"tempo":6},parent_snapshot_id="s0",source_execution_id="e1")
    store.save(s0); store.save(s1)
    assert store.get("s1")==s1
    assert [s.snapshot_id for s in store.get_lineage("c1")]==["s0","s1"]
    assert store.verify("s1")

def test_snapshot_store_rejects_mutation_of_existing_snapshot():
    store=StateSnapshotStore(SQLiteRuntimeStore(":memory:"))
    s0=StateSnapshot.capture("s0","c1",0,{"tempo":5})
    store.save(s0)
    changed=StateSnapshot.capture("s0","c1",0,{"tempo":9})
    try:
        store.save(changed)
    except ValueError as exc:
        assert "immutable snapshot conflict" in str(exc)
    else:
        assert False

def test_snapshot_lineage_hash_changes_with_parent():
    a=StateSnapshot.capture("s1","c1",1,{"tempo":6},parent_snapshot_id="s0")
    b=StateSnapshot.capture("s1","c1",1,{"tempo":6},parent_snapshot_id="other")
    assert a.state_hash==b.state_hash
    assert a.lineage_hash!=b.lineage_hash

def test_atomic_before_after_snapshot_commit_rolls_back_on_conflict():
    db=SQLiteRuntimeStore(":memory:")
    store=StateSnapshotStore(db)
    before=StateSnapshot.capture("b","c",1,{"tempo":5})
    after=StateSnapshot.capture("a","c",2,{"tempo":6},parent_snapshot_id="b")
    store.save(after)
    bad=StateSnapshot.capture("b","c",1,{"tempo":99})
    try:
        store.save_pair_atomic(before,bad)
    except ValueError:
        pass
    else:
        assert False
    assert store.get("b") is None
    assert store.get("a") == after
