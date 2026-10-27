"""Application boundary for provider-free ``find-duplicates`` discovery."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.application.context_access.access import ContextAccess
from memcommit.application.context_access.operand_resolution import (
    resolve_existing_context_access,
)
from memcommit.application.context_access.readable_contexts import (
    ReadableContextCatalog,
)
from memcommit.application.capabilities.reviewing.direct_item_duplicates import (
    ExactDuplicateGroup,
    find_exact_duplicate_groups,
)
from memcommit.models.context import Context
from memcommit.models.memory import Memory
from memcommit.persistence.store.lookup.context_names import (
    list_context_and_descendant_names,
)
from memcommit.persistence.store import ProfileStore, context_record_digest


@dataclass(frozen=True)
class FindDuplicatesRequest:
    context_name: str | None = None
    include_descendants: bool = False

    def __post_init__(self) -> None:
        if type(self.include_descendants) is not bool:
            raise TypeError("Find Duplicates descendant reach must be boolean.")


@dataclass(frozen=True)
class ExactDuplicateReport:
    """Complete provider-free role-aware exact discovery for one Context."""

    memory_count: int
    groups: tuple[ExactDuplicateGroup, ...]
    item_count: int = 0

    @property
    def duplicate_count(self) -> int:
        return sum(len(group.absorbed_uids) for group in self.groups)


@dataclass(frozen=True)
class ExactDuplicateContextReport:
    """One frozen direct Context and its exact duplicate analysis."""

    context_name: str
    context_uid: str
    context_digest: str
    report: ExactDuplicateReport


@dataclass(frozen=True)
class ExactDuplicateScopeReport:
    """Complete exact-DUP analysis for one direct or lexical Context scope."""

    root_name: str
    include_descendants: bool
    contexts: tuple[ExactDuplicateContextReport, ...]
    context_catalog: tuple[str, ...]

    @property
    def item_count(self) -> int:
        return sum(frame.report.item_count for frame in self.contexts)

    @property
    def memory_count(self) -> int:
        return sum(frame.report.memory_count for frame in self.contexts)

    @property
    def group_count(self) -> int:
        return sum(len(frame.report.groups) for frame in self.contexts)

    @property
    def duplicate_count(self) -> int:
        return sum(frame.report.duplicate_count for frame in self.contexts)


def analyze_exact_duplicates(context: Context) -> ExactDuplicateReport:
    """Return every same-role exact group without provider access or mutation."""

    if not isinstance(context, Context):
        raise TypeError("Find Duplicates requires one Context.")
    memory_count = sum(
        1 for item in context.iter_memories() if isinstance(item, Memory)
    )
    return ExactDuplicateReport(
        memory_count=memory_count,
        groups=find_exact_duplicate_groups(context),
        item_count=len(context.get_ordered_memory_uids()),
    )


def analyze_exact_duplicate_scope(
    active_store: ProfileStore,
    access: ContextAccess,
    *,
    include_descendants: bool,
) -> ExactDuplicateScopeReport:
    """Freeze and analyze each readable Context exactly once."""

    if not isinstance(active_store, ProfileStore) or not isinstance(
        access,
        ContextAccess,
    ):
        raise TypeError("Find Duplicates requires a Store and Context access.")
    if type(include_descendants) is not bool:
        raise TypeError("Find Duplicates descendant reach must be a boolean.")

    context_catalog = tuple(active_store.list_context_names())
    if not include_descendants:
        stored_context = access.store.load_direct(access.context_name)
        context = stored_context
        return ExactDuplicateScopeReport(
            root_name=access.access_name,
            include_descendants=False,
            contexts=(
                ExactDuplicateContextReport(
                    context_name=access.access_name,
                    context_uid=context.uid,
                    context_digest=context_record_digest(stored_context),
                    report=analyze_exact_duplicates(context),
                ),
            ),
            context_catalog=context_catalog,
        )

    catalog = ReadableContextCatalog(
        active_store,
        access,
    )
    names = list_context_and_descendant_names(
        (access.access_name,),
        catalog.list_context_names(),
    )
    return ExactDuplicateScopeReport(
        root_name=access.access_name,
        include_descendants=True,
        contexts=tuple(
            ExactDuplicateContextReport(
                context_name=name,
                context_uid=context.uid,
                context_digest=context_record_digest(context),
                report=analyze_exact_duplicates(context),
            )
            for name in names
            for context in (catalog.load_direct(name),)
        ),
        context_catalog=context_catalog,
    )


def find_duplicates(
    store: ProfileStore,
    request: FindDuplicatesRequest,
    *,
    current_name: str | None,
) -> ExactDuplicateScopeReport:
    """Resolve readable authority and analyze one exact or lexical scope."""

    access = resolve_existing_context_access(
        store,
        request.context_name,
        current_name=current_name,
    ).value
    return analyze_exact_duplicate_scope(
        store,
        access,
        include_descendants=request.include_descendants,
    )


__all__ = [
    "ExactDuplicateContextReport",
    "ExactDuplicateReport",
    "ExactDuplicateScopeReport",
    "FindDuplicatesRequest",
    "analyze_exact_duplicate_scope",
    "analyze_exact_duplicates",
    "find_duplicates",
]
