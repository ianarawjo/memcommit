"""Run frozen mem code against the supplemental shared-Profile sandbox."""

from __future__ import annotations

import os
from pathlib import Path
import sys


ACTORS = (
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
CONTROL = Path(
    "/Users/KimMunyeong/.codex/audit-stores/"
    "memcommit-six-world-v2-20260825/shared-concurrency/profile-control"
)
RUNNER = Path(__file__).with_name("run_isolated_mem.py")
PROFILE_NAME = "sixworld-v2-template"
PROFILE_UID = "8d6d6360-c3eb-40f9-a490-5c7b2a242bfd"


def main() -> None:
    if len(sys.argv) < 3 or sys.argv[1] not in ACTORS:
        raise SystemExit("usage: run_shared_mem.py ACTOR MEM_ARGS...")

    actor = sys.argv[1]
    mem_args = sys.argv[2:]
    environment = os.environ.copy()
    environment.update(
        {
            "MEMCOMMIT_AUDIT_ACTOR": actor,
            "MEMCOMMIT_AUDIT_CODE_ROOT": str(CODE_ROOT),
            "MEMCOMMIT_AUDIT_PROFILE_CONTROL": str(CONTROL),
            "MEMCOMMIT_AUDIT_EXPECTED_PROFILE_NAME": PROFILE_NAME,
            "MEMCOMMIT_AUDIT_EXPECTED_PROFILE_UID": PROFILE_UID,
            "MEMCOMMIT_AUDIT_EXPECTED_STORE_ROOT": str(
                CONTROL / "stores" / PROFILE_UID
            ),
            "PYTHONSAFEPATH": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": str(CODE_ROOT),
        }
    )
    os.chdir(CODE_ROOT)
    os.execvpe(
        sys.executable,
        [sys.executable, "-P", str(RUNNER), *mem_args],
        environment,
    )


if __name__ == "__main__":
    main()
