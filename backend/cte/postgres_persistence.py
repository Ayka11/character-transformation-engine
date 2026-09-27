"""PostgreSQL durable runtime store.

Production adapter implementing the same snapshot/event contract as
SQLiteRuntimeStore. SQLite remains the default local/test backend.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator, Callable

try:
    import psycopg
    from psycopg.types.json import Jsonb
except ImportError:  # pragma: no cover - dependency is optional outside installed runtime
    psycopg = None
    Jsonb = None

from .persistence import MUTABLE_SNAPSHOT_NAMESPACES
from .provenance import content_hash


@dataclass(frozen=True)
class Snapshot:
    namespace: str
    key: str
    version: str
    payload: dict
    payload_hash: str


class PostgreSQLRuntimeStore:
    def __init__(
        self,
        dsn: str,
        *,
        connect_factory: Callable[[str], Any] | None = None,
        initialize: bool = True,
    ):
        if not dsn:
            raise ValueError("PostgreSQL DSN is required")
        if psycopg is None and connect_factory is None:
            raise RuntimeError("psycopg is required for PostgreSQLRuntimeStore")
        self.dsn = dsn
        self._connect_factory = connect_factory or psycopg.connect
        if initialize:
            self._initialize()

    def _connect(self):
        return self._connect_factory(self.dsn)

    @contextmanager
    def transaction(self) -> Iterator[Any]:
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _initialize(self):
        with self.transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS runtime_snapshots (
                        namespace TEXT NOT NULL,
                        key TEXT NOT NULL,
                        version TEXT NOT NULL,
                        payload_json JSONB NOT NULL,
                        payload_hash TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (namespace, key)
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS runtime_events (
                        event_id TEXT PRIMARY KEY,
                        namespace TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        payload_json JSONB NOT NULL,
                        input_hash TEXT,
                        output_hash TEXT,
                        provenance_record_id TEXT,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )

    def put_snapshot(self, namespace: str, key: str, payload: dict, version: str) -> Snapshot:
        payload_hash = content_hash(payload)
        with self.transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT version,payload_hash,payload_json FROM runtime_snapshots WHERE namespace=%s AND key=%s",
                    (namespace, key),
                )
                row = cur.fetchone()
                if row is not None:
                    if row[1] == payload_hash:
                        existing = row[2] if isinstance(row[2], dict) else json.loads(row[2])
                        return Snapshot(namespace, key, row[0], existing, row[1])
                    if namespace not in MUTABLE_SNAPSHOT_NAMESPACES:
                        raise ValueError("immutable snapshot conflict")
                    cur.execute(
                        """
                        UPDATE runtime_snapshots
                        SET version=%s, payload_json=%s, payload_hash=%s
                        WHERE namespace=%s AND key=%s
                        """,
                        (version, Jsonb(payload), payload_hash, namespace, key),
                    )
                    return Snapshot(namespace, key, version, payload, payload_hash)

                cur.execute(
                    """
                    INSERT INTO runtime_snapshots
                    (namespace,key,version,payload_json,payload_hash)
                    VALUES (%s,%s,%s,%s,%s)
                    """,
                    (namespace, key, version, Jsonb(payload), payload_hash),
                )
        return Snapshot(namespace, key, version, payload, payload_hash)

    def get_snapshot(self, namespace: str, key: str) -> Snapshot | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT version,payload_json,payload_hash FROM runtime_snapshots WHERE namespace=%s AND key=%s",
                    (namespace, key),
                )
                row = cur.fetchone()
        if row is None:
            return None
        payload = row[1] if isinstance(row[1], dict) else json.loads(row[1])
        return Snapshot(namespace, key, row[0], payload, row[2])

    def list_snapshot_namespaces(self) -> list[str]:
        with self._connect() as conn:
            rows=conn.execute(
                "SELECT DISTINCT namespace FROM runtime_snapshots ORDER BY namespace"
            ).fetchall()
        return [row[0] for row in rows]

    def list_event_namespaces(self) -> list[str]:
        with self._connect() as conn:
            rows=conn.execute(
                "SELECT DISTINCT namespace FROM runtime_events ORDER BY namespace"
            ).fetchall()
        return [row[0] for row in rows]

    def prune_events_before(self, cutoff: str, namespace: str | None = None) -> int:
        with self._connect() as conn:
            if namespace is None:
                cursor=conn.execute("DELETE FROM runtime_events WHERE created_at < ?", (cutoff,))
            else:
                cursor=conn.execute("DELETE FROM runtime_events WHERE created_at < ? AND namespace = ?", (cutoff, namespace))
            conn.commit()
            return cursor.rowcount
    def list_snapshots(self, namespace: str) -> list[Snapshot]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT key,version,payload_json,payload_hash
                    FROM runtime_snapshots
                    WHERE namespace=%s
                    ORDER BY key
                    """,
                    (namespace,),
                )
                rows = cur.fetchall()
        result = []
        for key, version, payload_json, payload_hash in rows:
            payload = payload_json if isinstance(payload_json, dict) else json.loads(payload_json)
            result.append(Snapshot(namespace, key, version, payload, payload_hash))
        return result

    def append_event(
        self,
        event_id: str,
        namespace: str,
        event_type: str,
        payload: dict,
        input_hash: str | None = None,
        output_hash: str | None = None,
        provenance_record_id: str | None = None,
    ) -> None:
        with self.transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT input_hash,output_hash,payload_json
                    FROM runtime_events
                    WHERE event_id=%s
                    """,
                    (event_id,),
                )
                row = cur.fetchone()
                if row is not None:
                    existing = row[2] if isinstance(row[2], dict) else json.loads(row[2])
                    if row[0] == input_hash and row[1] == output_hash and existing == payload:
                        return
                    raise ValueError("immutable event conflict")
                cur.execute(
                    """
                    INSERT INTO runtime_events
                    (event_id,namespace,event_type,payload_json,input_hash,output_hash,provenance_record_id)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        event_id, namespace, event_type, Jsonb(payload),
                        input_hash, output_hash, provenance_record_id,
                    ),
                )

    def list_events(self, namespace: str) -> list[dict]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT event_id,event_type,payload_json,input_hash,
                           output_hash,provenance_record_id,created_at
                    FROM runtime_events
                    WHERE namespace=%s
                    ORDER BY created_at,event_id
                    """,
                    (namespace,),
                )
                rows = cur.fetchall()
        result = []
        for event_id, event_type, payload_json, input_hash, output_hash, provenance_record_id, created_at in rows:
            payload = payload_json if isinstance(payload_json, dict) else json.loads(payload_json)
            result.append(
                {
                    "event_id": event_id,
                    "event_type": event_type,
                    "payload": payload,
                    "input_hash": input_hash,
                    "output_hash": output_hash,
                    "provenance_record_id": provenance_record_id,
                    "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at),
                }
            )
        return result
