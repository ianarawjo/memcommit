#!/usr/bin/env python3
"""Finish task-3 ADMIN at sequences 90..105 without replay."""

from __future__ import annotations

from collections import Counter
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
BASE = HERE / "run_admin_continue.py"


def load_base():
    spec = importlib.util.spec_from_file_location("task3_admin_finish_base", BASE)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load ADMIN finish base")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def restore(namespace: dict[str, object]) -> None:
    ledger = json.loads(Path(namespace["LEDGER"]).read_text(encoding="utf-8"))
    if ledger.get("total_attempts") != 89:
        raise SystemExit("Expected exact ADMIN finish boundary 89/105")
    records = [
        item
        for value in ledger["operations"].values()
        for item in value["attempts"]
    ]
    if sorted(item["sequence"] for item in records) != list(range(1, 90)):
        raise SystemExit("Retained ADMIN sequence is not exactly 1..89")
    namespace["attempts_by_operation"] = {
        operation: list(ledger["operations"][operation]["attempts"])
        for operation in namespace["OPERATIONS"]
    }
    namespace["sequence"] = 89
    namespace["round_number"] = 5
    host = json.loads(Path(namespace["HOST_READS"]).read_text(encoding="utf-8"))
    namespace["host_reads"] = host["host_reads"]


def finish(namespace: dict[str, object]) -> None:
    c = str(namespace["C"])
    entry = str(namespace["ENTRY"])
    eval_ledger = str(namespace["EVAL_LEDGER"])
    import_context = str(namespace["IMPORT_CONTEXT"])
    namespace["round_number"] = 5
    run = namespace["run"]

    run("config", ["config", "set", "provider"], method="missing config value validation")
    run(
        "eval", ["eval", "semantic", "status", "--ledger-dir", eval_ledger],
        method="accumulated semantic Eval status",
    )
    run(
        "help",
        ["help", "Generate an LLM-based answer from readable Context knowledge "
         "or an authorized concealed query-only view."],
        method="Study copied-text guard before provider",
    )
    run(
        "import",
        ["import", "context", import_context, "--from-profile",
         "admin-v2-missing-source-profile", "--as", f"{c}/import-missing", "--direct"],
        method="missing source Profile import", targets=(f"{c}/import-missing",),
    )
    run(
        "init", ["init", f"{c}/missing-parent/leaf"],
        method="missing lexical parent without --parents",
        targets=(f"{c}/missing-parent/leaf",),
    )
    run(
        "init-study", ["init-study", "00000000-0000-0000-0000-000000000999"],
        method="UID-shaped invalid Study name",
    )
    run("lock", ["lock", "--profile"], method="whole active Profile lock")
    run("unlock", ["unlock", "--profile"], method="paired whole active Profile unlock")
    run(
        "log", ["log", "--actions", "--limit", "100"], method="Study action ledger",
    )
    run(
        "profile", ["profile", "use", "admin-v2-task-3-missing"],
        method="missing Profile selection",
    )
    run(
        "provider", ["provider", "probe", "--operation", "query"],
        method="single synthetic Query provider probe",
    )
    run("pwd", ["pwd"], method="late accumulated current pointer")
    run(
        "share", ["share", c, "--to", "admin-v2-missing-endpoint", "--direct"],
        method="valid Source to missing receiver endpoint", targets=(c,),
    )
    run("shell-init", ["shell-init", "bash"], method="unsupported shell validation")
    run(
        "rename",
        ["rename", f"{c}/tree/leaf-renamed", f"{c}/tree/leaf-cancel"],
        method="Init-created scratch confirmation declined",
        targets=(f"{c}/tree/leaf-renamed", f"{c}/tree/leaf-cancel"),
        stdin_text="n\n",
    )
    run(
        "switch", ["switch", entry], method="exact phase-entry restoration",
        targets=(entry,),
    )

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
    current = json.loads(
        (Path(namespace["STORE"]) / "state.json").read_text(encoding="utf-8")
    ).get("current")
    if current != entry:
        raise RuntimeError(f"ADMIN did not restore entry Context: {current}")
    namespace["persist_ledger"]()
    print("ADMIN_CAPTURE_COMPLETE 105/105", flush=True)


def main() -> None:
    base = load_base()
    namespace = base.specialized_namespace()
    restore(namespace)
    base.install_guarded_run(namespace)
    finish(namespace)


if __name__ == "__main__":
    main()
