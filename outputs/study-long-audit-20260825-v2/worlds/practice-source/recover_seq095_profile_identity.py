#!/usr/bin/env python3
"""Atomically restore only active_uid after unexpected init-study success."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tarfile
import tempfile


ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT / "recovery" / "seq095-init-study-profile"
PROFILE_CONTROL = Path(
    "/Users/KimMunyeong/.codex/audit-stores/"
    "memcommit-six-world-v2-20260825/worlds/practice-source/profile-control"
)
REGISTRY = PROFILE_CONTROL / "registry.json"
ORIGINAL_UID = "8d6d6360-c3eb-40f9-a490-5c7b2a242bfd"
NEW_UID = "bb7265f4-8391-47f4-9112-8334f5bf7ddc"
NEW_GRANTED_UID = "2504eed8-0656-48b1-9a69-9973ccdc6b4a"
CODE_ROOT = Path(
    "/Users/KimMunyeong/.codex/audit-snapshots/"
    "memcommit-six-world-v2-20260825-code"
)
STORES = {
    "original": PROFILE_CONTROL / "stores" / ORIGINAL_UID,
    "unexpected-study": PROFILE_CONTROL / "stores" / NEW_UID,
    "unexpected-granted-memory": PROFILE_CONTROL / "stores" / NEW_GRANTED_UID,
}


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def store_manifest(root: Path) -> tuple[list[dict[str, object]], str]:
    records: list[dict[str, object]] = []
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        value = path.read_bytes()
        record = {
            "path": relative,
            "size": len(value),
            "sha256": sha_bytes(value),
        }
        records.append(record)
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(value)
        digest.update(b"\0")
    return records, digest.hexdigest()


def archive_store(label: str, root: Path) -> dict[str, object]:
    archive = EVIDENCE / f"{label}-store-bytes.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        for path in sorted(root.rglob("*")):
            bundle.add(path, arcname=path.relative_to(root), recursive=False)
    manifest, tree_digest = store_manifest(root)
    manifest_path = EVIDENCE / f"{label}-store-manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "root": str(root),
                "file_count": len(manifest),
                "tree_sha256": tree_digest,
                "files": manifest,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "root": str(root),
        "file_count": len(manifest),
        "tree_sha256": tree_digest,
        "manifest": str(manifest_path.relative_to(ROOT)),
        "archive": str(archive.relative_to(ROOT)),
        "archive_sha256": sha_file(archive),
        "archive_size": archive.stat().st_size,
    }


def atomic_restore_active_uid(before: bytes) -> bytes:
    old = f'"active_uid": "{NEW_UID}"'.encode("utf-8")
    new = f'"active_uid": "{ORIGINAL_UID}"'.encode("utf-8")
    if before.count(old) != 1:
        raise RuntimeError("Registry does not contain exactly one unexpected active_uid.")
    after = before.replace(old, new, 1)
    before_value = json.loads(before)
    after_value = json.loads(after)
    if before_value["active_uid"] != NEW_UID or after_value["active_uid"] != ORIGINAL_UID:
        raise RuntimeError("active_uid replacement validation failed.")
    comparison = dict(before_value)
    comparison["active_uid"] = ORIGINAL_UID
    if comparison != after_value:
        raise RuntimeError("Registry logical change exceeds active_uid.")
    mode = stat.S_IMODE(REGISTRY.stat().st_mode)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".registry-seq095-recovery-",
        suffix=".json",
        dir=REGISTRY.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(after)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, REGISTRY)
        directory_descriptor = os.open(REGISTRY.parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    finally:
        if temporary.exists():
            temporary.unlink()
    return after


def resolved_identity() -> dict[str, str]:
    sys.path.insert(0, str(CODE_ROOT))
    import memcommit.profile_config as profile_config

    profile_config.profile_control_dir = lambda: PROFILE_CONTROL
    profile_config.default_store_dir = lambda: PROFILE_CONTROL / "authoring-store"
    registry = profile_config.load_profile_registry()
    return {
        "profile_name": registry.active.name,
        "profile_uid": registry.active.uid,
        "resolved_store": str(profile_config.resolve_active_store_dir().resolve()),
    }


def main() -> None:
    if EVIDENCE.exists():
        raise SystemExit("Sequence-95 recovery evidence already exists; refusing replay.")
    EVIDENCE.mkdir(parents=True)
    before = REGISTRY.read_bytes()
    before_value = json.loads(before)
    if before_value.get("active_uid") != NEW_UID:
        raise SystemExit("Unexpected Study is not the active Profile at recovery entry.")
    profile_entries = [
        item
        for item in before_value["profiles"]
        if item.get("uid") in {NEW_UID, NEW_GRANTED_UID}
    ]
    if {item["uid"] for item in profile_entries} != {NEW_UID, NEW_GRANTED_UID}:
        raise SystemExit("Unexpected Study Profile pair is incomplete.")
    (EVIDENCE / "registry-before.json").write_bytes(before)
    (EVIDENCE / "unexpected-profile-entries.json").write_text(
        json.dumps(profile_entries, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    snapshots_before = {
        label: archive_store(label, store)
        for label, store in STORES.items()
    }
    after = atomic_restore_active_uid(before)
    (EVIDENCE / "registry-after.json").write_bytes(after)
    snapshots_after = {}
    for label, store in STORES.items():
        manifest, tree_digest = store_manifest(store)
        snapshots_after[label] = {
            "file_count": len(manifest),
            "tree_sha256": tree_digest,
            "unchanged": (
                len(manifest) == snapshots_before[label]["file_count"]
                and tree_digest == snapshots_before[label]["tree_sha256"]
            ),
        }
    identity = resolved_identity()
    expected_identity = {
        "profile_name": "sixworld-v2-template",
        "profile_uid": ORIGINAL_UID,
        "resolved_store": str(STORES["original"].resolve()),
    }
    summary = {
        "schema_version": 2,
        "recovery": "host-side atomic active_uid-only replacement",
        "mem_recovery_calls": 0,
        "registry_before_sha256": sha_bytes(before),
        "registry_after_sha256": sha_bytes(after),
        "registry_byte_length_before": len(before),
        "registry_byte_length_after": len(after),
        "registry_byte_diff_count": sum(a != b for a, b in zip(before, after)),
        "registry_only_logical_change": "active_uid",
        "active_uid_before": NEW_UID,
        "active_uid_after": ORIGINAL_UID,
        "generation_before": before_value["generation"],
        "generation_after": json.loads(after)["generation"],
        "profiles_before_count": len(before_value["profiles"]),
        "profiles_after_count": len(json.loads(after)["profiles"]),
        "unexpected_profiles_retained": profile_entries,
        "store_snapshots_before": snapshots_before,
        "store_verification_after": snapshots_after,
        "resolved_identity": identity,
        "expected_identity": expected_identity,
        "runner_preassert_equivalent": "PASS" if identity == expected_identity else "FAIL",
        "result": (
            "PASS"
            if identity == expected_identity
            and all(item["unchanged"] for item in snapshots_after.values())
            else "FAIL"
        ),
    }
    (EVIDENCE / "recovery-summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if summary["result"] != "PASS":
        raise RuntimeError(f"Sequence-95 recovery verification failed: {summary}")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
