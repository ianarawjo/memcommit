"""Declared Task-conditioned final Meld reconciliation branches."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from memcommit.context import Context
from memcommit.application.operations.meld.model import MeldError, MeldSession
from memcommit.application.operations.meld.provider import (
    MELD_RESOLUTION_REQUEST_CONTRACT_VERSION,
    assess_meld_turn,
    meld_turn_request_digest,
)
from memcommit.application.operations.meld.resolution_cache import (
    MeldResolutionBranch,
    MeldResolutionCacheError,
    configured_meld_cache_identity,
    meld_resolution_cache_key,
)
from memcommit.application.operations.profile.config import (
    ProfileEntry,
    ProfileRegistry,
    study_run_identity,
)
from memcommit.infrastructure.providers.types import CODEX_CHATGPT_PROVIDER
from memcommit.persistence.store import MemoryStore, context_record_digest
from memcommit.study_prewarm.installations import (
    declared_artifact_available,
    record_declared_installation,
)
from memcommit.study_prewarm.quality import (
    SemanticIdentity,
    highest_quality_candidates,
    prewarm_quality_satisfies,
)
from memcommit.study_prewarm.registry import (
    StudyPrewarmRegistryError,
    load_artifact,
    load_registry,
    payload_digest,
)


MELD_RESOLUTION_ARTIFACT_KIND = "STUDY_MELD_RESOLUTION_BRANCHES"
MELD_RESOLUTION_ARTIFACT_SCHEMA_VERSION = 1
MELD_RESOLUTION_OPERATION = "MELD_RESOLUTION"
_TASKS = {"task-1", "task-2", "task-3"}


@dataclass(frozen=True)
class MeldResolutionPrewarmInstallResult:
    declared: int
    installed: int
    skipped_configuration: int
    branch_count: int
    entry_keys: tuple[str, ...]


class _SavedCompletionProvider:
    def __init__(self, completion: str):
        self.completion = completion
        self.called = False

    def complete(self, prompt, *, operation, output_schema=None):
        if self.called or operation != "meld_contexts":
            raise MeldError("Prepared Meld resolution replay is invalid.")
        self.called = True
        return self.completion


def _description_identity(description: Context) -> dict[str, str]:
    if not isinstance(description, Context):
        raise StudyPrewarmRegistryError(
            "Meld resolution prewarm requires a task description Context."
        )
    return {
        "name": description.name,
        "context_uid": description.uid,
        "context_digest": context_record_digest(description),
    }


def _configured_identity(
    *, provider: str, model: str | None, reasoning: str | None
) -> dict[str, object]:
    if provider == CODEX_CHATGPT_PROVIDER and model is None:
        model = "current-recommended"
    value = {
        "provider": provider,
        "model": model,
        "reasoning_effort": reasoning,
    }
    # Reuse the branch model's strict provider-configuration validation.
    sentinel = "0" * 64
    meld_resolution_cache_key(sentinel, value)
    return value


def _quality_identity(value: dict[str, object]) -> SemanticIdentity:
    provider = value.get("provider")
    model = value.get("model")
    reasoning = value.get("reasoning_effort")
    if (
        not isinstance(provider, str)
        or (model is not None and not isinstance(model, str))
        or (reasoning is not None and not isinstance(reasoning, str))
    ):
        raise StudyPrewarmRegistryError("Meld resolution provider is invalid.")
    return provider, model, reasoning


def _pending_copy(session: MeldSession) -> MeldSession:
    if not isinstance(session, MeldSession):
        raise StudyPrewarmRegistryError(
            "Each prepared Meld branch requires one assessed follow-up turn."
        )
    current = session.current_turn
    if (
        current is None
        or current.sequence <= 0
        or current.assessment is None
    ):
        raise StudyPrewarmRegistryError(
            "Each prepared Meld branch requires one assessed follow-up turn."
        )
    value = session.to_dict()
    turns = value.get("turns")
    assert isinstance(turns, list) and isinstance(turns[-1], dict)
    turns[-1]["assessment"] = None
    value["state"] = "AWAITING_REPLY"
    value["application"] = None
    try:
        return MeldSession.from_dict(value)
    except MeldError as error:
        raise StudyPrewarmRegistryError(
            "Prepared Meld branch cannot restore its pending request."
        ) from error


def _validate_prepared_branch(
    session: MeldSession,
    branch: MeldResolutionBranch,
    *,
    configured_provider: dict[str, object],
) -> None:
    pending = _pending_copy(session)
    if (
        branch.configured_provider != configured_provider
        or meld_turn_request_digest(pending) != branch.request_digest
    ):
        raise StudyPrewarmRegistryError(
            "Prepared Meld branch does not match its exact request."
        )
    try:
        assessment = assess_meld_turn(
            pending,
            _SavedCompletionProvider(branch.completion),
        )
        pending.record_assessment(pending.current_turn.uid, assessment)
    except MeldError as error:
        raise StudyPrewarmRegistryError(
            "Prepared Meld branch is not a complete valid assessment."
        ) from error
    assert session.current_assessment is not None
    if assessment.to_dict() != session.current_assessment.to_dict():
        raise StudyPrewarmRegistryError(
            "Prepared Meld branch differs from its reviewed assessment."
        )


def _artifact_material(
    *,
    task: str,
    description: dict[str, str],
    configured_provider: dict[str, object],
    branches: tuple[MeldResolutionBranch, ...],
) -> dict[str, object]:
    return {
        "operation": MELD_RESOLUTION_OPERATION,
        "task": task,
        "request_contract_version": MELD_RESOLUTION_REQUEST_CONTRACT_VERSION,
        "task_description": description,
        "configured_provider": configured_provider,
        "branch_keys": [branch.key for branch in branches],
        "branch_record_digests": [
            payload_digest(branch.to_dict()) for branch in branches
        ],
    }


def build_meld_resolution_prewarm_artifact(
    *,
    task: str,
    task_description: Context,
    prepared_branches: Iterable[tuple[MeldSession, MeldResolutionBranch]],
    provider: str,
    model: str | None,
    reasoning: str | None,
    offline_provider_seconds: float,
) -> tuple[str, dict[str, object]]:
    """Build one reviewed Task branch bundle for later Study runs."""

    if task not in _TASKS:
        raise StudyPrewarmRegistryError("Meld branch task is invalid.")
    if (
        not isinstance(offline_provider_seconds, (int, float))
        or isinstance(offline_provider_seconds, bool)
        or offline_provider_seconds < 0
    ):
        raise StudyPrewarmRegistryError(
            "Meld branch offline provider duration is invalid."
        )
    configured = _configured_identity(
        provider=provider,
        model=model,
        reasoning=reasoning,
    )
    pairs = tuple(prepared_branches)
    if not pairs:
        raise StudyPrewarmRegistryError(
            "Meld resolution prewarm requires at least one branch."
        )
    branches: list[MeldResolutionBranch] = []
    for session, branch in pairs:
        if not isinstance(branch, MeldResolutionBranch):
            raise StudyPrewarmRegistryError("Prepared Meld branch is invalid.")
        if branch.scope == "ISSUE":
            raise StudyPrewarmRegistryError(
                "Study Meld prewarm stores local issue selections as choices, "
                "not as independent semantic outcomes. Prepare one complete "
                "ALL or REMAINING reconciliation instead."
            )
        _validate_prepared_branch(
            session,
            branch,
            configured_provider=configured,
        )
        branches.append(branch)
    ordered = tuple(sorted(branches, key=lambda branch: branch.key))
    if len({branch.key for branch in ordered}) != len(ordered):
        raise StudyPrewarmRegistryError("Prepared Meld branch keys must be unique.")
    description = _description_identity(task_description)
    material = _artifact_material(
        task=task,
        description=description,
        configured_provider=configured,
        branches=ordered,
    )
    key = payload_digest(material)
    return key, {
        "kind": MELD_RESOLUTION_ARTIFACT_KIND,
        "schema_version": MELD_RESOLUTION_ARTIFACT_SCHEMA_VERSION,
        "key": key,
        **material,
        "offline_provider_seconds": float(offline_provider_seconds),
        "branches": [branch.to_dict() for branch in ordered],
    }


def _validate_artifact(
    value: dict[str, object],
    *,
    entry_key: str,
    entry_task: str,
) -> tuple[tuple[MeldResolutionBranch, ...], dict[str, str], dict[str, object]]:
    expected = {
        "kind",
        "schema_version",
        "key",
        "operation",
        "task",
        "request_contract_version",
        "task_description",
        "configured_provider",
        "branch_keys",
        "branch_record_digests",
        "offline_provider_seconds",
        "branches",
    }
    if (
        not isinstance(value, dict)
        or set(value) != expected
        or value.get("kind") != MELD_RESOLUTION_ARTIFACT_KIND
        or value.get("schema_version") != MELD_RESOLUTION_ARTIFACT_SCHEMA_VERSION
        or value.get("key") != entry_key
        or value.get("operation") != MELD_RESOLUTION_OPERATION
        or value.get("task") != entry_task
        or entry_task not in _TASKS
        or value.get("request_contract_version")
        != MELD_RESOLUTION_REQUEST_CONTRACT_VERSION
    ):
        raise StudyPrewarmRegistryError(
            "Declared Meld resolution prewarm is invalid."
        )
    raw_description = value.get("task_description")
    if (
        not isinstance(raw_description, dict)
        or set(raw_description) != {"name", "context_uid", "context_digest"}
        or any(not isinstance(item, str) or not item for item in raw_description.values())
    ):
        raise StudyPrewarmRegistryError(
            "Meld resolution task description identity is invalid."
        )
    configured = value.get("configured_provider")
    if not isinstance(configured, dict):
        raise StudyPrewarmRegistryError("Meld resolution provider is invalid.")
    try:
        configured = _configured_identity(
            provider=configured.get("provider"),
            model=configured.get("model"),
            reasoning=configured.get("reasoning_effort"),
        )
    except (MeldResolutionCacheError, TypeError) as error:
        raise StudyPrewarmRegistryError(
            "Meld resolution provider is invalid."
        ) from error
    raw_branches = value.get("branches")
    if not isinstance(raw_branches, list) or not raw_branches:
        raise StudyPrewarmRegistryError("Meld resolution branches are invalid.")
    try:
        branches = tuple(
            sorted(
                (MeldResolutionBranch.from_dict(item) for item in raw_branches),
                key=lambda branch: branch.key,
            )
        )
    except MeldResolutionCacheError as error:
        raise StudyPrewarmRegistryError(
            "Meld resolution branches are invalid."
        ) from error
    if (
        len({branch.key for branch in branches}) != len(branches)
        or any(branch.configured_provider != configured for branch in branches)
        or value.get("branch_keys") != [branch.key for branch in branches]
        or value.get("branch_record_digests")
        != [payload_digest(branch.to_dict()) for branch in branches]
        or not isinstance(value.get("offline_provider_seconds"), (int, float))
        or isinstance(value.get("offline_provider_seconds"), bool)
        or value.get("offline_provider_seconds") < 0
    ):
        raise StudyPrewarmRegistryError("Meld resolution branches are invalid.")
    material = _artifact_material(
        task=entry_task,
        description=raw_description,
        configured_provider=configured,
        branches=branches,
    )
    if payload_digest(material) != entry_key:
        raise StudyPrewarmRegistryError("Meld resolution prewarm key is stale.")
    return branches, raw_description, configured


def _validate_description(
    store: MemoryStore,
    description: dict[str, str],
) -> None:
    try:
        current = store.load_direct(description["name"])
    except FileNotFoundError as error:
        raise StudyPrewarmRegistryError(
            "Meld resolution task description is missing."
        ) from error
    if (
        current.uid != description["context_uid"]
        or context_record_digest(current) != description["context_digest"]
    ):
        raise StudyPrewarmRegistryError(
            "Meld resolution task description changed after preparation."
        )


def _installation_evidence(
    description: dict[str, str],
    branches: tuple[MeldResolutionBranch, ...],
) -> dict[str, str]:
    return {
        "task_description_uid": description["context_uid"],
        "task_description_digest": description["context_digest"],
        "branch_set_digest": payload_digest(
            [branch.to_dict() for branch in branches]
        ),
    }


def install_declared_meld_resolution_prewarms(
    *,
    store: MemoryStore,
    profile: ProfileEntry,
    registry_snapshot: ProfileRegistry,
    publish: bool = True,
) -> MeldResolutionPrewarmInstallResult:
    """Validate Task branch bundles and install hidden receipts only."""

    registry = load_registry(store.store_dir)
    if registry is None:
        return MeldResolutionPrewarmInstallResult(0, 0, 0, 0, ())
    identity = study_run_identity(profile)
    if identity is None or identity.role != "PARTICIPANT":
        raise StudyPrewarmRegistryError(
            "Meld resolution prewarm requires a participant Study Profile."
        )
    if registry.baseline_profile_uid != identity.baseline_profile_uid:
        raise StudyPrewarmRegistryError(
            "Meld resolution prewarm belongs to a different baseline."
        )
    # The snapshot argument intentionally proves that setup is operating on
    # the just-published participant identity, even though these local task
    # descriptions do not require a Grant lookup.
    if not any(item == profile for item in registry_snapshot.profiles):
        raise StudyPrewarmRegistryError("Study Profile identity changed.")
    current_config = configured_meld_cache_identity()
    requested_identity = _quality_identity(current_config)
    declared = skipped = branch_count = 0
    installed: list[str] = []
    for entry in registry.entries:
        if not entry.enabled or entry.operation != MELD_RESOLUTION_OPERATION:
            continue
        declared += 1
        artifact = load_artifact(store.store_dir, entry)
        branches, description, configured = _validate_artifact(
            artifact,
            entry_key=entry.key,
            entry_task=entry.task,
        )
        if not prewarm_quality_satisfies(
            _quality_identity(configured),
            requested_identity,
        ):
            skipped += 1
            continue
        _validate_description(store, description)
        branch_count += len(branches)
        if publish:
            record_declared_installation(
                store,
                entry=entry,
                evidence=_installation_evidence(description, branches),
            )
            installed.append(entry.key)
    return MeldResolutionPrewarmInstallResult(
        declared,
        len(installed),
        skipped,
        branch_count,
        tuple(installed),
    )


def find_installed_meld_resolution_branch(
    *,
    store: MemoryStore,
    branch_key: str | None = None,
    request_digest: str | None = None,
) -> MeldResolutionBranch | None:
    """Find one exact request whose prepared quality satisfies this run."""

    registry = load_registry(store.store_dir)
    if registry is None or (branch_key is None and request_digest is None):
        return None
    current_config = configured_meld_cache_identity()
    requested_identity = _quality_identity(current_config)
    matches: list[tuple[SemanticIdentity, MeldResolutionBranch]] = []
    for entry in registry.entries:
        if not entry.enabled or entry.operation != MELD_RESOLUTION_OPERATION:
            continue
        artifact = load_artifact(store.store_dir, entry)
        branches, description, configured = _validate_artifact(
            artifact,
            entry_key=entry.key,
            entry_task=entry.task,
        )
        cached_identity = _quality_identity(configured)
        if not prewarm_quality_satisfies(
            cached_identity,
            requested_identity,
        ):
            continue
        try:
            _validate_description(store, description)
        except StudyPrewarmRegistryError:
            continue
        if not declared_artifact_available(
            store,
            entry=entry,
            evidence=_installation_evidence(description, branches),
        ):
            continue
        matches.extend(
            (cached_identity, branch)
            for branch in branches
            if (
                branch.request_digest == request_digest
                if request_digest is not None
                else branch.key == branch_key
            )
        )
    selected = highest_quality_candidates(matches)
    if len(selected) > 1:
        raise StudyPrewarmRegistryError(
            "Multiple declared Meld branches match the same exact request."
        )
    return selected[0] if selected else None
