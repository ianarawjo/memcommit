"""Public application assembly for provider-free deterministic Find."""

from __future__ import annotations

from collections.abc import Sequence

from memcommit.api._runtime import ClientRuntime
from memcommit.api._support.errors import raise_public
from memcommit.api._support.readable import freeze_client_readable_catalog
from memcommit.api.errors import (
    FindAuthorityError,
    FindContextError,
    FindExecutionError,
    FindInputError,
    FindStorageError,
)
from memcommit.api.find import FindMatchResult, FindResult, FindSpanResult
from memcommit.context_locator import resolve_context_locator
from memcommit.operations.find.literal_application import (
    LiteralFindError,
    LiteralFindInputError,
    LiteralFindRequest,
)
from memcommit.operations.find.literal_runtime import execute_literal_find
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError


def _current_name(runtime: ClientRuntime) -> str | None:
    try:
        return runtime.store.current_context_name()
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as error:
        raise_public(FindStorageError, error)


def _canonical_targets(
    context_names: Sequence[str],
    *,
    current_name: str | None,
) -> tuple[str, ...]:
    if isinstance(context_names, (str, bytes)):
        raise TypeError("Find Context names must be a sequence.")
    operands = tuple(context_names)
    if not operands:
        if current_name is None:
            raise FileNotFoundError("No current Context is available.")
        operands = (current_name,)
    if any(not isinstance(name, str) or not name.strip() for name in operands):
        raise TypeError("Find Context names must be nonblank text.")
    canonical = tuple(
        resolve_context_locator(name, current=current_name) for name in operands
    )
    if len(set(canonical)) != len(canonical):
        raise ValueError("Find Context names must not repeat.")
    return canonical


def find(
    runtime: ClientRuntime,
    pattern: str,
    context_names: Sequence[str] = (),
    *,
    include_descendants: bool = False,
    follow_embeds: bool = False,
    regex: bool = False,
    ignore_case: bool = False,
) -> FindResult:
    """Find exact text spans without provider, cache, session, or mutation."""

    try:
        current_name = _current_name(runtime)
        targets = _canonical_targets(context_names, current_name=current_name)
        request = LiteralFindRequest(
            pattern=pattern,
            target_names=targets,
            include_descendants=include_descendants,
            follow_embeds=follow_embeds,
            mode="REGEX" if regex else "LITERAL",
            ignore_case=ignore_case,
        )
        catalog = freeze_client_readable_catalog(
            runtime,
            targets,
            current_name=current_name,
            include_query_routes=False,
        )
        result = execute_literal_find(request, catalog=catalog)
        return FindResult(
            pattern=request.pattern,
            context_names=request.target_names,
            include_descendants=request.include_descendants,
            follow_embeds=request.follow_embeds,
            mode=request.mode,
            ignore_case=request.ignore_case,
            scanned_item_count=result.scanned_item_count,
            occurrence_count=result.occurrence_count,
            matches=tuple(
                FindMatchResult(
                    context_name=match.source.context_name,
                    context_uid=match.source.context_uid,
                    kind=match.source.kind,
                    item_uid=match.source.item_uid,
                    content=match.source.content,
                    spans=tuple(
                        FindSpanResult(
                            start=span.start,
                            end=span.end,
                            text=span.text,
                        )
                        for span in match.spans
                    ),
                    source_context_name=match.source.source_context_name,
                    source_context_uid=match.source.source_context_uid,
                    source_memory_uid=match.source.source_memory_uid,
                )
                for match in result.matches
            ),
        )
    except FindStorageError:
        raise
    except (LiteralFindInputError, TypeError, ValueError) as error:
        raise_public(FindInputError, error)
    except (FileNotFoundError, KeyError) as error:
        raise_public(FindContextError, error)
    except (ProfileConfigError, ProfileError) as error:
        raise_public(FindAuthorityError, error)
    except OSError as error:
        raise_public(FindStorageError, error)
    except (LiteralFindError, RuntimeError) as error:
        raise_public(FindExecutionError, error)


__all__ = ["find"]
