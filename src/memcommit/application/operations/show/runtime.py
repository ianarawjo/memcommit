"""Operation-owned MemoryStore composition for read-only Show."""

from __future__ import annotations


from dataclasses import replace

from memcommit.application.context_access.access import resolve_context_access
from memcommit.application.context_access.operand_resolution import (
    resolve_existing_context_access,
)
from memcommit.application.capabilities.operand_resolution import (
    ContextOperandNotFoundError,
)
from memcommit.models.context import Context
from memcommit.models.memory import Memory
from memcommit.application.capabilities.local_target_lookup import (
    DirectItemAmbiguityError,
    DirectItemNotFoundError,
    resolve_local_direct_item_locator,
)
from memcommit.core.context_targeting.uid_locator import is_memory_uid_prefix
from memcommit.core.context_targeting.model import DirectMemoryLocator
from memcommit.core.context_targeting.resolution import (
    expand_lexical_context_names,
    parse_auto_typed_context_memory_operand,
)
from memcommit.application.operations.show.application import (
    ShowContextSnapshot,
    ShowDirectItemScopeError,
    ShowInputError,
    ShowItemNotFoundError,
    ShowMemory,
    ShowRequest,
    ShowResult,
    show,
)
from memcommit.source_projection.model import (
    SourceDisplayFacts,
    SourceForm,
    SourceReach,
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
    for item in context.iter_memories():
        explicit = explicit_item_facts.get(item.uid)
        if isinstance(item, Memory):
            items.append(
                ShowMemory(
                    uid=item.uid,
                    content=item.content,
                    source=explicit or SourceDisplayFacts(form=SourceForm.MEMORY),
                )
            )
    return ShowContextSnapshot(
        uid=context.uid,
        name=context.name,
        items=tuple(items),
        source=context_facts or SourceDisplayFacts(),
    )


class MemoryStoreShowPort:
    """Load selected independent local Context owners for read-only inspection."""

    def __init__(self, store: MemoryStore, *, loaded_context: Context | None = None):
        self._store = store
        self._loaded_context = loaded_context

    def load_contexts(self, context_name, *, current_context_name, include_descendants):
        if self._loaded_context is not None and context_name == self._loaded_context.name:
            selected = resolve_context_access(
                self._store, context_name, current_name=current_context_name
            )
        else:
            selected = resolve_existing_context_access(
                self._store,
                context_name,
                current_name=current_context_name,
            ).value
        names = expand_lexical_context_names(
            (selected.context_name,),
            self._store.list_context_names(),
            include_descendants=include_descendants,
        )
        return tuple(
            _snapshot_context(
                self._loaded_context
                if self._loaded_context is not None and self._loaded_context.name == name
                else self._store.load_direct(name),
                context_facts=SourceDisplayFacts(
                    reach=SourceReach.DIRECT
                    if name == selected.context_name
                    else SourceReach.DESCENDANT
                ),
            )
            for name in names
        )


def execute_show(
    request: ShowRequest,
    *,
    store: MemoryStore,
    loaded_context: Context | None = None,
) -> ShowResult:
    """Capture current once and inspect through one explicit Store boundary."""

    current_context_name = (
        request.current_context_name
        if request.current_context_name is not None
        else store.current_context_name()
    )
    return show(
        replace(request, current_context_name=current_context_name),
        port=MemoryStoreShowPort(store, loaded_context=loaded_context),
    )


def execute_show_cli_operand(
    operand: str | None,
    *,
    context_name: str | None,
    include_descendants: bool,
    store: MemoryStore,
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

    def execute(request: ShowRequest, *, loaded_context: Context | None = None) -> ShowResult:
        return execute_show(
            replace(request, current_context_name=current_context_name),
            store=store,
            loaded_context=loaded_context,
        )

    def execute_bare_direct_item(selector: str) -> ShowResult:
        if include_descendants:
            raise ShowDirectItemScopeError(
                "--recursive/-r cannot be combined with a direct-item selector."
            )
        try:
            context, memory = resolve_local_direct_item_locator(
                store,
                selector,
                current=current_context_name,
            )
        except DirectItemNotFoundError as local_error:
            if current_context_name is None:
                raise local_error
            try:
                return execute(ShowRequest(selector=selector))
            except ShowItemNotFoundError:
                raise local_error
        return execute(
            ShowRequest(
                context_name=context.name,
                selector=memory.uid,
            ),
            loaded_context=context,
        )

    if context_name is not None:
        resolved_context = resolve_existing_context_access(
            store,
            context_name,
            current_name=current_context_name,
        )
        return execute(
            ShowRequest(
                context_name=resolved_context.name,
                selector=operand,
                include_descendants=include_descendants,
            )
        )
    if operand is None:
        return execute(
            ShowRequest(
                include_descendants=include_descendants,
            )
        )

    parsed = parse_auto_typed_context_memory_operand(operand)
    if isinstance(parsed, DirectMemoryLocator):
        if include_descendants:
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
        try:
            context_target = resolve_existing_context_access(
                store,
                operand,
                current_name=current_context_name,
            )
        except ContextOperandNotFoundError:
            pass
        else:
            # A bare UID must be compared with the other kinds admitted by
            # Show before the Context route can win. Qualified CONTEXT:UID is
            # the explicit disambiguator when a direct row shares the prefix.
            direct_item_match = False
            try:
                resolve_local_direct_item_locator(
                    store,
                    operand,
                    current=current_context_name,
                )
            except DirectItemNotFoundError:
                pass
            else:
                direct_item_match = True
            if direct_item_match:
                raise ShowInputError(
                    f"UID {operand!r} matches both a readable Context and a "
                    "direct item; pass the exact Context name or CONTEXT:UID."
                )
            return execute(
                ShowRequest(
                    context_name=context_target.name,
                    include_descendants=include_descendants,
                )
            )
        return execute_bare_direct_item(parsed.memory_selector)

    if is_memory_uid_prefix(operand):
        # A short hexadecimal token can still be a valid Context name. Exact
        # Context identity wins; only a missing Context authorizes the same
        # unique global prefix lookup used by direct-Memory operations.
        try:
            return execute(
                ShowRequest(
                    context_name=parsed,
                    include_descendants=include_descendants,
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
            if include_descendants:
                raise ShowDirectItemScopeError(
                    "--recursive/-r cannot be combined with a direct-item selector."
                )
            return direct_item
    try:
        return execute(
            ShowRequest(
                context_name=parsed,
                include_descendants=include_descendants,
            )
        )
    except FileNotFoundError as error:
        raise ShowInputError(
            f"No Context or direct item matches {operand!r}."
        ) from error


__all__ = ["MemoryStoreShowPort", "execute_show", "execute_show_cli_operand"]
