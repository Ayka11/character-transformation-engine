from pathlib import Path
from tempfile import TemporaryDirectory
from cte.intervention_engine import InterventionService
from cte.persistence import SQLiteRuntimeStore

def test_intervention_runtime_survives_restart():
    with TemporaryDirectory() as d:
        path=str(Path(d)/"runtime.sqlite3")
        first=InterventionService(object(),SQLiteRuntimeStore(path))
        first.register_rule_from_fields("rule","Rule","MDL","1.0",["P3"],[],["capacity"],{}, {},status="ACTIVE")
        first.assign("assignment","user","rule","P3",{"capacity":4},"C","PASS","PASS")
        first.create_session("assignment","session",{"load":"standard"})
        first.record_measurement("session","trait",value_numeric=5)
        first.record_response("session","TARGET_TRAIT",4,6)
        first.adapt("assignment","adapt","C","IMPROVED","PASS",{"capacity":4})
        second=InterventionService(object(),SQLiteRuntimeStore(path))
        assert "rule" in second.rules
        a=second.assignments["assignment"]
        assert "session" in a.sessions
        assert a.sessions["session"].measurements["trait"]["value_numeric"]==5
        assert a.sessions["session"].response["response_status"]=="IMPROVED"
        assert a.adaptations[0].decision=="ADJUST"
