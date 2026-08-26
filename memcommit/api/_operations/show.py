"""Operation-owned assembly for the public read-only Show lifecycle."""

from __future__ import annotations

from memcommit.api._runtime import ClientRuntime
from memcommit.api._support.errors import raise_public
from memcommit.api.errors import (
    ShowAuthorityError,
    ShowContextError,
    ShowExecutionError,
    ShowInputError,
    ShowStorageError,
)
from memcommit.api.show import (
    ShowContextResult,
    ShowDirectItemResult,
    ShowEmbeddedContextResult,
    ShowMemoryReferenceResult,
    ShowMemoryResult,
    ShowQueryViewResult,
    ShowResult,
    ShowSourceResult,
)
from memcommit.operations.profile.config import (
    ProfileConfigError,
    load_profile_registry,
    profile_store_dir,
)
from memcommit.operations.profile.model import ProfileError
from memcommit.operations.show.application import (
    ShowContextSnapshot,
    ShowEmbeddedContext,
    ShowError as ApplicationShowError,
    ShowInputError as ApplicationShowInputError,
    ShowMemory,
    ShowMemoryReference,
    ShowQueryView,
    ShowRequest,
)
from memcommit.operations.show.runtime import execute_show
from memcommit.source_projection.model import SourceDisplayFacts


def _source(facts: SourceDisplayFacts) -> ShowSourceResult:
    return ShowSourceResult(
        access=facts.access.value,
        reach=facts.reach.value,
        form=facts.form.value,
        states=tuple(state.value for state in facts.states),
        permissions=facts.permissions,
    )


def _direct_item(
    item: ShowMemory | ShowMemoryReference | ShowQueryView | ShowEmbeddedContext,
    *,
    context_name: str,
) -> ShowDirectItemResult:
    if isinstance(item, ShowMemory):
        return ShowMemoryResult(
            uid=item.uid,
            context_name=context_name,
            content=item.content,
            source=_source(item.source),
        )
    if isinstance(item, ShowMemoryReference):
        return ShowMemoryReferenceResult(
            uid=item.uid,
            context_name=context_name,
            target_context_uid=item.target_context_uid,
            target_context_name=item.target_context_name,
            target_memory_uid=item.target_memory_uid,
            resolved=item.resolved,
            content=item.content,
            source=_source(item.source),
        )
    if isinstance(item, ShowQueryView):
        return ShowQueryViewResult(
            uid=item.uid,
            context_name=context_name,
            name=item.name,
            source=_source(item.source),
        )
    return ShowEmbeddedContextResult(
        uid=item.uid,
        context_name=context_name,
        name=item.name,
        source=_source(item.source),
    )


def _context(context: ShowContextSnapshot) -> ShowContextResult:
    return ShowContextResult(
        uid=context.uid,
        name=context.name,
        items=tuple(
            _direct_item(item, context_name=context.name) for item in context.items
        ),
        source=_source(context.source),
    )


def _public(result) -> ShowResult:
    value = result.value
    if isinstance(value, ShowContextSnapshot):
        return _context(value)
    return _direct_item(value, context_name=result.resolved_context_name)


def _allows_grants(runtime: ClientRuntime) -> bool:
    if runtime.registry is None or runtime.profile is None:
        return False
    live_registry = load_profile_registry()
    return bool(
        runtime.profile.uid == live_registry.active.uid
        and runtime.store_root == profile_store_dir(live_registry.active).resolve()
    )


def show(
    runtime: ClientRuntime,
    selector: str | None = None,
    *,
    context_name: str | None = None,
) -> ShowResult:
    """Inspect one exact readable Context or direct item without side effects."""

    try:
        request = ShowRequest(context_name=context_name, selector=selector)
        result = execute_show(
            request,
            store=runtime.store,
            allow_grants=_allows_grants(runtime),
            registry=runtime.registry,
        )
        return _public(result)
    except ApplicationShowInputError as error:
        raise_public(ShowInputError, error)
    except (ProfileConfigError, ProfileError) as error:
        raise_public(ShowAuthorityError, error)
    except (FileNotFoundError, KeyError) as error:
        raise_public(ShowContextError, error)
    except ApplicationShowError as error:
        raise_public(ShowExecutionError, error)
    except OSError as error:
        raise_public(ShowStorageError, error)
    except ValueError as error:
        # After request and locator validation, ValueError means persisted
        # Context or Profile state could not be safely interpreted.
        raise_public(ShowStorageError, error)
    except RuntimeError as error:
        raise_public(ShowContextError, error)


__all__ = ["show"]
