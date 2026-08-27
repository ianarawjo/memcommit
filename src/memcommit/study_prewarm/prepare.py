"""Validate and refresh the declared cache generation before a Study run."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
import re

from memcommit.application.authority.access import resolve_context_access
from memcommit.application.operations.compare.ledger.model import (
    COMPARISON_RULESET_VERSION,
    SUPPORTED_COMPARISON_RULESET_VERSIONS,
    ComparisonAnalysis,
)
from memcommit.application.operations.compare.ledger.provider import (
    COMPARISON_PROVIDER_CONTRACT_VERSION,
    SUPPORTED_COMPARISON_PROVIDER_CONTRACT_VERSIONS,
)
from memcommit.infrastructure.config import Config
from memcommit.context_targeting.readable_catalog import (
    freeze_profile_readable_context_catalog,
)
from memcommit.eval.study_compare_exact_matrix import (
    _comparison_input,
    plans_from_declared_exact_coordinates,
    run_exact_matrix,
)
from memcommit.eval.study_compare_graph_prewarm import TaskGraphPlan
from memcommit.infrastructure.providers.policy import (
    resolve_operation_provider_policy,
)
from memcommit.application.operations.profile.config import (
    ProfileEntry,
    ProfileRegistry,
    profile_control_dir,
    study_run_identity,
)
from memcommit.infrastructure.providers.types import (
    CODEX_CHATGPT_PROVIDER,
    CODEX_REASONING_EFFORTS,
)
from memcommit.persistence.store import MemoryStore
from memcommit.study_prewarm.compare import _exact_input_matches
from memcommit.study_prewarm.registry import (
    PrewarmOperation,
    StudyPrewarmEntry,
    StudyPrewarmRegistry,
    StudyPrewarmRegistryError,
    load_artifact,
    load_registry,
    payload_digest,
    replace_operation_artifacts,
)
from memcommit.study_prewarm.quality import prewarm_quality_satisfies


DEFAULT_INIT_STUDY_PREWARM_WORKERS = 96
DEFAULT_INIT_STUDY_PREWARM_REASONING = "xhigh"
_LEGACY_UPDATE_SCHEMA_VERSIONS = frozenset({6})
_COMPLETE_PROGRESS = re.compile(r"^COMPLETE (\d+)/(\d+) ")


@dataclass(frozen=True)
class _ValidatedCompareArtifact:
    task: str
    key: str
    analysis: ComparisonAnalysis
    artifact: dict[str, object]


@dataclass(frozen=True)
class StudyPrewarmCompatibility:
    registry: StudyPrewarmRegistry | None
    verified_enabled: int
    legacy_compare_parents: tuple[ComparisonAnalysis, ...]
    enabled_legacy_compare: int
    current_compare_artifacts: tuple[_ValidatedCompareArtifact, ...]
    current_update_records: tuple[tuple[str, str, dict[str, object]], ...]
    migrated_update_records: tuple[tuple[str, str, dict[str, object]], ...]

    @property
    def requires_refresh(self) -> bool:
        return bool(self.enabled_legacy_compare or self.migrated_update_records)


@dataclass(frozen=True)
class StudyPrewarmPreparationResult:
    checked: int
    regenerated: int
    workers: int


def _validate_current_entry(
    entry: StudyPrewarmEntry,
    artifact: dict[str, object],
) -> None:
    if entry.operation == "COMPARE":
        from memcommit.study_prewarm.compare import _validate_artifact

        _validate_artifact(
            artifact,
            entry_key=entry.key,
            entry_task=entry.task,
        )
    elif entry.operation == "UPDATE":
        from memcommit.study_prewarm.update import _validate_artifact

        _validate_artifact(artifact, entry_key=entry.key)
    elif entry.operation == "ATOMIZE":
        from memcommit.study_prewarm.atomize import _validate_artifact

        _validate_artifact(artifact, entry_key=entry.key)
    elif entry.operation == "SEVER":
        from memcommit.study_prewarm.sever import _validate_artifact

        _validate_artifact(artifact, entry_key=entry.key)
    elif entry.operation == "SUMMARIZE":
        from memcommit.study_prewarm.summarize import _validate_artifact

        _validate_artifact(
            artifact,
            entry_key=entry.key,
            entry_task=entry.task,
        )
    elif entry.operation == "MELD_DIRECTIONAL":
        from memcommit.study_prewarm.meld_directional import _validate_artifact

        _validate_artifact(artifact, entry_key=entry.key)
    elif entry.operation == "MELD_RESOLUTION":
        from memcommit.study_prewarm.meld_resolution import _validate_artifact

        _validate_artifact(
            artifact,
            entry_key=entry.key,
            entry_task=entry.task,
        )
    else:  # pragma: no cover - registry parsing owns this closed set.
        raise StudyPrewarmRegistryError("Unknown Study prewarm operation.")


def inspect_study_prewarm_compatibility(
    baseline_store_root: Path,
) -> StudyPrewarmCompatibility:
    """Validate bytes and classify only supported generation mismatches."""

    registry = load_registry(baseline_store_root)
    if registry is None:
        return StudyPrewarmCompatibility(None, 0, (), 0, (), (), ())

    legacy_compare: list[ComparisonAnalysis] = []
    enabled_legacy_compare = 0
    current_compare: list[_ValidatedCompareArtifact] = []
    current_updates: list[tuple[str, str, dict[str, object]]] = []
    migrated_updates: list[tuple[str, str, dict[str, object]]] = []
    verified_enabled = 0
    for entry in registry.entries:
        # Disabled declaration anchors remain digest-checked.  They are parsed
        # semantically only when they are a supported Compare plan generation.
        artifact = load_artifact(baseline_store_root, entry)
        if entry.operation == "COMPARE":
            ruleset = artifact.get("ruleset_version")
            provider_contract = artifact.get("provider_contract_version")
            if (
                ruleset != COMPARISON_RULESET_VERSION
                or provider_contract != COMPARISON_PROVIDER_CONTRACT_VERSION
            ):
                if (
                    not isinstance(ruleset, str)
                    or ruleset not in SUPPORTED_COMPARISON_RULESET_VERSIONS
                    or not isinstance(provider_contract, str)
                    or provider_contract
                    not in SUPPORTED_COMPARISON_PROVIDER_CONTRACT_VERSIONS
                ):
                    _validate_current_entry(entry, artifact)
                    raise AssertionError("unreachable")
                from memcommit.study_prewarm.compare import _validate_artifact

                analysis, _ = _validate_artifact(
                    artifact,
                    entry_key=entry.key,
                    entry_task=entry.task,
                    expected_ruleset_version=ruleset,
                    expected_provider_contract_version=provider_contract,
                )
                legacy_compare.append(analysis)
                if entry.enabled:
                    enabled_legacy_compare += 1
                    verified_enabled += 1
                continue
            if entry.enabled:
                from memcommit.study_prewarm.compare import _validate_artifact

                analysis, _ = _validate_artifact(
                    artifact,
                    entry_key=entry.key,
                    entry_task=entry.task,
                )
                current_compare.append(
                    _ValidatedCompareArtifact(
                        task=entry.task,
                        key=entry.key,
                        analysis=analysis,
                        artifact=artifact,
                    )
                )
                verified_enabled += 1
            continue
        if entry.operation == "UPDATE" and entry.enabled:
            schema_version = artifact.get("update_schema_version")
            if schema_version != _current_update_schema_version():
                if schema_version not in _LEGACY_UPDATE_SCHEMA_VERSIONS:
                    _validate_current_entry(entry, artifact)
                    raise AssertionError("unreachable")
                from memcommit.study_prewarm.update import (
                    upgrade_update_prewarm_artifact,
                )

                key, upgraded = upgrade_update_prewarm_artifact(
                    artifact,
                    entry_key=entry.key,
                    previous_schema_version=int(schema_version),
                )
                migrated_updates.append((entry.task, key, upgraded))
                verified_enabled += 1
                continue
        if not entry.enabled:
            continue
        _validate_current_entry(entry, artifact)
        verified_enabled += 1
        if entry.operation == "UPDATE":
            current_updates.append((entry.task, entry.key, artifact))

    return StudyPrewarmCompatibility(
        registry=registry,
        verified_enabled=verified_enabled,
        legacy_compare_parents=tuple(legacy_compare),
        enabled_legacy_compare=enabled_legacy_compare,
        current_compare_artifacts=tuple(current_compare),
        current_update_records=tuple(current_updates),
        migrated_update_records=tuple(migrated_updates),
    )


def _current_update_schema_version() -> int:
    from memcommit.application.operations.update.model import UPDATE_SCHEMA_VERSION

    return UPDATE_SCHEMA_VERSION


def _matrix_output_root(
    *,
    baseline_profile_uid: str,
    model: str,
    reasoning: str,
) -> Path:
    generation = payload_digest(
        {
            "operation": "COMPARE",
            "ruleset_version": COMPARISON_RULESET_VERSION,
            "provider_contract_version": COMPARISON_PROVIDER_CONTRACT_VERSION,
            "provider": CODEX_CHATGPT_PROVIDER,
            "model": model,
            "reasoning": reasoning,
        }
    )
    return (
        profile_control_dir()
        / "study-semantic-prewarm-work"
        / baseline_profile_uid
        / generation
    )


def _complete_current_compare_records(
    plans: Sequence[TaskGraphPlan],
    *,
    current: tuple[_ValidatedCompareArtifact, ...],
    model: str,
    reasoning: str,
) -> tuple[tuple[str, str, dict[str, object]], ...] | None:
    records: list[tuple[str, str, dict[str, object]]] = []
    for plan in plans:
        for pair in plan.pairs:
            requested = _comparison_input(pair)
            candidates = tuple(
                item
                for item in current
                if item.task == pair.task
                and _exact_input_matches(item.analysis, requested)
                and item.artifact.get("provider") == CODEX_CHATGPT_PROVIDER
                and item.artifact.get("model") == model
                and item.artifact.get("reasoning") == reasoning
                and isinstance(item.artifact.get("task_description"), dict)
                and item.artifact["task_description"].get("context_digest")
                == pair.description_digest
            )
            if not candidates:
                return None
            selected = min(candidates, key=lambda item: item.key)
            records.append((selected.task, selected.key, selected.artifact))
    return tuple(records)


def prepare_study_prewarms(
    *,
    baseline: ProfileEntry,
    baseline_store_root: Path,
    participant_store: MemoryStore,
    registry_snapshot: ProfileRegistry,
    workers: int = DEFAULT_INIT_STUDY_PREWARM_WORKERS,
    reasoning: str = DEFAULT_INIT_STUDY_PREWARM_REASONING,
    progress: Callable[[str], None] | None = None,
) -> StudyPrewarmPreparationResult:
    """Make every declared cache callable before its new bundle is attached."""

    if workers < 1:
        raise StudyPrewarmRegistryError("Study prewarm workers must be positive.")
    if reasoning not in CODEX_REASONING_EFFORTS:
        raise StudyPrewarmRegistryError(
            "Study prewarm reasoning effort is unsupported."
        )
    if progress is not None:
        progress("CHECK")
    compatibility = inspect_study_prewarm_compatibility(baseline_store_root)
    if compatibility.registry is None:
        if progress is not None:
            progress(f"READY {compatibility.verified_enabled}")
        return StudyPrewarmPreparationResult(
            checked=compatibility.verified_enabled,
            regenerated=0,
            workers=workers,
        )
    if compatibility.registry.baseline_profile_uid != baseline.uid:
        raise StudyPrewarmRegistryError(
            "Study prewarm registry belongs to a different baseline."
        )

    replacements: dict[
        PrewarmOperation,
        tuple[tuple[str, str, dict[str, object]], ...],
    ] = {}
    if compatibility.migrated_update_records:
        by_key = {
            key: (task, key, artifact)
            for task, key, artifact in (
                *compatibility.current_update_records,
                *compatibility.migrated_update_records,
            )
        }
        replacements["UPDATE"] = tuple(by_key[key] for key in sorted(by_key))

    regenerated_compare: tuple[tuple[str, str, dict[str, object]], ...] = ()
    if compatibility.legacy_compare_parents:
        identity = study_run_identity(registry_snapshot.active)
        if identity is None or identity.role != "PARTICIPANT":
            raise StudyPrewarmRegistryError(
                "Study cache refresh requires the staged participant identity."
            )
        policy = resolve_operation_provider_policy(
            "compare_contexts",
            config=Config(),
            mode="STUDY_PARTICIPANT",
            study_policy_version=identity.provider_policy_version,
        )
        if (
            policy.provider_id != CODEX_CHATGPT_PROVIDER
            or policy.model is None
            or policy.reasoning_effort is None
        ):
            raise StudyPrewarmRegistryError(
                "Study Compare refresh requires a configured Codex route."
            )
        if not prewarm_quality_satisfies(
            (policy.provider_id, policy.model, reasoning),
            (
                policy.provider_id,
                policy.model,
                policy.reasoning_effort,
            ),
        ):
            raise StudyPrewarmRegistryError(
                "Study prewarm generation quality does not satisfy the frozen "
                "participant route."
            )
        current_name = participant_store.current_context_name()
        if current_name is None:
            raise StudyPrewarmRegistryError(
                "Staged Study participant has no current Context."
            )
        selected = resolve_context_access(
            participant_store,
            current_name,
            current_name=current_name,
            required_permission="READ",
            registry=registry_snapshot,
        )
        catalog = freeze_profile_readable_context_catalog(
            participant_store,
            selected,
            include_query_routes=False,
            registry=registry_snapshot,
        )
        plans, _skipped_coordinates = plans_from_declared_exact_coordinates(
            catalog,
            parents=compatibility.legacy_compare_parents,
            model=policy.model,
            reasoning=reasoning,
            registry_snapshot=registry_snapshot,
        )
        current_matrix = _complete_current_compare_records(
            plans,
            current=compatibility.current_compare_artifacts,
            model=policy.model,
            reasoning=reasoning,
        )
        if current_matrix is not None:
            regenerated_compare = current_matrix
        else:
            if progress is not None:
                progress(f"REFRESH_START {workers}")
            last_reported = 0

            def matrix_progress(message: str) -> None:
                nonlocal last_reported
                match = _COMPLETE_PROGRESS.match(message)
                if progress is None or match is None:
                    return
                completed, total = (int(value) for value in match.groups())
                interval = max(1, total // 20)
                if completed == total or completed - last_reported >= interval:
                    last_reported = completed
                    progress(f"REFRESH_PROGRESS {completed} {total}")

            def capture(
                records: tuple[tuple[str, str, dict[str, object]], ...],
            ) -> int:
                nonlocal regenerated_compare
                regenerated_compare = records
                return len(records)

            run_exact_matrix(
                store=participant_store,
                plans=plans,
                output_root=_matrix_output_root(
                    baseline_profile_uid=baseline.uid,
                    model=policy.model,
                    reasoning=reasoning,
                ),
                baseline_profile_name=baseline.name,
                model=policy.model,
                reasoning=reasoning,
                timeout=policy.timeout_seconds,
                workers=workers,
                progress=matrix_progress,
                registry_snapshot=registry_snapshot,
                artifact_store_root=baseline_store_root,
                allow_legacy_parents=True,
                expected_pair_count=sum(len(plan.pairs) for plan in plans),
                use_declared_plan_pairs=True,
                publish_batch=capture,
            )
        if not regenerated_compare:
            raise StudyPrewarmRegistryError(
                "Study Compare refresh produced no exact artifacts."
            )
        if compatibility.enabled_legacy_compare or current_matrix is None:
            replacements["COMPARE"] = regenerated_compare

    if not replacements:
        if progress is not None:
            progress(f"READY {compatibility.verified_enabled}")
        return StudyPrewarmPreparationResult(
            checked=compatibility.verified_enabled,
            regenerated=0,
            workers=workers,
        )
    replace_operation_artifacts(
        baseline_store_root,
        baseline_profile_uid=baseline.uid,
        replacements=replacements,
    )
    regenerated = sum(len(records) for records in replacements.values())
    # Re-audit the active set after the atomic registry switch. Disabled legacy
    # Compare anchors remain plan metadata, so only enabled current entries
    # contribute to this publication check.
    refreshed = inspect_study_prewarm_compatibility(baseline_store_root)
    if refreshed.verified_enabled < regenerated:
        raise StudyPrewarmRegistryError(
            "Regenerated Study prewarm set did not survive validation."
        )
    if progress is not None:
        progress(f"REFRESH_COMPLETE {regenerated}")
    return StudyPrewarmPreparationResult(
        checked=refreshed.verified_enabled,
        regenerated=regenerated,
        workers=workers,
    )
