""""Durable SQLite runtime store.

This is a lightweight runtime persistence adapter for the executable baseline.
It does not replace the repository's PostgreSQL persistence contracts.
"""
from __future__ import annotations
import json
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path
from .provenance import content_hash, json_safe

MUTABLE_SNAPSHOT_NAMESPACES = {"orchestrator.execution", "intervention.assignment", "report.run", "research.study", "research.experiment", "research.participant", "research.assignment", "research.analysis", "science_lab.matrix", "science_lab.run", "integration.mutable"}

@dataclass(frozen=True)
class Snapshot:
    namespace:str
    key:str
    version:str
    payload:dict
    payload_hash:str

def build_runtime_store(sqlite_path: str = "data/cte-runtime.sqlite3"):
    """Create the configured durable store.
    CTE_DATABASE_URL selects the PostgreSQL production adapter; otherwise SQLite is used.
    """
    import os
    dsn=os.getenv("CTE_DATABASE_URL")
    if dsn:
        from .postgres_persistence import PostgreSQLRuntimeStore
        return PostgreSQLRuntimeStore(dsn)
    return SQLiteRuntimeStore(os.getenv("CTE_RUNTIME_DB", sqlite_path))

class SQLiteRuntimeStore:
    def __init__(self, path: str):
        # The store opens a fresh connection for each operation. A normal
        # SQLite :memory: database is therefore destroyed between connections.
        # Use an isolated temporary file for test/runtime callers requesting
        # in-memory semantics so all connections share the same database.
        self._temporary_path = None
        if not path or path == ":memory:":
            fd, temp_path = tempfile.mkstemp(prefix="cte-runtime-", suffix=".sqlite3")
            import os
            os.close(fd)
            self._temporary_path = temp_path
            self.path = temp_path
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
        payload=json_safe(payload)
        payload_hash=content_hash(payload)
        payload=json_safe(payload)
        payload_json=json.dumps(payload,sort_keys=True,separators=(",",":"))
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO runtime_snapshots(namespace,key,version,payload_json,payload_hash) VALUES(?,?,?,?,?)",
                (namespace,key,version,payload_json,payload_hash)
            )
            row=conn.execute(
                "SELECT version,payload_json,payload_hash FROM runtime_snapshots WHERE namespace=? AND key=?",
                (namespace,key)
            ).fetchone()
            if row is None:
                raise ValueError("snapshot disappeared during write")
            if row[2] == payload_hash:
                if row[0] == version:
                    return Snapshot(namespace,key,row[0],payload,row[2])
                if namespace in MUTABLE_SNAPSHOT_NAMESPACES:
                    conn.execute(
                        "UPDATE runtime_snapshots SET version=? WHERE namespace=? AND key=?",
                        (version,namespace,key)
                    )
                    conn.commit()
                    return Snapshot(namespace,key,version,payload,payload_hash)
                raise ValueError("immutable snapshot conflict")
            if namespace in MUTABLE_SNAPSHOT_NAMESPACES:
                conn.execute(
                    "UPDATE runtime_snapshots SET version=?, payload_json=?, payload_hash=? WHERE namespace=? AND key=?",
                    (version,payload_json,payload_hash,namespace,key)
                )
                conn.commit()
                return Snapshot(namespace,key,version,payload,payload_hash)
            raise ValueError("immutable snapshot conflict")

    def put_snapshot_if_hash(
        self, namespace: str, key: str, payload: dict, version: str,
        *, expected_hash: str | None,
    ) -> Snapshot:
        """Compare-and-swap a snapshot, rejecting stale writers."""
        payload = json_safe(payload)
        payload_hash = content_hash(payload)
        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        with self._connect() as conn:
            if expected_hash is None:
                try:
                    conn.execute(
                        "INSERT INTO runtime_snapshots(namespace,key,version,payload_json,payload_hash) VALUES(?,?,?,?,?)",
                        (namespace, key, version, payload_json, payload_hash),
                    )
                except sqlite3.IntegrityError as exc:
                    raise ValueError("snapshot concurrent update conflict") from exc
            else:
                cursor = conn.execute(
                    """UPDATE runtime_snapshots
                       SET version=?, payload_json=?, payload_hash=?
                       WHERE namespace=? AND key=? AND payload_hash=?""",
                    (version, payload_json, payload_hash, namespace, key, expected_hash),
                )
                if cursor.rowcount != 1:
                    raise ValueError("snapshot concurrent update conflict")
            conn.commit()
        return Snapshot(namespace, key, version, payload, payload_hash)

    def put_snapshots_atomic(self, items:list[tuple[str,str,dict,str]])->list[Snapshot]:
        """Insert immutable snapshots atomically; identical existing rows are idempotent."""
        prepared=[(ns,key,json_safe(payload),version,content_hash(payload)) for ns,key,payload,version in items]
        with self._connect() as conn:
            results=[]
            try:
                for namespace,key,payload,version,payload_hash in prepared:
                    row=conn.execute("SELECT version,payload_hash FROM runtime_snapshots WHERE namespace=? AND key=?",
                                     (namespace,key)).fetchone()
                    if row is not None:
                        if row[1] != payload_hash:
                            if namespace in MUTABLE_SNAPSHOT_NAMESPACES:
                                raise ValueError("atomic mutation of existing mutable snapshot is not supported")
                            raise ValueError("immutable snapshot conflict")
                        if row[0] != version:
                            raise ValueError("immutable snapshot conflict")
                        results.append(Snapshot(namespace,key,row[0],payload,payload_hash)); continue
                    conn.execute("INSERT INTO runtime_snapshots(namespace,key,version,payload_json,payload_hash) VALUES(?,?,?,?,?)",
                                 (namespace,key,version,json.dumps(payload,sort_keys=True,separators=(",",":")),payload_hash))
                    results.append(Snapshot(namespace,key,version,payload,payload_hash))
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return results

    def get_snapshot(self, namespace:str, key:str)->Snapshot|None:
        with self._connect() as conn:
            row=conn.execute(
                "SELECT version,payload_json,payload_hash FROM runtime_snapshots WHERE namespace=? AND key=?",
                (namespace,key)
            ).fetchone()
        if row is None:
            return None
        return Snapshot(namespace,key,row[0],json.loads(row[1]),row[2])

    def list_snapshot_namespaces(self) -> list[str]:
        with self._connect() as conn:
            rows=conn.execute("SELECT DISTINCT namespace FROM runtime_snapshots ORDER BY namespace").fetchall()
        return [row[0] for row in rows]

    def list_event_namespaces(self) -> list[str]:
        with self._connect() as conn:
            rows=conn.execute("SELECT DISTINCT namespace FROM runtime_events ORDER BY namespace").fetchall()
        return [row[0] for row in rows]

    def prune_events_before(self, cutoff: str, namespace: str | None = None) -> int:
        with self._connect() as conn:
            if namespace is None:
                cursor=conn.execute("DELETE FROM runtime_events WHERE created_at < ?", (cutoff,))
            else:
                cursor=conn.execute("DELETE FROM runtime_events WHERE created_at < ? AND namespace = ?", (cutoff, namespace))
            conn.commit()
            return cursor.rowcount

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
        payload_json=json.dumps(payload,sort_keys=True,separators=(",",":"))
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO runtime_events(event_id,namespace,event_type,payload_json,input_hash,output_hash,provenance_record_id) VALUES(?,?,?,?,?,?,?)",
                (event_id,namespace,event_type,payload_json,input_hash,output_hash,provenance_record_id)
            )
            row=conn.execute(
                "SELECT namespace,event_type,payload_json,input_hash,output_hash,provenance_record_id FROM runtime_events WHERE event_id=?",
                (event_id,)
            ).fetchone()
            if row is None:
                raise ValueError("event disappeared during write")
            same=(
                row[0]==namespace and row[1]==event_type and
                row[2]==payload_json and row[3]==input_hash and
                row[4]==output_hash and row[5]==provenance_record_id
            )
            if not same:
                raise ValueError("immutable event conflict")
            conn.commit()

    def append_event_if_latest_status(
        self, namespace: str, protocol_id: str, version: str, expected_status: str,
        event_id: str, event_type: str, payload: dict, output_hash: str | None = None,
        provenance_record_id: str | None = None,
    ) -> None:
        """Atomically compare lifecycle state and append one event, or fail on a race."""
        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                row = conn.execute(
                    """SELECT payload_json FROM runtime_events
                       WHERE namespace = ?
                         AND json_extract(payload_json, '$.protocol_id') = ?
                         AND json_extract(payload_json, '$.version') = ?
                       ORDER BY json_extract(payload_json, '$.recorded_at') DESC
                       LIMIT 1""",
                    (namespace, protocol_id, version),
                ).fetchone()
                current = json.loads(row[0]).get("status") if row else None
                if current != expected_status:
                    raise ValueError("concurrent lifecycle transition conflict")
                conn.execute(
                    """INSERT INTO runtime_events
                       (event_id,namespace,event_type,payload_json,output_hash,provenance_record_id)
                       VALUES(?,?,?,?,?,?)""",
                    (event_id, namespace, event_type, payload_json, output_hash, provenance_record_id),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def get_event(self, event_id: str) -> dict | None:
        with self._connect() as conn:
            row=conn.execute("SELECT event_type,namespace,payload_json,input_hash,output_hash,provenance_record_id,created_at FROM runtime_events WHERE event_id=?", (event_id,)).fetchone()
        if row is None:
            return None
        return {"event_id":event_id,"event_type":row[0],"namespace":row[1],"payload":json.loads(row[2]),"input_hash":row[3],"output_hash":row[4],"provenance_record_id":row[5],"created_at":row[6]}

    def list_events(self, namespace:str)->list[dict]:
        with self._connect() as conn:
            rows=conn.execute(
                "SELECT event_id,event_type,payload_json,input_hash,output_hash,provenance_record_id,created_at FROM runtime_events WHERE namespace=? ORDER BY created_at,event_id",
                (namespace,)
            ).fetchall()
        return [{"event_id":r[0],"event_type":r[1],"payload":json.loads(r[2]),
                 "input_hash":r[3],"output_hash":r[4],"provenance_record_id":r[5],"created_at":r[6]} for r in rows]
