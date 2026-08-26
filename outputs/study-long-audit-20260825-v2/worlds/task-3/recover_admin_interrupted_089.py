#!/usr/bin/env python3
"""Record the already-invoked, SIGINT-interrupted ADMIN Checkout M5."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
BASE = HERE / "run_admin_continue.py"


def load_base():
    spec = importlib.util.spec_from_file_location("task3_admin_recovery_base", BASE)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load ADMIN recovery base")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    base = load_base()
    namespace = base.specialized_namespace()
    ledger_path = Path(namespace["LEDGER"])
    host_path = Path(namespace["HOST_READS"])
    raw = Path(namespace["RAW"]) / "089-checkout-m5.txt"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    host = json.loads(host_path.read_text(encoding="utf-8"))
    if ledger.get("total_attempts") != 88 or raw.exists():
        raise SystemExit("Interrupted sequence 89 is not at its exact recovery boundary")
    previous = next(
        item
        for value in ledger["operations"].values()
        for item in value["attempts"]
        if item["sequence"] == 88
    )
    namespace["host_reads"] = host["host_reads"]
    namespace["sequence"] = 89
    namespace["round_number"] = 5

    post_tree = namespace["context_tree_digest"]()
    post_registry = namespace["sha"](namespace["REGISTRY"])
    post_config = namespace["sha"](namespace["CONFIG"])
    post_source = namespace["sha"](namespace["SOURCE_PATH"])
    if (
        post_tree != previous["post_context_tree_digest"]
        or post_registry != previous["post_registry_digest"]
        or post_config != previous["post_config_digest"]
        or post_source != namespace["SOURCE_DIGEST"]
    ):
        raise RuntimeError("Interrupted Checkout published unexpected durable state")
    identity = namespace["assert_identity"](
        label="admin sequence 89 checkout M5 interrupted post-host recovery"
    )
    namespace["record_host"](
        "interrupted_counted_call_recovery",
        counted_sequence=89,
        command=(
            "python /Users/KimMunyeong/Github/memcommit/outputs/"
            "study-long-audit-20260825-v2/run_world_mem.py task-3 checkout "
            "task-3/local/admin-v2-missing-checkout"
        ),
        observed_signal="SIGINT",
        conventional_exit=130,
        stdout_capture="unavailable because parent communicate() was interrupted",
        stderr_capture="unavailable because parent communicate() was interrupted",
        pre_context_tree_digest=previous["post_context_tree_digest"],
        post_context_tree_digest=post_tree,
        pre_registry_digest=previous["post_registry_digest"],
        post_registry_digest=post_registry,
        pre_config_digest=previous["post_config_digest"],
        post_config_digest=post_config,
        no_durable_change=True,
        result="PASS",
    )

    command = (
        "python /Users/KimMunyeong/Github/memcommit/outputs/"
        "study-long-audit-20260825-v2/run_world_mem.py task-3 checkout "
        "task-3/local/admin-v2-missing-checkout"
    )
    raw.write_text(
        "COMMAND\n"
        + command
        + "\n\nSTDIN\n<none>\n\nEXIT\n130 (SIGINT observed by parent harness)"
        + "\n\nWALL_SECONDS\n<unavailable: parent communicate() interrupted>"
        + "\n\nPOST_CALL_IDENTITY_HOST_ASSERTION\n"
        + json.dumps(identity, ensure_ascii=False, sort_keys=True)
        + "\n\nSTDOUT\n<not captured: parent communicate() interrupted>"
        + "\n\nSTDERR\n<not captured: parent communicate() interrupted>\n",
        encoding="utf-8",
    )
    empty_digest = hashlib.sha256(b"").hexdigest()
    record = {
        "attempt": 5,
        "sequence": 89,
        "command": command,
        "exit": 130,
        "starting_state": (
            "One cumulative no-reset Store; ADMIN round 5; phase-local "
            "sequence 89; invocation began before the parent harness received SIGINT."
        ),
        "entry_route": (
            "pinned noninteractive ADMIN CLI · M5 · interrupted exact missing checkout"
        ),
        "target_route": "task-3/local/admin-v2-missing-checkout",
        "scope": "ADMIN round 5 exact missing-Context checkout argv under SIGINT",
        "input_provenance": (
            "cumulative CORE+TRANSFORM+ADMIN Store; protocol M5; actual argv "
            "`checkout task-3/local/admin-v2-missing-checkout`"
        ),
        "consumer": "admin fail-closed checkout and audit-interruption accounting",
        "expected": (
            "Switch to the exact existing Context or create only the declared -b "
            "branch; missing/relative-unavailable targets fail safely. ADMIN method M5."
        ),
        "actual": (
            "Exit 130 (SIGINT observed while parent harness waited). Output was not "
            "captured; exact post-host digests prove no durable Store, registry, or "
            "config change."
        ),
        "defect_ids": ["T3V2-ADMIN-HARNESS-INTERRUPTED-CALL"],
        "cost": {
            "wall_seconds": None,
            "output_bytes": None,
            "output_lines": None,
            "timed_out": False,
            "interrupted": True,
            "tui": False,
            "terminal_screens": 0,
            "extra_manual_steps": 0,
        },
        "pre_target_digest": empty_digest,
        "post_target_digest": empty_digest,
        "pre_context_tree_digest": previous["post_context_tree_digest"],
        "post_context_tree_digest": post_tree,
        "pre_registry_digest": previous["post_registry_digest"],
        "post_registry_digest": post_registry,
        "pre_config_digest": previous["post_config_digest"],
        "post_config_digest": post_config,
        "recovery_evidence": (
            "The invocation was not replayed. Sequence 88 post digests equal the "
            "first recovery host read, and active identity was reasserted after SIGINT."
        ),
        "state_continuity": {
            "one_cumulative_store": True,
            "source_digest_preserved": True,
            "post_call_identity_asserted": True,
            "profile_name": identity["profile_name"],
            "profile_uid": identity["profile_uid"],
            "resolved_store": identity["resolved_store"],
        },
        "stdin_provenance": "none",
        "raw_output": "raw/admin/089-checkout-m5.txt",
    }
    ledger["operations"]["checkout"]["attempts"].append(record)
    ledger["total_attempts"] = 89
    ledger["status"] = "running"
    ledger["outcome"] = "Captured 89/105 ADMIN attempts; final classification pending."
    ledger_path.write_text(
        json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    host["counted_mem_calls"] = 89
    host["host_reads"] = namespace["host_reads"]
    host_path.write_text(
        json.dumps(host, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print("RECOVERED_INTERRUPTED_ADMIN_SEQUENCE_089")


if __name__ == "__main__":
    main()
