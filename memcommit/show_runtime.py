"""MemoryStore composition for the read-only Show application."""

from __future__ import annotations

from dataclasses import replace

from memcommit.authority.access import (
    ContextAccess,
    GrantedReadStore,
    context_access_display_facts,
    project_grants_into_context,
    resolve_context_access,
)
from memcommit.context import Context, Memory, MemoryRef, QueryContextRef
from memcommit.context_locator import resolve_context_locator
from memcommit.profile_config import ProfileRegistry
from memcommit.profiles import (
    ProfileError,
    authority_grant_snapshot_lock,
    grants_for_attachment,
)
from memcommit.show_application import (
    ShowContextSnapshot,
    ShowEmbeddedContext,
    ShowInputError,
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
from memcommit.store import MemoryStore


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
                    source=explicit
                    or SourceDisplayFacts(form=SourceForm.MEMORY),
                )
            )
        elif isinstance(item, MemoryRef):
            items.append(
                ShowMemoryReference(
                    uid=item.uid,
                    target_context_uid=item.target_context_uid,
                    target_context_name=item.target_context_name,
                    target_memory_uid=item.target_memory_uid,
                    content=(item.target.content if item.target is not None else None),
                    source=explicit
                    or SourceDisplayFacts(
                        form=SourceForm.MEMORY_REF,
                        states=(
                            (SourceState.READ_ONLY,)
                            if item.is_resolved
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
                    source=explicit
                    or SourceDisplayFacts(form=SourceForm.QUERY_VIEW),
                )
            )
        elif isinstance(item, Context):
            row_facts = explicit or SourceDisplayFacts(reach=SourceReach.VIA_EMBED)
            items.append(
                ShowEmbeddedContext(
                    uid=item.uid,
                    name=item.name,
                    source=row_facts,
                    # Only an explicit attached-Grant annotation follows a
                    # selected projected row into its Context header. Ordinary
                    # embeds retain the established unannotated child header.
                    context=_snapshot_context(
                        item,
                        context_facts=explicit,
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
                raise ProfileError(
                    "No current context. Run 'mem init <name>' first."
                )
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

    def load_context(
        self,
        context_name: str | None,
        *,
        current_context_name: str | None,
    ) -> ShowContextSnapshot:
        if not self._allow_grants:
            return self._load(
                context_name,
                current_context_name=current_context_name,
                registry=None,
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
            return self._load(
                context_name,
                current_context_name=current_context_name,
                registry=live_registry,
            )


def execute_show(
    request: ShowRequest,
    *,
    store: MemoryStore,
    allow_grants: bool,
    registry: ProfileRegistry | None = None,
) -> ShowResult:
    """Capture current once and inspect through one explicit Store boundary."""

    current_context_name = store.current_context_name()
    return show(
        replace(request, current_context_name=current_context_name),
        port=MemoryStoreShowPort(
            store,
            allow_grants=allow_grants,
            registry=registry,
        ),
    )


__all__ = ["MemoryStoreShowPort", "execute_show"]
