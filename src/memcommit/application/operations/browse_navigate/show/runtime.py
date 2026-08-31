"""Operation-owned MemoryStore composition for read-only Show."""

from __future__ import annotations

from dataclasses import replace

from memcommit.application.capabilities.authority.context_access import (
    ContextAccess,
    GrantedReadStore,
    context_access_display_facts,
    project_grants_into_context,
    resolve_context_access,
    top_level_grants,
)
from memcommit.core.context import Context, Memory, MemoryRef, QueryContextRef
from memcommit.application.capabilities.context_snapshot import (
    ContextSnapshotRef,
)
from memcommit.application.capabilities.context_locator import resolve_context_locator
from memcommit.application.capabilities.local_target_lookup import (
    DirectItemAmbiguityError,
    DirectItemNotFoundError,
    resolve_local_direct_item_locator,
)
from memcommit.application.capabilities.memory_report_targeting import (
    ReadableMemoryTargetAmbiguityError,
    ReadableMemoryTargetNotFoundError,
    freeze_memory_report_readable_catalog,
    resolve_readable_memory_target,
)
from memcommit.core.context_targeting.uid_locator import is_memory_uid_prefix
from memcommit.core.context_targeting.model import (
    ContextScope,
    DirectMemoryLocator,
    ExistingContextOperand,
)
from memcommit.application.capabilities.authority.readable_contexts import (
    ReadableContextCatalog,
)
from memcommit.core.context_targeting.resolution import (
    expand_lexical_context_names,
    parse_auto_typed_context_memory_operand,
)
from memcommit.application.operations.profiles.profile.config import ProfileRegistry
from memcommit.application.operations.profiles.profile.model import (
    ProfileError,
    authority_grant_snapshot_lock,
    grants_for_attachment,
)
from memcommit.application.operations.browse_navigate.show.application import (
    ShowContextSnapshot,
    ShowDirectItemScopeError,
    ShowEmbeddedContext,
    ShowInputError,
    ShowItemNotFoundError,
    ShowMemory,
    ShowMemoryReference,
    ShowQueryView,
    ShowRequest,
    ShowResult,
    show,
)
from memcommit.source_projection.model import (
    SourceDisplayFacts,
    SourceForm,
    SourceReach,
    SourceState,
    context_access_facts,
)
from memcommit.persistence.store import MemoryStore


def _snapshot_context(
    context: Context,
    *,
    context_facts: SourceDisplayFacts | None = None,
    item_facts: dict[str, SourceDisplayFacts] | None = None,
) -> ShowContextSnapshot:
    items = []
    explicit_item_facts = item_facts or {}
    for item in context.iter_items():
        explicit = explicit_item_facts.get(item.uid)
        if isinstance(item, Memory):
            items.append(
                ShowMemory(
                    uid=item.uid,
                    content=item.content,
                    source=explicit or SourceDisplayFacts(form=SourceForm.MEMORY),
                )
            )
        elif isinstance(item, MemoryRef):
            form = (
                SourceForm.MEMORY_REFERENCE
                if item.is_snapshot
                else SourceForm.MEMORY_EMBED
            )
            items.append(
                ShowMemoryReference(
                    uid=item.uid,
                    target_context_uid=item.target_context_uid,
                    target_context_name=item.target_context_name,
                    target_memory_uid=item.target_memory_uid,
                    content=(item.target.content if item.target is not None else None),
                    source=explicit
                    or SourceDisplayFacts(
                        form=form,
                        states=(
                            (SourceState.READ_ONLY,)
                            if item.is_resolved
                            else (SourceState.OPAQUE,)
                            if item.is_granted
                            else (SourceState.DANGLING,)
                        ),
                    ),
                )
            )
        elif isinstance(item, QueryContextRef):
            items.append(
                ShowQueryView(
                    uid=item.uid,
                    name=item.name,
                    source=explicit or SourceDisplayFacts(form=SourceForm.QUERY_VIEW),
                )
            )
        elif isinstance(item, Context):
            row_facts = explicit or (
                SourceDisplayFacts(
                    form=SourceForm.CONTEXT_REFERENCE,
                    states=(SourceState.READ_ONLY,),
                )
                if isinstance(item, ContextSnapshotRef)
                else SourceDisplayFacts(reach=SourceReach.VIA_EMBED)
            )
            items.append(
                ShowEmbeddedContext(
                    uid=item.uid,
                    name=item.name,
                    source=row_facts,
                    # Only an explicit attached-Grant annotation follows a
                    # selected projected row into its Context header. Ordinary
                    # embeds retain the established unannotated child header;
                    # an immutable Context Reference keeps its typed form.
                    context=_snapshot_context(
                        item,
                        context_facts=(
                            row_facts
                            if isinstance(item, ContextSnapshotRef)
                            else explicit
                        ),
                    ),
                )
            )
    return ShowContextSnapshot(
        uid=context.uid,
        name=context.name,
        items=tuple(items),
        source=context_facts or SourceDisplayFacts(),
    )


class MemoryStoreShowPort:
    """Resolve READ authority and freeze only Show-visible direct content."""

    def __init__(
        self,
        store: MemoryStore,
        *,
        allow_grants: bool,
        registry: ProfileRegistry | None = None,
    ) -> None:
        self._store = store
        self._allow_grants = allow_grants
        self._registry = registry

    def _local_access(
        self,
        context_name: str | None,
        *,
        current_context_name: str | None,
    ) -> ContextAccess:
        operand = context_name
        if operand is None:
            if not current_context_name:
                raise ProfileError("No current context. Run 'mem init <name>' first.")
            operand = current_context_name
        canonical_name = resolve_context_locator(
            operand,
            current=current_context_name,
        )
        if not self._store.context_exists(canonical_name):
            raise FileNotFoundError(f"Context '{canonical_name}' not found.")
        return ContextAccess(
            store=self._store,
            context_name=canonical_name,
            display_name=canonical_name,
            attachment_name=None,
            permission="READ",
        )

    def _load(
        self,
        context_name: str | None,
        *,
        current_context_name: str | None,
        registry: ProfileRegistry | None,
    ) -> ShowContextSnapshot:
        try:
            access = (
                resolve_context_access(
                    self._store,
                    context_name,
                    current_name=current_context_name,
                    required_permission="READ",
                    registry=registry,
                )
                if self._allow_grants
                else self._local_access(
                    context_name,
                    current_context_name=current_context_name,
                )
            )
        except ValueError as error:
            raise ShowInputError(str(error)) from error
        item_facts: dict[str, SourceDisplayFacts] = {}
        if access.is_granted:
            if registry is None:
                raise RuntimeError("Granted Show requires a Profile snapshot.")
            context = GrantedReadStore(access, registry=registry).load(
                access.display_name
            )
        else:
            context = access.store.load(access.context_name)
            if self._allow_grants and registry is not None:
                grants = grants_for_attachment(
                    attachment_name=access.context_name,
                    registry=registry,
                )
                if grants:
                    context = project_grants_into_context(context, grants)
                    for grant in grants:
                        if "READ" in grant.permissions:
                            item_facts[grant.resource_uid] = context_access_facts(
                                granted=True,
                                permission="READ",
                                permissions=grant.permissions,
                            )
                        elif "QUERY" in grant.permissions:
                            existing = context.memories.get(grant.uid)
                            if existing is None:
                                context.add(
                                    QueryContextRef(
                                        uid=grant.uid,
                                        name=grant.public_name,
                                        target_source_uid=grant.resource_uid,
                                        provider="authority-grant",
                                    )
                                )
                            elif not (
                                isinstance(existing, QueryContextRef)
                                and existing.name == grant.public_name
                            ):
                                raise ProfileError(
                                    "A query-only grant identity collides with "
                                    "an existing direct item."
                                )
                            item_facts[grant.uid] = context_access_facts(
                                granted=True,
                                permission="QUERY",
                                permissions=grant.permissions,
                                form=SourceForm.QUERY_VIEW,
                            )
        context_facts = (
            context_access_display_facts(
                access,
                states=(SourceState.READ_ONLY,),
            )
            if access.is_granted
            else None
        )
        return _snapshot_context(
            context,
            context_facts=context_facts,
            item_facts=item_facts,
        )

    def _recursive_contexts(
        self,
        context_name: str | None,
        *,
        current_context_name: str | None,
        include_descendants: bool,
        follow_embeds: bool,
        registry: ProfileRegistry | None,
    ) -> tuple[ShowContextSnapshot, ...]:
        try:
            root_access = (
                resolve_context_access(
                    self._store,
                    context_name,
                    current_name=current_context_name,
                    required_permission="READ",
                    registry=registry,
                )
                if self._allow_grants
                else self._local_access(
                    context_name,
                    current_context_name=current_context_name,
                )
            )
        except ValueError as error:
            raise ShowInputError(str(error)) from error

        catalog = (
            ReadableContextCatalog(
                self._store,
                root_access,
                registry=registry,
                include_query_routes=True,
            )
            if self._allow_grants
            else None
        )
        catalog_names = tuple(
            sorted(
                (
                    catalog.list_context_names()
                    if catalog is not None
                    else self._store.list_context_names()
                ),
                key=str.casefold,
            )
        )
        scope = ContextScope.create(
            (root_access.display_name,),
            include_descendants=include_descendants,
        )
        expanded_names = expand_lexical_context_names(scope, catalog_names)
        names = (
            root_access.display_name,
            *(name for name in expanded_names if name != root_access.display_name),
        )

        contexts: list[ShowContextSnapshot] = []
        seen_live_uids: set[str] = set()
        seen_snapshot_contexts: set[tuple[str, str]] = set()

        def access_for(public_name: str) -> ContextAccess:
            if catalog is not None:
                return catalog.access_for(public_name)
            return ContextAccess(
                store=self._store,
                context_name=public_name,
                display_name=public_name,
                attachment_name=None,
                permission="READ",
            )

        def load_public(
            public_name: str,
            *,
            access: ContextAccess,
        ) -> tuple[Context, dict[str, SourceDisplayFacts]]:
            context = (
                catalog.load(public_name)
                if catalog is not None
                else self._store.load(public_name)
            )
            item_facts: dict[str, SourceDisplayFacts] = {}
            if not access.is_granted and self._allow_grants and registry is not None:
                grants = grants_for_attachment(
                    attachment_name=access.context_name,
                    registry=registry,
                )
                if grants:
                    for grant in top_level_grants(grants):
                        if "READ" in grant.permissions:
                            item_facts[grant.resource_uid] = context_access_facts(
                                granted=True,
                                permission="READ",
                                permissions=grant.permissions,
                            )
                        elif "QUERY" in grant.permissions:
                            existing = context.memories.get(grant.uid)
                            if existing is None:
                                context.add(
                                    QueryContextRef(
                                        uid=grant.uid,
                                        name=grant.public_name,
                                        target_source_uid=grant.resource_uid,
                                        provider="authority-grant",
                                    )
                                )
                            elif not (
                                isinstance(existing, QueryContextRef)
                                and existing.name == grant.public_name
                            ):
                                raise ProfileError(
                                    "A query-only grant identity collides with "
                                    "an existing direct item."
                                )
                            item_facts[grant.uid] = context_access_facts(
                                granted=True,
                                permission="QUERY",
                                permissions=grant.permissions,
                                form=SourceForm.QUERY_VIEW,
                            )
            return context, item_facts

        def visit_snapshot(
            snapshot: ContextSnapshotRef,
            *,
            reach: SourceReach,
        ) -> None:
            package_records = snapshot.snapshot_package["contexts"]
            assert isinstance(package_records, list)
            retained_uids = frozenset(
                record["uid"]
                for record in package_records
                if isinstance(record, dict) and isinstance(record.get("uid"), str)
            )

            def visit_retained(
                context: Context,
                *,
                retained_reach: SourceReach,
                root: bool = False,
            ) -> None:
                key = (snapshot.uid, context.uid)
                if key in seen_snapshot_contexts:
                    return
                seen_snapshot_contexts.add(key)
                contexts.append(
                    _snapshot_context(
                        context,
                        context_facts=SourceDisplayFacts(
                            reach=retained_reach,
                            form=(
                                SourceForm.CONTEXT_REFERENCE
                                if root
                                else SourceForm.CONTEXT
                            ),
                            states=(SourceState.READ_ONLY,),
                        ),
                    )
                )
                if not follow_embeds:
                    return
                for item in context.iter_items():
                    if isinstance(item, ContextSnapshotRef):
                        visit_snapshot(item, reach=SourceReach.VIA_EMBED)
                    elif isinstance(item, Context) and item.uid in retained_uids:
                        visit_retained(
                            item,
                            retained_reach=(
                                SourceReach.DESCENDANT
                                if getattr(item, "_snapshot_relation", None)
                                == "DESCENDANT"
                                else SourceReach.VIA_EMBED
                            ),
                        )

            visit_retained(snapshot, retained_reach=reach, root=True)

        def visit_public(
            public_name: str,
            *,
            reach: SourceReach,
            expected_uid: str | None = None,
        ) -> None:
            access = access_for(public_name)
            context, item_facts = load_public(
                public_name,
                access=access,
            )
            if expected_uid is not None and context.uid != expected_uid:
                raise RuntimeError("An embedded Context identity changed during Show.")
            if context.uid in seen_live_uids:
                return
            seen_live_uids.add(context.uid)
            contexts.append(
                _snapshot_context(
                    context,
                    context_facts=context_access_display_facts(
                        access,
                        reach=reach,
                        states=(SourceState.READ_ONLY,) if access.is_granted else (),
                    ),
                    item_facts=item_facts,
                )
            )
            if not follow_embeds:
                return
            for item in context.iter_items():
                if not isinstance(item, Context):
                    continue
                if isinstance(item, ContextSnapshotRef):
                    visit_snapshot(item, reach=SourceReach.VIA_EMBED)
                    continue
                if item.name not in catalog_names:
                    continue
                visit_public(
                    item.name,
                    reach=SourceReach.VIA_EMBED,
                    expected_uid=item.uid,
                )

        for index, name in enumerate(names):
            visit_public(
                name,
                reach=(SourceReach.DIRECT if index == 0 else SourceReach.DESCENDANT),
            )
        return tuple(contexts)

    def load_contexts(
        self,
        context_name: str | None,
        *,
        current_context_name: str | None,
        include_descendants: bool,
        follow_embeds: bool,
    ) -> tuple[ShowContextSnapshot, ...]:
        if not self._allow_grants:
            return (
                self._recursive_contexts(
                    context_name,
                    current_context_name=current_context_name,
                    include_descendants=include_descendants,
                    follow_embeds=follow_embeds,
                    registry=None,
                )
                if include_descendants or follow_embeds
                else (
                    self._load(
                        context_name,
                        current_context_name=current_context_name,
                        registry=None,
                    ),
                )
            )
        # Grant changes and Profile switching share this lock. The complete
        # snapshot therefore belongs to one authorization generation.
        with authority_grant_snapshot_lock() as live_registry:
            if (
                self._registry is not None
                and self._registry.active.uid != live_registry.active.uid
            ):
                raise RuntimeError(
                    "The active Profile changed before Show could freeze access."
                )
            return (
                self._recursive_contexts(
                    context_name,
                    current_context_name=current_context_name,
                    include_descendants=include_descendants,
                    follow_embeds=follow_embeds,
                    registry=live_registry,
                )
                if include_descendants or follow_embeds
                else (
                    self._load(
                        context_name,
                        current_context_name=current_context_name,
                        registry=live_registry,
                    ),
                )
            )


def execute_show(
    request: ShowRequest,
    *,
    store: MemoryStore,
    allow_grants: bool,
    registry: ProfileRegistry | None = None,
) -> ShowResult:
    """Capture current once and inspect through one explicit Store boundary."""

    current_context_name = (
        request.current_context_name
        if request.current_context_name is not None
        else store.current_context_name()
    )
    return show(
        replace(request, current_context_name=current_context_name),
        port=MemoryStoreShowPort(
            store,
            allow_grants=allow_grants,
            registry=registry,
        ),
    )


def execute_show_cli_operand(
    operand: str | None,
    *,
    context_name: str | None,
    include_descendants: bool,
    follow_embeds: bool,
    store: MemoryStore,
    allow_grants: bool,
    registry: ProfileRegistry | None = None,
) -> ShowResult:
    """Resolve Show's positional Context/direct-item grammar once.

    Explicit ``--context`` retains its compatibility meaning: with an operand
    it forces direct-item selection inside that owner, and without one it names
    the Context itself.  A bare UUID-shaped operand uses the shared strict local
    direct-item catalog; a qualified operand names its owner explicitly.  A
    short UUID prefix first preserves an exact Context of the same name, then
    uses that catalog so it agrees with direct-Memory commands when the prefix
    is unique. Other text preserves Show's established current direct-name
    selection before falling back to an existing Context locator.
    """

    current_context_name = store.current_context_name()

    def execute(request: ShowRequest) -> ShowResult:
        return execute_show(
            replace(request, current_context_name=current_context_name),
            store=store,
            allow_grants=allow_grants,
            registry=registry,
        )

    def execute_bare_direct_item(selector: str) -> ShowResult:
        if include_descendants or follow_embeds:
            raise ShowDirectItemScopeError(
                "--recursive/-r cannot be combined with a direct-item selector."
            )
        if allow_grants:
            readable_catalog = freeze_memory_report_readable_catalog(
                store,
                current=current_context_name,
                registry=registry,
            )
            if readable_catalog is not None:
                try:
                    readable_target = resolve_readable_memory_target(
                        readable_catalog,
                        selector,
                    )
                except ReadableMemoryTargetNotFoundError:
                    pass
                except ReadableMemoryTargetAmbiguityError as error:
                    raise ShowInputError(
                        f"Ambiguous selector {selector!r}: {error}"
                    ) from error
                else:
                    return execute(
                        ShowRequest(
                            context_name=readable_target.context_name,
                            selector=readable_target.uid,
                        )
                    )
        try:
            target = resolve_local_direct_item_locator(
                store,
                selector,
                current=current_context_name,
            )
        except DirectItemNotFoundError as local_error:
            # A current attached Grant may expose a row outside the enumerable
            # ordinary-local owner catalog. Preserve the established exact
            # current-row route without broadening global Grant enumeration.
            if current_context_name is None:
                raise local_error
            try:
                return execute(ShowRequest(selector=selector))
            except ShowItemNotFoundError:
                raise local_error
        return execute(
            ShowRequest(
                context_name=target.context_name,
                selector=target.item_uid,
            )
        )

    if operand is None or context_name is not None:
        return execute(
            ShowRequest(
                context_name=context_name,
                selector=operand,
                include_descendants=include_descendants,
                follow_embeds=follow_embeds,
            )
        )

    parsed = parse_auto_typed_context_memory_operand(operand)
    if isinstance(parsed, DirectMemoryLocator):
        if include_descendants or follow_embeds:
            raise ShowDirectItemScopeError(
                "--recursive/-r cannot be combined with a direct-item selector."
            )
        if parsed.context_locator is not None:
            return execute(
                ShowRequest(
                    context_name=parsed.context_locator,
                    selector=parsed.memory_selector,
                )
            )
        return execute_bare_direct_item(parsed.memory_selector)

    assert isinstance(parsed, ExistingContextOperand)
    if is_memory_uid_prefix(operand):
        # A short hexadecimal token can still be a valid Context name. Exact
        # Context identity wins; only a missing Context authorizes the same
        # unique global prefix lookup used by direct-Memory operations.
        try:
            return execute(
                ShowRequest(
                    context_name=parsed.locator,
                    include_descendants=include_descendants,
                    follow_embeds=follow_embeds,
                )
            )
        except FileNotFoundError:
            pass
        try:
            return execute_bare_direct_item(operand)
        except DirectItemAmbiguityError as error:
            # Retain Show's established public error class while exposing the
            # complete owner coordinates supplied by the shared catalog.
            raise ShowInputError(f"Ambiguous selector {operand!r}: {error}") from error
        except DirectItemNotFoundError as error:
            raise ShowInputError(
                f"No Context or direct item matches {operand!r}."
            ) from error

    if current_context_name is not None:
        try:
            direct_item = execute(ShowRequest(selector=operand))
        except ShowItemNotFoundError:
            pass
        else:
            if include_descendants or follow_embeds:
                raise ShowDirectItemScopeError(
                    "--recursive/-r cannot be combined with a direct-item selector."
                )
            return direct_item
    try:
        return execute(
            ShowRequest(
                context_name=parsed.locator,
                include_descendants=include_descendants,
                follow_embeds=follow_embeds,
            )
        )
    except FileNotFoundError as error:
        raise ShowInputError(
            f"No Context or direct item matches {operand!r}."
        ) from error


__all__ = ["MemoryStoreShowPort", "execute_show", "execute_show_cli_operand"]
