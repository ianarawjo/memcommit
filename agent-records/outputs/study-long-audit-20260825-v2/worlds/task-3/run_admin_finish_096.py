#!/usr/bin/env python3
"""Finish task-3 ADMIN at sequences 96..105 after identity recovery."""

from __future__ import annotations

from collections import Counter
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
BASE = HERE / "run_admin_continue.py"


def load_base():
    spec = importlib.util.spec_from_file_location("task3_admin_finish96_base", BASE)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load ADMIN finish base")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def restore(namespace: dict[str, object]) -> None:
    ledger = json.loads(Path(namespace["LEDGER"]).read_text(encoding="utf-8"))
    if ledger.get("total_attempts") != 95:
        raise SystemExit("Expected exact ADMIN finish boundary 95/105")
    records = [
        item
        for value in ledger["operations"].values()
        for item in value["attempts"]
    ]
    if sorted(item["sequence"] for item in records) != list(range(1, 96)):
        raise SystemExit("Retained ADMIN sequence is not exactly 1..95")
    namespace["attempts_by_operation"] = {
        operation: list(ledger["operations"][operation]["attempts"])
        for operation in namespace["OPERATIONS"]
    }
    namespace["sequence"] = 95
    namespace["round_number"] = 5
    host = json.loads(Path(namespace["HOST_READS"]).read_text(encoding="utf-8"))
    namespace["host_reads"] = host["host_reads"]


def finish(namespace: dict[str, object]) -> None:
    c = str(namespace["C"])
    entry = str(namespace["ENTRY"])
    run = namespace["run"]
    namespace["round_number"] = 5

    run("lock", ["lock", "--profile"], method="whole active Profile lock")
    run("unlock", ["unlock", "--profile"], method="paired whole active Profile unlock")
    run("log", ["log", "--actions", "--limit", "100"], method="Study action ledger")
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
    # Static equivalence to the runner's active identity pre-assert, performed
    # before the first post-recovery counted call.
    identity = namespace["assert_identity"](
        label="pre-sequence96 runner identity prerequisite"
    )
    if identity["profile_uid"] != namespace["PROFILE_UID"]:
        raise RuntimeError("Runner identity prerequisite failed")
    base.install_guarded_run(namespace)
    finish(namespace)


if __name__ == "__main__":
    main()
