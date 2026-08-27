"""Operation-owned application boundary for read-only semantic Search."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from memcommit.core.context import Memory, MemoryRef, QueryContextRef
from memcommit.application.operations.search.model import (
    FindError,
    SearchArtifact,
    SearchCandidate,
    SearchMatch,
    rank_candidates,
)


FindSearchMode = Literal["CURRENT"]
FindSearchResultKind = Literal[
    "memory",
    "ref",
    "query",
    "artifact",
]
FindSearchRelevance = Literal["primary", "related"]
FindSearchStage = Literal[
    "INPUTS_FROZEN",
    "CONNECTING_PROVIDER",
    "SEARCHING",
    "CHECKING_COVERAGE",
]


@dataclass(frozen=True)
class FindSearchRequest:
    """One exact process-local query and readable location scope."""

    query: str
    target_names: tuple[str, ...]
    include_descendants: bool = True
    follow_embeds: bool = True
    limit: int = 5

    def __post_init__(self) -> None:
        if not isinstance(self.query, str) or not self.query.strip():
            raise ValueError("Enter a nonblank Search query.")
        if (
            not self.target_names
            or any(not isinstance(name, str) or not name for name in self.target_names)
            or len(set(self.target_names)) != len(self.target_names)
        ):
            raise ValueError("Select at least one distinct readable Context.")
        if not isinstance(self.include_descendants, bool) or not isinstance(
            self.follow_embeds, bool
        ):
            raise ValueError("Search scope choices must be explicit booleans.")
        if isinstance(self.limit, bool) or not 1 <= self.limit <= 20:
            raise ValueError("Search limit must be between 1 and 20.")


@dataclass(frozen=True)
class FindSearchResult:
    """One host-resolved row tied to authorized frozen evidence."""

    context_name: str
    kind: FindSearchResultKind
    uid: str
    content: str
    relevance: FindSearchRelevance = "primary"
    source_context_name: str | None = None
    source_context_uid: str | None = None
    source_memory_uid: str | None = None
    current_match: SearchMatch | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.context_name, str) or not self.context_name.strip():
            raise ValueError("Search results require a Context name.")
        if self.kind not in {
            "memory",
            "ref",
            "query",
            "artifact",
        }:
            raise ValueError("Search returned an unsupported result kind.")
        if not isinstance(self.uid, str) or not self.uid.strip():
            raise ValueError("Search results require a local identity.")
        if not isinstance(self.content, str) or not self.content.strip():
            raise ValueError("Search results require nonblank content.")
        if self.relevance not in {"primary", "related"}:
            raise ValueError("Search returned invalid relevance.")
        source_values = (
            self.source_context_name,
            self.source_context_uid,
            self.source_memory_uid,
        )
        if any(value is not None for value in source_values) and not all(
            isinstance(value, str) and value.strip() for value in source_values
        ):
            raise ValueError("Search result Save As identity must be complete or absent.")


@dataclass(frozen=True)
class FindSearchResponse:
    """Read-only results tied to the exact request that produced them."""

    request: FindSearchRequest
    mode: FindSearchMode
    results: tuple[FindSearchResult, ...]
    related_query: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.request, FindSearchRequest):
            raise ValueError("Search responses require the frozen request.")
        if self.mode != "CURRENT":
            raise ValueError("Search returned an invalid search mode.")
        if not isinstance(self.results, tuple) or any(
            not isinstance(result, FindSearchResult) for result in self.results
        ):
            raise ValueError("Search returned invalid result rows.")
        if not isinstance(self.related_query, str):
            raise ValueError("Search returned an invalid broader query.")
        related = [result for result in self.results if result.relevance == "related"]
        primary = [result for result in self.results if result.relevance == "primary"]
        if related and (primary or not self.related_query.strip()):
            raise ValueError("Related Search results require one separate broader query.")
        if not related and self.related_query:
            raise ValueError("A broader Search query requires related results.")


@dataclass(frozen=True)
class FrozenFindCurrentSource:
    """One authorized current-state candidate frame."""

    candidates: tuple[SearchCandidate, ...]
    coverage_root_name: str | None = None


class FindSearchSourcePort(Protocol):
    """Freeze readable evidence before semantic provider construction."""

    def freeze_current(self, request: FindSearchRequest) -> FrozenFindCurrentSource:
        """Return current-state candidates after readable-scope validation."""

class FindSearchProvider(Protocol):
    def complete(
        self,
        prompt: str,
        *,
        operation: str,
        output_schema: dict[str, object] | None = None,
    ) -> str: ...


class FindSearchProviderFactory(Protocol):
    """Construct a provider only after the source port freezes authority."""

    def __call__(self) -> FindSearchProvider: ...


class FindSearchObserver(Protocol):
    def __call__(self, stage: FindSearchStage) -> None: ...


def _observe(observer: FindSearchObserver | None, stage: FindSearchStage) -> None:
    if observer is not None:
        observer(stage)


def _namespace_branch(name: str, root_name: str) -> str | None:
    prefix = root_name + "/"
    if not name.startswith(prefix):
        return None
    return name[len(prefix) :].split("/", 1)[0]


def supplement_namespace_branch_coverage(
    query: str,
    candidates: tuple[SearchCandidate, ...] | list[SearchCandidate],
    matches: list[SearchMatch],
    provider: FindSearchProvider,
    *,
    root_name: str,
    limit: int,
) -> list[SearchMatch]:
    """Retain a material match from another relevant lexical branch."""

    if (
        limit < 2
        or not matches
        or any(match.relevance != "primary" for match in matches)
    ):
        return matches
    candidate_branches = {
        branch
        for candidate in candidates
        if candidate.kind != "artifact"
        if (branch := _namespace_branch(candidate.context_name, root_name)) is not None
    }
    selected_branches = {
        branch
        for match in matches
        if (branch := _namespace_branch(match.candidate.context_name, root_name))
        is not None
    }
    omitted = candidate_branches - selected_branches
    if not selected_branches or not omitted:
        return matches
    omitted_candidates = [
        candidate
        for candidate in candidates
        if _namespace_branch(candidate.context_name, root_name) in omitted
        and candidate.kind != "artifact"
    ]
    supplemental = [
        match
        for match in rank_candidates(
            query,
            omitted_candidates,
            provider,
            limit=limit,
        )
        if match.relevance == "primary"
    ]
    if not supplemental:
        return matches

    reserve = min(len(supplemental), max(1, min(3, limit // 2)))
    keep = min(len(matches), limit - reserve)
    combined = [*matches[:keep], *supplemental[:reserve]]
    seen: set[tuple[str, str]] = set()
    result: list[SearchMatch] = []
    for match in combined:
        identity = (match.candidate.context_uid, match.candidate.item.uid)
        if identity in seen:
            continue
        seen.add(identity)
        result.append(match)
    return result[:limit]


def related_query_for_matches(matches: list[SearchMatch]) -> str:
    """Return one common related query while rejecting mixed result tiers."""

    related_queries = {
        match.related_query for match in matches if match.relevance == "related"
    }
    primary_count = sum(match.relevance == "primary" for match in matches)
    related_count = sum(match.relevance == "related" for match in matches)
    if primary_count and related_count:
        raise FindError("Search cannot mix primary and related results.")
    if related_count:
        if len(related_queries) != 1 or None in related_queries:
            raise FindError("Related Search results require one broader query.")
        return next(iter(related_queries)) or ""
    return ""


def _current_result(match: SearchMatch) -> FindSearchResult:
    candidate = match.candidate
    item = candidate.item
    if isinstance(item, Memory):
        kind: FindSearchResultKind = "memory"
        content = item.content
        source_identity = (candidate.context_name, candidate.context_uid, item.uid)
    elif isinstance(item, MemoryRef):
        kind = "ref"
        content = (
            item.target.content if item.target is not None else "(DANGLING memory ref)"
        )
        source_identity = (
            item.target_context_name,
            item.target_context_uid,
            item.target_memory_uid,
        )
    elif isinstance(item, QueryContextRef):
        kind = "query"
        content = f"{item.name} · query view"
        source_identity = (None, None, None)
    elif isinstance(item, SearchArtifact):
        kind = "artifact"
        content = f"{item.title}\n{item.content}"
        source_identity = (None, None, None)
    else:  # pragma: no cover - SearchCandidate validates this union.
        raise FindError("Search returned an unsupported result type.")
    return FindSearchResult(
        context_name=candidate.context_name,
        kind=kind,
        uid=item.uid,
        content=content,
        relevance=match.relevance,
        source_context_name=source_identity[0],
        source_context_uid=source_identity[1],
        source_memory_uid=source_identity[2],
        current_match=match,
    )


def run_find_search(
    request: FindSearchRequest,
    *,
    source_port: FindSearchSourcePort,
    provider_factory: FindSearchProviderFactory,
    observer: FindSearchObserver | None = None,
) -> FindSearchResponse:
    """Execute one read-only Search request without CLI or TUI dependencies."""

    current_source = source_port.freeze_current(request)
    _observe(observer, "INPUTS_FROZEN")
    _observe(observer, "CONNECTING_PROVIDER")
    provider = provider_factory()
    _observe(observer, "SEARCHING")
    matches = rank_candidates(
        request.query,
        list(current_source.candidates),
        provider,
        limit=request.limit,
    )
    if current_source.coverage_root_name is not None:
        _observe(observer, "CHECKING_COVERAGE")
        matches = supplement_namespace_branch_coverage(
            request.query,
            current_source.candidates,
            matches,
            provider,
            root_name=current_source.coverage_root_name,
            limit=request.limit,
        )
    return FindSearchResponse(
        request=request,
        mode="CURRENT",
        results=tuple(_current_result(match) for match in matches),
        related_query=related_query_for_matches(matches),
    )


__all__ = [
    "FindSearchMode",
    "FindSearchObserver",
    "FindSearchProvider",
    "FindSearchProviderFactory",
    "FindSearchRequest",
    "FindSearchResponse",
    "FindSearchResult",
    "FindSearchResultKind",
    "FindSearchRelevance",
    "FindSearchSourcePort",
    "FindSearchStage",
    "FrozenFindCurrentSource",
    "related_query_for_matches",
    "run_find_search",
    "supplement_namespace_branch_coverage",
]
