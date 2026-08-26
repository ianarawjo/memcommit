#!/usr/bin/env python3
"""Continue practice-source ADMIN after the reviewed Rename recovery gate.

This continuation loads the already captured 37 attempts. Its first counted
call consumes unused Rename M2 to restore the Branch M1 owner name. Undo M2 is
allowed only after raw receipt membership and the exact six-member B2 stack
top both pass host-only verification.
"""

from __future__ import annotations

import json
from pathlib import Path

import run_admin_audit as audit


B1_CONTEXT_UID = "e8aad7e1-d1e0-4f56-81bf-4b7250bc1a23"
B1_CHECKPOINT_UID = "56a482b9-eafe-4cbb-9b79-ef2ff69b0153"
B2_UNIT_UID = "branch:f5beb417-13ee-45e9-b9e3-95b230c9d420"
B2_MEMBERS = [
    {
        "context_uid": "8fbc83d4-3c3f-49fe-b735-f63e068d7b47",
        "context_name": f"{audit.C}/b2-tree",
        "checkpoint_uid": "21f34fea-7685-4353-a66d-337bf07d9146",
    },
    {
        "context_uid": "532149eb-a80b-4d50-b5d4-4b4c7477992c",
        "context_name": f"{audit.C}/b2-tree/contexts",
        "checkpoint_uid": "12282a3b-ce02-4f0d-9d7d-ee39b618a8cd",
    },
    {
        "context_uid": "d470144f-61b8-4a7a-88a3-cb6fe6788224",
        "context_name": f"{audit.C}/b2-tree/examples",
        "checkpoint_uid": "1b299e7e-bee9-4539-b86c-24da00780123",
    },
    {
        "context_uid": "7bb30fd2-1a68-40dd-b824-0647c8386073",
        "context_name": f"{audit.C}/b2-tree/goals",
        "checkpoint_uid": "5ec59ed6-e4b4-40c3-99a3-65acc08611d4",
    },
    {
        "context_uid": "6f0b9de7-87aa-4b4b-88cd-47116622567d",
        "context_name": f"{audit.C}/b2-tree/relations",
        "checkpoint_uid": "4e6d99a0-e6c3-45fb-81da-7e6f771ccb92",
    },
    {
        "context_uid": "b6492e53-fb93-40fd-95d2-90df1b889151",
        "context_name": f"{audit.C}/b2-tree/rules",
        "checkpoint_uid": "191b16e5-6677-4cbd-8695-02da8d11fd84",
    },
]


def load_captured_state() -> None:
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
    if len(records) != 37 or [item["sequence"] for item in records] != list(range(1, 38)):
        raise SystemExit("Expected exactly captured ADMIN sequences 1..37.")
    if len(list(audit.RAW.glob("*.txt"))) != 37:
        raise SystemExit("Raw ADMIN evidence is not exactly 37 files.")
    if (audit.RAW / "038-rename-m2.txt").exists():
        raise SystemExit("Continuation already started; refusing replay.")
    for operation in audit.OPERATIONS:
        audit.attempts_by_operation[operation] = list(
            ledger["operations"][operation]["attempts"]
        )
    audit.host_reads = list(host_ledger["host_reads"])
    audit.sequence = 37
    audit.round_number = 2
    audit.eval_run_id = next(
        str(item["run_id"])
        for item in audit.host_reads
        if item.get("kind") == "eval_full_run_id"
    )
    if audit.sha(audit.SOURCE_PATH) != audit.SOURCE_DIGEST:
        raise SystemExit("practice/source changed before ADMIN continuation.")
    audit.assert_identity(label="ADMIN continuation entry after reviewed safety gate")


def verify_recovered_owner_membership() -> None:
    context_path = (
        audit.STORE / "contexts" / Path(*f"{audit.C}/b1".split("/")) / "context.json"
    )
    context = json.loads(context_path.read_text(encoding="utf-8"))
    checkpoint_dir = context_path.parent / "checkpoints"
    matches = []
    for path in checkpoint_dir.glob("*.json"):
        entry = json.loads(path.read_text(encoding="utf-8"))
        if entry.get("uid") == B1_CHECKPOINT_UID:
            matches.append((path, entry))
    if len(matches) != 1:
        raise RuntimeError(f"Expected one retained B1 checkpoint, got {len(matches)}")
    path, entry = matches[0]
    members = entry["args"]["branch_tree"]["contexts"]
    owner_in_membership = any(
        item["target_uid"] == context["uid"]
        and item["target_name"] == context["name"]
        for item in members
    )
    audit.record_host(
        "raw_branch_owner_membership",
        label="inverse Rename M2 restored Branch M1 owner membership",
        context_path=str(context_path),
        checkpoint_path=str(path),
        context_uid=context["uid"],
        context_name=context["name"],
        expected_context_uid=B1_CONTEXT_UID,
        expected_context_name=f"{audit.C}/b1",
        receipt_members=members,
        owner_in_membership=owner_in_membership,
        result="PASS" if owner_in_membership else "FAIL",
    )
    if context["uid"] != B1_CONTEXT_UID or not owner_in_membership:
        raise RuntimeError("Inverse Rename M2 did not restore raw Branch membership.")


def verify_exact_b2_top() -> str:
    store = audit.MemoryStore(
        root=audit.STORE,
        create=False,
        resolve_granted_links=False,
    )
    stacks = audit.build_command_stacks(store)
    if not stacks.undo:
        raise RuntimeError("Recovered undo stack is empty.")
    unit = stacks.undo[-1]
    members = [
        {
            "context_uid": change.context_uid,
            "context_name": change.context_name,
            "checkpoint_uid": change.checkpoint_uid,
        }
        for change in unit.changes
    ]
    granted_target = audit.staged_granted_target()
    passed = (
        unit.uid == B2_UNIT_UID
        and unit.command == "branch"
        and members == B2_MEMBERS
        and granted_target is None
    )
    audit.record_host(
        "command_stack_assertion",
        label="post-recovery exact B2 top immediately before Undo2 --keep",
        side="undo",
        unit_uid=unit.uid,
        command=unit.command,
        member_set=members,
        expected_unit_uid=B2_UNIT_UID,
        expected_member_set=B2_MEMBERS,
        staged_update_granted_target=granted_target,
        result="PASS" if passed else "FAIL",
    )
    if not passed:
        raise RuntimeError("Recovered command stack does not have the exact B2 top.")
    return unit.uid


def finish_round_2() -> None:
    audit.round_number = 2
    audit.run(
        "rename",
        ["rename", f"{audit.C}/renamed-1", f"{audit.C}/b1", "--force"],
        method="inverse recovery rename restoring retained Branch membership",
        targets=(f"{audit.C}/renamed-1", f"{audit.C}/b1"),
    )
    record = audit.attempts_by_operation["rename"][-1]
    record["defect_ids"] = ["PS2-A-RENAME-BRANCH-HISTORY"]
    record["recovery_evidence"] = (
        "Inverse Rename M2 restores the original B1 owner name; Undo2 remains gated "
        "on raw membership plus the exact B2 stack top in admin-host-reads.json."
    )
    audit.persist_ledger()
    verify_recovered_owner_membership()
    unit = verify_exact_b2_top()
    audit.run(
        "undo",
        ["undo", "--keep"],
        method="verified recursive Branch undo compatibility route after recovery",
        targets=(f"{audit.C}/b2-tree", f"{audit.C}/b2-tree/goals"),
    )
    audit.stack_snapshot(
        label="round2 redo-top same UID",
        side="redo",
        expected_uid=unit,
    )
    audit.run(
        "redo",
        ["redo"],
        method="verified recursive Branch redo",
        targets=(f"{audit.C}/b2-tree", f"{audit.C}/b2-tree/goals"),
    )
    audit.run(
        "lock",
        ["lock", f"{audit.C}/b2-tree", "--recursive"],
        method="recursive branch-tree lock",
        targets=(f"{audit.C}/b2-tree", f"{audit.C}/b2-tree/goals"),
    )
    audit.run(
        "unlock",
        ["unlock", f"{audit.C}/b2-tree", "--recursive"],
        method="paired recursive branch-tree unlock",
        targets=(f"{audit.C}/b2-tree", f"{audit.C}/b2-tree/goals"),
    )


def finish() -> None:
    load_captured_state()
    finish_round_2()
    audit.round_3()
    audit.round_4()
    audit.round_5()
    records = [
        item
        for operation in audit.OPERATIONS
        for item in audit.attempts_by_operation[operation]
    ]
    counts = {
        operation: len(audit.attempts_by_operation[operation])
        for operation in audit.OPERATIONS
    }
    if audit.sequence != 105 or len(records) != 105 or set(counts.values()) != {5}:
        raise RuntimeError(f"ADMIN completion contract failed: {audit.sequence}, {counts}")
    if audit.sha(audit.SOURCE_PATH) != audit.SOURCE_DIGEST:
        raise RuntimeError("practice/source changed during ADMIN continuation.")
    registry = audit.profile_config.load_profile_registry()
    if registry.active.uid != audit.PROFILE_UID:
        raise RuntimeError("ADMIN finished on the wrong active Profile.")
    current = json.loads((audit.STORE / "state.json").read_text(encoding="utf-8"))["current"]
    if current != audit.ENTRY:
        raise RuntimeError(f"ADMIN did not restore ENTRY: {current}")
    audit.persist_ledger()
    print("ADMIN_CAPTURE_COMPLETE 105/105", flush=True)


if __name__ == "__main__":
    finish()
