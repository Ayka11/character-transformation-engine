#!/usr/bin/env python3
"""Create or validate a portable CTE runtime backup.

Environment:
  CTE_DATABASE_URL - PostgreSQL DSN for production
  CTE_RUNTIME_DB   - SQLite path when PostgreSQL is not configured
"""
from __future__ import annotations

import argparse
from pathlib import Path

from cte.persistence import build_runtime_store
from cte.runtime_backup import load_backup, save_backup, validate_backup


def main() -> int:
    parser=argparse.ArgumentParser()
    sub=parser.add_subparsers(dest="command",required=True)
    create=sub.add_parser("create")
    create.add_argument("path",type=Path)
    validate=sub.add_parser("validate")
    validate.add_argument("path",type=Path)
    args=parser.parse_args()

    if args.command=="create":
        store=build_runtime_store()
        result=save_backup(store,args.path)
        print(result)
        return 0

    backup=load_backup(args.path)
    validate_backup(backup)
    print({
        "valid":True,
        "manifest_hash":backup["manifest_hash"],
        "snapshot_count":len(backup["snapshots"]),
        "event_count":len(backup["events"]),
    })
    return 0


if __name__=="__main__":
    raise SystemExit(main())