#!/usr/bin/env python3
"""Resume task-3 ADMIN at sequence 38 without replaying counted calls.

The initial ADMIN harness stopped after sequence 37 because the read-only
command-stack reconstruction rejected the recursive Branch checkpoint set.
This continuation preserves the already-counted ledger, records the failed
stack reconstruction, derives the exact producer UID and member set directly
from the frozen Branch receipts, and continues the protocol exactly once.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
REFERENCE = HERE.parent / "practice-source/run_admin_audit.py"


def specialized_namespace() -> dict[str, object]:
    source = REFERENCE.read_text(encoding="utf-8")
    source = source.replace(
        'if __name__ == "__main__":\n    main()\n',
        '',
    )
    source = source.replace('WORLD = "practice-source"', 'WORLD = "task-3"')
    source = source.replace('worlds/practice-source', 'worlds/task-3')
    source = source.replace(
        'admin-v2-practice-source-inactive',
        'admin-v2-task-3-inactive',
    )
    source = source.replace(
        'admin-v2-practice-source-study',
        'admin-v2-task-3-study',
    )
    source = source.replace(
        'admin-v2-practice-source-workers',
        'admin-v2-task-3-workers',
    )
    source = source.replace('admin/v2-practice-source', 'admin/v2-task-3')
    source = source.replace(
        'admin-v2-practice-source-missing',
        'admin-v2-task-3-missing',
    )
    source = source.replace(
        'practice/admin-v2-missing-share-source',
        'task-3/local/admin-v2-missing-share-source',
    )
    source = source.replace(
        'practice/admin-v2-missing-branch-source',
        'task-3/local/admin-v2-missing-branch-source',
    )
    source = source.replace(
        'practice/admin-v2-missing-checkout',
        'task-3/local/admin-v2-missing-checkout',
    )
    # Once Rename M2 repairs the Round-1 inverse name, every later successful
    # Rename stays on an Init-created scratch Context. Branch/Checkout targets
    # retain their exact creation names so command-history membership remains
    # reconstructible for the remaining Undo/Redo transactions.
    source = source.replace(
        'f"{C}/renamed-1", "--source-root-only"',
        'f"{C}/b1", "--source-root-only"',
    ).replace(
        'targets=(f"{C}/renamed-1", f"{C}/b3")',
        'targets=(f"{C}/b1", f"{C}/b3")',
    )
    source = source.replace(
        'run("rename", ["rename", f"{C}/co3", f"{C}/renamed-co3", "--force"], method="Checkout3 result rename", targets=(f"{C}/co3", f"{C}/renamed-co3"))',
        'run("rename", ["rename", f"{C}/tree/leaf", f"{C}/tree/leaf-renamed", "--force"], method="Init-created nested scratch rename", targets=(f"{C}/tree/leaf", f"{C}/tree/leaf-renamed"))',
    )
    source = source.replace(
        'run("lock", ["lock", f"{C}/co4-tree", "--recursive"], method="recursive Checkout4 tree lock", targets=(f"{C}/co4-tree", f"{C}/co4-tree/description"))',
        'run("lock", ["lock", C, "--recursive"], method="recursive scratch lock including Checkout4 tree", targets=(C, f"{C}/co4-tree", f"{C}/co4-tree/description"))',
    ).replace(
        'run("rename", ["rename", f"{C}/co4-tree", f"{C}/renamed-co4-tree", "--force"], method="locked Checkout4 rename failure", targets=(f"{C}/co4-tree", f"{C}/renamed-co4-tree"))',
        'run("rename", ["rename", f"{C}/tree/leaf-renamed", f"{C}/tree/leaf-locked", "--force"], method="locked Init-created scratch rename failure", targets=(f"{C}/tree/leaf-renamed", f"{C}/tree/leaf-locked"))',
    ).replace(
        'run("unlock", ["unlock", f"{C}/co4-tree", "--recursive"], method="paired Checkout4 tree unlock", targets=(f"{C}/co4-tree", f"{C}/co4-tree/description"))',
        'run("unlock", ["unlock", C, "--recursive"], method="paired recursive scratch unlock", targets=(C, f"{C}/co4-tree", f"{C}/co4-tree/description"))',
    )
    source = source.replace(
        'run("rename", ["rename", f"{C}/co4-tree", f"{C}/renamed-co4-cancel"], method="explicit confirmation declined", targets=(f"{C}/co4-tree", f"{C}/renamed-co4-cancel"), stdin_text="n\\n")',
        'run("rename", ["rename", f"{C}/tree/leaf-renamed", f"{C}/tree/leaf-cancel"], method="Init-created scratch confirmation declined", targets=(f"{C}/tree/leaf-renamed", f"{C}/tree/leaf-cancel"), stdin_text="n\\n")',
    )
    namespace: dict[str, object] = {
        "__name__": "task3_admin_protocol_resume",
        "__file__": str(HERE / "run_admin_audit.py"),
    }
    exec(compile(source, str(REFERENCE), "exec"), namespace)

    store = Path(namespace["STORE"])
    source_path = (
        store / "contexts/task-3/local/personal-memory/2024/03/context.json"
    )
    namespace.update(
        {
            "C": "task-3/local/admin-v2-scratch",
            "R": "task-3/local/guardrails",
            "R_CHILD": "task-3/local/guardrails/approval-and-delivery",
            "O": "task-1",
            "O_CHILD": "task-1/description",
            "ENTRY": "practice",
            "SOURCE_PATH": source_path,
            "SOURCE_DIGEST": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        }
    )
    return namespace


def restore_evidence(namespace: dict[str, object]) -> None:
    ledger_path = Path(namespace["LEDGER"])
    host_path = Path(namespace["HOST_READS"])
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    if ledger.get("total_attempts") != 37:
        raise SystemExit("Expected exactly 37 retained ADMIN attempts.")
    records = [
        item
        for value in ledger["operations"].values()
        for item in value["attempts"]
    ]
    if sorted(item["sequence"] for item in records) != list(range(1, 38)):
        raise SystemExit("Retained ADMIN sequence is not exactly 1..37.")
    restored = {operation: [] for operation in namespace["OPERATIONS"]}
    for operation, value in ledger["operations"].items():
        restored[operation].extend(value["attempts"])
    namespace["attempts_by_operation"] = restored
    namespace["sequence"] = 37
    namespace["round_number"] = 2

    host = json.loads(host_path.read_text(encoding="utf-8"))
    namespace["host_reads"] = host["host_reads"]

    raw20 = Path(namespace["RAW"]) / "020-shell_init-m1.txt"
    text = raw20.read_text(encoding="utf-8")
    namespace["shell_init_m1"] = text.split("\nSTDOUT\n", 1)[1].split(
        "\n\nSTDERR\n", 1
    )[0]
    run_ids = [
        item.get("run_id")
        for item in namespace["host_reads"]
        if item.get("kind") == "eval_full_run_id"
    ]
    if len(run_ids) != 1 or not isinstance(run_ids[0], str):
        raise SystemExit("Retained Eval M2 full run ID is unavailable.")
    namespace["eval_run_id"] = run_ids[0]


def install_guarded_run(namespace: dict[str, object]) -> None:
    original_run = namespace["run"]

    def guarded_run(
        operation: str,
        args: list[str],
        *,
        method: str,
        targets: tuple[str, ...] = (),
        stdin_text: str | None = None,
    ):
        before_tree = namespace["context_tree_digest"]()
        before_registry = namespace["sha"](namespace["REGISTRY"])
        completed = original_run(
            operation,
            args,
            method=method,
            targets=targets,
            stdin_text=stdin_text,
        )
        after_tree = namespace["context_tree_digest"]()
        after_registry = namespace["sha"](namespace["REGISTRY"])
        if operation == "share":
            unchanged = (
                before_tree == after_tree and before_registry == after_registry
            )
            namespace["record_host"](
                "share_zero_delivery_assertion",
                command_args=args,
                context_tree_unchanged=before_tree == after_tree,
                registry_unchanged=before_registry == after_registry,
                delivery_count=0,
                result="PASS" if unchanged else "FAIL",
            )
            if not unchanged:
                raise RuntimeError("Share trial changed sender/registry state")
        if operation == "init-study":
            blocked = completed.returncode != 0
            namespace["record_host"](
                "init_study_zero_success_assertion",
                command_args=args,
                exit=completed.returncode,
                success_count=0 if blocked else 1,
                result="PASS" if blocked else "FAIL",
            )
            if not blocked:
                raise RuntimeError("init-study unexpectedly succeeded")
        return completed

    namespace["run"] = guarded_run


def receipt_snapshot(
    namespace: dict[str, object],
    *,
    label: str,
    side: str,
    expected_uid: str | None,
    stack_error: Exception,
) -> str:
    c = str(namespace["C"])
    if label.startswith("round2"):
        target_root = f"{c}/b2-tree"
    elif label.startswith("round3"):
        target_root = f"{c}/co3"
    elif label.startswith("round4") or label.startswith("round5"):
        target_root = f"{c}/co4-tree"
    else:
        raise RuntimeError(f"No receipt fallback target for {label}")

    store = Path(namespace["STORE"])
    target_dir = store / "contexts" / Path(*target_root.split("/"))
    candidates: list[tuple[Path, dict[str, object]]] = []
    for path in target_dir.glob("checkpoints/*.json"):
        value = json.loads(path.read_text(encoding="utf-8"))
        args = value.get("args")
        receipt = args.get("branch_tree") if isinstance(args, dict) else None
        if value.get("command") == "branch" and isinstance(receipt, dict):
            candidates.append((path, value))
    if not candidates:
        raise RuntimeError(f"No Branch receipt at {target_root}")
    root_path, root_record = max(candidates, key=lambda item: item[0].stat().st_mtime_ns)
    args = root_record["args"]
    receipt = args["branch_tree"]
    operation_uid = receipt["operation_uid"]
    unit_uid = f"branch:{operation_uid}"
    if expected_uid is not None and unit_uid != expected_uid:
        raise RuntimeError(
            f"{label}: expected receipt unit {expected_uid}, got {unit_uid}"
        )

    members = []
    missing = []
    for item in args["command_contexts"]:
        name = item["name"]
        context_dir = store / "contexts" / Path(*name.split("/"))
        checkpoint_uid = None
        checkpoint_path = None
        for path in context_dir.glob("checkpoints/*.json"):
            value = json.loads(path.read_text(encoding="utf-8"))
            value_args = value.get("args")
            value_receipt = (
                value_args.get("branch_tree")
                if isinstance(value_args, dict)
                else None
            )
            if (
                value.get("command") == "branch"
                and isinstance(value_receipt, dict)
                and value_receipt.get("operation_uid") == operation_uid
            ):
                checkpoint_uid = value.get("uid")
                checkpoint_path = str(path.relative_to(store))
                break
        if checkpoint_uid is None:
            missing.append(name)
        members.append(
            {
                "context_uid": item["uid"],
                "context_name": name,
                "checkpoint_uid": checkpoint_uid,
                "checkpoint_path": checkpoint_path,
            }
        )
    granted_target = namespace["staged_granted_target"]()
    if granted_target is not None:
        raise RuntimeError(f"{label}: staged-update.granted_target is not null")
    namespace["record_host"](
        "command_stack_reconstruction_failure_with_receipt_evidence",
        label=label,
        side=side,
        unit_uid=unit_uid,
        command="branch",
        target_root=target_root,
        root_checkpoint_uid=root_record.get("uid"),
        root_checkpoint_path=str(root_path.relative_to(store)),
        member_set=members,
        missing_member_checkpoints=missing,
        staged_update_granted_target=granted_target,
        stack_error=f"{type(stack_error).__name__}: {stack_error}",
        result="DEFECT" if not missing else "INCOMPLETE_EVIDENCE",
    )
    if missing:
        raise RuntimeError(f"{label}: receipt member checkpoints missing: {missing}")
    return unit_uid


def resume(namespace: dict[str, object]) -> None:
    namespace["round_number"] = 2
    c = str(namespace["C"])
    # Preserve the exact read-only failure that stopped the first process,
    # then use the still-unused Rename M2 as a counted inverse-name recovery.
    try:
        namespace["stack_snapshot"](
            label="round2 pre-recovery stack reconstruction",
            side="undo",
        )
    except Exception as error:
        receipt_snapshot(
            namespace,
            label="round2 pre-recovery stack reconstruction",
            side="undo",
            expected_uid=None,
            stack_error=error,
        )
    else:
        raise RuntimeError("Expected the retained pre-recovery stack defect")
    namespace["run"](
        "rename",
        ["rename", f"{c}/renamed-1", f"{c}/b1", "--force"],
        method="counted inverse-name recovery for Round1 Branch owner",
        targets=(f"{c}/renamed-1", f"{c}/b1"),
    )
    unit = namespace["stack_snapshot"](
        label="round2 immediately after inverse Rename and before Undo2 --keep",
        side="undo",
    )
    namespace["run"](
        "undo",
        ["undo", "--keep"],
        method="verified recursive Branch undo compatibility route",
        targets=(f"{c}/b2-tree", f"{c}/b2-tree/goals"),
    )
    namespace["stack_snapshot"](
        label="round2 redo-top same UID",
        side="redo",
        expected_uid=unit,
    )
    namespace["run"](
        "redo",
        ["redo"],
        method="verified recursive Branch redo",
        targets=(f"{c}/b2-tree", f"{c}/b2-tree/goals"),
    )
    namespace["run"](
        "lock",
        ["lock", f"{c}/b2-tree", "--recursive"],
        method="recursive branch-tree lock",
        targets=(f"{c}/b2-tree", f"{c}/b2-tree/goals"),
    )
    namespace["run"](
        "unlock",
        ["unlock", f"{c}/b2-tree", "--recursive"],
        method="paired recursive branch-tree unlock",
        targets=(f"{c}/b2-tree", f"{c}/b2-tree/goals"),
    )
    namespace["round_3"]()
    namespace["round_4"]()
    namespace["round_5"]()

    sequence = namespace["sequence"]
    counts = Counter(
        operation
        for operation, values in namespace["attempts_by_operation"].items()
        for _ in values
    )
    if sequence != 105 or set(counts.values()) != {5}:
        raise RuntimeError(f"ADMIN attempt contract failed: {sequence}, {counts}")
    if namespace["sha"](namespace["SOURCE_PATH"]) != namespace["SOURCE_DIGEST"]:
        raise RuntimeError("task-3 guarded source changed during ADMIN")
    namespace["persist_ledger"]()
    print("ADMIN_CAPTURE_COMPLETE 105/105", flush=True)


def main() -> None:
    namespace = specialized_namespace()
    restore_evidence(namespace)
    install_guarded_run(namespace)
    resume(namespace)


if __name__ == "__main__":
    main()
