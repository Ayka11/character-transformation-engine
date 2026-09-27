"""Operational audit retention policy.

Retention applies only to operational API audit events by default. Before purge,
the caller must provide a backup manifest hash proving an archive was created.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .provenance import content_hash

PROTECTED_EVENT_NAMESPACES = frozenset({"transformation.journal"})


@dataclass(frozen=True)
class RetentionPolicy:
    policy_id: str
    namespace: str = "api"
    retention_days: int = 90
    archive_required: bool = True
    version: str = "1.0"
    immutable_hash: str = ""


def build_policy(policy_id: str, *, retention_days: int = 90, namespace: str = "api") -> RetentionPolicy:
    if retention_days < 1:
        raise ValueError("retention_days must be >= 1")
    if not namespace:
        raise ValueError("namespace is required")
    payload = {
        "policy_id": policy_id,
        "namespace": namespace,
        "retention_days": retention_days,
        "archive_required": True,
        "version": "1.0",
    }
    return RetentionPolicy(**payload, immutable_hash=content_hash(payload))


def retention_cutoff(policy: RetentionPolicy, now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    cutoff = current.astimezone(timezone.utc) - timedelta(days=policy.retention_days)
    return cutoff.strftime("%Y-%m-%d %H:%M:%S")


def apply_retention(
    store,
    policy: RetentionPolicy,
    *,
    archive_manifest_hash: str | None,
    now: datetime | None = None,
) -> dict:
    if policy.namespace in PROTECTED_EVENT_NAMESPACES:
        raise ValueError(f"retention purge is forbidden for protected namespace: {policy.namespace}")
    if policy.archive_required and not archive_manifest_hash:
        raise ValueError("audit archive backup manifest is required before retention purge")
    cutoff = retention_cutoff(policy, now)
    deleted = store.prune_events_before(cutoff, policy.namespace)
    return {
        "policy_id": policy.policy_id,
        "namespace": policy.namespace,
        "retention_days": policy.retention_days,
        "cutoff": cutoff,
        "deleted_events": deleted,
        "archive_manifest_hash": archive_manifest_hash,
        "policy_hash": policy.immutable_hash,
        "provenance": {
            "tag": "DRV",
            "rule_id": "AUDIT_RETENTION_V1",
            "input_hash": content_hash({
                "policy": policy.immutable_hash,
                "cutoff": cutoff,
                "archive_manifest_hash": archive_manifest_hash,
            }),
        },
    }
