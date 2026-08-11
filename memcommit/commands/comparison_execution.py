"""Shared execution boundary for exact ordered Compare analyses."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from memcommit.comparison import (
    COMPARISON_RULESET_VERSION,
    ComparisonAnalysis,
    ComparisonError,
    ComparisonInput,
)
from memcommit.comparison_store import (
    ConcurrentComparisonUpdateError,
    load_comparison_analysis,
    save_comparison_analysis,
)
from memcommit.commands.command_wait import CommandWaitView
from memcommit.commands.granted_context import (
    ContextAccess,
    GrantedReadStore,
    freeze_granted_context_binding,
    resolve_context_access,
    revalidate_granted_context_binding,
)
from memcommit.commands.tui_primitives import display_escape_text
from memcommit.context import Context, Memory, MemoryRef, QueryContextRef
from memcommit.context_targeting.loading import load_context_scope
from memcommit.derived_policy import (
    AnalysisRetention,
    analysis_retention,
    authorize_analysis_save,
    authorize_combination,
)
from memcommit.granted_comparison_store import (
    load_granted_comparison_artifact,
    save_granted_comparison_artifact,
)
from memcommit.profiles import ProfileError, authority_grant_snapshot_lock
from memcommit.query_provider import CodexChatGPTProvider
from memcommit.store import MemoryStore


COMPARISON_AGGREGATE_TIMEOUT_SECONDS = 900


@dataclass(frozen=True)
class ComparisonExecutionResult:
    """One saved, projected, or newly analyzed ordered comparison."""

    analysis: ComparisonAnalysis
    reused: bool
    durable: bool
    retention: AnalysisRetention | None
    origin: str


def connect_comparison_provider(provider_factory):
    """Connect one provider with Compare's whole-ledger timeout boundary."""

    provider = provider_factory()
    if isinstance(provider, CodexChatGPTProvider):
        provider.timeout = max(
            provider.timeout,
            COMPARISON_AGGREGATE_TIMEOUT_SECONDS,
        )
    return provider


def comparison_wait_view(comparison_input: ComparisonInput) -> CommandWaitView:
    """Restore the exact frozen setup while its report is unavailable."""

    lines = [
        "MEM COMPARE · FROZEN INPUT · RESULT PENDING",
        "",
    ]
    labels = ("REFERENCE A", "PEER B")
    for label, frame, descendants in zip(
        labels,
        comparison_input.frames,
        comparison_input.include_descendants,
        strict=True,
    ):
        lines.append(f"{label} · {display_escape_text(frame.context_name)}")
        lines.append(
            "  SCOPE · "
            + ("INCLUDE DESCENDANTS" if descendants else "THIS CONTEXT ONLY")
        )
        lines.append(f"  FROZEN MEMORIES · {len(frame.memories)}")
        lines.append("")
    lines.extend(
        [
            "The comparison report will replace this setup after the provider",
            "returns. The two frozen source frames cannot be changed here.",
        ]
    )
    return CommandWaitView(
        title="COMPARE CONFIRMED INPUTS · READ-ONLY",
        text="\n".join(lines),
    )


def recursive_comparison_projection(root: Context) -> Context:
    """Flatten one loaded tree while retaining each Memory's public path."""

    if not any(isinstance(item, Context) for item in root.iter_items()):
        return root
    projected = Context(uid=root.uid, name=root.name)
    seen_contexts: set[str] = set()

    def visit(context: Context) -> None:
        if context.uid in seen_contexts:
            return
        seen_contexts.add(context.uid)
        for item in context.iter_items():
            if isinstance(item, Memory):
                projected.add(
                    Memory(
                        uid=item.uid,
                        content=f"[{context.name}] {item.content}",
                    )
                )
            elif isinstance(item, Context):
                visit(item)
            elif isinstance(item, QueryContextRef):
                # Concealed query-only content is never ordinary Compare input.
                continue
            elif isinstance(item, MemoryRef):
                raise ComparisonError(
                    "Recursive Compare does not copy live Memory references; "
                    f"unsupported item [{item.uid[:8]}] in {context.name!r}."
                )

    visit(root)
    return projected


def load_comparison_context(
    access: ContextAccess,
    *,
    include_descendants: bool = False,
) -> Context:
    """Load one local or granted source using Compare's exact projection."""

    reader = GrantedReadStore(access) if access.is_granted else access.store
    context = load_context_scope(
        reader,
        access.display_name if access.is_granted else access.context_name,
        include_descendants=include_descendants,
    )
    return recursive_comparison_projection(context)


def _missing_durable_analysis_error() -> ProfileError:
    return ProfileError(
        "Symmetric Meld must save its ordered Compare basis, but the available "
        "Grants do not share SAVE_ANALYSIS or SAVE_BOUND_ANALYSIS authority."
    )


def ensure_comparison_analysis(
    *,
    store: MemoryStore,
    reference_access: ContextAccess,
    compared_access: ContextAccess,
    reference: Context,
    compared: Context,
    current_name: str | None,
    include_descendants: tuple[bool, bool] = (False, False),
    refresh: bool = False,
    require_durable: bool = False,
    analyze: Callable[[ComparisonInput], ComparisonAnalysis],
    project: Callable[[ComparisonInput], ComparisonAnalysis | None] | None = None,
) -> ComparisonExecutionResult:
    """Reuse or create the exact ordered basis without changing current state.

    The caller freezes the public endpoint meaning once, then supplies the
    Context projections it intends to analyze. This function owns artifact
    lookup, provider-result publication, grant revalidation, and CAS. A
    symmetric Meld may require durable retention because its target-bound
    session must be reproducible; ordinary Compare may still render an
    explicitly unsaved granted result.
    """

    accesses = (reference_access, compared_access)
    authorize_combination(accesses)
    granted = any(access.is_granted for access in accesses)
    bindings = tuple(
        freeze_granted_context_binding(access) if access.is_granted else None
        for access in accesses
    )
    granted_artifact = (
        load_granted_comparison_artifact(store, reference.uid, compared.uid)
        if granted
        else None
    )
    if granted:
        existing = (
            granted_artifact.analysis
            if granted_artifact is not None
            else None
        )
    else:
        existing = load_comparison_analysis(reference.uid, compared.uid)
    if (
        existing is not None
        and existing.include_descendants == include_descendants
        and existing.matches(reference, compared)
        and existing.ruleset_version == COMPARISON_RULESET_VERSION
        and not refresh
    ):
        return ComparisonExecutionResult(
            analysis=existing,
            reused=True,
            durable=True,
            retention=(
                granted_artifact.retention
                if granted_artifact is not None
                else None
            ),
            origin="SAVED_REUSE",
        )

    retention = analysis_retention(accesses) if granted else None
    if require_durable and granted and retention is None:
        # Fail before provider connection: an unsaved basis cannot become a
        # reproducible target-bound symmetric Meld session.
        raise _missing_durable_analysis_error()
    if retention is not None:
        authorize_analysis_save(accesses, retention=retention)

    comparison_input = ComparisonInput.from_contexts(
        reference,
        compared,
        reference_descendants=include_descendants[0],
        compared_descendants=include_descendants[1],
    )
    projected = (
        project(comparison_input)
        if project is not None and not refresh and not require_durable
        else None
    )
    if projected is not None:
        if (
            projected.ruleset_version != COMPARISON_RULESET_VERSION
            or projected.include_descendants != include_descendants
            or not projected.matches(reference, compared)
        ):
            raise ComparisonError(
                "Projected Compare result does not match the current frames, "
                "scope, or ruleset."
            )
        if granted:
            # A projection is ephemeral, but it still discloses the complete
            # current frames. Revalidate every Grant after host projection and
            # before returning any report, just as the live publication path
            # does after provider inference.
            with authority_grant_snapshot_lock() as registry:
                current_accesses: list[ContextAccess] = []
                for access, binding in zip(accesses, bindings, strict=True):
                    current_accesses.append(
                        revalidate_granted_context_binding(
                            binding,
                            registry=registry,
                            active_store=store,
                        )
                        if binding is not None
                        else resolve_context_access(
                            store,
                            access.context_name,
                            current_name=current_name,
                            required_permission="READ",
                            registry=registry,
                        )
                    )
                authorize_combination(current_accesses)
                current_reference = load_comparison_context(
                    current_accesses[0],
                    include_descendants=include_descendants[0],
                )
                current_compared = load_comparison_context(
                    current_accesses[1],
                    include_descendants=include_descendants[1],
                )
                if not projected.matches(current_reference, current_compared):
                    raise ConcurrentComparisonUpdateError(
                        "A granted comparison source changed while Compare was "
                        "projecting it; no result was published."
                    )
        return ComparisonExecutionResult(
            analysis=projected,
            reused=True,
            durable=False,
            retention=None,
            origin="PROJECTED",
        )
    analysis = analyze(comparison_input)

    if granted:
        with authority_grant_snapshot_lock() as registry:
            current_accesses: list[ContextAccess] = []
            for access, binding in zip(accesses, bindings, strict=True):
                current_accesses.append(
                    revalidate_granted_context_binding(
                        binding,
                        registry=registry,
                        active_store=store,
                    )
                    if binding is not None
                    else resolve_context_access(
                        store,
                        access.context_name,
                        current_name=current_name,
                        required_permission="READ",
                        registry=registry,
                    )
                )
            current_reference = load_comparison_context(
                current_accesses[0],
                include_descendants=include_descendants[0],
            )
            current_compared = load_comparison_context(
                current_accesses[1],
                include_descendants=include_descendants[1],
            )
            if not analysis.matches(current_reference, current_compared):
                raise ConcurrentComparisonUpdateError(
                    "A granted comparison source changed while Compare was "
                    "analyzing it; no result was published."
                )
            current_retention = analysis_retention(current_accesses)
            if require_durable and current_retention is None:
                raise _missing_durable_analysis_error()
            if current_retention is not None:
                save_granted_comparison_artifact(
                    store,
                    analysis,
                    current_accesses,
                    retention=current_retention,
                    expected_analysis_uid=(
                        existing.uid if existing is not None else None
                    ),
                )
        return ComparisonExecutionResult(
            analysis=analysis,
            reused=False,
            durable=current_retention is not None,
            retention=current_retention,
            origin="LIVE",
        )

    save_comparison_analysis(
        store,
        analysis,
        expected_analysis_uid=(existing.uid if existing is not None else None),
    )
    return ComparisonExecutionResult(
        analysis=analysis,
        reused=False,
        durable=True,
        retention=None,
        origin="LIVE",
    )


def install_prepared_comparison_analysis(
    *,
    store: MemoryStore,
    reference_access: ContextAccess,
    compared_access: ContextAccess,
    reference: Context,
    compared: Context,
    current_name: str | None,
    include_descendants: tuple[bool, bool],
    analysis: ComparisonAnalysis,
) -> ComparisonExecutionResult:
    """Install one exact portable seed through Compare's production boundary.

    A prepared semantic payload is portable across Study runs cloned from the
    same immutable baseline, but its Grant wrapper is not. The ordinary
    execution boundary therefore resolves current authority, rechecks the
    complete current frames under lock, and writes a new run-local binding.
    No provider is connected by this setup-only path.
    """

    if not isinstance(analysis, ComparisonAnalysis):
        raise TypeError("Prepared Compare seed must be a ComparisonAnalysis.")
    if (
        analysis.ruleset_version != COMPARISON_RULESET_VERSION
        or analysis.include_descendants != include_descendants
        or not analysis.matches(reference, compared)
    ):
        raise ComparisonError(
            "Prepared Compare seed does not match the exact current frames, "
            "scope, or ruleset."
        )

    def prepared(comparison_input: ComparisonInput) -> ComparisonAnalysis:
        # Recheck the freshly constructed request too. This prevents a caller
        # from validating one scope and publishing the seed under another.
        if (
            comparison_input.include_descendants != include_descendants
            or tuple(
                (frame.context_uid, frame.context_name, frame.context_digest)
                for frame in comparison_input.frames
            )
            != tuple(
                (frame.context_uid, frame.context_name, frame.context_digest)
                for frame in analysis.frames
            )
        ):
            raise ComparisonError(
                "Prepared Compare seed changed at the installation boundary."
            )
        return analysis

    result = ensure_comparison_analysis(
        store=store,
        reference_access=reference_access,
        compared_access=compared_access,
        reference=reference,
        compared=compared,
        current_name=current_name,
        include_descendants=include_descendants,
        # Setup installation intentionally replaces a stale slot, but the
        # production CAS still observes its exact previous analysis UID.
        refresh=True,
        require_durable=True,
        analyze=prepared,
    )
    return ComparisonExecutionResult(
        analysis=result.analysis,
        reused=True,
        durable=result.durable,
        retention=result.retention,
        origin="EXACT_PREWARM",
    )
