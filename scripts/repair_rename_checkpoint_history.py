#!/usr/bin/env python3
"""Dry-run or apply one exact historical Context-locator repair."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "src"))

from memcommit.application.operations.rename.history_repair import (  # noqa: E402
    apply_rename_history_repair,
    plan_rename_history_repair,
)
from memcommit.persistence.store import MemoryStore  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Repair typed checkpoint frames missed by an earlier Context rename. "
            "The default is a read-only plan."
        )
    )
    parser.add_argument("--context-uid", required=True)
    parser.add_argument("--old-name", required=True)
    parser.add_argument("--new-name", required=True)
    parser.add_argument("--store-root", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-plan-digest")
    return parser


def main() -> int:
    args = _parser().parse_args()
    store = MemoryStore(create=False, root=args.store_root)
    if not args.apply:
        if args.expected_plan_digest is not None:
            raise SystemExit("--expected-plan-digest is used only with --apply")
        plan = plan_rename_history_repair(
            store,
            context_uid=args.context_uid,
            old_name=args.old_name,
            new_name=args.new_name,
        )
        print(json.dumps(asdict(plan), ensure_ascii=False, indent=2))
        return 0
    if args.expected_plan_digest is None:
        raise SystemExit("--apply requires --expected-plan-digest from a dry run")
    result = apply_rename_history_repair(
        store,
        context_uid=args.context_uid,
        old_name=args.old_name,
        new_name=args.new_name,
        expected_plan_digest=args.expected_plan_digest,
    )
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
