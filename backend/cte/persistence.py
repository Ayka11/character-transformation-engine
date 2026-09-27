"""Durable SQLite runtime store.

This is a lightweight runtime persistence adapter for the executable baseline.
It does not replace the repository's PostgreSQL persistence contracts.
"""
from __future__ import annotations
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from .provenance import content_hash

MUTABLE_SNAPSHOT_NAMESPACES = {"orchestrator.execution", "intervention.assignment", "report.run"}

@dataclass(frozen=True)
class Snapshot:
    namespace:str
    key:str
    version:str
    payload:dict
    payload_hash:str

class SQLiteRuntimeStore:
    def __init__(self, path: str):
        if not path or path==":memory:":
            self.path=path
        else:
            p=Path(path)
            p.parent.mkdir(parents=True,exist_ok=True)
            self.path=str(p)
        self._initialize()

    def _connect(self):
        return sqlite3.connect(self.path)

    def _initialize(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS runtime_snapshots (
                    namespace TEXT NOT NULL,
                    key TEXT NOT NULL,
                    version TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (namespace,key)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS runtime_events (
                    event_id TEXT PRIMARY KEY,
                    namespace TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    input_hash TEXT,
                    output_hash TEXT,
                    provenance_record_id TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def put_snapshot(self, namespace:str, key:str, payload:dict, version:str)->Snapshot:
        payload_hash=content_hash(payload)
        with self._connect() as conn:
            row=conn.execute(
                "SELECT version,payload_hash FROM runtime_snapshots WHERE namespace=? AND key=?",
                (namespace,key)
            ).fetchone()
            if row is not None:
                if row[1] == payload_hash:
                    return Snapshot(namespace,key,row[0],payload,payload_hash)
                if namespace in MUTABLE_SNAPSHOT_NAMESPACES:
                    conn.execute(
                        "UPDATE runtime_snapshots SET version=?, payload_json=?, payload_hash=? WHERE namespace=? AND key=?",
                        (version,json.dumps(payload,sort_keys=True,separators=(",",":")),payload_hash,namespace,key)
                    )
                    conn.commit()
                    return Snapshot(namespace,key,version,payload,payload_hash)
                raise ValueError("immutable snapshot conflict")
            conn.execute(
                "INSERT INTO runtime_snapshots(namespace,key,version,payload_json,payload_hash) VALUES(?,?,?,?,?)",
                (namespace,key,version,json.dumps(payload,sort_keys=True,separators=(",",":")),payload_hash)
            )
            conn.commit()
        return Snapshot(namespace,key,version,payload,payload_hash)

    def get_snapshot(self, namespace:str, key:str)->Snapshot|None:
        with self._connect() as conn:
            row=conn.execute(
                "SELECT version,payload_json,payload_hash FROM runtime_snapshots WHERE namespace=? AND key=?",
                (namespace,key)
            ).fetchone()
        if row is None:
            return None
        return Snapshot(namespace,key,row[0],json.loads(row[1]),row[2])

    def list_snapshots(self, namespace:str)->list[Snapshot]:
        with self._connect() as conn:
            rows=conn.execute(
                "SELECT key,version,payload_json,payload_hash FROM runtime_snapshots WHERE namespace=? ORDER BY key",
                (namespace,)
            ).fetchall()
        return [Snapshot(namespace,k,v,json.loads(p),h) for k,v,p,h in rows]

    def append_event(self,event_id:str,namespace:str,event_type:str,payload:dict,
                     input_hash:str|None=None,output_hash:str|None=None,
                     provenance_record_id:str|None=None)->None:
        with self._connect() as conn:
            row=conn.execute("SELECT input_hash,output_hash,payload_json FROM runtime_events WHERE event_id=?",(event_id,)).fetchone()
            if row is not None:
                same=(row[0]==input_hash and row[1]==output_hash and json.loads(row[2])==payload)
                if not same:
                    raise ValueError("immutable event conflict")
                return
            conn.execute(
                "INSERT INTO runtime_events(event_id,namespace,event_type,payload_json,input_hash,output_hash,provenance_record_id) VALUES(?,?,?,?,?,?,?)",
                (event_id,namespace,event_type,json.dumps(payload,sort_keys=True,separators=(",",":")),input_hash,output_hash,provenance_record_id)
            )
            conn.commit()

    def list_events(self, namespace:str)->list[dict]:
        with self._connect() as conn:
            rows=conn.execute(
                "SELECT event_id,event_type,payload_json,input_hash,output_hash,provenance_record_id,created_at FROM runtime_events WHERE namespace=? ORDER BY created_at,event_id",
                (namespace,)
            ).fetchall()
        return [{"event_id":r[0],"event_type":r[1],"payload":json.loads(r[2]),
                 "input_hash":r[3],"output_hash":r[4],"provenance_record_id":r[5],"created_at":r[6]} for r in rows]
