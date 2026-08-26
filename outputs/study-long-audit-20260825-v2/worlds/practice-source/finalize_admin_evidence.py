#!/usr/bin/env python3
"""Finalize practice-source ADMIN ledgers without invoking mem."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
PHASE = HERE / "phase-admin.json"
HOST = HERE / "admin-host-reads.json"
BLOCKER2 = HERE / "admin-blocker-2-evidence.json"
WORLD_ISSUES = HERE / "issues.json"
TRANSFORM_ISSUES = HERE / "issues-transform.json"
ADMIN_ISSUES = HERE / "issues-admin.json"

PROFILE_UID = "8d6d6360-c3eb-40f9-a490-5c7b2a242bfd"
PROFILE_NAME = "sixworld-v2-template"
SOURCE_SHA256 = "3c7872e184194b45295052ec4efe40c9088f1b962e12fd4d30cfd2aeed7de212"
PROFILE_CONTROL = Path(
    "/Users/KimMunyeong/.codex/audit-stores/"
    "memcommit-six-world-v2-20260825/worlds/practice-source/profile-control"
)
STORE = PROFILE_CONTROL / "stores" / PROFILE_UID
SOURCE = STORE / "contexts/practice/source/context.json"
STATE = STORE / "state.json"
REGISTRY = PROFILE_CONTROL / "registry.json"
SPARSE_PARENT = (
    STORE
    / "contexts/practice/audit-workspace/admin-v2-scratch/missing-parent/context.json"
)
SPARSE_LEAF = (
    STORE
    / "contexts/practice/audit-workspace/admin-v2-scratch/missing-parent/leaf/context.json"
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def attempts(phase: dict) -> list[dict]:
    return [attempt for op in phase["operations"].values() for attempt in op["attempts"]]


phase = load(PHASE)
all_attempts = attempts(phase)
assert len(all_attempts) == 105
assert sorted(a["sequence"] for a in all_attempts) == list(range(1, 106))
assert set(len(op["attempts"]) for op in phase["operations"].values()) == {5}

by_sequence = {a["sequence"]: a for a in all_attempts}
by_sequence[1]["starting_state"] = (
    "After TRANSFORM sequence 120, one cumulative no-reset Store continued into "
    "ADMIN round 1; phase-local sequence 1; current Context captured by command "
    "output/host state."
)
by_sequence[94]["defect_ids"] = ["PS2-A-INIT-SPARSE-PARENT"]
by_sequence[94]["recovery_evidence"] = (
    "Host read after ADMIN sequence 105 confirms the requested leaf exists while "
    "its missing lexical parent's context.json remains absent; no cleanup was performed."
)
by_sequence[95]["state_continuity"].update(
    {
        "one_cumulative_store": True,
        "original_cumulative_store_preserved_and_resumed": True,
        "unexpected_temporary_profile_activation": True,
    }
)

phase["schema_version"] = 2
phase["status"] = "complete"
phase["starting_boundary"].pop("transform_final_digest", None)
phase["starting_boundary"].pop("admin_initial_digest", None)
exception = phase["interleave_exceptions"][0]
exception["counted_commands"] = exception["commands"]
exception["commands"] = ["mem switch --previous", "mem switch --next"]
exception.pop("logical_commands", None)
phase["issues"] = [
    "PS2-A-RENAME-BRANCH-HISTORY",
    "PS2-A-BRANCH-HISTORY-CASCADE",
    "PS2-A-INIT-STUDY-UUID-CREATES",
    "PS2-A-INIT-SPARSE-PARENT",
]
phase["verification"] = {
    "operations": 21,
    "attempts_per_operation": 5,
    "counted_attempts": 105,
    "phase_local_sequences": "1..105",
    "raw_outputs": len(list((HERE / "raw/admin").glob("*.txt"))),
    "runner_only_attempts": sum(
        a["command"].startswith(
            "python /Users/KimMunyeong/Github/memcommit/outputs/"
            "study-long-audit-20260825-v2/run_world_mem.py practice-source "
        )
        for a in all_attempts
    ),
    "share_deliveries": 0,
    "init_study_successes": 1,
    "init_study_success_classification": "defect",
    "screenshots": 0,
    "final_profile_name": PROFILE_NAME,
    "final_profile_uid": PROFILE_UID,
    "final_resolved_store": str(STORE),
    "final_current_context": "practice",
    "source_sha256": SOURCE_SHA256,
    "source_preserved": True,
}
phase["safety_results"] = {
    "share": "Five attempts failed before delivery; target and registry digests remained unchanged.",
    "history_negative_control": (
        "Six post-cascade Undo/Redo attempts failed closed before Context mutation after "
        "the retained malformed copied Branch history made stack construction unavailable."
    ),
    "init_study_recovery": (
        "The unexpected sequence-95 success was recovered with an approved active_uid-only "
        "host replacement; the new Profiles and Stores remain retained and unchanged."
    ),
    "source": "practice/source remained byte-exact throughout ADMIN.",
}
phase["outcome"] = (
    "Complete: 105/105 ADMIN attempts across 21 operations and five interleaved methods. "
    "Share delivered nothing, practice/source remained byte-exact, and the original Profile, "
    "Store, and current Context were restored. One init-study negative control unexpectedly "
    "succeeded and required approved host-only identity recovery; six later Undo/Redo negative "
    "controls failed closed on retained malformed copied Branch history."
)

registry = load(REGISTRY)
active_uid = registry["active_uid"]
active = next(item for item in registry["profiles"] if item["uid"] == active_uid)
current = load(STATE)["current"]
assert active_uid == PROFILE_UID
assert active["name"] == PROFILE_NAME
assert current == "practice"
assert sha256(SOURCE) == SOURCE_SHA256
assert not SPARSE_PARENT.exists()
assert SPARSE_LEAF.exists()
phase["source_guard"]["current_sha256"] = sha256(SOURCE)
phase["source_guard"]["preserved"] = True
phase["execution_boundary"]["final_current_context"] = current

host = load(HOST)
assert host["counted_mem_calls"] == 105
for entry in host["host_reads"]:
    if entry.get("kind") in {"sparse_parent_materialization", "phase_final_boundary"}:
        raise AssertionError("final host reads already present")
next_index = len(host["host_reads"]) + 1
host["host_reads"].append(
    {
        "index": next_index,
        "after_counted_sequence": 105,
        "kind": "sparse_parent_materialization",
        "label": "ADMIN init M5 physical lexical-parent boundary",
        "result": "FAIL",
        "expected": "A missing lexical parent prevents leaf creation without --parents.",
        "actual": "The leaf context.json exists while the parent context.json is absent.",
        "parent_context_json": str(SPARSE_PARENT),
        "parent_exists": False,
        "leaf_context_json": str(SPARSE_LEAF),
        "leaf_exists": True,
        "leaf_sha256": sha256(SPARSE_LEAF),
    }
)
host["host_reads"].append(
    {
        "index": next_index + 1,
        "after_counted_sequence": 105,
        "kind": "phase_final_boundary",
        "label": "ADMIN final cumulative identity and protected Source",
        "result": "PASS",
        "profile_name": active["name"],
        "profile_uid": active_uid,
        "resolved_store": str(STORE),
        "current_context": current,
        "source_sha256": sha256(SOURCE),
        "source_preserved": True,
        "counted_mem_calls": 105,
    }
)

blocker2 = load(BLOCKER2)
blocker2["additional_mem_calls_after_gate"] = 61
blocker2["blocked_next_transaction"] = {
    "at_gate_next_planned_operation": "switch",
    "at_gate_next_planned_attempt": 3,
    "at_gate_next_planned_argv": "switch task-1",
    "at_gate_undo3_called": False,
    "at_gate_reason": (
        "The protocol-required Checkout3 stack top could not be reconstructed before "
        "Switch O or Undo3."
    ),
}
blocker2["reviewed_continuation"] = {
    "authorization": (
        "Retain malformed history as a negative control; no supplemental Delete or recovery "
        "mem call; record remaining history operations as actual counted fail-closed attempts."
    ),
    "first_resumed_sequence": 45,
    "final_sequence": 105,
    "counted_attempts_after_gate": 61,
    "history_negative_control_sequences": [46, 47, 64, 83, 85, 86],
    "history_negative_control_exits": [1, 1, 1, 1, 1, 1],
    "context_mutation": False,
    "supplemental_delete_calls": 0,
    "recovery_mem_calls": 0,
    "result": "COMPLETE",
}
blocker2["safety_conclusion"] = (
    "Branch and checkout -b copied retained Branch checkpoints without rebinding owner "
    "membership. After independent frozen-source review, the malformed history was retained "
    "as a negative control: all six remaining Undo/Redo attempts failed during stack "
    "construction before Context mutation, and ADMIN completed without supplemental deletion."
)

core = load(WORLD_ISSUES)
transform = load(TRANSFORM_ISSUES)
admin = load(ADMIN_ISSUES)
if core.get("phase") == "all":
    raise AssertionError("world issue registry already merged")
merged = core["issues"] + transform["issues"] + admin["issues"]
ids = [item["id"] for item in merged]
assert len(ids) == 23
assert len(set(ids)) == 23
world_issues = {"world": "practice-source", "phase": "all", "issues": merged}

assert phase["verification"]["raw_outputs"] == 105
assert phase["verification"]["runner_only_attempts"] == 105

save(PHASE, phase)
save(HOST, host)
save(BLOCKER2, blocker2)
save(WORLD_ISSUES, world_issues)

print("Finalized phase-admin.json, host/blocker evidence, and 23-ID world issue registry.")
