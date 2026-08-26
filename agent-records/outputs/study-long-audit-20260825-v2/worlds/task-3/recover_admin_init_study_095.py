#!/usr/bin/env python3
"""Preserve and recover the seq95 init-study active-Profile escape."""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile


HERE = Path(__file__).resolve().parent
BASE = HERE / "run_admin_continue.py"
EXPECTED_UID = "8d6d6360-c3eb-40f9-a490-5c7b2a242bfd"
NEW_UID = "c657200b-1480-446e-b5aa-6910b56d7b86"
NEW_NAME = "00000000-0000-0000-0000-000000000999"


def load_base():
    spec = importlib.util.spec_from_file_location("task3_admin_seq95_base", BASE)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load ADMIN sequence95 recovery base")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def atomic_replace(path: Path, value: bytes) -> None:
    mode = path.stat().st_mode & 0o777
    fd, temp_name = tempfile.mkstemp(prefix="registry-recovery-", dir=path.parent)
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(value)
            file.flush()
            os.fsync(file.fileno())
        os.chmod(temp, mode)
        os.replace(temp, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temp.exists():
            temp.unlink()


def main() -> None:
    base = load_base()
    namespace = base.specialized_namespace()
    ledger_path = Path(namespace["LEDGER"])
    host_path = Path(namespace["HOST_READS"])
    registry_path = Path(namespace["REGISTRY"])
    config_path = Path(namespace["CONFIG"])
    original_store = Path(namespace["STORE"])
    new_store = original_store.parent / NEW_UID
    evidence_dir = HERE / "recovery" / "admin-seq095-init-study"
    before_copy = evidence_dir / "registry-immediate-post-call.json"
    after_copy = evidence_dir / "registry-after-active-pointer-recovery.json"
    evidence_path = evidence_dir / "evidence.json"
    raw_path = Path(namespace["RAW"]) / "095-init_study-m5.txt"

    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    host = json.loads(host_path.read_text(encoding="utf-8"))
    if ledger.get("total_attempts") != 94 or raw_path.exists() or evidence_dir.exists():
        raise SystemExit("Sequence95 recovery is not at its exact one-shot boundary")
    previous = next(
        item
        for value in ledger["operations"].values()
        for item in value["attempts"]
        if item["sequence"] == 94
    )
    registry_before_bytes = registry_path.read_bytes()
    registry_before = json.loads(registry_before_bytes)
    if registry_before.get("active_uid") != NEW_UID:
        raise RuntimeError("Escaped init-study Profile is no longer active")
    matches = [item for item in registry_before["profiles"] if item.get("uid") == NEW_UID]
    if len(matches) != 1 or matches[0].get("name") != NEW_NAME:
        raise RuntimeError("Escaped init-study exact Profile record is unavailable")
    new_profile_record = matches[0]
    if not new_store.is_dir():
        raise RuntimeError("Escaped init-study Store is unavailable")

    original_before = tree_digest(original_store)
    new_before = tree_digest(new_store)
    config_before = hashlib.sha256(config_path.read_bytes()).hexdigest()
    registry_before_sha = sha_bytes(registry_before_bytes)
    evidence_dir.mkdir(parents=True)
    before_copy.write_bytes(registry_before_bytes)

    registry_after = dict(registry_before)
    registry_after["active_uid"] = EXPECTED_UID
    registry_after_bytes = (
        json.dumps(registry_after, indent=2, ensure_ascii=False) + "\n"
    ).encode()
    atomic_replace(registry_path, registry_after_bytes)

    registry_after_actual = registry_path.read_bytes()
    if registry_after_actual != registry_after_bytes:
        raise RuntimeError("Atomic registry recovery bytes differ")
    after_copy.write_bytes(registry_after_actual)
    original_after = tree_digest(original_store)
    new_after = tree_digest(new_store)
    config_after = hashlib.sha256(config_path.read_bytes()).hexdigest()
    if (
        original_before != original_after
        or new_before != new_after
        or config_before != config_after
    ):
        raise RuntimeError("Profile pointer recovery changed a Store or config")

    namespace["host_reads"] = host["host_reads"]
    namespace["sequence"] = 95
    namespace["round_number"] = 5
    identity = namespace["assert_identity"](
        label="admin sequence 95 init-study M5 active-pointer recovery"
    )
    namespace["record_host"](
        "init_study_unexpected_success_and_identity_escape",
        counted_sequence=95,
        command=(
            "python /Users/KimMunyeong/Github/memcommit/agent-records/outputs/"
            "study-long-audit-20260825-v2/run_world_mem.py task-3 init-study "
            + NEW_NAME
        ),
        exit=0,
        detected_profile_name=NEW_NAME,
        detected_profile_uid=NEW_UID,
        detected_store=str(new_store),
        new_profile_record=new_profile_record,
        init_study_success_count=1,
        result="FAIL",
    )
    namespace["record_host"](
        "active_profile_pointer_atomic_recovery",
        counted_sequence=95,
        registry_before_sha256=registry_before_sha,
        registry_after_sha256=sha_bytes(registry_after_actual),
        registry_before_copy=str(before_copy.relative_to(HERE)),
        registry_after_copy=str(after_copy.relative_to(HERE)),
        original_store_sha256_before=original_before,
        original_store_sha256_after=original_after,
        new_store_sha256_before=new_before,
        new_store_sha256_after=new_after,
        config_sha256_before=config_before,
        config_sha256_after=config_after,
        new_profile_and_store_retained=True,
        recovered_profile_name=identity["profile_name"],
        recovered_profile_uid=identity["profile_uid"],
        recovered_store=identity["resolved_store"],
        result="PASS",
    )
    evidence = {
        "schema_version": 1,
        "world": "task-3",
        "phase": "admin",
        "counted_sequence": 95,
        "command": (
            "python /Users/KimMunyeong/Github/memcommit/agent-records/outputs/"
            "study-long-audit-20260825-v2/run_world_mem.py task-3 init-study "
            + NEW_NAME
        ),
        "actual_exit": 0,
        "immediate_post_call": {
            "active_profile_name": NEW_NAME,
            "active_profile_uid": NEW_UID,
            "resolved_store": str(new_store),
            "new_profile_record": new_profile_record,
            "registry_sha256": registry_before_sha,
            "registry_bytes_base64": base64.b64encode(registry_before_bytes).decode(),
            "config_sha256": config_before,
            "original_store_sha256": original_before,
            "new_store_sha256": new_before,
        },
        "host_recovery": {
            "kind": "atomic registry active_uid-only replacement",
            "deleted_or_modified_new_profile": False,
            "deleted_or_modified_new_store": False,
            "registry_sha256": sha_bytes(registry_after_actual),
            "registry_bytes_base64": base64.b64encode(registry_after_actual).decode(),
            "config_sha256": config_after,
            "original_store_sha256": original_after,
            "new_store_sha256": new_after,
            "active_profile_name": identity["profile_name"],
            "active_profile_uid": identity["profile_uid"],
            "resolved_store": identity["resolved_store"],
        },
        "checks": {
            "only_registry_active_uid_changed": (
                {**registry_before, "active_uid": EXPECTED_UID} == json.loads(registry_after_actual)
            ),
            "original_store_unchanged": original_before == original_after,
            "new_store_unchanged": new_before == new_after,
            "config_unchanged": config_before == config_after,
            "new_profile_retained": True,
        },
    }
    evidence_path.write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    command = evidence["command"]
    raw_path.write_text(
        "COMMAND\n" + command + "\n\nSTDIN\n<none>\n\nEXIT\n0"
        "\n\nWALL_SECONDS\n<unavailable: post-call identity assertion interrupted recording>"
        "\n\nPOST_CALL_IDENTITY_HOST_ASSERTION\n"
        "FAIL: active Profile changed to " + NEW_NAME + " [" + NEW_UID + "]"
        "\n\nSTDOUT\n<not retained: recording stopped at mandatory identity assertion>"
        "\n\nSTDERR\n<not retained: recording stopped at mandatory identity assertion>"
        "\n\nOBSERVED_DURABLE_OUTCOME\nCreated and selected a full managed Study "
        "Profile/Store; exact evidence: recovery/admin-seq095-init-study/evidence.json\n",
        encoding="utf-8",
    )
    record = {
        "attempt": 5,
        "sequence": 95,
        "command": command,
        "exit": 0,
        "starting_state": (
            "One cumulative no-reset original Store; ADMIN round 5; sequence 95; "
            "active Profile was pinned immediately before the call."
        ),
        "entry_route": "pinned noninteractive ADMIN CLI · M5 · UUID-shaped Study name",
        "target_route": "new managed Profile/Store named " + NEW_NAME,
        "scope": "ADMIN round 5 exact init-study invalid-name safety boundary",
        "input_provenance": (
            "cumulative CORE+TRANSFORM+ADMIN lane; protocol M5; actual argv "
            "`init-study " + NEW_NAME + "`"
        ),
        "consumer": "Study initialization zero-success and fixed-identity audit",
        "expected": (
            "Fail before creating or selecting any Study/Profile; active identity "
            "and Store remain pinned. ADMIN method M5."
        ),
        "actual": (
            "Exit 0. Created and activated managed Profile " + NEW_NAME + " [" + NEW_UID
            + "] with a new populated Store; mandatory post-call identity assertion "
            "detected the escape before any later counted call."
        ),
        "defect_ids": ["T3V2-INIT-STUDY-UUID-CREATES-ACTIVE-PROFILE"],
        "cost": {
            "wall_seconds": None,
            "output_bytes": None,
            "output_lines": None,
            "timed_out": False,
            "recording_interrupted_by_identity_assertion": True,
            "tui": False,
            "terminal_screens": 0,
            "extra_manual_steps": 0,
        },
        "pre_target_digest": hashlib.sha256(b"").hexdigest(),
        "post_target_digest": hashlib.sha256(b"").hexdigest(),
        "pre_context_tree_digest": previous["post_context_tree_digest"],
        "post_context_tree_digest": previous["post_context_tree_digest"],
        "pre_registry_digest": previous["post_registry_digest"],
        "post_registry_digest": registry_before_sha,
        "pre_config_digest": previous["post_config_digest"],
        "post_config_digest": config_before,
        "recovery_evidence": str(evidence_path.relative_to(HERE)),
        "state_continuity": {
            "one_cumulative_store": False,
            "source_digest_preserved": True,
            "post_call_identity_asserted": True,
            "identity_drift_detected": True,
            "profile_name": NEW_NAME,
            "profile_uid": NEW_UID,
            "resolved_store": str(new_store),
            "active_pointer_recovered_before_next_counted_call": True,
            "new_profile_and_store_retained": True,
        },
        "stdin_provenance": "none",
        "raw_output": "raw/admin/095-init_study-m5.txt",
    }
    ledger["operations"]["init-study"]["attempts"].append(record)
    ledger["total_attempts"] = 95
    ledger["status"] = "running"
    ledger["outcome"] = "Captured 95/105 ADMIN attempts; final classification pending."
    ledger_path.write_text(
        json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    host["counted_mem_calls"] = 95
    host["host_reads"] = namespace["host_reads"]
    host_path.write_text(
        json.dumps(host, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print("RECOVERED_ADMIN_SEQUENCE_095_ACTIVE_POINTER")


if __name__ == "__main__":
    main()
