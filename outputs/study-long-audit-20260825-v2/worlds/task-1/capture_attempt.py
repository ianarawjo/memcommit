#!/usr/bin/env python3
"""Capture one counted task-1 audit invocation and its lane-state boundary."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
import time


WORLD = "task-1"
ROOT = Path(__file__).resolve().parent
RAW = ROOT / "raw" / "core"
RUNNER = Path(
    "/Users/KimMunyeong/Github/memcommit/outputs/"
    "study-long-audit-20260825-v2/run_world_mem.py"
)
LANE = Path(
    "/Users/KimMunyeong/.codex/audit-stores/"
    "memcommit-six-world-v2-20260825/worlds/task-1/profile-control"
)


def digest_tree(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        if path.suffix == ".lock" or "__pycache__" in path.parts:
            continue
        relative = path.relative_to(root).as_posix().encode()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        data = path.read_bytes()
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def main() -> None:
    if len(sys.argv) < 5 or sys.argv[4] != "--":
        raise SystemExit("usage: capture_attempt.py SEQUENCE OP ATTEMPT -- MEM_ARGS...")
    sequence = int(sys.argv[1])
    operation = sys.argv[2]
    attempt = int(sys.argv[3])
    mem_args = sys.argv[5:]
    accepted_entry_names = {operation}
    if operation == "list":
        accepted_entry_names.add("ls")
    if not mem_args or mem_args[0] not in accepted_entry_names:
        raise SystemExit("first MEM_ARG must equal OP or its cataloged alias")

    RAW.mkdir(parents=True, exist_ok=True)
    stem = f"{sequence:03d}-{operation}-m{attempt}"
    command_argv = ["python", str(RUNNER), WORLD, *mem_args]
    command = shlex.join(command_argv)
    pre_digest = digest_tree(LANE)
    started = time.monotonic()
    result = subprocess.run(command_argv, text=True, capture_output=True)
    elapsed = time.monotonic() - started
    post_digest = digest_tree(LANE)

    raw_path = RAW / f"{stem}.txt"
    raw_text = (
        f"COMMAND\n{command}\n\nEXIT\n{result.returncode}\n\n"
        f"WALL_SECONDS\n{elapsed:.6f}\n\nSTDOUT\n{result.stdout}\n\n"
        f"STDERR\n{result.stderr}"
    )
    raw_path.write_text(raw_text, encoding="utf-8")
    meta = {
        "sequence": sequence,
        "operation": operation,
        "attempt": attempt,
        "command": command,
        "exit": result.returncode,
        "wall_seconds": round(elapsed, 6),
        "pre_target_digest": pre_digest,
        "post_target_digest": post_digest,
        "raw_output": str(raw_path.relative_to(ROOT)),
    }
    (RAW / f"{stem}.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(meta))


if __name__ == "__main__":
    main()
