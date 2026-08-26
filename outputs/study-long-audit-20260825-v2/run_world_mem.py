"""Convenience entry point for one pinned six-world audit lane."""

from __future__ import annotations

import os
from pathlib import Path
import sys


WORLD_NAMES = (
    "task-1",
    "task-2",
    "task-3",
    "ticker",
    "a-is-apple",
    "practice-source",
)
CODE_ROOT = Path(
    "/Users/KimMunyeong/.codex/audit-snapshots/"
    "memcommit-six-world-v2-20260825-code"
)
LANES_ROOT = Path(
    "/Users/KimMunyeong/.codex/audit-stores/"
    "memcommit-six-world-v2-20260825/worlds"
)
RUNNER = Path(__file__).with_name("run_isolated_mem.py")
PROFILE_NAME = "sixworld-v2-template"
PROFILE_UID = "8d6d6360-c3eb-40f9-a490-5c7b2a242bfd"


def main() -> None:
    if len(sys.argv) < 3 or sys.argv[1] not in WORLD_NAMES:
        choices = ", ".join(WORLD_NAMES)
        raise SystemExit(f"usage: {Path(sys.argv[0]).name} WORLD MEM_ARGS... ({choices})")
    world = sys.argv[1]
    mem_args = sys.argv[2:]
    profile_control = LANES_ROOT / world / "profile-control"
    store_root = profile_control / "stores" / PROFILE_UID

    if mem_args[0] == "eval":
        if "--ledger-dir" not in mem_args:
            raise SystemExit("Audit eval calls require an explicit lane-local --ledger-dir")
        ledger_index = mem_args.index("--ledger-dir") + 1
        if ledger_index >= len(mem_args):
            raise SystemExit("--ledger-dir requires a value")
        requested = Path(mem_args[ledger_index]).resolve()
        lane_root = (LANES_ROOT / world).resolve()
        if requested != lane_root and lane_root not in requested.parents:
            raise SystemExit("Audit eval ledger must stay inside its world lane")

    environment = os.environ.copy()
    environment.update(
        {
            "MEMCOMMIT_AUDIT_CODE_ROOT": str(CODE_ROOT),
            "MEMCOMMIT_AUDIT_PROFILE_CONTROL": str(profile_control),
            "MEMCOMMIT_AUDIT_EXPECTED_PROFILE_NAME": PROFILE_NAME,
            "MEMCOMMIT_AUDIT_EXPECTED_PROFILE_UID": PROFILE_UID,
            "MEMCOMMIT_AUDIT_EXPECTED_STORE_ROOT": str(store_root),
            "PYTHONSAFEPATH": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": str(CODE_ROOT),
        }
    )
    if environment.get("MEMCOMMIT_AUDIT_COLOR") == "1":
        environment.pop("NO_COLOR", None)
        environment["TERM"] = "xterm-256color"
        environment["COLORTERM"] = "truecolor"

    os.chdir(CODE_ROOT)
    os.execvpe(
        sys.executable,
        [sys.executable, "-P", str(RUNNER), *mem_args],
        environment,
    )


if __name__ == "__main__":
    main()
