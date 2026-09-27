"""Operational backup, restore and audit-retention API.

Operations are disabled unless CTE_OPS_API_KEY is configured. The separate
ops key prevents accidentally exposing destructive maintenance routes merely
because normal API authentication is disabled.
"""
from __future__ import annotations

import hmac
import os
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .audit_retention import apply_retention, build_policy
from .runtime_backup import build_backup, restore_backup, validate_backup


class RestoreInput(BaseModel):
    backup: dict[str, Any]
    dry_run: bool = True


class RetentionInput(BaseModel):
    policy_id: str
    retention_days: int = Field(90, ge=1)
    namespace: str = "api"
    archive_manifest_hash: str | None = None


def _require_ops_key(provided: str | None) -> None:
    expected = os.getenv("CTE_OPS_API_KEY")
    if not expected:
        raise HTTPException(503, "operational API is disabled")
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(401, "operational authentication required")


def install_ops_api(app: FastAPI, store) -> None:
    @app.get("/ops/backup")
    def create_backup(x_cte_ops_key: str | None = Header(default=None)):
        _require_ops_key(x_cte_ops_key)
        return build_backup(store)

    @app.post("/ops/backup/validate")
    def validate_backup_endpoint(
        backup: dict[str, Any],
        x_cte_ops_key: str | None = Header(default=None),
    ):
        _require_ops_key(x_cte_ops_key)
        validate_backup(backup)
        return {
            "valid": True,
            "manifest_hash": backup["manifest_hash"],
            "snapshot_count": len(backup["snapshots"]),
            "event_count": len(backup["events"]),
        }

    @app.post("/ops/backup/restore")
    def restore_endpoint(
        p: RestoreInput,
        x_cte_ops_key: str | None = Header(default=None),
    ):
        _require_ops_key(x_cte_ops_key)
        try:
            return restore_backup(store, p.backup, dry_run=p.dry_run)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/ops/audit-retention")
    def retention_endpoint(
        p: RetentionInput,
        x_cte_ops_key: str | None = Header(default=None),
    ):
        _require_ops_key(x_cte_ops_key)
        policy = build_policy(
            p.policy_id,
            retention_days=p.retention_days,
            namespace=p.namespace,
        )
        try:
            return apply_retention(
                store,
                policy,
                archive_manifest_hash=p.archive_manifest_hash,
            )
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
