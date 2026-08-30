"""Public Python assembly for provider-free read-only Find Duplicates."""

from __future__ import annotations

from memcommit.adapters.python_api._runtime import ClientRuntime
from memcommit.adapters.python_api._support.active_profile import (
    active_profile_registry,
)
from memcommit.adapters.python_api._support.errors import raise_public
from memcommit.adapters.python_api.dedup import (
    ExactDedupGroupResult,
    ExactDuplicateContextResult,
    ExactDuplicateFindResult,
)
from memcommit.adapters.python_api.errors import (
    SemanticAuthorityError,
    SemanticContextError,
    SemanticInputError,
    SemanticStorageError,
)
from memcommit.application.capabilities.context_locator import resolve_context_locator
from memcommit.application.operations.find_duplicates.application import (
    FindDuplicatesRequest,
    find_duplicates,
)
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError


def find_duplicates_exact(
    runtime: ClientRuntime,
    context_name: str | None = None,
    *,
    include_descendants: bool = False,
) -> ExactDuplicateFindResult:
    """Return same-role exact groups for one direct or lexical Context scope."""

    try:
        if type(include_descendants) is not bool:
            raise TypeError("Find Duplicates descendant reach must be a boolean.")
        current_name = runtime.store.current_context_name()
        if context_name is None:
            if current_name is None:
                raise FileNotFoundError("No current Context is available.")
            canonical = current_name
        else:
            canonical = resolve_context_locator(context_name, current=current_name)
        registry = active_profile_registry(runtime)
        scope = find_duplicates(
            runtime.store,
            FindDuplicatesRequest(
                context_name=canonical,
                include_descendants=include_descendants,
            ),
            current_name=current_name,
            registry=registry,
        )
    except (FileNotFoundError, KeyError) as error:
        raise_public(SemanticContextError, error)
    except (ProfileConfigError, ProfileError) as error:
        raise_public(SemanticAuthorityError, error)
    except OSError as error:
        raise_public(SemanticStorageError, error)
    except (TypeError, ValueError) as error:
        raise_public(SemanticInputError, error)
    contexts = tuple(
        ExactDuplicateContextResult(
            context_name=frame.context_name,
            context_uid=frame.context_uid,
            memory_count=frame.report.memory_count,
            item_count=frame.report.item_count,
            groups=tuple(
                ExactDedupGroupResult(
                    survivor_uid=group.survivor_uid,
                    absorbed_uids=group.absorbed_uids,
                    content=group.content,
                    item_kind=group.item_kind,
                    summary=group.summary,
                    context_name=frame.context_name,
                )
                for group in frame.report.groups
            ),
        )
        for frame in scope.contexts
    )
    return ExactDuplicateFindResult(
        context_name=scope.root_name,
        memory_count=scope.memory_count,
        item_count=scope.item_count,
        groups=tuple(group for frame in contexts for group in frame.groups),
        include_descendants=scope.include_descendants,
        contexts=contexts,
    )


__all__ = ["find_duplicates_exact"]
