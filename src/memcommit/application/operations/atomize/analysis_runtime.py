"""Production Store, prepared-cache, and provider adapters for Atomize open."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable

from memcommit.application.operations.atomize.domain import (
    AtomizeAnalysisSession,
    AtomizeImpactError,
    AtomizeProvider,
    atomize_analysis_matches_context,
    collect_atomize_candidates,
    create_atomize_analysis,
    impact_atomize,
)
from memcommit.application.operations.atomize.analysis_application import (
    AtomizeAnalysisOpenRequest,
    AtomizeAnalysisOpenResult,
    AtomizeProviderFactory,
    run_atomize_analysis_open,
)
from memcommit.application.operations.atomize.application import AtomizeSessionSnapshot
from memcommit.application.operations.atomize.workbench import create_atomize_workbench
from memcommit.context import Context
from memcommit.providers.subscription import CodexChatGPTProvider
from memcommit.semantic.prompt_policy import resolve_semantic_prompt_policy
from memcommit.persistence.store import MemoryStore
from memcommit.study_prewarm.atomize import find_declared_atomize_prewarm


ATOMIZE_AGGREGATE_TIMEOUT_SECONDS = 300


def _archive_displaced_atomize_pair(
    store: MemoryStore,
    *,
    existing: AtomizeAnalysisSession | None,
    workbench,
    replacement_uid: str,
) -> bool:
    """Retain the prior UID only when a genuinely new analysis replaces it."""

    if existing is None or existing.uid == replacement_uid:
        return False
    return store.archive_atomize_session(existing, workbench)


def _remove_failed_atomize_archive(
    store: MemoryStore,
    *,
    existing: AtomizeAnalysisSession | None,
    created: bool,
) -> None:
    if existing is None or not created:
        return
    store.delete_atomize_session_history(existing.context_uid, existing.uid)


def _connect_aggregate_atomize_provider(
    provider_factory: Callable[[], AtomizeProvider],
) -> AtomizeProvider:
    """Give only the large aggregate Codex call a longer completion window."""

    provider = provider_factory()
    if isinstance(provider, CodexChatGPTProvider):
        # A Task-sized aggregate includes every direct Memory and the complete
        # bounded pair frame. Extending only this call retains the existing
        # failure latency of unrelated semantic operations.
        provider.timeout = max(
            provider.timeout,
            ATOMIZE_AGGREGATE_TIMEOUT_SECONDS,
        )
    return provider


def _requested_memory_uids(
    context: Context,
    memory_selector: str | None,
) -> tuple[str, ...]:
    if memory_selector is None:
        return tuple(
            candidate.memory.uid for candidate in collect_atomize_candidates(context)
        )
    # Memory focus is an optional operation shape layered during the rollout.
    # Keeping the import at the activated edge lets the extracted application
    # boundary remain compatible with profiles that expose only whole-Context
    # Atomize.
    from memcommit.application.operations.atomize.domain import select_atomize_candidates

    return tuple(
        candidate.memory.uid
        for candidate in select_atomize_candidates(context, memory_selector)[0]
    )


def _install_prepared_atomize_analysis(
    *,
    store: MemoryStore,
    context: Context,
    analysis: AtomizeAnalysisSession,
    output_context_name: str | None,
) -> AtomizeAnalysisOpenResult:
    """Publish one exact hidden analysis as a fresh visible session pair."""

    if (
        analysis.context_uid != context.uid
        or analysis.context_name != context.name
        or not atomize_analysis_matches_context(analysis, context)
    ):
        raise AtomizeImpactError(
            "Prepared atomize analysis does not match the current Context."
        )
    latest = store.load_direct(context.name)
    if not atomize_analysis_matches_context(analysis, latest):
        raise AtomizeImpactError(
            "Context changed while the prepared atomize analysis was being "
            "installed; no preview was saved."
        )

    existing = store.load_atomize_analysis(context.uid)
    previous_workbench = (
        store.load_atomize_workbench(existing) if existing is not None else None
    )
    workbench = create_atomize_workbench(
        analysis,
        output_context_name=output_context_name or context.name,
    )
    analysis_saved = False
    history_created = False
    try:
        history_created = _archive_displaced_atomize_pair(
            store,
            existing=existing,
            workbench=previous_workbench,
            replacement_uid=analysis.uid,
        )
        store.save_atomize_analysis(analysis)
        analysis_saved = True
        store.save_atomize_workbench(workbench)
    except Exception:
        if not analysis_saved:
            _remove_failed_atomize_archive(
                store,
                existing=existing,
                created=history_created,
            )
            raise
        try:
            if existing is None:
                store.delete_atomize_workbench(analysis.context_uid)
                store.delete_atomize_analysis(analysis.context_uid)
            else:
                store.save_atomize_analysis(existing)
                if previous_workbench is None:
                    store.delete_atomize_workbench(existing.context_uid)
                else:
                    store.save_atomize_workbench(previous_workbench)
            _remove_failed_atomize_archive(
                store,
                existing=existing,
                created=history_created,
            )
        except Exception as cleanup_error:
            raise RuntimeError(
                "Prepared atomize installation failed and its previous derived "
                "state could not be restored."
            ) from cleanup_error
        raise
    return AtomizeAnalysisOpenResult(
        analysis=analysis,
        workbench=workbench,
        origin="EXACT_PREWARM",
    )


@dataclass
class MemoryStoreAtomizeAnalysisOpenPort:
    """Open one exact saved, prepared, or provider-backed Atomize session."""

    store: MemoryStore
    validate_before_save: Callable[[], None] | None = None
    prepared_analysis_override: AtomizeAnalysisSession | None = None
    prepared_output_name: str | None = None
    expected_session: AtomizeSessionSnapshot | None = None

    def _replace_expected_session(
        self,
        analysis: AtomizeAnalysisSession,
        workbench,
    ) -> None:
        """Publish one provider result only over the exact reviewed pair."""

        expected = self.expected_session
        assert expected is not None
        with self.store._atomize_session_write_lock(  # noqa: SLF001
            expected.analysis.context_uid
        ):
            current_analysis = self.store.load_atomize_analysis(
                expected.analysis.context_uid
            )
            current_workbench = (
                self.store.load_atomize_workbench(current_analysis)
                if current_analysis is not None
                else None
            )
            if (
                current_analysis != expected.analysis
                or current_workbench != expected.workbench
            ):
                raise AtomizeImpactError(
                    "The atomize workbench changed while reviewed "
                    "materialization was running; no proposal was saved."
                )
            history_created = _archive_displaced_atomize_pair(
                self.store,
                existing=expected.analysis,
                workbench=expected.workbench,
                replacement_uid=analysis.uid,
            )
            analysis_saved = False
            try:
                self.store._save_atomize_analysis_locked(analysis)  # noqa: SLF001
                analysis_saved = True
                self.store._save_atomize_workbench_locked(workbench)  # noqa: SLF001
            except Exception:
                if analysis_saved:
                    self.store._save_atomize_analysis_locked(  # noqa: SLF001
                        expected.analysis
                    )
                    if expected.workbench is None:
                        path = self.store._atomize_workbench_path(  # noqa: SLF001
                            expected.analysis.context_uid
                        )
                        if path.exists():
                            path.unlink()
                    else:
                        self.store._save_atomize_workbench_locked(  # noqa: SLF001
                            expected.workbench
                        )
                _remove_failed_atomize_archive(
                    self.store,
                    existing=expected.analysis,
                    created=history_created,
                )
                raise

    def _prepared(
        self,
        request: AtomizeAnalysisOpenRequest,
        *,
        prompt_policy_id: str,
    ) -> tuple[AtomizeAnalysisSession | None, str | None]:
        if not request.allow_prepared:
            return None, request.output_context_name
        if self.prepared_analysis_override is not None:
            if (
                self.prepared_analysis_override.prompt_policy_id
                != prompt_policy_id
            ):
                return None, request.output_context_name
            return self.prepared_analysis_override, (
                request.output_context_name or self.prepared_output_name
            )
        match = find_declared_atomize_prewarm(
            store=self.store,
            context=request.context,
        )
        if match is None:
            return None, request.output_context_name
        if match.analysis.prompt_policy_id != prompt_policy_id:
            return None, request.output_context_name
        return match.analysis, (
            request.output_context_name or match.output_context_name
        )

    def open(
        self,
        request: AtomizeAnalysisOpenRequest,
        *,
        provider_factory: AtomizeProviderFactory,
    ) -> AtomizeAnalysisOpenResult:
        context = request.context
        prompt_policy_id = resolve_semantic_prompt_policy().policy_id
        existing = self.store.load_atomize_analysis(context.uid)
        requested_uids = _requested_memory_uids(
            context,
            request.memory_selector,
        )
        existing_scope_matches = (
            existing is not None
            and tuple(item.memory_uid for item in existing.items) == requested_uids
            and existing.prompt_policy_id == prompt_policy_id
        )
        if existing is not None and not request.refresh and existing_scope_matches:
            if (
                existing.context_uid != context.uid
                or existing.context_name != context.name
            ):
                raise AtomizeImpactError(
                    "The saved atomize analysis does not match this Context's "
                    "identity."
                )
            if not atomize_analysis_matches_context(existing, context):
                raise AtomizeImpactError(
                    "Saved atomize analysis is stale. Reanalysis must be "
                    "requested explicitly; the existing result was not replaced."
                )
            workbench = self.store.load_atomize_workbench(existing)
            if workbench is None:
                workbench = create_atomize_workbench(
                    existing,
                    output_context_name=request.output_context_name,
                )
                self.store.save_atomize_workbench(workbench)
            elif (
                request.output_context_name is not None
                and workbench.output_context_name != request.output_context_name
            ):
                # Output planning is durable review state, not provider input.
                workbench = replace(
                    workbench,
                    output_context_name=request.output_context_name,
                )
                self.store.save_atomize_workbench(workbench)
            return AtomizeAnalysisOpenResult(
                analysis=existing,
                workbench=workbench,
                origin="SAVED",
            )

        prepared_analysis, effective_prepared_output = self._prepared(
            request,
            prompt_policy_id=prompt_policy_id,
        )
        if prepared_analysis is not None and not request.refresh:
            prepared_uids = tuple(
                item.memory_uid for item in prepared_analysis.items
            )
            if request.memory_selector is not None and requested_uids != prepared_uids:
                raise AtomizeImpactError(
                    "A focused atomize request cannot reuse a whole-Context "
                    "prepared analysis."
                )
            if (
                request.declared_frames
                or request.declared_frame_origins
                or request.source_review_uid is not None
                or request.source_review_digest is not None
            ):
                raise AtomizeImpactError(
                    "A prepared atomize analysis cannot replace a reviewed "
                    "reanalysis request."
                )
            if self.validate_before_save is not None:
                self.validate_before_save()
            return _install_prepared_atomize_analysis(
                store=self.store,
                context=context,
                analysis=prepared_analysis,
                output_context_name=effective_prepared_output,
            )

        previous_workbench = (
            self.store.load_atomize_workbench(existing)
            if existing is not None
            else None
        )
        effective_output_name = (
            request.output_context_name
            or (
                previous_workbench.output_context_name
                if previous_workbench is not None
                else None
            )
            or context.name
        )
        impact_options: dict[str, object] = {}
        if request.memory_selector is not None:
            impact_options["memory_selector"] = request.memory_selector
        report = impact_atomize(
            context,
            lambda: _connect_aggregate_atomize_provider(provider_factory),
            declared_frames=request.declared_frames,
            **impact_options,
        )
        analysis = create_atomize_analysis(
            context,
            report,
            declared_frames=request.declared_frames,
            declared_frame_origins=request.declared_frame_origins,
            source_review_uid=request.source_review_uid,
            source_review_digest=request.source_review_digest,
        )
        latest = self.store.load_direct(context.name)
        if not atomize_analysis_matches_context(analysis, latest):
            raise AtomizeImpactError(
                "Context changed while atomize analysis was running; no "
                "preview was saved. Run the operation again."
            )
        if self.validate_before_save is not None:
            self.validate_before_save()
        workbench = create_atomize_workbench(
            analysis,
            output_context_name=effective_output_name,
        )
        if self.expected_session is not None:
            self._replace_expected_session(analysis, workbench)
            return AtomizeAnalysisOpenResult(
                analysis=analysis,
                workbench=workbench,
                origin="PROVIDER",
            )

        analysis_saved = False
        history_created = False
        try:
            history_created = _archive_displaced_atomize_pair(
                self.store,
                existing=existing,
                workbench=previous_workbench,
                replacement_uid=analysis.uid,
            )
            self.store.save_atomize_analysis(analysis)
            analysis_saved = True
            self.store.save_atomize_workbench(workbench)
        except Exception:
            if not analysis_saved:
                _remove_failed_atomize_archive(
                    self.store,
                    existing=existing,
                    created=history_created,
                )
                raise
            try:
                if existing is None:
                    self.store.delete_atomize_workbench(analysis.context_uid)
                    self.store.delete_atomize_analysis(analysis.context_uid)
                else:
                    self.store.save_atomize_analysis(existing)
                    if previous_workbench is None:
                        self.store.delete_atomize_workbench(existing.context_uid)
                    else:
                        self.store.save_atomize_workbench(previous_workbench)
                _remove_failed_atomize_archive(
                    self.store,
                    existing=existing,
                    created=history_created,
                )
            except Exception as cleanup_error:
                raise RuntimeError(
                    "Atomize analysis failed and its previous derived state "
                    "could not be restored."
                ) from cleanup_error
            raise
        return AtomizeAnalysisOpenResult(
            analysis=analysis,
            workbench=workbench,
            origin="PROVIDER",
        )


def execute_atomize_analysis_open(
    request: AtomizeAnalysisOpenRequest,
    *,
    store: MemoryStore,
    provider_factory: AtomizeProviderFactory,
    validate_before_save: Callable[[], None] | None = None,
    prepared_analysis_override: AtomizeAnalysisSession | None = None,
    prepared_output_name: str | None = None,
    expected_session: AtomizeSessionSnapshot | None = None,
) -> AtomizeAnalysisOpenResult:
    """Execute one Atomize open through production non-terminal adapters."""

    return run_atomize_analysis_open(
        request,
        port=MemoryStoreAtomizeAnalysisOpenPort(
            store=store,
            validate_before_save=validate_before_save,
            prepared_analysis_override=prepared_analysis_override,
            prepared_output_name=prepared_output_name,
            expected_session=expected_session,
        ),
        provider_factory=provider_factory,
    )


__all__ = [
    "ATOMIZE_AGGREGATE_TIMEOUT_SECONDS",
    "MemoryStoreAtomizeAnalysisOpenPort",
    "execute_atomize_analysis_open",
]
