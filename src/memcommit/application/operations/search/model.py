"""Compatibility facade for the split Search candidate and ranking modules.

New production code imports ``candidates``, ``ranking``, or ``errors`` directly.
"""

from memcommit.application.operations.search.candidates import (
    SearchArtifact,
    SearchCandidate,
    SearchItem,
    SearchKind,
    append_artifact_candidates,
    collect_candidates,
    collect_candidates_from_roots,
    search_candidate_uid_catalog,
)
from memcommit.application.operations.search.errors import (
    SearchError,
)
from memcommit.application.operations.search.ranking import (
    PromptProvider,
    SEARCH_CORPUS_CHAR_LIMIT,
    SEARCH_EXECUTION_POLICY,
    SEARCH_RELATED_QUERY_LIMIT,
    SearchMatch,
    SearchRelevance,
    rank_candidates,
)


__all__ = [
    "PromptProvider",
    "SEARCH_CORPUS_CHAR_LIMIT",
    "SEARCH_EXECUTION_POLICY",
    "SEARCH_RELATED_QUERY_LIMIT",
    "SearchArtifact",
    "SearchCandidate",
    "SearchError",
    "SearchItem",
    "SearchKind",
    "SearchMatch",
    "SearchRelevance",
    "append_artifact_candidates",
    "collect_candidates",
    "collect_candidates_from_roots",
    "rank_candidates",
    "search_candidate_uid_catalog",
]
