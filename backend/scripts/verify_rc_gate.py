"""Deterministic software-side release-candidate gate.

This script intentionally does not make deployment or scientific claims. It checks
the repository state that must be true before an RC tag is considered.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import sys

EXPECTED_VERSION = "2.6.0-rc1"
ROOT = Path(__file__).resolve().parents[2]

REQUIRED_FILES = (
    "backend/cte/__init__.py",
    "backend/cte/persistence.py",
    "backend/cte/postgres_persistence.py",
    "backend/cte/transformation_recovery.py",
    "backend/ops/BACKUP_RESTORE_RUNBOOK.md",
    "backend/PRODUCTION_CONFIGURATION.md",
    "backend/migrations/002_runtime_postgres.sql",
    "backend/migrations/002_runtime_postgres.down.sql",
    "backend/migrations/MIGRATION_ROLLBACK_PLAN.md",
    "v2-release/V2.6_PRODUCTION_READINESS.md",
    "v2-release/V2.6_RC_VERIFICATION.md",
)

FORBIDDEN_CREDENTIAL_PATTERNS = (
    re.compile(r"postgres(?:ql)?://[^\s<>]+:[^\s<>]+@", re.I),
    re.compile(r"(?i)(api[_-]?key|password|secret)\s*[:=]\s*[A-Za-z0-9._/-]{12,}"),
)


def git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def main() -> int:
    from cte import __version__

    failures: list[str] = []
    if __version__ != EXPECTED_VERSION:
        failures.append(f"version mismatch: {__version__!r} != {EXPECTED_VERSION!r}")

    github_sha = os.getenv("GITHUB_SHA")
    if github_sha:
        actual = git_head()
        if actual != github_sha:
            failures.append(f"exact commit mismatch: HEAD={actual} GITHUB_SHA={github_sha}")

    missing = [path for path in REQUIRED_FILES if not (ROOT / path).is_file()]
    failures.extend(f"missing release artifact: {path}" for path in missing)

    prod_config = ROOT / "backend/PRODUCTION_CONFIGURATION.md"
    if prod_config.is_file():
        text = prod_config.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_CREDENTIAL_PATTERNS:
            if pattern.search(text):
                failures.append("credential-like material detected in production configuration")

    if failures:
        print("RC_GATE: FAIL")
        for item in failures:
            print(f"- {item}")
        return 1

    print("RC_GATE: PASS")
    print(f"version={EXPECTED_VERSION}")
    print(f"commit={git_head()}")
    print(f"required_artifacts={len(REQUIRED_FILES)}")
    print("scientific_status=IMPLEMENTATION_BASELINE")
    print("deployment_controls=EXTERNAL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
