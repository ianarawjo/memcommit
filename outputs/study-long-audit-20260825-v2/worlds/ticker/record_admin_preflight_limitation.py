#!/usr/bin/env python3
"""Record the accidental read-only ADMIN help preflight outside counted coverage."""

from __future__ import annotations

import json
from pathlib import Path


REPO = Path("/Users/KimMunyeong/Github/memcommit")
ROOT = REPO / "outputs/study-long-audit-20260825-v2"
WORLD = ROOT / "worlds/ticker"
RUNNER = ROOT / "run_world_mem.py"
STORE = Path(
    "/Users/KimMunyeong/.codex/audit-stores/memcommit-six-world-v2-20260825/"
    "worlds/ticker/profile-control/stores/8d6d6360-c3eb-40f9-a490-5c7b2a242bfd"
)
ATTEMPTS = STORE / "ledger/command-attempts"
RAW = WORLD / "raw/admin-preflight"
DIGEST = "29c8ec096c0ad2c15b44358bc063fcb5d0ade30d00e83b8cb09b4ed36cdc98e1"
OPS = (
    "status", "branch", "checkout", "config", "eval", "help", "import",
    "init", "init-study", "lock", "log", "profile", "provider", "pwd",
    "redo", "rename", "share", "shell-init", "switch", "undo", "unlock",
)


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    records = []
    for path in ATTEMPTS.glob("*.json"):
        value = json.loads(path.read_text())
        if value.get("started_at", "") >= "2026-08-25T17:47:54+00:00" and value.get("command", "").endswith(" -h"):
            value["host_path"] = str(path)
            records.append(value)
    records.sort(key=lambda value: value["started_at"])
    by_operation = {record["operation"]: record for record in records}
    if set(by_operation) != set(OPS) - {"eval"}:
        raise RuntimeError(f"preflight command attempt mismatch: {sorted(by_operation)}")

    entries = []
    attempt_count = 225
    for sequence, operation in enumerate(OPS, 1):
        command = f"python {RUNNER} ticker {operation} -h"
        before = attempt_count
        record = by_operation.get(operation)
        if record is None:
            after = before
            exit_code = 1
            attempt_uid = None
            attempt_status = "NOT_ENTERED"
            attempt_failure = "Frozen launcher rejected Eval without required lane-local --ledger-dir."
            raw_note = "Audit eval calls require an explicit lane-local --ledger-dir"
        else:
            after = before + 1
            attempt_count = after
            exit_code = (record.get("failure") or {}).get("exit_code", 0)
            attempt_uid = record["uid"]
            attempt_status = record["status"]
            attempt_failure = record.get("failure")
            raw_note = (
                "The unplanned console stream was visible only in the orchestration call and was not retained before "
                "that aggregate output was truncated. The product command-attempt record below is the authoritative "
                "raw lifecycle evidence; console bytes are unavailable and are not reconstructed."
            )
        raw_path = RAW / f"{sequence:03d}-{operation}-help.txt"
        raw_path.write_text(
            "COMMAND\n" + command + "\n\nEXIT\n" + str(exit_code) +
            "\n\nRAW CAPTURE STATUS\n" + raw_note +
            "\n\nPRODUCT COMMAND ATTEMPT\n" +
            (json.dumps(record, ensure_ascii=False, indent=2) if record else "(none; launcher pre-dispatch rejection)") + "\n"
        )
        entries.append({
            "sequence": sequence,
            "operation": operation,
            "command": command,
            "exit": exit_code,
            "read_only_help_or_launcher_precheck": True,
            "pre_context_tree_digest": DIGEST,
            "post_context_tree_digest": DIGEST,
            "profile_identity": {
                "name": "sixworld-v2-template",
                "uid": "8d6d6360-c3eb-40f9-a490-5c7b2a242bfd",
                "resolved_store": str(STORE),
            },
            "command_attempt_ledger_count_before": before,
            "command_attempt_ledger_count_after": after,
            "command_attempt_ledger_delta": after - before,
            "command_attempt_uid": attempt_uid,
            "command_attempt_status": attempt_status,
            "command_attempt_failure": attempt_failure,
            "raw_evidence": str(raw_path.relative_to(ROOT)),
            "console_raw_capture_available": record is None,
        })
    payload = {
        "schema_version": 1,
        "study": "study-long-audit-20260825-v2",
        "world": "ticker",
        "phase": "admin-supplemental-preflight",
        "excluded_from_1980": True,
        "excluded_from_ticker_admin_105": True,
        "methodology_limitation": (
            "An agent mistakenly invoked 21 pinned `OP -h` preflight commands before creating phase-admin.json. "
            "Twenty entered the product read-only Help path and one Eval invocation was rejected by the frozen launcher "
            "before product dispatch. They made no Context-tree or Profile-selection change, but they violate the intended "
            "no-uncounted-mem-call method and therefore remain explicit supplemental evidence, never coverage."
        ),
        "reset_or_restoration_performed": False,
        "reexecuted": False,
        "calls": entries,
        "summary": {
            "launcher_invocations": 21,
            "product_command_attempts": 20,
            "context_tree_mutations": 0,
            "profile_identity_changes": 0,
            "console_streams_not_retained": 20,
        },
    }
    (WORLD / "supplemental-admin-preflight.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
