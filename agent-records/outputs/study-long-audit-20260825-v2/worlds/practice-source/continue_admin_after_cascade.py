#!/usr/bin/env python3
"""Finish ADMIN with malformed Branch history retained as a negative control."""

from __future__ import annotations

import json
from pathlib import Path

import run_admin_audit as audit


CASCADE_DEFECT = "PS2-A-BRANCH-HISTORY-CASCADE"


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
    if len(records) != 44 or [item["sequence"] for item in records] != list(range(1, 45)):
        raise SystemExit("Expected exactly captured ADMIN sequences 1..44.")
    if len(list(audit.RAW.glob("*.txt"))) != 44:
        raise SystemExit("Raw ADMIN evidence is not exactly 44 files.")
    if (audit.RAW / "045-switch-m3.txt").exists():
        raise SystemExit("Cascade continuation already started; refusing replay.")
    for operation in audit.OPERATIONS:
        audit.attempts_by_operation[operation] = list(
            ledger["operations"][operation]["attempts"]
        )
    audit.host_reads = list(host_ledger["host_reads"])
    audit.sequence = 44
    audit.round_number = 3
    audit.eval_run_id = next(
        str(item["run_id"])
        for item in audit.host_reads
        if item.get("kind") == "eval_full_run_id"
    )
    if audit.sha(audit.SOURCE_PATH) != audit.SOURCE_DIGEST:
        raise SystemExit("practice/source changed before cascade continuation.")
    audit.assert_identity(label="ADMIN continuation entry after cascade decision gate")


def record_exact_invalid_target_sets() -> None:
    target_sets = [
        {
            "unit_uid": "branch:2d646a57-621f-42b7-b9e2-97dd909980e5",
            "target_contexts": [
                {
                    "context_uid": "ea8d2437-a035-47cb-8ba6-f0bbdc085068",
                    "context_name": f"{audit.C}/b3",
                    "checkpoint_uid": "2084392b-c951-4e18-91de-e942f92cc1f3",
                }
            ],
        },
        {
            "unit_uid": "branch:39879ca8-ed15-428b-be1f-59fdc4063a49",
            "target_contexts": [
                {
                    "context_uid": "de468ea4-5d2d-4712-ba21-257215cacc90",
                    "context_name": f"{audit.C}/co3",
                    "checkpoint_uid": "cf6eb124-8096-4278-b6c3-9fe35535c2d5",
                }
            ],
        },
    ]
    for item in target_sets:
        target = item["target_contexts"][0]
        path = (
            audit.STORE
            / "contexts"
            / Path(*target["context_name"].split("/"))
            / "context.json"
        )
        value = json.loads(path.read_text(encoding="utf-8"))
        if value["uid"] != target["context_uid"] or value["name"] != target["context_name"]:
            raise RuntimeError(f"Invalid-owner target set changed: {target}")
        descendants = [
            name
            for name in audit.MemoryStore(
                root=audit.STORE,
                create=False,
                resolve_granted_links=False,
            ).list_context_names()
            if name.startswith(target["context_name"] + "/")
        ]
        if descendants:
            raise RuntimeError(f"Unexpected invalid-owner descendants: {descendants}")
    audit.record_host(
        "invalid_creation_unit_target_sets",
        target_sets=target_sets,
        total_target_contexts=2,
        physical_descendant_count=0,
        supplemental_delete_allowed=False,
        disposition="RETAIN_AS_NEGATIVE_CONTROL",
        result="PASS",
    )


def verify_future_checkout_source_clean() -> None:
    store = audit.MemoryStore(
        root=audit.STORE,
        create=False,
        resolve_granted_links=False,
    )
    names = [
        name
        for name in store.list_context_names()
        if name == audit.O or name.startswith(audit.O + "/")
    ]
    branch_checkpoints: list[dict[str, str]] = []
    checkpoint_files = 0
    for name in names:
        directory = audit.STORE / "contexts" / Path(*name.split("/")) / "checkpoints"
        for path in directory.glob("*.json"):
            checkpoint_files += 1
            entry = json.loads(path.read_text(encoding="utf-8"))
            if entry.get("command") == "branch":
                branch_checkpoints.append(
                    {"context_name": name, "checkpoint_uid": str(entry.get("uid"))}
                )
    audit.record_host(
        "future_checkout_source_checkpoint_scan",
        source_root=audit.O,
        contexts_scanned=names,
        checkpoint_files=checkpoint_files,
        branch_checkpoints=branch_checkpoints,
        branch_checkpoint_count=len(branch_checkpoints),
        result="PASS" if not branch_checkpoints else "FAIL",
    )
    if branch_checkpoints:
        raise RuntimeError(f"Future Checkout4 Source is not clean: {branch_checkpoints}")


def assert_malformed_stack(*, label: str) -> None:
    store = audit.MemoryStore(
        root=audit.STORE,
        create=False,
        resolve_granted_links=False,
    )
    error_type = None
    error_text = None
    try:
        audit.build_command_stacks(store)
    except Exception as error:  # exact type/text asserted below
        error_type = f"{type(error).__module__}.{type(error).__name__}"
        error_text = str(error)
    passed = (
        error_type == "memcommit.command_history.CommandHistoryError"
        and error_text == "Branch checkpoint owner is outside its creation membership."
        and audit.staged_granted_target() is None
    )
    audit.record_host(
        "command_stack_negative_control",
        label=label,
        first_failing_context=f"{audit.C}/b3",
        error_type=error_type,
        error=error_text,
        staged_update_granted_target=audit.staged_granted_target(),
        result="PASS" if passed else "FAIL",
    )
    if not passed:
        raise RuntimeError(f"Malformed stack negative control changed: {error_type}: {error_text}")


def run_fail_closed_history(
    operation: str,
    args: list[str],
    *,
    method: str,
    targets: tuple[str, ...] = (),
) -> None:
    assert_malformed_stack(label=f"before {operation} M{audit.round_number}")
    before_current = json.loads(
        (audit.STORE / "state.json").read_text(encoding="utf-8")
    )["current"]
    result = audit.run(operation, args, method=method, targets=targets)
    record = audit.attempts_by_operation[operation][-1]
    after_current = json.loads(
        (audit.STORE / "state.json").read_text(encoding="utf-8")
    )["current"]
    fail_closed = (
        result.returncode != 0
        and record["pre_context_tree_digest"] == record["post_context_tree_digest"]
        and record["pre_target_digest"] == record["post_target_digest"]
        and record["pre_registry_digest"] == record["post_registry_digest"]
        and record["pre_config_digest"] == record["post_config_digest"]
        and before_current == after_current
    )
    record["defect_ids"] = [CASCADE_DEFECT]
    record["recovery_evidence"] = (
        "Malformed Branch history retained as a negative control; frozen stack "
        "construction failed before Context or current-pointer mutation."
    )
    audit.persist_ledger()
    audit.record_host(
        "history_command_fail_closed",
        operation=operation,
        attempt=audit.round_number,
        sequence=audit.sequence,
        exit=result.returncode,
        before_current=before_current,
        after_current=after_current,
        pre_context_tree_digest=record["pre_context_tree_digest"],
        post_context_tree_digest=record["post_context_tree_digest"],
        pre_target_digest=record["pre_target_digest"],
        post_target_digest=record["post_target_digest"],
        result="PASS" if fail_closed else "FAIL",
    )
    if not fail_closed:
        raise RuntimeError(f"{operation} M{audit.round_number} did not fail closed.")


def finish_round_3() -> None:
    audit.round_number = 3
    audit.run(
        "switch",
        ["switch", audit.O],
        method="switch away while malformed Checkout3 stays fail-closed",
        targets=(audit.O, f"{audit.C}/co3"),
    )
    run_fail_closed_history(
        "undo",
        ["undo"],
        method="malformed Checkout3 history negative-control failure",
        targets=(f"{audit.C}/co3", audit.O),
    )
    run_fail_closed_history(
        "redo",
        ["redo"],
        method="malformed Checkout3 history negative-control failure",
        targets=(f"{audit.C}/co3", audit.O),
    )
    audit.run("status", ["status", "--recursive"], method="recursive current inventory", targets=(audit.O, audit.O_CHILD))
    audit.run("config", ["config", "show"], method="explicit lane config show")
    audit.run("eval", ["eval", "semantic", "check", audit.eval_run_id, "--ledger-dir", str(audit.EVAL_LEDGER)], method="full M2 run-ID validation")
    audit.run("help", ["help", "query"], method="exact Query operation lookup")
    audit.run("import", ["import", "memory", audit.IMPORT_MEMORY_UID, "--from-profile", audit.IMPORT_PROFILE, "--context", audit.IMPORT_MEMORY_CONTEXT, "--into", audit.C], method="exact Memory by-value import", targets=(audit.C,))
    audit.run("lock", ["lock", "--memory", audit.IMPORT_MEMORY_UID[:8], "--context", audit.C], method="exact imported Memory lock", targets=(audit.C,))
    audit.run("unlock", ["unlock", "--memory", audit.IMPORT_MEMORY_UID[:8], "--context", audit.C], method="paired exact imported Memory unlock", targets=(audit.C,))
    audit.run("log", ["log", "--memory", audit.IMPORT_MEMORY_UID[:8], "--context", audit.C, "--limit", "5"], method="exact imported Memory lineage", targets=(audit.C,))
    audit.run("profile", ["profile", "list"], method="full Profile inventory")
    audit.run("provider", ["provider", "status", "--operation", "query"], method="effective Query provider status")
    audit.run("pwd", ["pwd"], method="independent O pointer after failed Redo3", targets=(audit.O,))
    audit.run("share", ["share", "--to", "admin-v2-missing-endpoint"], method="missing Source with incomplete receiver route")
    shell = audit.run("shell-init", ["shell-init", "zsh"], method="zsh output for host syntax validation")
    audit.host_shell_check("shell_init_zsh_syntax", ["zsh", "-n"], shell.stdout)
    audit.run("init", ["init", audit.C], method="existing scratch collision", targets=(audit.C,))
    audit.run("init-study", ["init-study", "admin-v2-practice-source-study", "--scenario", "legacy-v1", "--from-profile", "admin-v2-missing-baseline"], method="missing baseline Profile")
    audit.run("rename", ["rename", f"{audit.C}/tree/leaf", f"{audit.C}/tree/renamed-leaf", "--force"], method="init-created scratch leaf rename", targets=(f"{audit.C}/tree/leaf", f"{audit.C}/tree/renamed-leaf"))


def finish_round_4() -> None:
    audit.round_number = 4
    run_fail_closed_history("redo", ["redo"], method="malformed history early Redo negative-control failure")
    audit.run("branch", ["branch", audit.C, "--from", audit.R, "--direct"], method="existing scratch-root collision", targets=(audit.C, audit.R))
    audit.run("status", ["status", "--direct", "--recursive"], method="conflicting direct+recursive validation", targets=(audit.O,))
    audit.run("config", ["config", "set", "provider", "codex_chatgpt"], method="lane-local semantic provider config key")
    audit.run("eval", ["eval", "semantic", "task2-status", "--all", "--ledger-dir", str(audit.EVAL_LEDGER)], method="all retained Task2 status")
    audit.run("help", ["help", "atomize"], method="different exact Atomize operation lookup")
    audit.run("import", ["import", "memory", audit.IMPORT_MEMORY_UID, "--from-profile", audit.IMPORT_PROFILE, "--context", audit.IMPORT_MEMORY_CONTEXT, "--into", audit.C], method="repeat exact Memory collision", targets=(audit.C,))
    audit.run("init", ["init", "00000000-0000-0000-0000-000000000777"], method="UID-shaped Context name failure")
    audit.run("init-study", ["init-study", "admin-v2-practice-source-workers", "--prewarm-workers", "0"], method="prewarm worker validation failure")
    audit.run("log", ["log", "--operations", "--limit", "50"], method="Profile operation-attempt ledger")
    audit.run("profile", ["profile", "use", audit.PROFILE_NAME], method="idempotent use of same active Profile")
    audit.run("provider", ["provider", "use", "codex_chatgpt", "--operation", "query"], method="Study-locked Query provider mutation failure")
    audit.run("pwd", ["pwd"], method="pre-Checkout4 independent root pointer", targets=(audit.O,))
    audit.run("share", ["share", audit.C, "--direct", "--recursive"], method="mutually exclusive Share scope flags", targets=(audit.C,))
    shell = audit.run("shell-init", ["shell-init", "zsh"], method="zsh output sourced in disposable shell")
    audit.host_shell_check("shell_init_disposable_source", ["zsh", "-dfc", "source /dev/stdin; whence -w mem"], shell.stdout)
    audit.run("checkout", ["checkout", "-b", f"{audit.C}/co4-tree", "--recursive"], method="Git-style recursive branch checkout from host-verified clean Source", targets=(audit.O, f"{audit.C}/co4-tree", f"{audit.C}/co4-tree/description"))
    audit.run("switch", ["switch", f"{audit.C}/co4-tree/description"], method="verified branched child switch", targets=(f"{audit.C}/co4-tree", f"{audit.C}/co4-tree/description"))
    audit.run("lock", ["lock", f"{audit.C}/co4-tree", "--recursive"], method="recursive Checkout4 tree lock", targets=(f"{audit.C}/co4-tree", f"{audit.C}/co4-tree/description"))
    audit.run("rename", ["rename", f"{audit.C}/co4-tree", f"{audit.C}/renamed-co4-tree", "--force"], method="locked Checkout4 rename failure", targets=(f"{audit.C}/co4-tree", f"{audit.C}/renamed-co4-tree"))
    run_fail_closed_history("undo", ["undo"], method="malformed global history failure before locked Checkout4 restoration", targets=(f"{audit.C}/co4-tree", f"{audit.C}/co4-tree/description"))
    audit.run("unlock", ["unlock", f"{audit.C}/co4-tree", "--recursive"], method="paired Checkout4 tree unlock", targets=(f"{audit.C}/co4-tree", f"{audit.C}/co4-tree/description"))


def finish_round_5() -> None:
    audit.round_number = 5
    run_fail_closed_history("undo", ["undo"], method="malformed global history failure after Checkout4 Unlock", targets=(f"{audit.C}/co4-tree", f"{audit.C}/co4-tree/description"))
    run_fail_closed_history("redo", ["redo"], method="malformed global history Redo negative-control failure", targets=(f"{audit.C}/co4-tree", f"{audit.C}/co4-tree/description"))
    audit.run("status", ["status"], method="default direct status", targets=(f"{audit.C}/co4-tree",))
    audit.run("branch", ["branch", f"{audit.C}/b5", "--from", "practice/admin-v2-missing-branch-source", "--direct"], method="missing explicit Branch Source", targets=(f"{audit.C}/b5",))
    audit.run("checkout", ["checkout", "practice/admin-v2-missing-checkout"], method="missing exact checkout target")
    audit.run("config", ["config", "set", "provider"], method="missing config value validation")
    audit.run("eval", ["eval", "semantic", "status", "--ledger-dir", str(audit.EVAL_LEDGER)], method="accumulated semantic Eval status")
    audit.run("help", ["help", "Generate an LLM-based answer from readable Context knowledge or an authorized concealed query-only view."], method="Study copied-text guard before provider")
    audit.run("import", ["import", "context", audit.IMPORT_CONTEXT, "--from-profile", "admin-v2-missing-source-profile", "--as", f"{audit.C}/import-missing", "--direct"], method="missing source Profile import", targets=(f"{audit.C}/import-missing",))
    audit.run("init", ["init", f"{audit.C}/missing-parent/leaf"], method="missing lexical parent without --parents", targets=(f"{audit.C}/missing-parent/leaf",))
    audit.run("init-study", ["init-study", "00000000-0000-0000-0000-000000000999"], method="UID-shaped invalid Study name")
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


def finish() -> None:
    load_captured_state()
    record_exact_invalid_target_sets()
    verify_future_checkout_source_clean()
    finish_round_3()
    finish_round_4()
    finish_round_5()
    counts = {
        operation: len(audit.attempts_by_operation[operation])
        for operation in audit.OPERATIONS
    }
    if audit.sequence != 105 or set(counts.values()) != {5}:
        raise RuntimeError(f"ADMIN completion contract failed: {audit.sequence}, {counts}")
    if audit.sha(audit.SOURCE_PATH) != audit.SOURCE_DIGEST:
        raise RuntimeError("practice/source changed during ADMIN completion.")
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
