"""MemoryStore adapter for the operation-owned Fit application."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import hashlib
from typing import Iterable, Protocol

from memcommit.authority.access import (
    ContextAccess,
    GrantedReadStore,
    freeze_granted_context_binding,
    revalidate_granted_context_binding,
    resolve_context_access,
)
from memcommit.context import Context, Memory
from memcommit.context_locator import (
    is_relative_context_locator,
    resolve_context_locator,
)
from memcommit.context_targeting.memory_focus import (
    MemoryFocusError,
    resolve_memory_focus,
)
from memcommit.context_targeting.loading import (
    try_resolve_short_local_direct_memory_locator,
)
from memcommit.context_targeting.model import (
    DirectMemoryLocator,
    ExistingContextOperand,
)
from memcommit.context_targeting.resolution import (
    parse_auto_typed_context_memory_operand,
)
from memcommit.context_targeting.readable_catalog import (
    freeze_profile_readable_context_catalog,
)
from memcommit.derived_policy import authorize_combination
from memcommit.operations.fit.ground_report import (
    FIT_RULESET_VERSION,
    FIT_SCHEMA_VERSION,
    FitError,
    FitExample,
    FitProvider,
    FitReport,
    FitRule,
    fit_ground_examples,
)
from memcommit.operations.fit.coherence import (
    FitCoherenceError,
    FrozenGroundCoherence,
    execute_ground_coherence,
    freeze_ground_coherence,
    prepare_ground_coherence,
)
from memcommit.operations.fit.application import (
    FitInputOrigin,
    FitInputOriginKind,
    FitMemorySourceRequest,
    FitPropositionsRequest,
    FitPropositionsResult,
    FitRequest,
    FitResult,
    FitStoredSourcesRequest,
)
from memcommit.operations.fit.judgment import (
    FitAnalysis,
    FitProposition,
    FitQuestion,
    execute_fit_judgments,
    prepare_fit_judgments,
)
from memcommit.operations.ground.model import (
    GROUND_PROPOSITION_SCHEMA_VERSION,
    GroundItem,
    GroundSession,
    is_bound_ground_schema,
)
from memcommit.operations.ground.workspace_fit import execute_ground_workspace_fit
from memcommit.operations.ground.workspace_runtime import (
    ground_workspace_exists,
    load_ground_workspace,
)
from memcommit.operations.fit.store import FitStore
from memcommit.profiles import authority_grant_snapshot_lock
from memcommit.store import (
    MemoryStore,
    context_record_digest,
    ground_session_record_digest,
)
from memcommit.operations.update.model import GrantedUpdateTarget


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
            access.display_name,
        )
    return ("LOCAL", str(access.store.store_dir.resolve()), access.context_name)


def _load_fit_context_direct(
    access: ContextAccess,
    *,
    registry=None,
) -> Context:
    if access.is_granted:
        return GrantedReadStore(access, registry=registry).load_direct(
            access.display_name
        )
    return access.store.load_direct(access.context_name)


def _memory_digest(memory: Memory) -> str:
    return hashlib.sha256(memory.content.encode("utf-8")).hexdigest()


def _literal_combination_access(store: MemoryStore) -> ContextAccess:
    """Represent caller-supplied text as a separate local combination domain."""

    return ContextAccess(
        store=store,
        context_name="<fit-literal-propositions>",
        display_name="<fit-literal-propositions>",
        attachment_name=None,
        permission="READ",
    )


def _authorize_fit_combination(
    accesses: tuple[ContextAccess, ...],
    *,
    store: MemoryStore,
    has_literals: bool,
) -> None:
    values = (
        (*accesses, _literal_combination_access(store))
        if has_literals
        else accesses
    )
    authorize_combination(values)


def _revalidate_fit_sources(
    frozen: tuple[_FrozenFitSource, ...],
    *,
    store: MemoryStore,
    has_literals: bool,
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
                    f"Fit Source Context {access.display_name!r} disappeared "
                    "during judgment."
                ) from error
            current_accesses.append(access)
            current_contexts.append(context)

        _authorize_fit_combination(
            tuple(current_accesses),
            store=store,
            has_literals=has_literals,
        )
        for source, context in zip(frozen, current_contexts, strict=True):
            if context.uid != source.context_uid:
                raise FitSourceError(
                    f"Fit Source Context {source.access.display_name!r} changed "
                    "identity during judgment."
                )
            if source.whole_context_digest is not None and (
                context_record_digest(context) != source.whole_context_digest
            ):
                raise FitSourceError(
                    f"Fit Source Context {source.access.display_name!r} changed "
                    "during judgment."
                )
            for memory_uid, digest in source.selected_memory_digests:
                memory = context.memories.get(memory_uid)
                if not isinstance(memory, Memory) or _memory_digest(memory) != digest:
                    raise FitSourceError(
                        f"Fit Source Memory {memory_uid[:8]!r} in "
                        f"{source.access.display_name!r} changed during judgment."
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
    readable_names: frozenset[str] | None = None

    def all_readable_names() -> frozenset[str]:
        """Freeze the Profile-wide READ catalog without opening Context bodies."""

        nonlocal readable_names
        if readable_names is not None:
            return readable_names
        local_names = tuple(store.list_context_names())
        if not local_names:
            readable_names = frozenset()
            return readable_names
        anchor_name = local_names[0]
        anchor = ContextAccess(
            store=store,
            context_name=anchor_name,
            display_name=anchor_name,
            attachment_name=None,
            permission="READ",
        )
        catalog = freeze_profile_readable_context_catalog(
            store,
            anchor,
            include_query_routes=False,
        )
        readable_names = frozenset(catalog.list_context_names())
        return readable_names

    def source(locator: str | None) -> _FitSourceAccumulator:
        access = resolve_context_access(
            store,
            locator,
            current_name=current_name,
            required_permission="READ",
        )
        key = _fit_access_key(access)
        existing = accumulators.get(key)
        if existing is not None:
            return existing
        context = _load_fit_context_direct(access)
        value = _FitSourceAccumulator(
            access=access,
            context=context,
            granted_binding=(
                freeze_granted_context_binding(access)
                if access.is_granted
                else None
            ),
        )
        accumulators[key] = value
        access_order.append(key)
        return value

    # Resolve every named source before provider construction. Literal text is
    # a separate caller-owned domain when authority-granted content participates.
    ordered_rows: list[FitProposition | _SelectedFitMemory] = list(
        request.propositions
    )

    def select_memory(memory_source: FitMemorySourceRequest) -> None:
        selected_context = source(memory_source.context_locator)
        direct_memories = tuple(
            item
            for item in selected_context.context.iter_items()
            if isinstance(item, Memory)
        )
        try:
            focus = resolve_memory_focus(
                direct_memories,
                memory_source.selector,
                label="direct Fit Memory",
            )
        except MemoryFocusError as error:
            raise FitSourceError(str(error)) from error
        memory = focus.actionable[0]
        # Fit is an n-ary compatibility operator over the argv operand frame.
        # Repeating one stored coordinate therefore repeats that proposition;
        # source digests still collapse safely for exact revalidation.
        selected_context.selected_memory_digests[memory.uid] = _memory_digest(memory)
        ordered_rows.append(
            _SelectedFitMemory("MEMORY", selected_context, memory)
        )

    def select_context(locator: str) -> None:
        selected_context = source(locator)
        direct_memories = tuple(
            item
            for item in selected_context.context.iter_items()
            if isinstance(item, Memory)
        )
        if not direct_memories:
            raise FitSourceError(
                f"Fit Source Context {selected_context.access.display_name!r} "
                "contains no direct ordinary Memories."
            )
        for memory in direct_memories:
            ordered_rows.append(
                _SelectedFitMemory("CONTEXT", selected_context, memory)
            )
        selected_context.whole_context_digest = context_record_digest(
            selected_context.context
        )

    used_aliases = {
        item.alias for item in (*request.background, *request.propositions)
    }
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
        if isinstance(parsed, DirectMemoryLocator):
            select_memory(
                FitMemorySourceRequest(
                    selector=parsed.memory_selector.casefold(),
                    context_locator=parsed.context_locator,
                )
            )
            continue
        assert isinstance(parsed, ExistingContextOperand)
        canonical_name = resolve_context_locator(
            parsed.locator,
            current=current_name,
        )
        if canonical_name in all_readable_names():
            select_context(parsed.locator)
            continue
        short_target = try_resolve_short_local_direct_memory_locator(
            store,
            parsed.locator,
            current=current_name,
        )
        if short_target is not None:
            select_memory(
                FitMemorySourceRequest(
                    selector=short_target.memory_uid,
                    context_locator=short_target.context_name,
                )
            )
            continue
        if is_relative_context_locator(parsed.locator):
            raise FitSourceError(
                f"Fit Context locator {parsed.locator!r} is outside the readable "
                "namespace."
            )
        add_literal(parsed.locator)

    for memory_source in request.memory_sources:
        select_memory(memory_source)
    for locator in request.context_locators:
        select_context(locator)

    accesses = tuple(accumulators[key].access for key in access_order)
    has_literals = bool(
        request.background
        or any(isinstance(row, FitProposition) for row in ordered_rows)
    )
    _authorize_fit_combination(
        accesses,
        store=store,
        has_literals=has_literals,
    )

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
                context_name=row.source.access.display_name,
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
        has_literals=has_literals,
    )
    return replace(result, input_origins=tuple(origins))


@dataclass(frozen=True)
class FrozenGroundFit:
    ground_uid: str
    ground_name: str
    ground_revision: int
    ground_digest: str
    rules: tuple[FitRule, ...]
    examples: tuple[FitExample, ...]
    coherence: FrozenGroundCoherence | None = None


def freeze_ground_fit(
    session: GroundSession,
    *,
    contexts: Iterable[Context] = (),
) -> FrozenGroundFit:
    """Project one immutable Ground revision into the public Fit contract.

    Version 2 preserves its exact-output replay contract. Version 3 evaluates
    each native Example proposition and treats optional I/O, evidence, and
    placement metadata as non-authoritative projections. An unlinked version-3
    Example applies to the complete active Rule set; explicit links narrow the
    judgment to exactly those Rules.
    """

    if not is_bound_ground_schema(session.schema_version):
        raise FitError("Fit currently requires a bound Ground workbench.")
    active_rules = tuple(
        item
        for item in session.items
        if item.kind == "RULE" and item.status in {"PROPOSED", "ACCEPTED"}
    )
    examples = tuple(
        item
        for item in session.items
        if item.kind == "CASE"
        and item.status in {"PROPOSED", "ACCEPTED"}
        and item.disposition == "INCLUDE"
        and (
            bool(item.proposition.strip())
            if session.schema_version == GROUND_PROPOSITION_SCHEMA_VERSION
            else bool(item.expected.strip())
        )
    )
    if not active_rules:
        raise FitError("The Ground contains no active Rules to fit.")
    if not examples:
        raise FitError("The Ground contains no active Examples to fit.")
    rules = tuple(
        FitRule(item.uid, f"r{index}", item.content)
        for index, item in enumerate(active_rules, 1)
    )
    rule_uids = tuple(rule.uid for rule in rules)
    active_rule_uids = set(rule_uids)

    def example_rule_uids(item: GroundItem) -> tuple[str, ...]:
        if session.schema_version != GROUND_PROPOSITION_SCHEMA_VERSION:
            # Exact output can depend on composed Rules beyond the Rule that
            # originally motivated this legacy Example.
            return rule_uids
        if any(uid not in active_rule_uids for uid in item.related_uids):
            raise FitError("A Ground Example links a Rule that is not active.")
        linked = tuple(item.related_uids)
        if linked:
            return linked
        return rule_uids

    proposition_schema = (
        session.schema_version == GROUND_PROPOSITION_SCHEMA_VERSION
    )
    frozen = FrozenGroundFit(
        ground_uid=session.uid,
        ground_name=session.contract_name,
        ground_revision=session.revision,
        ground_digest=ground_session_record_digest(session),
        rules=rules,
        examples=tuple(
            FitExample(
                uid=item.uid,
                alias=f"e{index}",
                statement=item.proposition or f"{item.content} -> {item.expected}",
                projection=(
                    "PROPOSITION" if proposition_schema else "EXACT_OUTPUT"
                ),
                rule_uids=example_rule_uids(item),
                input_text=None if proposition_schema else item.content,
                expected_output=None if proposition_schema else item.expected,
            )
            for index, item in enumerate(examples, 1)
        ),
    )
    if contexts:
        try:
            return replace(
                frozen,
                coherence=freeze_ground_coherence(session, tuple(contexts)),
            )
        except FitCoherenceError as error:
            raise FitError(str(error)) from error
    return frozen


def _load_bound_fit_contexts(
    store: MemoryStore,
    session: GroundSession,
) -> tuple[Context, ...]:
    """Load exact direct bound frames without resolving nested references."""

    contexts = []
    for frame in session.frames:
        try:
            contexts.append(store.load_direct(frame.context_name))
        except FileNotFoundError as error:
            raise FitError(
                f"Bound Context '{frame.context_name}' was not found."
            ) from error
    return tuple(contexts)


def execute_ground_fit(
    *,
    store: MemoryStore,
    ground_name: str,
    provider_factory: FitProviderFactory,
) -> FitReport:
    """Execute Fit over one exact Ground revision and detect a concurrent edit."""

    if ground_workspace_exists(store, ground_name):
        return execute_ground_workspace_fit(
            store=store,
            ground_name=ground_name,
            provider_factory=provider_factory,
        )

    session = store.load_ground_session(ground_name)
    if session is None:
        raise FitError(f"Ground '{ground_name}' was not found.")
    frozen = freeze_ground_fit(
        session,
        contexts=_load_bound_fit_contexts(store, session),
    )
    if frozen.coherence is None:
        raise FitError("Ground Fit did not freeze its coherence frame.")
    provider = provider_factory()
    report = fit_ground_examples(
        ground_uid=frozen.ground_uid,
        ground_name=frozen.ground_name,
        ground_revision=frozen.ground_revision,
        ground_digest=frozen.ground_digest,
        rules=frozen.rules,
        examples=frozen.examples,
        provider=provider,
    )
    try:
        coherence = execute_ground_coherence(
            prepare_ground_coherence(frozen.coherence),
            provider=provider,
        )
    except FitCoherenceError as error:
        raise FitError(str(error)) from error
    if (
        report.provider_identity is not None
        and coherence.provider_identity is not None
        and report.provider_identity != coherence.provider_identity
    ):
        raise FitError("Fit provider identity changed between complete checks.")
    report = replace(
        report,
        coherence=coherence,
        provider_identity=(
            coherence.provider_identity or report.provider_identity
        ),
        schema_version=FIT_SCHEMA_VERSION,
        ruleset_version=FIT_RULESET_VERSION,
    )
    current = store.load_ground_session(ground_name)
    if current is None or ground_session_record_digest(current) != frozen.ground_digest:
        raise FitError("The Ground changed during Fit; no report was published.")
    # Context content is a first-class Fit input. Re-freezing locally after
    # the provider turn prevents a stale binding from publishing a report.
    freeze_ground_fit(
        current,
        contexts=_load_bound_fit_contexts(store, current),
    )
    return report


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
    if ground_workspace_exists(store, request.ground_name):
        latest = fit_store.latest_for_workspace(
            load_ground_workspace(store, request.ground_name)
        )
        return FitResult(
            report,
            current=(
                latest is not None
                and latest.report.uid == report.uid
                and latest.current
            ),
        )
    session = store.load_ground_session(request.ground_name)
    if session is None:
        raise FitError(f"Ground '{request.ground_name}' was not found.")
    latest = fit_store.latest_for_ground(session)
    return FitResult(
        report,
        current=(
            latest is not None
            and latest.report.uid == report.uid
            and latest.current
        ),
    )
