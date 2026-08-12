"""Strict task-local registry for setup-time Study semantic artifacts.

The registry is copied only from the selected Study baseline into a new run.
It is not searched under ``outputs/`` and it is never an operation allowlist.
Each enabled entry names one exact artifact whose digest is checked before an
operation-owned installer is allowed to inspect its semantic payload.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
from typing import Literal
import uuid


REGISTRY_DIRECTORY_NAME = "study-semantic-prewarm"
REGISTRY_FILE_NAME = "registry.json"
REGISTRY_KIND = "STUDY_SEMANTIC_PREWARM_REGISTRY"
REGISTRY_SCHEMA_VERSION = 1
REGISTRY_POLICY_VERSION = "declared-exact-v1"

PrewarmOperation = Literal[
    "COMPARE",
    "UPDATE",
    "MELD_DIRECTIONAL",
    "SEVER",
    "ATOMIZE",
]


class StudyPrewarmRegistryError(RuntimeError):
    """A declared Study prewarm bundle is malformed or unsafe."""


def _strict_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key: {key}")
        result[key] = value
    return result


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def payload_digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def registry_root(store_root: Path) -> Path:
    return Path(store_root) / REGISTRY_DIRECTORY_NAME


def _artifact_relative_path(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise StudyPrewarmRegistryError("Prewarm artifact path is invalid.")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or path.parts[0] != "artifacts"
        or any(part in {"", ".", ".."} for part in path.parts)
        or path.suffix != ".json"
    ):
        raise StudyPrewarmRegistryError("Prewarm artifact path is unsafe.")
    return path.as_posix()


@dataclass(frozen=True)
class StudyPrewarmEntry:
    key: str
    operation: PrewarmOperation
    task: str
    policy: Literal["EXACT_PREWARM"]
    artifact: str
    artifact_sha256: str
    enabled: bool

    @classmethod
    def from_dict(cls, value: object) -> "StudyPrewarmEntry":
        expected = {
            "key",
            "operation",
            "task",
            "policy",
            "artifact",
            "artifact_sha256",
            "enabled",
        }
        if not isinstance(value, dict) or set(value) != expected:
            raise StudyPrewarmRegistryError("Prewarm registry entry is invalid.")
        key = value.get("key")
        digest = value.get("artifact_sha256")
        operation = value.get("operation")
        task = value.get("task")
        if (
            not isinstance(key, str)
            or len(key) != 64
            or any(character not in "0123456789abcdef" for character in key)
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or operation
            not in {
                "COMPARE",
                "UPDATE",
                "MELD_DIRECTIONAL",
                "SEVER",
                "ATOMIZE",
            }
            or not isinstance(task, str)
            or task not in {"tutorial", "task-1", "task-2", "task-3"}
            or value.get("policy") != "EXACT_PREWARM"
            or type(value.get("enabled")) is not bool
        ):
            raise StudyPrewarmRegistryError("Prewarm registry entry is invalid.")
        return cls(
            key=key,
            operation=operation,  # type: ignore[arg-type]
            task=task,
            policy="EXACT_PREWARM",
            artifact=_artifact_relative_path(value.get("artifact")),
            artifact_sha256=digest,
            enabled=value["enabled"],  # type: ignore[arg-type]
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "operation": self.operation,
            "task": self.task,
            "policy": self.policy,
            "artifact": self.artifact,
            "artifact_sha256": self.artifact_sha256,
            "enabled": self.enabled,
        }


@dataclass(frozen=True)
class StudyPrewarmRegistry:
    baseline_profile_uid: str
    entries: tuple[StudyPrewarmEntry, ...]

    @classmethod
    def from_dict(cls, value: object) -> "StudyPrewarmRegistry":
        expected = {
            "kind",
            "schema_version",
            "policy_version",
            "baseline_profile_uid",
            "entries",
        }
        if not isinstance(value, dict) or set(value) != expected:
            raise StudyPrewarmRegistryError("Study prewarm registry is invalid.")
        if (
            value.get("kind") != REGISTRY_KIND
            or value.get("schema_version") != REGISTRY_SCHEMA_VERSION
            or value.get("policy_version") != REGISTRY_POLICY_VERSION
            or not isinstance(value.get("baseline_profile_uid"), str)
        ):
            raise StudyPrewarmRegistryError("Study prewarm registry is invalid.")
        try:
            baseline_profile_uid = str(uuid.UUID(value["baseline_profile_uid"]))
        except (AttributeError, TypeError, ValueError) as error:
            raise StudyPrewarmRegistryError(
                "Study prewarm baseline identity is invalid."
            ) from error
        if baseline_profile_uid != value["baseline_profile_uid"]:
            raise StudyPrewarmRegistryError(
                "Study prewarm baseline identity is invalid."
            )
        raw_entries = value.get("entries")
        if not isinstance(raw_entries, list):
            raise StudyPrewarmRegistryError("Study prewarm entries are invalid.")
        entries = tuple(StudyPrewarmEntry.from_dict(item) for item in raw_entries)
        if len({entry.key for entry in entries}) != len(entries):
            raise StudyPrewarmRegistryError("Study prewarm keys must be unique.")
        return cls(
            baseline_profile_uid=baseline_profile_uid,
            entries=entries,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": REGISTRY_KIND,
            "schema_version": REGISTRY_SCHEMA_VERSION,
            "policy_version": REGISTRY_POLICY_VERSION,
            "baseline_profile_uid": self.baseline_profile_uid,
            "entries": [entry.to_dict() for entry in self.entries],
        }


def load_registry(store_root: Path) -> StudyPrewarmRegistry | None:
    root = registry_root(store_root)
    if not root.exists():
        return None
    if not root.is_dir() or root.is_symlink():
        raise StudyPrewarmRegistryError("Study prewarm directory is unsafe.")
    path = root / REGISTRY_FILE_NAME
    if not path.exists() or not path.is_file() or path.is_symlink():
        raise StudyPrewarmRegistryError("Study prewarm registry is missing or unsafe.")
    try:
        with path.open(encoding="utf-8") as file:
            raw = json.load(file, object_pairs_hook=_strict_object)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise StudyPrewarmRegistryError("Cannot read Study prewarm registry.") from error
    registry = StudyPrewarmRegistry.from_dict(raw)
    for entry in registry.entries:
        artifact_path = root / entry.artifact
        if (
            not artifact_path.exists()
            or not artifact_path.is_file()
            or artifact_path.is_symlink()
            or file_digest(artifact_path) != entry.artifact_sha256
        ):
            raise StudyPrewarmRegistryError(
                f"Study prewarm artifact {entry.key!r} is missing or stale."
            )
    return registry


def load_artifact(store_root: Path, entry: StudyPrewarmEntry) -> dict[str, object]:
    path = registry_root(store_root) / entry.artifact
    if not path.is_file() or path.is_symlink() or file_digest(path) != entry.artifact_sha256:
        raise StudyPrewarmRegistryError("Study prewarm artifact changed after lookup.")
    try:
        with path.open(encoding="utf-8") as file:
            value = json.load(file, object_pairs_hook=_strict_object)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise StudyPrewarmRegistryError("Cannot read Study prewarm artifact.") from error
    if not isinstance(value, dict):
        raise StudyPrewarmRegistryError("Study prewarm artifact is invalid.")
    return value


def _write_json_atomic(path: Path, value: object) -> None:
    if path.exists() and (not path.is_file() or path.is_symlink()):
        raise StudyPrewarmRegistryError(f"Unsafe Study prewarm path: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.write-{uuid.uuid4().hex}")
    try:
        with temporary.open("x", encoding="utf-8") as file:
            file.write(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def publish_artifact(
    store_root: Path,
    *,
    baseline_profile_uid: str,
    operation: PrewarmOperation,
    task: str,
    key: str,
    artifact: dict[str, object],
) -> StudyPrewarmEntry:
    """Atomically add one declared exact artifact to a baseline registry."""

    root = registry_root(store_root)
    if root.exists() and (not root.is_dir() or root.is_symlink()):
        raise StudyPrewarmRegistryError("Study prewarm directory is unsafe.")
    artifact_relative = f"artifacts/{operation.lower()}/{key}.json"
    artifact_path = root / artifact_relative
    serialized = json.dumps(
        artifact,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    artifact_sha256 = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    entry = StudyPrewarmEntry(
        key=key,
        operation=operation,
        task=task,
        policy="EXACT_PREWARM",
        artifact=artifact_relative,
        artifact_sha256=artifact_sha256,
        enabled=True,
    )
    previous = load_registry(store_root) if root.exists() else None
    if previous is not None and previous.baseline_profile_uid != baseline_profile_uid:
        raise StudyPrewarmRegistryError(
            "Cannot mix prewarms from different Study baselines."
        )
    entries = list(previous.entries if previous is not None else ())
    matching = [item for item in entries if item.key == key]
    if matching:
        if matching != [entry] or artifact_path.read_text(encoding="utf-8") != serialized:
            raise StudyPrewarmRegistryError(
                "A different prewarm already occupies this exact key."
            )
        return entry
    if artifact_path.exists():
        raise StudyPrewarmRegistryError("Unregistered prewarm artifact path is occupied.")
    _write_json_atomic(artifact_path, artifact)
    registry = StudyPrewarmRegistry(
        baseline_profile_uid=baseline_profile_uid,
        entries=tuple([*entries, entry]),
    )
    _write_json_atomic(root / REGISTRY_FILE_NAME, registry.to_dict())
    # Validate the just-published bundle using the same strict setup reader.
    restored = load_registry(store_root)
    if restored is None or entry not in restored.entries:
        raise StudyPrewarmRegistryError("Published prewarm could not be reloaded.")
    return entry
