"""Hidden installation receipts for declared Study semantic artifacts.

The registry artifact is the semantic cache.  Installing a Study run must not
copy that artifact into an operation's ordinary session catalog, because a
participant has not started that operation yet.  Every operation instead
records the same small receipt envelope here and materializes ordinary state
only when an explicit command consumes the receipt.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Mapping

from memcommit.profile_config import (
    load_profile_registry,
    profile_store_dir,
    study_run_identity,
)
from memcommit.store import MemoryStore, _write_json_atomic
from memcommit.study_prewarm.registry import (
    StudyPrewarmEntry,
    StudyPrewarmRegistryError,
    load_registry,
    uses_shared_bundle,
)


INSTALLATIONS_DIRECTORY_NAME = "study-prewarm-installations"
DECLARED_INSTALLATION_KIND = "STUDY_PREWARM_HIDDEN_RECEIPT"
DECLARED_INSTALLATION_SCHEMA_VERSION = 1


def _operation_slug(operation: str) -> str:
    return operation.casefold().replace("_", "-")


def declared_installation_path(
    store: MemoryStore,
    entry: StudyPrewarmEntry,
) -> Path:
    return (
        store.store_dir
        / INSTALLATIONS_DIRECTORY_NAME
        / f"declared-{_operation_slug(entry.operation)}-{entry.key}.json"
    )


def _normalized_evidence(evidence: Mapping[str, str]) -> dict[str, str]:
    if not evidence or any(
        not isinstance(key, str)
        or not key
        or not isinstance(value, str)
        or not value
        for key, value in evidence.items()
    ):
        raise StudyPrewarmRegistryError(
            "Study prewarm installation evidence is invalid."
        )
    return dict(sorted(evidence.items()))


def record_declared_installation(
    store: MemoryStore,
    *,
    entry: StudyPrewarmEntry,
    evidence: Mapping[str, str],
) -> None:
    """Record one validated cache artifact without publishing a session."""

    path = declared_installation_path(store, entry)
    if path.parent.exists() and (
        not path.parent.is_dir() or path.parent.is_symlink()
    ):
        raise StudyPrewarmRegistryError(
            "Study prewarm receipt directory is unsafe."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(
        path,
        {
            "kind": DECLARED_INSTALLATION_KIND,
            "schema_version": DECLARED_INSTALLATION_SCHEMA_VERSION,
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "operation": entry.operation,
            "task": entry.task,
            "entry_key": entry.key,
            "artifact_sha256": entry.artifact_sha256,
            "evidence": _normalized_evidence(evidence),
        },
    )


def declared_installation_matches(
    store: MemoryStore,
    *,
    entry: StudyPrewarmEntry,
    evidence: Mapping[str, str],
) -> bool:
    """Verify that setup validated this exact artifact and semantic basis."""

    path = declared_installation_path(store, entry)
    if not path.exists():
        return False
    if not path.is_file() or path.is_symlink():
        raise StudyPrewarmRegistryError("Study prewarm receipt is unsafe.")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise StudyPrewarmRegistryError(
            "Study prewarm receipt is invalid."
        ) from error
    return bool(
        isinstance(value, dict)
        and set(value)
        == {
            "kind",
            "schema_version",
            "installed_at",
            "operation",
            "task",
            "entry_key",
            "artifact_sha256",
            "evidence",
        }
        and value.get("kind") == DECLARED_INSTALLATION_KIND
        and value.get("schema_version")
        == DECLARED_INSTALLATION_SCHEMA_VERSION
        and isinstance(value.get("installed_at"), str)
        and bool(value.get("installed_at"))
        and value.get("operation") == entry.operation
        and value.get("task") == entry.task
        and value.get("entry_key") == entry.key
        and value.get("artifact_sha256") == entry.artifact_sha256
        and value.get("evidence") == _normalized_evidence(evidence)
    )


def declared_artifact_available(
    store: MemoryStore,
    *,
    entry: StudyPrewarmEntry,
    evidence: Mapping[str, str],
) -> bool:
    """Authorize one old receipt or one first-use shared Study artifact.

    A copied legacy run proves setup-time validation with its hidden receipt.
    A new Study run instead pins an immutable shared bundle and performs the
    same operation-specific evidence validation at first use.  The bundle
    reference is the availability proof; ordinary session or analysis state
    is still created only by the operation the participant actually invoked.
    """

    if declared_installation_matches(store, entry=entry, evidence=evidence):
        return True
    if not uses_shared_bundle(store.store_dir):
        return False
    registry = load_registry(store.store_dir)
    profiles = load_profile_registry()
    identity = study_run_identity(profiles.active)
    return bool(
        registry is not None
        and entry in registry.entries
        and store.store_dir.resolve() == profile_store_dir(profiles.active).resolve()
        and identity is not None
        and identity.role == "PARTICIPANT"
        and identity.baseline_profile_uid == registry.baseline_profile_uid
    )
