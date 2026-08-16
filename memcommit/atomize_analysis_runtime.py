"""Production Store, prepared-cache, and provider adapters for Atomize open."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable

from memcommit.atomize import (
    AtomizeAnalysisSession,
    AtomizeImpactError,
    AtomizeProvider,
    atomize_analysis_matches_context,
    collect_atomize_candidates,
    create_atomize_analysis,
    impact_atomize,
)
from memcommit.atomize_analysis_application import (
    AtomizeAnalysisOpenRequest,
    AtomizeAnalysisOpenResult,
    AtomizeProviderFactory,
    run_atomize_analysis_open,
)
from memcommit.atomize_workbench import create_atomize_workbench
from memcommit.context import Context
from memcommit.query_provider import CodexChatGPTProvider
from memcommit.store import MemoryStore
from memcommit.study_prewarm.atomize import find_declared_atomize_prewarm


ATOMIZE_AGGREGATE_TIMEOUT_SECONDS = 300


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
    from memcommit.atomize import select_atomize_candidates

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
    try:
        store.save_atomize_analysis(analysis)
        analysis_saved = True
        store.save_atomize_workbench(workbench)
    except Exception:
        if not analysis_saved:
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

    def _prepared(
        self,
        request: AtomizeAnalysisOpenRequest,
    ) -> tuple[AtomizeAnalysisSession | None, str | None]:
        if not request.allow_prepared:
            return None, request.output_context_name
        if self.prepared_analysis_override is not None:
            return self.prepared_analysis_override, (
                request.output_context_name or self.prepared_output_name
            )
        match = find_declared_atomize_prewarm(
            store=self.store,
            context=request.context,
        )
        if match is None:
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
        existing = self.store.load_atomize_analysis(context.uid)
        requested_uids = _requested_memory_uids(
            context,
            request.memory_selector,
        )
        existing_scope_matches = (
            existing is not None
            and tuple(item.memory_uid for item in existing.items) == requested_uids
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

        prepared_analysis, effective_prepared_output = self._prepared(request)
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
        analysis_saved = False
        try:
            self.store.save_atomize_analysis(analysis)
            analysis_saved = True
            self.store.save_atomize_workbench(workbench)
        except Exception:
            if not analysis_saved:
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
) -> AtomizeAnalysisOpenResult:
    """Execute one Atomize open through production non-terminal adapters."""

    return run_atomize_analysis_open(
        request,
        port=MemoryStoreAtomizeAnalysisOpenPort(
            store=store,
            validate_before_save=validate_before_save,
            prepared_analysis_override=prepared_analysis_override,
            prepared_output_name=prepared_output_name,
        ),
        provider_factory=provider_factory,
    )


__all__ = [
    "ATOMIZE_AGGREGATE_TIMEOUT_SECONDS",
    "MemoryStoreAtomizeAnalysisOpenPort",
    "execute_atomize_analysis_open",
]
