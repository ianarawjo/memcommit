#!/usr/bin/env python3
"""Generate or verify the static MemCommit callable catalog."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY))

from scripts.callable_catalog.catalog import (  # noqa: E402
    build_catalog,
    render_callable_jsonl,
    render_operation_markdown,
    render_summary_json,
)


OUTPUTS = {
    "callable-catalog.jsonl": render_callable_jsonl,
    "callable-catalog-summary.json": render_summary_json,
    "operation-route-catalog.md": render_operation_markdown,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail when checked-in generated files differ from the source scan",
    )
    args = parser.parse_args()

    snapshot = build_catalog(REPOSITORY)
    output_dir = REPOSITORY / "agent-records" / "docs" / "generated"
    stale: list[str] = []
    for name, renderer in OUTPUTS.items():
        path = output_dir / name
        rendered = renderer(snapshot)
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != rendered:
                stale.append(path.relative_to(REPOSITORY).as_posix())
            continue
        output_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8")

    if stale:
        for path in stale:
            print(f"stale generated catalog: {path}", file=sys.stderr)
        return 1
    if not args.check:
        print(
            f"catalogued {len(snapshot.callables)} callables across "
            f"{len(snapshot.source_modules)} modules and "
            f"{len(snapshot.operations)} operations"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
