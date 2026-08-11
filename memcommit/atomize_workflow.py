"""Open or explicitly refresh one durable atomize analysis/workbench pair."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable

from memcommit.atomize import (
    AtomizeAnalysisSession,
    AtomizeFrameOrigin,
    AtomizeImpactError,
    AtomizeProvider,
    atomize_analysis_matches_context,
    create_atomize_analysis,
    impact_atomize,
)
from memcommit.atomize_workbench import (
    AtomizeWorkbenchSession,
    create_atomize_workbench,
)
from memcommit.context import Context
from memcommit.query_provider import CodexChatGPTProvider
from memcommit.store import MemoryStore


ATOMIZE_AGGREGATE_TIMEOUT_SECONDS = 300


@dataclass(frozen=True)
class OpenAtomizeWorkbenchResult:
    analysis: AtomizeAnalysisSession
    workbench: AtomizeWorkbenchSession
    created_analysis: bool


def install_prepared_atomize_analysis(
    *,
    store: MemoryStore,
    ctx: Context,
    analysis: AtomizeAnalysisSession,
    output_context_name: str | None = None,
) -> OpenAtomizeWorkbenchResult:
    """Install one exact prepared analysis without opening a provider.

    Study setup uses the same durable analysis/workbench pair as an ordinary
    Atomize run.  The portable semantic payload is accepted only after it
    matches the current direct Source exactly; the workbench is regenerated
    for this run so no review response or application state crosses runs.
    """

    if (
        analysis.context_uid != ctx.uid
        or analysis.context_name != ctx.name
        or not atomize_analysis_matches_context(analysis, ctx)
    ):
        raise AtomizeImpactError(
            "Prepared atomize analysis does not match the current Context."
        )
    latest = store.load_direct(ctx.name)
    if not atomize_analysis_matches_context(analysis, latest):
        raise AtomizeImpactError(
            "Context changed while the prepared atomize analysis was being "
            "installed; no preview was saved."
        )

    existing = store.load_atomize_analysis(ctx.uid)
    previous_workbench = (
        store.load_atomize_workbench(existing)
        if existing is not None
        else None
    )
    workbench = create_atomize_workbench(
        analysis,
        output_context_name=output_context_name or ctx.name,
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
    return OpenAtomizeWorkbenchResult(
        analysis=analysis,
        workbench=workbench,
        created_analysis=False,
    )


def _connect_aggregate_atomize_provider(
    provider_factory: Callable[[], AtomizeProvider],
) -> AtomizeProvider:
    """Give only the large aggregate Codex call a longer completion window."""
    provider = provider_factory()
    if isinstance(provider, CodexChatGPTProvider):
        # A Task-sized aggregate includes every direct Memory and the complete
        # bounded pair frame. The ordinary two-minute provider default proved
        # too short in the live 51-Memory fixture, while extending every mem
        # semantic command would make unrelated failures unnecessarily slow.
        provider.timeout = max(
            provider.timeout,
            ATOMIZE_AGGREGATE_TIMEOUT_SECONDS,
        )
    return provider


def open_or_create_atomize_workbench(
    *,
    store: MemoryStore,
    ctx: Context,
    provider_factory: Callable[[], AtomizeProvider],
    refresh: bool = False,
    declared_frames: dict[str, str] | None = None,
    declared_frame_origins: dict[str, AtomizeFrameOrigin] | None = None,
    source_review_uid: str | None = None,
    source_review_digest: str | None = None,
    output_context_name: str | None = None,
    validate_before_save: Callable[[], None] | None = None,
) -> OpenAtomizeWorkbenchResult:
    """Reuse an exact current result; call the provider only at a clear edge."""
    existing = store.load_atomize_analysis(ctx.uid)
    if existing is not None and not refresh:
        if (
            existing.context_uid != ctx.uid
            or existing.context_name != ctx.name
        ):
            raise AtomizeImpactError(
                "The saved atomize analysis does not match this Context's "
                "identity."
            )
        if not atomize_analysis_matches_context(existing, ctx):
            raise AtomizeImpactError(
                "Saved atomize analysis is stale. Reanalysis must be "
                "requested explicitly; the existing result was not replaced."
            )
        workbench = store.load_atomize_workbench(existing)
        if workbench is None:
            workbench = create_atomize_workbench(
                existing,
                output_context_name=output_context_name,
            )
            store.save_atomize_workbench(workbench)
        elif (
            output_context_name is not None
            and workbench.output_context_name != output_context_name
        ):
            # Destination planning is durable workbench state, not semantic
            # analysis input. Reusing the analysis keeps Impact, Review, and
            # Atomize on the same session while allowing the launcher to set
            # an explicit Output without another provider call.
            workbench = replace(
                workbench,
                output_context_name=output_context_name,
            )
            store.save_atomize_workbench(workbench)
        return OpenAtomizeWorkbenchResult(
            analysis=existing,
            workbench=workbench,
            created_analysis=False,
        )

    previous_workbench = (
        store.load_atomize_workbench(existing)
        if existing is not None
        else None
    )
    effective_output_name = (
        output_context_name
        or (
            previous_workbench.output_context_name
            if previous_workbench is not None
            else None
        )
        or ctx.name
    )
    report = impact_atomize(
        ctx,
        lambda: _connect_aggregate_atomize_provider(provider_factory),
        declared_frames=declared_frames,
    )
    analysis = create_atomize_analysis(
        ctx,
        report,
        declared_frames=declared_frames,
        declared_frame_origins=declared_frame_origins,
        source_review_uid=source_review_uid,
        source_review_digest=source_review_digest,
    )
    latest = store.load_direct(ctx.name)
    if not atomize_analysis_matches_context(analysis, latest):
        raise AtomizeImpactError(
            "Context changed while atomize analysis was running; no preview "
            "was saved. Run the operation again."
        )
    if validate_before_save is not None:
        validate_before_save()
    workbench = create_atomize_workbench(
        analysis,
        output_context_name=effective_output_name,
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
                "Atomize analysis failed and its previous derived state could "
                "not be restored."
            ) from cleanup_error
        raise
    return OpenAtomizeWorkbenchResult(
        analysis=analysis,
        workbench=workbench,
        created_analysis=True,
    )
