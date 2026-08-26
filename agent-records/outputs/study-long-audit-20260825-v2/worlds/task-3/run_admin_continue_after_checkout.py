#!/usr/bin/env python3
"""Resume task-3 ADMIN at sequence 45 after inherited history broke stacks."""

from __future__ import annotations

from collections import Counter
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
BASE_PATH = HERE / "run_admin_continue.py"


def load_base():
    spec = importlib.util.spec_from_file_location("task3_admin_resume_base", BASE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load task-3 ADMIN continuation base")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def restore(namespace: dict[str, object]) -> None:
    ledger = json.loads(Path(namespace["LEDGER"]).read_text(encoding="utf-8"))
    if ledger.get("total_attempts") != 44:
        raise SystemExit("Expected exactly 44 retained ADMIN attempts.")
    records = [
        item
        for value in ledger["operations"].values()
        for item in value["attempts"]
    ]
    if sorted(item["sequence"] for item in records) != list(range(1, 45)):
        raise SystemExit("Retained ADMIN sequence is not exactly 1..44.")
    namespace["attempts_by_operation"] = {
        operation: list(ledger["operations"][operation]["attempts"])
        for operation in namespace["OPERATIONS"]
    }
    namespace["sequence"] = 44
    namespace["round_number"] = 3
    host = json.loads(Path(namespace["HOST_READS"]).read_text(encoding="utf-8"))
    namespace["host_reads"] = host["host_reads"]
    raw20 = Path(namespace["RAW"]) / "020-shell_init-m1.txt"
    raw_text = raw20.read_text(encoding="utf-8")
    namespace["shell_init_m1"] = raw_text.split("\nSTDOUT\n", 1)[1].split(
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


def install_receipt_fallback(base, namespace: dict[str, object]) -> None:
    original = namespace["stack_snapshot"]

    def tolerant(
        *,
        label: str,
        side: str,
        expected_uid: str | None = None,
        expected_command: str = "branch",
    ) -> str:
        try:
            return original(
                label=label,
                side=side,
                expected_uid=expected_uid,
                expected_command=expected_command,
            )
        except Exception as error:
            return base.receipt_snapshot(
                namespace,
                label=label,
                side=side,
                expected_uid=expected_uid,
                stack_error=error,
            )

    namespace["stack_snapshot"] = tolerant


def finish_round_3(namespace: dict[str, object]) -> None:
    c = str(namespace["C"])
    o = str(namespace["O"])
    o_child = str(namespace["O_CHILD"])
    import_uid = str(namespace["IMPORT_MEMORY_UID"])
    import_context = str(namespace["IMPORT_MEMORY_CONTEXT"])
    import_profile = str(namespace["IMPORT_PROFILE"])
    eval_ledger = str(namespace["EVAL_LEDGER"])
    eval_run_id = str(namespace["eval_run_id"])
    namespace["round_number"] = 3

    unit = namespace["stack_snapshot"](
        label="round3 Checkout3 producer before Switch O",
        side="undo",
    )
    namespace["run"](
        "switch",
        ["switch", o],
        method="switch away while Checkout3 stays receipt-identifiable",
        targets=(o, f"{c}/co3"),
    )
    namespace["stack_snapshot"](
        label="round3 top UID direct receipt before Undo3",
        side="undo",
        expected_uid=unit,
    )
    namespace["run"](
        "undo",
        ["undo"],
        method="Checkout3 undo under inherited-history reconstruction defect",
        targets=(f"{c}/co3", o),
    )
    namespace["stack_snapshot"](
        label="round3 Checkout3 receipt before Redo3",
        side="redo",
        expected_uid=unit,
    )
    namespace["run"](
        "redo",
        ["redo"],
        method="Checkout3 redo after fail-closed Undo",
        targets=(f"{c}/co3", o),
    )
    namespace["run"](
        "status", ["status", "--recursive"],
        method="recursive current inventory", targets=(o, o_child),
    )
    namespace["run"](
        "config", ["config", "show"], method="explicit lane config show",
    )
    namespace["run"](
        "eval", ["eval", "semantic", "check", eval_run_id, "--ledger-dir", eval_ledger],
        method="full M2 run-ID validation",
    )
    namespace["run"](
        "help", ["help", "query"], method="exact Query operation lookup",
    )
    namespace["run"](
        "import",
        ["import", "memory", import_uid, "--from-profile", import_profile,
         "--context", import_context, "--into", c],
        method="exact Memory by-value import", targets=(c,),
    )
    namespace["run"](
        "lock", ["lock", "--memory", import_uid[:8], "--context", c],
        method="exact imported Memory lock", targets=(c,),
    )
    namespace["run"](
        "unlock", ["unlock", "--memory", import_uid[:8], "--context", c],
        method="paired exact imported Memory unlock", targets=(c,),
    )
    namespace["run"](
        "log", ["log", "--memory", import_uid[:8], "--context", c, "--limit", "5"],
        method="exact imported Memory lineage", targets=(c,),
    )
    namespace["run"](
        "profile", ["profile", "list"], method="full Profile inventory",
    )
    namespace["run"](
        "provider", ["provider", "status", "--operation", "query"],
        method="effective Query provider status",
    )
    namespace["run"](
        "pwd", ["pwd"], method="independent O pointer after failed Redo3", targets=(o,),
    )
    namespace["run"](
        "share", ["share", "--to", "admin-v2-missing-endpoint"],
        method="missing Source with incomplete receiver route",
    )
    shell = namespace["run"](
        "shell-init", ["shell-init", "zsh"],
        method="zsh output for host syntax validation",
    )
    namespace["host_shell_check"](
        "shell_init_zsh_syntax", ["zsh", "-n"], shell.stdout,
    )
    namespace["run"](
        "init", ["init", c], method="existing scratch collision", targets=(c,),
    )
    namespace["run"](
        "init-study",
        ["init-study", "admin-v2-task-3-study", "--scenario", "legacy-v1",
         "--from-profile", "admin-v2-missing-baseline"],
        method="missing baseline Profile",
    )
    namespace["run"](
        "rename",
        ["rename", f"{c}/tree/leaf", f"{c}/tree/leaf-renamed", "--force"],
        method="Init-created nested scratch rename",
        targets=(f"{c}/tree/leaf", f"{c}/tree/leaf-renamed"),
    )


def finish(namespace: dict[str, object]) -> None:
    finish_round_3(namespace)
    namespace["round_4"]()
    namespace["round_5"]()
    counts = Counter(
        operation
        for operation, values in namespace["attempts_by_operation"].items()
        for _ in values
    )
    if namespace["sequence"] != 105 or set(counts.values()) != {5}:
        raise RuntimeError(
            f"ADMIN attempt contract failed: {namespace['sequence']}, {counts}"
        )
    if namespace["sha"](namespace["SOURCE_PATH"]) != namespace["SOURCE_DIGEST"]:
        raise RuntimeError("task-3 guarded source changed during ADMIN")
    namespace["persist_ledger"]()
    print("ADMIN_CAPTURE_COMPLETE 105/105", flush=True)


def main() -> None:
    base = load_base()
    namespace = base.specialized_namespace()
    restore(namespace)
    base.install_guarded_run(namespace)
    install_receipt_fallback(base, namespace)
    finish(namespace)


if __name__ == "__main__":
    main()
