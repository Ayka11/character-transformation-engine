import os

import pytest

from cte.persistence import build_runtime_store
from cte.postgres_persistence import PostgreSQLRuntimeStore


class FakeConnection:
    def __init__(self):
        self.committed=False
        self.rolled_back=False
        self.closed=False

    def commit(self):
        self.committed=True

    def rollback(self):
        self.rolled_back=True

    def close(self):
        self.closed=True


def test_postgresql_store_requires_dsn():
    with pytest.raises(ValueError):
        PostgreSQLRuntimeStore("")


def test_transaction_commits_and_closes():
    connection=FakeConnection()
    store=PostgreSQLRuntimeStore(
        "postgresql://example",
        connect_factory=lambda dsn: connection,
        initialize=False,
    )
    with store.transaction() as conn:
        assert conn is connection
    assert connection.committed
    assert connection.closed


def test_transaction_rolls_back_on_error():
    connection=FakeConnection()
    store=PostgreSQLRuntimeStore(
        "postgresql://example",
        connect_factory=lambda dsn: connection,
        initialize=False,
    )
    with pytest.raises(RuntimeError):
        with store.transaction():
            raise RuntimeError("boom")
    assert connection.rolled_back
    assert connection.closed


def test_default_factory_stays_sqlite_without_database_url(monkeypatch, tmp_path):
    monkeypatch.delenv("CTE_DATABASE_URL", raising=False)
    store=build_runtime_store(str(tmp_path/"runtime.sqlite3"))
    assert store.__class__.__name__=="SQLiteRuntimeStore"
