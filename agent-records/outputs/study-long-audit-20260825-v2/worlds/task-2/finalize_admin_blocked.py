#!/usr/bin/env python3
"""Record the task-2 ADMIN safety stop without replaying any mem command."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path


ROOT = Path("/Users/KimMunyeong/Github/memcommit")
OUT = ROOT / "agent-records/outputs/study-long-audit-20260825-v2/worlds/task-2"
PHASE = OUT / "phase-admin.json"
HOST = OUT / "admin-host-reads.json"
BLOCKER = OUT / "admin-stack-blocker.json"

ISSUE = {
    "id": "T2V2-BRANCH-NESTED-HISTORY-01",
    "title": "Rename leaves Branch creation membership stale and recursive Branch copies the invalid history",
    "expected": (
        "A successful recursive Branch writes a complete command unit whose exact "
        "UID and member set can be reconstructed immediately for Undo."
    ),
    "actual": (
        "Rename M1 changed Branch1's owner name from b1 to renamed-1 without "
        "rebasing its retained Branch membership. Branch M2 then succeeded and "
        "copied that invalid history into a seven-Context subtree. The prescribed "
        "counted inverse Rename M2 restored the original owner, but the cloned "
        "checkpoint still had a different owner UID/name; build_command_stacks "
        "continued to fail with 'Branch checkpoint owner is outside its creation "
        "membership.'"
    ),
    "workaround": (
        "Do not invoke Undo or continue a recovery-sensitive sequence. Avoid "
        "recursive Branch over a subtree containing previously branched Context "
        "history until the product rejects the operation pre-mutation or safely "
        "rebases/isolates copied historical receipts."
    ),
    "severity": "critical",
    "classification": "recovery-safety/branch-command-history",
    "evidence_ids": [
        "admin:rename:1",
        "admin:branch:2",
        "admin:rename:2",
        "admin-host:after-branch2-before-undo2",
        "admin-stack-blocker.json",
    ],
}


def main() -> None:
    phase = json.loads(PHASE.read_text(encoding="utf-8"))
    if phase.get("counted_actual_mem_commands") != 24:
        raise SystemExit("Refusing to finalize unexpected ADMIN count")
    branch2 = phase["operations"]["branch"]["attempts"][1]
    if branch2["sequence"] != 23 or branch2["exit"] != 0:
        raise SystemExit("Refusing to finalize unexpected Branch M2 evidence")
    if ISSUE["id"] not in branch2["defect_ids"]:
        branch2["defect_ids"].append(ISSUE["id"])
    for rename_attempt in phase["operations"]["rename"]["attempts"]:
        if ISSUE["id"] not in rename_attempt["defect_ids"]:
            rename_attempt["defect_ids"].append(ISSUE["id"])

    phase["status"] = "blocked_at_required_recovery_host_read"
    phase["starting_boundary"] = {
        "cumulative_from_transform": True,
        "no_reset": True,
        "explicit_cumulative_bridge": (
            "ADMIN starts after all 105 CORE and 120 TRANSFORM calls in the exact "
            "same pinned Profile and cumulative Store; no reset, replacement, or "
            "alternate Store occurred. Phase-entry current Context was practice."
        ),
    }
    phase["issues"] = [ISSUE]
    phase["coverage"] = {
        name: len(record["attempts"])
        for name, record in phase["operations"].items()
    }
    exits = [
        attempt["exit"]
        for record in phase["operations"].values()
        for attempt in record["attempts"]
    ]
    phase["execution_summary"] = {
        "counted_actual_mem_commands": 24,
        "successful_exits": sum(code == 0 for code in exits),
        "safe_nonzero_exits": sum(code != 0 for code in exits),
        "provider_infrastructure_failures": 0,
        "share_deliveries": 0,
        "init_study_successes": 0,
        "store_resets": 0,
        "starting_phase_sequence": 1,
        "ending_phase_sequence": 24,
        "raw_world_sequence_range": [226, 249],
        "remaining_counted_calls_not_run": 81,
        "stop_reason": (
            "Required pre-Undo2 exact command-stack host-read failed after "
            "successful Branch M2 and again after the prescribed counted inverse "
            "Rename M2 recovery; no Undo2 or later counted call was run."
        ),
    }
    phase["interleave_exceptions"] = [
        {
            "operation": "switch",
            "attempts": [1, 2],
            "sequences": [21, 22],
            "commands": [
                "mem switch --previous",
                "mem switch --next",
            ],
            "rationale": (
                "The admin protocol requires switch M1 as round 1's last counted "
                "call and switch M2 as round 2's first counted call, with no "
                "intervening mem invocation, to exercise the exact previous/next "
                "navigation transaction."
            ),
        }
    ]
    phase["blocked_boundary"] = {
        "after_phase_sequence": 24,
        "next_required_operation": "undo attempt 2 with --keep",
        "required_host_read": "exact undo-stack top unit UID and complete member set",
        "error": "CommandHistoryError: Branch checkpoint owner is outside its creation membership.",
        "action": "Stopped before Undo2 after the allowed inverse Rename; no guessed UID or later counted call was used.",
        "evidence": str(BLOCKER.relative_to(ROOT)),
    }
    phase["host_read_evidence"] = str(HOST.relative_to(ROOT))

    blocker = {
        "world": "task-2",
        "phase": "admin",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "after_phase_sequence": 24,
        "trigger_command": branch2["command"],
        "trigger_exit": branch2["exit"],
        "trigger_raw_output": branch2["raw_output"],
        "inverse_recovery_command": phase["operations"]["rename"]["attempts"][1]["command"],
        "inverse_recovery_exit": phase["operations"]["rename"]["attempts"][1]["exit"],
        "inverse_recovery_raw_output": phase["operations"]["rename"]["attempts"][1]["raw_output"],
        "required_next_command_not_run": (
            "python /Users/KimMunyeong/Github/memcommit/agent-records/outputs/"
            "study-long-audit-20260825-v2/run_world_mem.py task-2 undo --keep"
        ),
        "host_read_error": (
            "memcommit.command_history.CommandHistoryError: Branch checkpoint "
            "owner is outside its creation membership."
        ),
        "diagnosis": {
            "recursive_branch_operation_uid": "c0dae645-c0bc-4084-8145-8e05d3ad7fb3",
            "recursive_branch_target_root": "task-2/participant/admin-v2-scratch/b2-tree",
            "recursive_branch_context_count": 7,
            "offending_copied_checkpoint_uid": "653cd445-e69d-4cf7-b8a2-d1f403beee67",
            "offending_checkpoint_sha256": "aba1b4306d8c97f1b63a7000d9bf815b9419b2e26a640d8c61ae0d386275dfa2",
            "copied_owner": {
                "uid": "5f68e09b-cdd8-4632-a81b-7af7e67bdc04",
                "name": "task-2/participant/admin-v2-scratch/b2-tree/participant/admin-v2-scratch/renamed-1",
            },
            "retained_historical_membership": {
                "operation_uid": "d2d55d2f-e312-4daf-a988-ed790d51a551",
                "target_uid": "a111c808-d3e1-4e47-a056-2e954dd82b16",
                "target_name": "task-2/participant/admin-v2-scratch/b1",
            },
            "owner_in_retained_membership": False,
            "staged_update_granted_target_before_transaction": None,
        },
        "safety_action": (
            "No Undo2, Redo2, or later counted operation was executed because "
            "the protocol forbids guessing or bypassing the exact stack unit."
        ),
    }

    host = json.loads(HOST.read_text(encoding="utf-8"))
    host["safety_reads"].append(
        {
            "kind": "required-command-stack-host-read-failure",
            "label": "after-branch2-before-undo2",
            "after_phase_sequence": 24,
            "timestamp": blocker["timestamp"],
            "error": blocker["host_read_error"],
            "blocker_evidence": str(BLOCKER.relative_to(ROOT)),
            "next_counted_command_run": False,
        }
    )

    BLOCKER.write_text(json.dumps(blocker, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    HOST.write_text(json.dumps(host, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    PHASE.write_text(json.dumps(phase, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
