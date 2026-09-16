"""MemoryStore adapter for the operation-owned Fit application."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import hashlib
from typing import Protocol

from memcommit.application.context_access.access import (
    ContextAccess,
    GrantedReadStore,
    freeze_granted_context_binding,
    revalidate_granted_context_binding,
)
from memcommit.application.context_access.operand_resolution import (
    freeze_profile_context_access_candidates,
    resolve_existing_context_access,
    try_resolve_context_access_or_local_memory,
)
from memcommit.core.context import Context, Memory
from memcommit.application.capabilities.context_locator import (
    is_relative_context_locator,
)
from memcommit.application.capabilities.durable_uid_resolution import (
    is_unresolved_uid_selector,
)
from memcommit.application.capabilities.operand_resolution import (
    ResolvedExistingContextOperand,
)
from memcommit.application.capabilities.semantic.memory_scope import (
    MemoryScopeError,
    resolve_memory_scope,
)
from memcommit.core.context_targeting.model import (
    DirectMemoryTarget,
    DirectMemoryLocator,
)
from memcommit.core.context_targeting.resolution import (
    parse_auto_typed_context_memory_operand,
)
from memcommit.application.operations.fit.ground_report import (
    FitError,
    FitProvider,
    FitReport,
)
from memcommit.application.operations.fit.application import (
    FitInputOrigin,
    FitInputOriginKind,
    FitMemorySourceRequest,
    FitPropositionsRequest,
    FitPropositionsResult,
    FitRequest,
    FitResult,
    FitStoredSourcesRequest,
)
from memcommit.application.operations.fit.judgment import (
    FitAnalysis,
    FitProposition,
    FitQuestion,
    execute_fit_judgments,
    prepare_fit_judgments,
)
from memcommit.application.operations.ground.workspace_fit import (
    execute_ground_workspace_fit,
)
from memcommit.application.operations.ground.workspace_runtime import (
    load_ground_workspace,
)
from memcommit.application.operations.fit.store import FitStore
from memcommit.application.operations.profile.model import authority_grant_snapshot_lock
from memcommit.persistence.store import (
    MemoryStore,
    context_record_digest,
)
from memcommit.application.operations.update.model import GrantedUpdateTarget


class FitProviderFactory(Protocol):
    def __call__(self) -> FitProvider:
        """Connect only after the complete Fit input is locally validated."""


def run_proposition_fit(
    request: FitPropositionsRequest,
    *,
    provider_factory: FitProviderFactory,
) -> FitPropositionsResult:
    """Plan a complete general Fit frame before connecting its provider."""

    if not isinstance(request, FitPropositionsRequest):
        raise TypeError("General Fit runtime requires a typed request.")
    question = FitQuestion(
        "fit",
        propositions=request.propositions,
        background=request.background,
    )
    prepared = prepare_fit_judgments((question,))
    batch = execute_fit_judgments(prepared, provider=provider_factory())
    return FitPropositionsResult(
        FitAnalysis(
            uid=batch.uid,
            question=question,
            assessment=batch.assessments[0],
            overview=batch.overview,
            created_at=batch.created_at,
            provider_identity=batch.provider_identity,
        )
    )


class FitSourceError(ValueError):
    """One stored general-Fit source could not be frozen exactly."""


@dataclass
class _FitSourceAccumulator:
    access: ContextAccess
    context: Context
    granted_binding: GrantedUpdateTarget | None
    whole_context_digest: str | None = None
    selected_memory_digests: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class _FrozenFitSource:
    access: ContextAccess
    context_uid: str
    granted_binding: GrantedUpdateTarget | None
    whole_context_digest: str | None
    selected_memory_digests: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class _SelectedFitMemory:
    kind: FitInputOriginKind
    source: _FitSourceAccumulator
    memory: Memory


def _fit_access_key(access: ContextAccess) -> tuple[str, ...]:
    if access.is_granted:
        assert access.view is not None
        return (
            "GRANT",
            access.view.grant.uid,
            access.view.authority.uid,
            access.context_name,
            access.access_name,
        )
    return ("LOCAL", str(access.store.store_dir.resolve()), access.context_name)


def _load_fit_context_direct(
    access: ContextAccess,
    *,
    registry=None,
) -> Context:
    if access.is_granted:
        return GrantedReadStore(access, registry=registry).load_direct(
            access.access_name
        )
    return access.store.load_direct(access.context_name)


def _memory_digest(memory: Memory) -> str:
    return hashlib.sha256(memory.content.encode("utf-8")).hexdigest()


def _revalidate_fit_sources(
    frozen: tuple[_FrozenFitSource, ...],
    *,
    store: MemoryStore,
) -> None:
    """Recheck identities, content, and Grant authority before publication."""

    def validate(registry=None) -> None:
        current_accesses: list[ContextAccess] = []
        current_contexts: list[Context] = []
        for source in frozen:
            access = (
                revalidate_granted_context_binding(
                    source.granted_binding,
                    registry=registry,
                    active_store=store,
                )
                if source.granted_binding is not None
                else source.access
            )
            try:
                context = _load_fit_context_direct(access, registry=registry)
            except FileNotFoundError as error:
                raise FitSourceError(
                    f"Fit Source Context {access.access_name!r} disappeared "
                    "during judgment."
                ) from error
            current_accesses.append(access)
            current_contexts.append(context)

        for source, context in zip(frozen, current_contexts, strict=True):
            if context.uid != source.context_uid:
                raise FitSourceError(
                    f"Fit Source Context {source.access.access_name!r} changed "
                    "identity during judgment."
                )
            if source.whole_context_digest is not None and (
                context_record_digest(context) != source.whole_context_digest
            ):
                raise FitSourceError(
                    f"Fit Source Context {source.access.access_name!r} changed "
                    "during judgment."
                )
            for memory_uid, digest in source.selected_memory_digests:
                memory = context.memories.get(memory_uid)
                if not isinstance(memory, Memory) or _memory_digest(memory) != digest:
                    raise FitSourceError(
                        f"Fit Source Memory {memory_uid[:8]!r} in "
                        f"{source.access.access_name!r} changed during judgment."
                    )

    if any(source.granted_binding is not None for source in frozen):
        with authority_grant_snapshot_lock() as registry:
            validate(registry)
        return
    validate()


def run_stored_source_fit(
    request: FitStoredSourcesRequest,
    *,
    store: MemoryStore,
    provider_factory: FitProviderFactory,
) -> FitPropositionsResult:
    """Resolve stored Memories into one exact, read-only general Fit frame."""

    if not isinstance(request, FitStoredSourcesRequest):
        raise TypeError("Stored-source Fit runtime requires a typed request.")
    current_name = store.current_context_name()
    accumulators: dict[tuple[str, ...], _FitSourceAccumulator] = {}
    access_order: list[tuple[str, ...]] = []
    context_candidates = freeze_profile_context_access_candidates(
        store,
        current_name=current_name,
    )

    def source(locator: str | None) -> _FitSourceAccumulator:
        access = resolve_existing_context_access(
            store,
            locator,
            current_name=current_name,
            required_permission="READ",
            candidates=context_candidates,
        ).value
        key = _fit_access_key(access)
        existing = accumulators.get(key)
        if existing is not None:
            return existing
        context = _load_fit_context_direct(access)
        value = _FitSourceAccumulator(
            access=access,
            context=context,
            granted_binding=(
                freeze_granted_context_binding(access) if access.is_granted else None
            ),
        )
        accumulators[key] = value
        access_order.append(key)
        return value

    # Resolve every named source before provider construction. Literal text is
    # a separate caller-owned domain when authority-granted content participates.
    ordered_rows: list[FitProposition | _SelectedFitMemory] = list(request.propositions)

    def select_memory(memory_source: FitMemorySourceRequest) -> None:
        selected_context = source(memory_source.context_locator)
        direct_memories = tuple(
            item
            for item in selected_context.context.iter_items()
            if isinstance(item, Memory)
        )
        try:
            scope = resolve_memory_scope(
                direct_memories,
                memory_source.selector,
                label="direct Fit Memory",
            )
        except MemoryScopeError as error:
            raise FitSourceError(str(error)) from error
        memory = scope.actionable[0]
        # Fit is an n-ary compatibility operator over the argv operand frame.
        # Repeating one stored coordinate therefore repeats that proposition;
        # source digests still collapse safely for exact revalidation.
        selected_context.selected_memory_digests[memory.uid] = _memory_digest(memory)
        ordered_rows.append(_SelectedFitMemory("MEMORY", selected_context, memory))

    def select_context(locator: str) -> None:
        selected_context = source(locator)
        direct_memories = tuple(
            item
            for item in selected_context.context.iter_items()
            if isinstance(item, Memory)
        )
        if not direct_memories:
            raise FitSourceError(
                f"Fit Source Context {selected_context.access.access_name!r} "
                "contains no direct ordinary Memories."
            )
        for memory in direct_memories:
            ordered_rows.append(_SelectedFitMemory("CONTEXT", selected_context, memory))
        selected_context.whole_context_digest = context_record_digest(
            selected_context.context
        )

    used_aliases = {item.alias for item in (*request.background, *request.propositions)}
    literal_alias_index = 0

    def add_literal(content: str) -> None:
        nonlocal literal_alias_index
        if not content.strip():
            raise FitSourceError("A Fit text: operand must contain proposition text.")
        while True:
            literal_alias_index += 1
            alias = f"p{literal_alias_index}"
            if alias not in used_aliases:
                used_aliases.add(alias)
                break
        ordered_rows.append(FitProposition(alias, content, "PROPOSITION"))

    for operand in request.auto_operands:
        if operand.startswith("text:"):
            add_literal(operand.removeprefix("text:"))
            continue

        parsed = parse_auto_typed_context_memory_operand(operand)
        if isinstance(parsed, DirectMemoryLocator) and parsed.context_locator is not None:
            select_memory(
                FitMemorySourceRequest(
                    selector=parsed.memory_selector.casefold(),
                    context_locator=parsed.context_locator,
                )
            )
            continue
        resolved = try_resolve_context_access_or_local_memory(
            store,
            operand,
            current_name=current_name,
            candidates=context_candidates,
        )
        if isinstance(resolved, ResolvedExistingContextOperand):
            select_context(resolved.name)
            continue
        if isinstance(resolved, DirectMemoryTarget):
            select_memory(
                FitMemorySourceRequest(
                    selector=resolved.memory_uid,
                    context_locator=resolved.context_name,
                )
            )
            continue
        if is_relative_context_locator(operand):
            raise FitSourceError(
                f"Fit Context locator {operand!r} is outside the readable "
                "namespace."
            )
        if is_unresolved_uid_selector(operand):
            raise FitSourceError(
                f"No direct Fit Memory or readable Context has UID prefix "
                f"{operand!r}."
            )
        add_literal(operand)

    for memory_source in request.memory_sources:
        select_memory(memory_source)
    for locator in request.context_locators:
        select_context(locator)

    memory_alias_index = 0

    def next_alias() -> str:
        nonlocal memory_alias_index
        while True:
            memory_alias_index += 1
            alias = f"m{memory_alias_index}"
            if alias not in used_aliases:
                used_aliases.add(alias)
                return alias

    propositions: list[FitProposition] = []
    origins: list[FitInputOrigin] = []
    for row in ordered_rows:
        if isinstance(row, FitProposition):
            propositions.append(row)
            continue
        alias = next_alias()
        propositions.append(FitProposition(alias, row.memory.content, "MEMORY"))
        origins.append(
            FitInputOrigin(
                alias=alias,
                kind=row.kind,
                context_name=row.source.access.access_name,
                context_uid=row.source.context.uid,
                memory_uid=row.memory.uid,
            )
        )

    frozen = tuple(
        _FrozenFitSource(
            access=accumulator.access,
            context_uid=accumulator.context.uid,
            granted_binding=accumulator.granted_binding,
            whole_context_digest=accumulator.whole_context_digest,
            selected_memory_digests=tuple(accumulator.selected_memory_digests.items()),
        )
        for key in access_order
        for accumulator in (accumulators[key],)
    )
    result = run_proposition_fit(
        FitPropositionsRequest(
            propositions=tuple(propositions),
            background=request.background,
        ),
        provider_factory=provider_factory,
    )
    _revalidate_fit_sources(
        frozen,
        store=store,
    )
    return replace(result, input_origins=tuple(origins))


def execute_ground_fit(
    *,
    store: MemoryStore,
    ground_name: str,
    provider_factory: FitProviderFactory,
) -> FitReport:
    """Execute Fit over one physical Context-rooted Ground workspace."""

    return execute_ground_workspace_fit(
        store=store,
        ground_name=ground_name,
        provider_factory=provider_factory,
    )


def execute_and_save_ground_fit(
    *,
    store: MemoryStore,
    ground_name: str,
    provider_factory: FitProviderFactory,
) -> FitReport:
    """Run Fit and publish its immutable receipt at one freshness boundary."""

    report = execute_ground_fit(
        store=store,
        ground_name=ground_name,
        provider_factory=provider_factory,
    )
    FitStore(store).save(report)
    return report


def run_fit_with_store(
    request: FitRequest,
    *,
    store: MemoryStore,
    provider_factory: FitProviderFactory,
) -> FitResult:
    """Execute or reopen Fit behind one interface-independent runtime port."""

    if not isinstance(request, FitRequest):
        raise TypeError("Fit runtime requires a typed request.")
    if request.receipt_uid is None:
        return FitResult(
            execute_and_save_ground_fit(
                store=store,
                ground_name=request.ground_name,
                provider_factory=provider_factory,
            ),
            current=True,
        )

    fit_store = FitStore(store)
    report = fit_store.load(request.receipt_uid)
    if report.ground_name != request.ground_name:
        raise FitError("The Fit receipt belongs to a different Ground.")
    latest = fit_store.latest_for_workspace(
        load_ground_workspace(store, request.ground_name)
    )
    return FitResult(
        report,
        current=(
            latest is not None and latest.report.uid == report.uid and latest.current
        ),
    )
