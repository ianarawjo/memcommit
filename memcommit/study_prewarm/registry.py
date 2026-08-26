"""Strict task-local registry for setup-time Study semantic artifacts.

The selected Study baseline publishes one content-addressed, immutable bundle.
Participant runs pin that bundle with a small local reference instead of
copying every artifact.  It is not searched under ``outputs/`` and it is never
an operation allowlist.  Each enabled entry names one exact artifact whose
digest is checked before an operation-owned installer may inspect its semantic
payload.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
from typing import Literal
import uuid

from memcommit.operations.profile.config import profile_control_dir


REGISTRY_DIRECTORY_NAME = "study-semantic-prewarm"
REGISTRY_FILE_NAME = "registry.json"
REGISTRY_KIND = "STUDY_SEMANTIC_PREWARM_REGISTRY"
REGISTRY_SCHEMA_VERSION = 1
REGISTRY_POLICY_VERSION = "declared-exact-v1"
BUNDLE_REFERENCE_FILE_NAME = "study-semantic-prewarm-reference.json"
BUNDLE_REFERENCE_KIND = "STUDY_SEMANTIC_PREWARM_BUNDLE_REFERENCE"
BUNDLE_REFERENCE_SCHEMA_VERSION = 1
SHARED_BUNDLES_DIRECTORY_NAME = "study-semantic-prewarm-bundles"

PrewarmOperation = Literal[
    "COMPARE",
    "UPDATE",
    "MELD_DIRECTIONAL",
    "MELD_RESOLUTION",
    "SEVER",
    "ATOMIZE",
    "SUMMARIZE",
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


def bundle_reference_path(store_root: Path) -> Path:
    return Path(store_root) / BUNDLE_REFERENCE_FILE_NAME


def shared_bundles_root() -> Path:
    return profile_control_dir() / SHARED_BUNDLES_DIRECTORY_NAME


def shared_bundle_root(bundle_digest: str) -> Path:
    return shared_bundles_root() / bundle_digest


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
                "MELD_RESOLUTION",
                "SEVER",
                "ATOMIZE",
                "SUMMARIZE",
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


def registry_bundle_digest(registry: StudyPrewarmRegistry) -> str:
    """Identify the registry and every artifact byte it transitively binds."""

    return payload_digest(registry.to_dict())


def _load_registry_root(
    root: Path,
    *,
    validate_artifacts: bool,
) -> StudyPrewarmRegistry:
    if not root.is_dir() or root.is_symlink():
        raise StudyPrewarmRegistryError("Study prewarm directory is unsafe.")
    path = root / REGISTRY_FILE_NAME
    if not path.exists() or not path.is_file() or path.is_symlink():
        raise StudyPrewarmRegistryError("Study prewarm registry is missing or unsafe.")
    try:
        with path.open(encoding="utf-8") as file:
            raw = json.load(file, object_pairs_hook=_strict_object)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise StudyPrewarmRegistryError(
            "Cannot read Study prewarm registry."
        ) from error
    registry = StudyPrewarmRegistry.from_dict(raw)
    if validate_artifacts:
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


def _read_bundle_reference(store_root: Path) -> tuple[str, str] | None:
    path = bundle_reference_path(store_root)
    if not path.exists():
        return None
    if not path.is_file() or path.is_symlink():
        raise StudyPrewarmRegistryError("Study prewarm bundle reference is unsafe.")
    try:
        with path.open(encoding="utf-8") as file:
            value = json.load(file, object_pairs_hook=_strict_object)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise StudyPrewarmRegistryError(
            "Cannot read Study prewarm bundle reference."
        ) from error
    expected = {
        "kind",
        "schema_version",
        "baseline_profile_uid",
        "bundle_digest",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise StudyPrewarmRegistryError("Study prewarm bundle reference is invalid.")
    digest = value.get("bundle_digest")
    baseline_uid = value.get("baseline_profile_uid")
    if (
        value.get("kind") != BUNDLE_REFERENCE_KIND
        or value.get("schema_version") != BUNDLE_REFERENCE_SCHEMA_VERSION
        or not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
        or not isinstance(baseline_uid, str)
    ):
        raise StudyPrewarmRegistryError("Study prewarm bundle reference is invalid.")
    try:
        canonical_uid = str(uuid.UUID(baseline_uid))
    except (AttributeError, TypeError, ValueError) as error:
        raise StudyPrewarmRegistryError(
            "Study prewarm bundle baseline identity is invalid."
        ) from error
    if canonical_uid != baseline_uid:
        raise StudyPrewarmRegistryError(
            "Study prewarm bundle baseline identity is invalid."
        )
    return digest, baseline_uid


def _registry_source_root(store_root: Path) -> Path | None:
    local = registry_root(store_root)
    if local.exists():
        if bundle_reference_path(store_root).exists():
            raise StudyPrewarmRegistryError(
                "Study prewarm store has both a local bundle and a shared reference."
            )
        return local
    reference = _read_bundle_reference(store_root)
    if reference is None:
        return None
    digest, baseline_uid = reference
    root = shared_bundle_root(digest)
    registry = _load_registry_root(root, validate_artifacts=False)
    if (
        registry_bundle_digest(registry) != digest
        or registry.baseline_profile_uid != baseline_uid
    ):
        raise StudyPrewarmRegistryError(
            "Shared Study prewarm bundle does not match its pinned reference."
        )
    return root


def load_registry(store_root: Path) -> StudyPrewarmRegistry | None:
    root = _registry_source_root(store_root)
    if root is None:
        return None
    # Registry metadata is cheap and binds every artifact digest.  Artifact
    # bytes remain lazy: the operation reads and verifies only its requested
    # exact entry through ``load_artifact``.
    return _load_registry_root(root, validate_artifacts=False)


def uses_shared_bundle(store_root: Path) -> bool:
    """Report whether this store pins a shared Study bundle."""

    return _read_bundle_reference(store_root) is not None


def load_artifact(store_root: Path, entry: StudyPrewarmEntry) -> dict[str, object]:
    root = _registry_source_root(store_root)
    if root is None:
        raise StudyPrewarmRegistryError("Study prewarm registry is unavailable.")
    path = root / entry.artifact
    if (
        not path.is_file()
        or path.is_symlink()
        or file_digest(path) != entry.artifact_sha256
    ):
        raise StudyPrewarmRegistryError("Study prewarm artifact changed after lookup.")
    try:
        with path.open(encoding="utf-8") as file:
            value = json.load(file, object_pairs_hook=_strict_object)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise StudyPrewarmRegistryError(
            "Cannot read Study prewarm artifact."
        ) from error
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


def publish_shared_bundle(store_root: Path) -> tuple[str, StudyPrewarmRegistry] | None:
    """Publish one baseline's declared artifacts into immutable shared storage.

    The bundle directory is content-addressed by the validated registry, whose
    entries already bind every artifact byte by SHA-256.  A later baseline
    revision therefore creates a new directory rather than changing an older
    participant run's semantic starting point.
    """

    source = registry_root(store_root)
    if not source.exists():
        return None
    if bundle_reference_path(store_root).exists():
        raise StudyPrewarmRegistryError(
            "A shared Study run cannot republish its pinned prewarm bundle."
        )
    registry = _load_registry_root(source, validate_artifacts=False)
    digest = registry_bundle_digest(registry)
    parent = shared_bundles_root()
    if parent.exists() and (not parent.is_dir() or parent.is_symlink()):
        raise StudyPrewarmRegistryError("Shared Study prewarm storage is unsafe.")
    parent.mkdir(parents=True, exist_ok=True)
    destination = shared_bundle_root(digest)
    if destination.exists():
        # Existing immutable content was validated when first published.
        # Later init-study runs only pin its digest; exact artifact bytes are
        # rechecked lazily by the operation that requests that entry.
        restored = _load_registry_root(destination, validate_artifacts=False)
        if registry_bundle_digest(restored) != digest or restored != registry:
            raise StudyPrewarmRegistryError(
                "Shared Study prewarm bundle digest is occupied."
            )
        return digest, restored

    # A new digest is the only path that pays the one-time full source-tree
    # validation and copy cost.
    registry = _load_registry_root(source, validate_artifacts=True)
    staging = parent / f".{digest}.write-{uuid.uuid4().hex}"
    try:
        staging.mkdir()
        _write_json_atomic(staging / REGISTRY_FILE_NAME, registry.to_dict())
        for entry in registry.entries:
            source_path = source / entry.artifact
            target_path = staging / entry.artifact
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)
        restored = _load_registry_root(staging, validate_artifacts=True)
        if registry_bundle_digest(restored) != digest or restored != registry:
            raise StudyPrewarmRegistryError(
                "Shared Study prewarm bundle changed while publishing."
            )
        try:
            os.replace(staging, destination)
        except OSError:
            # Two init-study processes may finish the same digest concurrently.
            # The losing publisher accepts only a fully validated identical
            # destination; every other collision remains an error.
            if not destination.exists():
                raise
            concurrent = _load_registry_root(
                destination,
                validate_artifacts=True,
            )
            if registry_bundle_digest(concurrent) != digest or concurrent != registry:
                raise StudyPrewarmRegistryError(
                    "Concurrent Study prewarm bundle publication conflicted."
                )
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return digest, registry


def attach_shared_bundle(
    *,
    baseline_store_root: Path,
    participant_store_root: Path,
) -> str | None:
    """Pin a participant run to one shared immutable baseline bundle."""

    published = publish_shared_bundle(baseline_store_root)
    if published is None:
        return None
    digest, registry = published
    participant_root = Path(participant_store_root)
    if registry_root(participant_root).exists():
        raise StudyPrewarmRegistryError(
            "Participant Study store already contains a local prewarm bundle."
        )
    path = bundle_reference_path(participant_root)
    if path.exists():
        raise StudyPrewarmRegistryError(
            "Participant Study prewarm reference is already occupied."
        )
    _write_json_atomic(
        path,
        {
            "kind": BUNDLE_REFERENCE_KIND,
            "schema_version": BUNDLE_REFERENCE_SCHEMA_VERSION,
            "baseline_profile_uid": registry.baseline_profile_uid,
            "bundle_digest": digest,
        },
    )
    # Read through the participant boundary before publication.  This proves
    # that later operations can resolve the exact pinned bundle without
    # inheriting mutable state from the baseline Profile.
    rebound = load_registry(participant_root)
    if rebound != registry:
        raise StudyPrewarmRegistryError(
            "Participant Study prewarm reference could not be reloaded."
        )
    return digest


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
    if bundle_reference_path(store_root).exists():
        raise StudyPrewarmRegistryError(
            "Cannot publish an artifact into a shared Study bundle reference."
        )
    if root.exists() and (not root.is_dir() or root.is_symlink()):
        raise StudyPrewarmRegistryError("Study prewarm directory is unsafe.")
    artifact_relative = f"artifacts/{operation.lower()}/{key}.json"
    artifact_path = root / artifact_relative
    serialized = (
        json.dumps(
            artifact,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
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
    previous = (
        _load_registry_root(root, validate_artifacts=True) if root.exists() else None
    )
    if previous is not None and previous.baseline_profile_uid != baseline_profile_uid:
        raise StudyPrewarmRegistryError(
            "Cannot mix prewarms from different Study baselines."
        )
    entries = list(previous.entries if previous is not None else ())
    matching = [item for item in entries if item.key == key]
    if matching:
        if (
            matching != [entry]
            or artifact_path.read_text(encoding="utf-8") != serialized
        ):
            raise StudyPrewarmRegistryError(
                "A different prewarm already occupies this exact key."
            )
        return entry
    if artifact_path.exists():
        raise StudyPrewarmRegistryError(
            "Unregistered prewarm artifact path is occupied."
        )
    _write_json_atomic(artifact_path, artifact)
    registry = StudyPrewarmRegistry(
        baseline_profile_uid=baseline_profile_uid,
        entries=tuple([*entries, entry]),
    )
    _write_json_atomic(root / REGISTRY_FILE_NAME, registry.to_dict())
    # Validate the just-published bundle using the same strict setup reader.
    restored = _load_registry_root(root, validate_artifacts=True)
    if restored is None or entry not in restored.entries:
        raise StudyPrewarmRegistryError("Published prewarm could not be reloaded.")
    return entry


def replace_operation_artifacts(
    store_root: Path,
    *,
    baseline_profile_uid: str,
    replacements: Mapping[
        PrewarmOperation,
        Sequence[tuple[str, str, dict[str, object]]],
    ],
) -> StudyPrewarmRegistry:
    """Atomically switch complete operation families to regenerated entries.

    Artifact files are immutable by key and may be written before the registry
    switch.  The one atomic registry-file replacement is the publication
    boundary: a failed generation leaves the previously declared set active.
    Replaced entries remain digest-bound but disabled so a later generation can
    reconstruct the original finite declaration without exposing stale caches
    to participant operations.
    """

    root = registry_root(store_root)
    if bundle_reference_path(store_root).exists():
        raise StudyPrewarmRegistryError(
            "Cannot replace artifacts in a shared Study bundle reference."
        )
    if not replacements:
        raise StudyPrewarmRegistryError("No Study prewarm replacements were supplied.")
    previous = _load_registry_root(root, validate_artifacts=True)
    if previous.baseline_profile_uid != baseline_profile_uid:
        raise StudyPrewarmRegistryError(
            "Cannot replace prewarms from a different Study baseline."
        )

    replaced_operations = frozenset(replacements)
    entries = [
        (
            replace(entry, enabled=False)
            if entry.operation in replaced_operations
            else entry
        )
        for entry in previous.entries
    ]
    entry_indexes = {entry.key: index for index, entry in enumerate(entries)}
    desired_keys: set[str] = set()

    for operation, artifacts in replacements.items():
        if operation not in {
            "COMPARE",
            "UPDATE",
            "MELD_DIRECTIONAL",
            "MELD_RESOLUTION",
            "SEVER",
            "ATOMIZE",
            "SUMMARIZE",
        }:
            raise StudyPrewarmRegistryError("Unknown Study prewarm operation.")
        if not artifacts:
            raise StudyPrewarmRegistryError(
                f"Replacement for {operation} contains no artifacts."
            )
        for task, key, artifact in artifacts:
            artifact_relative = f"artifacts/{operation.lower()}/{key}.json"
            serialized = (
                json.dumps(
                    artifact,
                    ensure_ascii=False,
                    allow_nan=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            )
            artifact_sha256 = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
            candidate = StudyPrewarmEntry.from_dict(
                {
                    "key": key,
                    "operation": operation,
                    "task": task,
                    "policy": "EXACT_PREWARM",
                    "artifact": artifact_relative,
                    "artifact_sha256": artifact_sha256,
                    "enabled": True,
                }
            )
            if key in desired_keys:
                raise StudyPrewarmRegistryError(
                    "Regenerated Study prewarm keys must be unique."
                )
            desired_keys.add(key)
            existing_index = entry_indexes.get(key)
            if existing_index is not None:
                existing = entries[existing_index]
                existing_path = root / existing.artifact
                if (
                    existing.operation != operation
                    or existing.task != task
                    or existing.artifact != artifact_relative
                    or existing.artifact_sha256 != artifact_sha256
                    or existing_path.read_text(encoding="utf-8") != serialized
                ):
                    raise StudyPrewarmRegistryError(
                        "A different prewarm already occupies a regenerated key."
                    )
                entries[existing_index] = replace(existing, enabled=True)
                continue

            artifact_path = root / artifact_relative
            if artifact_path.exists():
                if (
                    not artifact_path.is_file()
                    or artifact_path.is_symlink()
                    or artifact_path.read_text(encoding="utf-8") != serialized
                ):
                    raise StudyPrewarmRegistryError(
                        "An unregistered prewarm path conflicts with regeneration."
                    )
            else:
                _write_json_atomic(artifact_path, artifact)
            entry_indexes[key] = len(entries)
            entries.append(candidate)

    registry = StudyPrewarmRegistry(
        baseline_profile_uid=baseline_profile_uid,
        entries=tuple(entries),
    )
    # Only this metadata switch changes which artifact generation is callable.
    _write_json_atomic(root / REGISTRY_FILE_NAME, registry.to_dict())
    restored = _load_registry_root(root, validate_artifacts=True)
    if restored != registry:
        raise StudyPrewarmRegistryError(
            "Regenerated Study prewarm registry could not be reloaded."
        )
    return restored
