from pathlib import Path
from tempfile import TemporaryDirectory
from cte.orchestrator import OrchestratorService
from cte.persistence import SQLiteRuntimeStore

def test_orchestrator_execution_and_events_survive_restart():
    with TemporaryDirectory() as d:
        path=str(Path(d)/"runtime.sqlite3")
        store=SQLiteRuntimeStore(path)
        first=OrchestratorService(store)
        first.create_execution("x","corr",{"input":1},["INTAKE"])
        first.start("x")
        first.advance_stage("x","INTAKE","PASSED",input_hash="i",output_hash="o",module_version="1.8",provenance_record_id="p")
        second=OrchestratorService(SQLiteRuntimeStore(path))
        assert second.executions["x"].state=="RUNNING"
        assert second.executions["x"].stages["INTAKE"].state=="PASSED"
        assert any(e.event_type=="EXECUTION_STARTED" for e in second.executions["x"].events)

def test_orchestrator_resume_persists_after_restart():
    with TemporaryDirectory() as d:
        path=str(Path(d)/"runtime.sqlite3")
        store=SQLiteRuntimeStore(path)
        first=OrchestratorService(store)
        first.create_execution("x","corr",{},["INTAKE"])
        first.start("x")
        first.pause("x","temporary condition")
        second=OrchestratorService(SQLiteRuntimeStore(path))
        second.resume("x",True)
        third=OrchestratorService(SQLiteRuntimeStore(path))
        assert third.executions["x"].state=="RUNNING"

def test_blocked_state_is_persisted_before_restart():
    with TemporaryDirectory() as d:
        path=str(Path(d)/"runtime.sqlite3")
        first=OrchestratorService(SQLiteRuntimeStore(path))
        first.create_execution("x","corr",{},["INTAKE"])
        first.start("x")
        first.advance_stage("x","INTAKE","BLOCKED",reason="blocked",metadata={})
        second=OrchestratorService(SQLiteRuntimeStore(path))
        assert second.executions["x"].state=="BLOCKED"

def test_orchestrator_registries_survive_restart():
    with TemporaryDirectory() as d:
        path=str(Path(d)/"runtime.sqlite3")
        first=OrchestratorService(SQLiteRuntimeStore(path))
        first.register_module("m","1.0","1.8")
        first.register_schema("s","1.0","backward-compatible")
        first.register_rule("r","1.0","MDL")
        second=OrchestratorService(SQLiteRuntimeStore(path))
        assert second.modules["m"].version=="1.0"
        assert second.schemas["s"].compatibility_policy=="backward-compatible"
        assert second.rules["r"].provenance_class=="MDL"
