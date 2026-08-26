#!/usr/bin/env python3
"""Reconstruct counted seq95 and finish ADMIN after approved host recovery."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import run_admin_audit as audit


DEFECT = "PS2-A-INIT-STUDY-UUID-CREATES"
NEW_UID = "bb7265f4-8391-47f4-9112-8334f5bf7ddc"
NEW_GRANTED_UID = "2504eed8-0656-48b1-9a69-9973ccdc6b4a"
RECOVERY = audit.ROOT / "recovery" / "seq095-init-study-profile"


def empty_target_digest() -> str:
    return hashlib.sha256().hexdigest()


def load_and_reconstruct() -> dict[str, object]:
    ledger = json.loads(audit.LEDGER.read_text(encoding="utf-8"))
    host_ledger = json.loads(audit.HOST_READS.read_text(encoding="utf-8"))
    records = sorted(
        (
            item
            for operation in audit.OPERATIONS
            for item in ledger["operations"][operation]["attempts"]
        ),
        key=lambda item: item["sequence"],
    )
    if len(records) != 94 or [item["sequence"] for item in records] != list(range(1, 95)):
        raise SystemExit("Expected exactly captured ADMIN sequences 1..94.")
    if len(list(audit.RAW.glob("*.txt"))) != 95:
        raise SystemExit("Expected 95 raw files including reconstructed seq95 evidence.")
    if (audit.RAW / "096-lock-m5.txt").exists():
        raise SystemExit("Post-Profile continuation already started; refusing replay.")
    summary = json.loads(
        (RECOVERY / "recovery-summary.json").read_text(encoding="utf-8")
    )
    if summary.get("result") != "PASS" or summary.get("runner_preassert_equivalent") != "PASS":
        raise SystemExit("Approved sequence-95 identity recovery is not verified.")
    for operation in audit.OPERATIONS:
        audit.attempts_by_operation[operation] = list(
            ledger["operations"][operation]["attempts"]
        )
    audit.host_reads = list(host_ledger["host_reads"])
    audit.sequence = 95
    audit.round_number = 5
    before = records[-1]
    sequence_95 = {
        "attempt": 5,
        "sequence": 95,
        "command": (
            "python /Users/KimMunyeong/Github/memcommit/outputs/"
            "study-long-audit-20260825-v2/run_world_mem.py practice-source "
            "init-study 00000000-0000-0000-0000-000000000999"
        ),
        "exit": 0,
        "starting_state": (
            "One cumulative no-reset Store; ADMIN round 5; phase-local sequence 95; "
            "original current Context remained in the original Store while init-study "
            "unexpectedly activated a new Store."
        ),
        "entry_route": "pinned noninteractive ADMIN CLI · M5 · UUID-shaped Study-name negative control",
        "target_route": "Profile/process-local admin surface",
        "scope": "ADMIN round 5 exact argv · UUID-shaped Study-name negative control",
        "input_provenance": (
            "cumulative CORE+TRANSFORM+ADMIN Store; protocol M5; actual argv "
            "`init-study 00000000-0000-0000-0000-000000000999`"
        ),
        "consumer": "admin safety, recoverability, orientation, and exact-identity audit",
        "expected": audit.expected_for("init-study", 5),
        "actual": (
            "Exit 0. Durable host evidence confirms creation and activation of managed "
            "Study Profile bb7265f4 and granted-memory Profile 2504eed8, contrary to "
            "the required zero-success boundary."
        ),
        "defect_ids": [DEFECT],
        "cost": {
            "wall_seconds": None,
            "output_bytes": None,
            "output_lines": None,
            "timed_out": False,
            "tui": False,
            "terminal_screens": 0,
            "extra_manual_steps": 0,
            "measurement_status": "not retained because post-call identity assertion preceded raw persistence",
        },
        "pre_target_digest": empty_target_digest(),
        "post_target_digest": empty_target_digest(),
        "pre_context_tree_digest": before["post_context_tree_digest"],
        "post_context_tree_digest": before["post_context_tree_digest"],
        "pre_registry_digest": before["post_registry_digest"],
        "post_registry_digest": summary["registry_before_sha256"],
        "pre_config_digest": before["post_config_digest"],
        "post_config_digest": before["post_config_digest"],
        "recovery_evidence": (
            "No mem recovery call. Exact registry and three Store snapshots preceded "
            "an atomic active_uid-only host replacement; all Store tree digests were "
            "unchanged and the unexpected Profiles/Stores were retained."
        ),
        "state_continuity": {
            "one_cumulative_store": False,
            "source_digest_preserved": True,
            "post_call_identity_asserted": False,
            "observed_profile_name": "00000000-0000-0000-0000-000000000999",
            "observed_profile_uid": NEW_UID,
            "observed_store": str(audit.PROFILE_CONTROL / "stores" / NEW_UID),
            "approved_host_recovery": str(
                (RECOVERY / "recovery-summary.json").relative_to(audit.ROOT)
            ),
        },
        "stdin_provenance": "none",
        "raw_output": "raw/admin/095-init_study-m5.txt",
    }
    audit.attempts_by_operation["init-study"].append(sequence_95)
    audit.record_host(
        "identity_assertion",
        label="admin sequence 95 init-study M5",
        result="FAIL",
        profile_name="00000000-0000-0000-0000-000000000999",
        profile_uid=NEW_UID,
        resolved_store=str(audit.PROFILE_CONTROL / "stores" / NEW_UID),
        raw_persistence_interrupted=True,
    )
    audit.record_host(
        "unexpected_init_study_durable_result",
        sequence=95,
        exit=0,
        study_profile_uid=NEW_UID,
        granted_memory_profile_uid=NEW_GRANTED_UID,
        registry_before_recovery_sha256=summary["registry_before_sha256"],
        unexpected_profiles_retained=True,
        unexpected_stores_retained=True,
        result="FAIL",
    )
    audit.record_host(
        "approved_profile_identity_recovery",
        sequence=95,
        mem_recovery_calls=0,
        registry_before_sha256=summary["registry_before_sha256"],
        registry_after_sha256=summary["registry_after_sha256"],
        registry_only_logical_change="active_uid",
        original_store_tree_sha256=summary["store_snapshots_before"]["original"]["tree_sha256"],
        all_store_trees_unchanged=all(
            item["unchanged"] for item in summary["store_verification_after"].values()
        ),
        evidence=str((RECOVERY / "recovery-summary.json").relative_to(audit.ROOT)),
        result="PASS",
    )
    audit.assert_identity(label="ADMIN sequence-95 recovery runner preassert equivalent")
    audit.persist_ledger()
    return summary


def finish(summary: dict[str, object]) -> None:
    audit.run("lock", ["lock", "--profile"], method="whole active Profile lock")
    audit.run("unlock", ["unlock", "--profile"], method="paired whole active Profile unlock")
    audit.run("log", ["log", "--actions", "--limit", "100"], method="Study action ledger")
    audit.run("profile", ["profile", "use", "admin-v2-practice-source-missing"], method="missing Profile selection")
    audit.run("provider", ["provider", "probe", "--operation", "query"], method="single synthetic Query provider probe")
    audit.run("pwd", ["pwd"], method="late accumulated current pointer")
    audit.run("share", ["share", audit.C, "--to", "admin-v2-missing-endpoint", "--direct"], method="valid Source to missing receiver endpoint", targets=(audit.C,))
    audit.run("shell-init", ["shell-init", "bash"], method="unsupported shell validation")
    audit.run("rename", ["rename", f"{audit.C}/co4-tree", f"{audit.C}/renamed-co4-cancel"], method="explicit confirmation declined", targets=(f"{audit.C}/co4-tree", f"{audit.C}/renamed-co4-cancel"), stdin_text="n\n")
    audit.run("switch", ["switch", audit.ENTRY], method="exact phase-entry restoration", targets=(audit.ENTRY,))
    counts = {
        operation: len(audit.attempts_by_operation[operation])
        for operation in audit.OPERATIONS
    }
    if audit.sequence != 105 or set(counts.values()) != {5}:
        raise RuntimeError(f"ADMIN completion contract failed: {audit.sequence}, {counts}")
    if audit.sha(audit.SOURCE_PATH) != audit.SOURCE_DIGEST:
        raise RuntimeError("practice/source changed during final ADMIN completion.")
    registry = audit.profile_config.load_profile_registry()
    if registry.active.uid != audit.PROFILE_UID:
        raise RuntimeError("ADMIN finished on the wrong active Profile.")
    current = json.loads((audit.STORE / "state.json").read_text(encoding="utf-8"))["current"]
    if current != audit.ENTRY:
        raise RuntimeError(f"ADMIN did not restore ENTRY: {current}")
    for label in ("unexpected-study", "unexpected-granted-memory"):
        root = Path(summary["store_snapshots_before"][label]["root"])
        _, digest = store_manifest(root)
        if digest != summary["store_snapshots_before"][label]["tree_sha256"]:
            raise RuntimeError(f"Inactive unexpected Store changed: {label}")
    audit.persist_ledger()
    print("ADMIN_CAPTURE_COMPLETE 105/105", flush=True)


def store_manifest(root: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    count = 0
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        value = path.read_bytes()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(value)
        digest.update(b"\0")
        count += 1
    return count, digest.hexdigest()


if __name__ == "__main__":
    finish(load_and_reconstruct())
