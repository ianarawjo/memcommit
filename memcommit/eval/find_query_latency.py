"""Reproducible Find/Query latency matrix over the GPT-5.6 Codex family.

This module is deliberately evaluation-only.  It rebuilds the reviewed Task 3
fixtures in memory, invokes the production Find and Query prompt contracts, and
writes an atomic, resumable ledger without opening or mutating a user profile.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping, Sequence

from memcommit.context import Context, Memory
from memcommit.eval.semantic_campaign import _atomic_write_json
from memcommit.eval.study_fixtures import load_study_fixture
from memcommit.provider_types import ProviderIdentity, SemanticProvider
from memcommit.query_provider import (
    CodexChatGPTProvider,
    QueryProviderError,
    _build_query_prompt,
)
from memcommit.search import (
    FindError,
    SearchCandidate,
    SearchMatch,
    _build_find_prompt,
    _find_output_schema,
    collect_candidates,
    rank_candidates,
)


CAMPAIGN_KIND = "find-query-provider-matrix"
CAMPAIGN_VERSION = 2
MATRIX_MODELS = ("gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna")
MATRIX_EFFORTS = ("none", "low", "medium")
FIND_DATASET = "task3-personal-memory"
QUERY_DATASET = "task3-healthcare-qna"
FIND_ROOT_NAME = "task-3/local/personal-memory"
QUERY_SOURCE_NAME = (
    "remote/government/healthcare-agent/info-request/questions-and-answers"
)
_UID_NAMESPACE = uuid.UUID("f9ea65c1-12c8-4218-8bda-48178a44f26a")


@dataclass(frozen=True)
class MatrixCondition:
    model: str
    effort: str

    @property
    def condition_id(self) -> str:
        return f"{self.model}:{self.effort}"


@dataclass(frozen=True)
class FindCase:
    case_id: str
    label: str
    query: str
    historical_results: tuple[str, ...] = ()
    study_selected: tuple[str, ...] = ()
    expect_empty_primary: bool = False


@dataclass(frozen=True)
class QueryConcept:
    concept_id: str
    patterns: tuple[str, ...]


@dataclass(frozen=True)
class QueryCase:
    case_id: str
    label: str
    question: str
    concepts: tuple[QueryConcept, ...]
    forbidden_patterns: tuple[str, ...] = ()


@dataclass(frozen=True)
class FrozenFindCorpus:
    candidates: tuple[SearchCandidate, ...]
    locator_by_candidate_id: Mapping[str, str]
    digest: str
    record_count: int


@dataclass(frozen=True)
class FrozenQueryCorpus:
    source_name: str
    source_content: str
    digest: str
    record_count: int


FIND_CASES = (
    FindCase(
        case_id="find-accessibility",
        label="Stable accessibility and communication preferences",
        query=(
            "stable current accessibility, communication, sensory, mobility, "
            "or accommodation preferences useful across healthcare "
            "interactions, excluding private event details and third-party "
            "information"
        ),
        historical_results=(
            "local/personal-memory/2025-02/10",
            "local/personal-memory/2024-04/03",
            "local/personal-memory/2024-03/06",
            "local/personal-memory/2024-04/09",
            "local/personal-memory/2024-03/04",
        ),
        study_selected=(
            "local/personal-memory/2025-02/10",
            "local/personal-memory/2024-04/03",
            "local/personal-memory/2024-04/09",
            "local/personal-memory/2024-03/04",
        ),
    ),
    FindCase(
        case_id="find-coordination",
        label="Stable healthcare coordination preferences",
        query=(
            "stable current healthcare coordination preferences for "
            "scheduling, reminders, preparation, language, preferred contact "
            "channel, or support logistics, excluding actual phone numbers, "
            "addresses, dates, medication details, and third-party information"
        ),
        historical_results=(
            "local/personal-memory/2025-02/10",
            "local/personal-memory/2024-04/09",
            "local/personal-memory/2024-09/01",
            "local/personal-memory/2025-02/03",
            "local/personal-memory/2024-04/03",
        ),
        study_selected=(
            "local/personal-memory/2024-09/01",
            "local/personal-memory/2025-02/03",
        ),
    ),
    FindCase(
        case_id="find-unsupported",
        label="Unsupported blood-type and hospital lookup",
        query="the user's blood type and the name of the hospital that diagnosed it",
        expect_empty_primary=True,
    ),
)


QUERY_CASES = (
    QueryCase(
        case_id="query-synthesis",
        label="Multi-fact transmission-boundary synthesis",
        question=(
            "When I actually send information through the government "
            "healthcare institution system's transmission screen, what counts "
            "as consent, who may receive it, what may it be used for, who "
            "controls retention or deletion, and what can this Q&A agent not do?"
        ),
        concepts=(
            QueryConcept(
                "consent-unit",
                (
                    r"all (?:the )?(?:content|information).*(?:send|sent).*"
                    r"(?:one|single).*consent",
                    r"one (?:submitted )?unit.*consent",
                ),
            ),
            QueryConcept(
                "healthcare-third-parties",
                (r"third part(?:y|ies).*healthcare", r"healthcare.*third part(?:y|ies)"),
            ),
            QueryConcept("service-improvement", (r"service improvement",)),
            QueryConcept(
                "scope-varies",
                (
                    r"exact (?:services|recipients|scope).*(?:var(?:y|ies)|depend|not (?:specified|identified|known)|cannot be identified)",
                    r"depend.*type of information",
                    r"cannot identify.*exact (?:services|recipients|scope)",
                ),
            ),
            QueryConcept(
                "institution-retention",
                (
                    r"institution.*(?:retention|audit)",
                    r"(?:retention|audit).*institution",
                ),
            ),
            QueryConcept(
                "agent-boundary",
                (
                    r"agent cannot.*(?:select|modify|transmit|delete|control)",
                    r"cannot.*(?:select|modify|transmit|delete).*information",
                ),
            ),
        ),
    ),
    QueryCase(
        case_id="query-narrow",
        label="Narrow mention-versus-transmission boundary",
        question=(
            "Does merely mentioning personal Memory content in this "
            "conversation send it to the institution or delete it?"
        ),
        concepts=(
            QueryConcept(
                "mention-does-not-send",
                (
                    r"merely mentioning.*(?:does not|doesn't|won't).*"
                    r"(?:send|submit|transmit)",
                    r"mentioning.*not.*(?:send|submit|transmit)",
                ),
            ),
            QueryConcept(
                "transmission-screen-boundary",
                (
                    r"only.*(?:actually )?sent.*transmission screen",
                    r"only.*(?:actually )?submitted.*transmission screen",
                    r"transmission screen.*(?:counts|constitutes|consent)",
                ),
            ),
            QueryConcept(
                "mention-does-not-delete",
                (
                    r"mentioning.*(?:does not|doesn't|won't).*delet",
                    r"agent cannot.*delet",
                    r"not.*physically delet",
                ),
            ),
        ),
    ),
    QueryCase(
        case_id="query-unsupported",
        label="Unsupported exact retention and recipient details",
        question=(
            "What is the exact retention period in days, and which named "
            "third-party company receives medication information?"
        ),
        concepts=(
            QueryConcept(
                "retention-not-specified",
                (
                    r"retention (?:period|duration).*(?:not (?:specified|provided|stated|identified)|does not (?:specify|state)|cannot (?:determine|answer))",
                    r"(?:not (?:specified|provided|stated)|cannot (?:determine|answer)).*retention",
                    r"does not (?:specify|state|provide).*retention",
                ),
            ),
            QueryConcept(
                "company-not-identified",
                (
                    r"(?:company|third part(?:y|ies)|recipient).*(?:not (?:named|specified|identified|provided)|does not (?:name|identify)|cannot (?:determine|identify|answer))",
                    r"(?:not (?:named|specified|identified)|cannot (?:determine|identify|answer)).*(?:company|third part(?:y|ies)|recipient)",
                    r"does not (?:name|identify|specify|provide).*(?:company|third part(?:y|ies)|recipient)",
                ),
            ),
        ),
        forbidden_patterns=(r"\b\d+\s+days?\b",),
    ),
)


ALL_CASES: tuple[FindCase | QueryCase, ...] = (*FIND_CASES, *QUERY_CASES)
DEFAULT_CONDITIONS = tuple(
    MatrixCondition(model=model, effort=effort)
    for model in MATRIX_MODELS
    for effort in MATRIX_EFFORTS
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _json_digest(value: object) -> str:
    return _digest_text(
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    )


def _stable_uid(kind: str, value: str) -> str:
    return str(uuid.uuid5(_UID_NAMESPACE, f"{kind}:{value}"))


def build_find_corpus() -> FrozenFindCorpus:
    """Rebuild the 300-Memory Task 3 hierarchy without opening a profile."""
    dataset = load_study_fixture(FIND_DATASET, language="en")
    root = Context(uid=_stable_uid("context", FIND_ROOT_NAME), name=FIND_ROOT_NAME)
    year_contexts: dict[str, Context] = {}
    month_contexts: dict[str, Context] = {}
    locator_by_memory_uid: dict[str, str] = {}

    for record in dataset.records:
        parts = record.canonical_locator.split("/")
        if len(parts) != 4 or parts[:2] != ["local", "personal-memory"]:
            raise ValueError(
                f"Unexpected Task 3 personal-memory locator: {record.canonical_locator}"
            )
        month, _ordinal = parts[2:]
        year = month.split("-", 1)[0]
        year_context = year_contexts.get(year)
        if year_context is None:
            year_name = f"{FIND_ROOT_NAME}/{year}"
            year_context = Context(
                uid=_stable_uid("context", year_name),
                name=year_name,
            )
            year_contexts[year] = year_context
            root.add(year_context)
        month_context = month_contexts.get(month)
        if month_context is None:
            month_name = f"{FIND_ROOT_NAME}/{month}"
            month_context = Context(
                uid=_stable_uid("context", month_name),
                name=month_name,
            )
            month_contexts[month] = month_context
            year_context.add(month_context)
        memory_uid = _stable_uid("memory", record.canonical_locator)
        month_context.add(Memory(uid=memory_uid, content=record.content))
        locator_by_memory_uid[memory_uid] = record.canonical_locator

    candidates = tuple(collect_candidates(root, recursive=True))
    locator_by_candidate_id = {
        candidate.candidate_id: locator_by_memory_uid[candidate.item.uid]
        for candidate in candidates
    }
    digest_payload = [
        {
            "candidate_id": candidate.candidate_id,
            "locator": locator_by_candidate_id[candidate.candidate_id],
            "contexts": candidate.context_names,
            "content": candidate.search_text,
        }
        for candidate in candidates
    ]
    return FrozenFindCorpus(
        candidates=candidates,
        locator_by_candidate_id=locator_by_candidate_id,
        digest=_json_digest(digest_payload),
        record_count=len(dataset.records),
    )


def build_query_corpus() -> FrozenQueryCorpus:
    """Freeze the production-shaped query-only source from 75 reviewed rows."""
    dataset = load_study_fixture(QUERY_DATASET, language="en")
    source_content = "\n\n".join(record.content for record in dataset.records)
    digest_payload = [
        {"locator": record.canonical_locator, "content": record.content}
        for record in dataset.records
    ]
    return FrozenQueryCorpus(
        source_name=QUERY_SOURCE_NAME,
        source_content=source_content,
        digest=_json_digest(digest_payload),
        record_count=len(dataset.records),
    )


def build_schedule(
    cases: Sequence[FindCase | QueryCase] = ALL_CASES,
    conditions: Sequence[MatrixCondition] = DEFAULT_CONDITIONS,
) -> list[dict[str, str]]:
    """Rotate condition order per case to reduce fixed-order confounding."""
    schedule: list[dict[str, str]] = []
    for case_index, case in enumerate(cases):
        for offset in range(len(conditions)):
            condition = conditions[(offset + case_index) % len(conditions)]
            schedule.append(
                {
                    "cell_id": f"{case.case_id}:{condition.condition_id}",
                    "case_id": case.case_id,
                    "operation": "find" if isinstance(case, FindCase) else "query",
                    "model": condition.model,
                    "effort": condition.effort,
                }
            )
    return schedule


def score_query(case: QueryCase, answer: str) -> dict[str, object]:
    flags = re.IGNORECASE | re.DOTALL
    concepts = []
    for concept in case.concepts:
        matched_pattern = next(
            (pattern for pattern in concept.patterns if re.search(pattern, answer, flags)),
            None,
        )
        concepts.append(
            {
                "concept_id": concept.concept_id,
                "matched": matched_pattern is not None,
                "matched_pattern": matched_pattern,
            }
        )
    forbidden = [
        pattern
        for pattern in case.forbidden_patterns
        if re.search(pattern, answer, flags)
    ]
    matched_count = sum(bool(item["matched"]) for item in concepts)
    return {
        "concepts": concepts,
        "matched_concepts": matched_count,
        "required_concepts": len(concepts),
        "concept_recall": matched_count / len(concepts) if concepts else 1.0,
        "forbidden_matches": forbidden,
        "forbidden_violation": bool(forbidden),
    }


def _fraction(found: set[str], expected: Sequence[str]) -> float | None:
    if not expected:
        return None
    return len(found.intersection(expected)) / len(set(expected))


def score_find(
    case: FindCase,
    matches: Sequence[SearchMatch],
    corpus: FrozenFindCorpus,
) -> dict[str, object]:
    primary = [match for match in matches if match.relevance == "primary"]
    related = [match for match in matches if match.relevance == "related"]
    primary_locators = [
        corpus.locator_by_candidate_id[match.candidate.candidate_id]
        for match in primary
    ]
    related_locators = [
        corpus.locator_by_candidate_id[match.candidate.candidate_id]
        for match in related
    ]
    primary_set = set(primary_locators)
    historical_set = set(case.historical_results)
    historical_hits = primary_set.intersection(historical_set)
    return {
        "primary_locators": primary_locators,
        "related_locators": related_locators,
        "related_query": related[0].related_query if related else None,
        "primary_count": len(primary_locators),
        "historical_result_recall": _fraction(primary_set, case.historical_results),
        "historical_result_precision": (
            len(historical_hits) / len(primary_set)
            if primary_set and historical_set
            else (None if not historical_set else 0.0)
        ),
        "study_selected_recall": _fraction(primary_set, case.study_selected),
        "empty_primary_correct": (
            not primary_locators if case.expect_empty_primary else None
        ),
    }


class _RecordingProvider:
    """Measure one provider primitive while retaining its exact completion."""

    def __init__(self, delegate: SemanticProvider):
        self.delegate = delegate
        self.call_count = 0
        self.provider_seconds = 0.0
        self.raw_response: str | None = None

    def complete(
        self,
        prompt: str,
        *,
        operation: str,
        output_schema: dict[str, object] | None = None,
    ) -> str:
        self.call_count += 1
        started = time.perf_counter()
        try:
            response = self.delegate.complete(
                prompt,
                operation=operation,
                output_schema=output_schema,
            )
            self.raw_response = response
            return response
        finally:
            self.provider_seconds += time.perf_counter() - started


ProviderConnector = Callable[..., SemanticProvider]


def _identity_dict(provider: SemanticProvider) -> dict[str, object]:
    identity = getattr(provider, "identity", None)
    if isinstance(identity, ProviderIdentity):
        return asdict(identity)
    return {
        "provider": getattr(identity, "provider", "unknown"),
        "model": getattr(identity, "model", "unknown"),
        "reasoning_effort": getattr(identity, "reasoning_effort", None),
    }


def _case_definition(case: FindCase | QueryCase) -> dict[str, object]:
    if isinstance(case, FindCase):
        return {
            "case_id": case.case_id,
            "operation": "find",
            "label": case.label,
            "query": case.query,
            "historical_results": list(case.historical_results),
            "study_selected": list(case.study_selected),
            "expect_empty_primary": case.expect_empty_primary,
        }
    return {
        "case_id": case.case_id,
        "operation": "query",
        "label": case.label,
        "question": case.question,
        "concepts": [asdict(concept) for concept in case.concepts],
        "forbidden_patterns": list(case.forbidden_patterns),
    }


def _run_cell(
    cell: Mapping[str, str],
    case: FindCase | QueryCase,
    *,
    find_corpus: FrozenFindCorpus,
    query_corpus: FrozenQueryCorpus,
    connector: ProviderConnector,
    timeout: float,
) -> dict[str, object]:
    cell_started = time.perf_counter()
    started_at = _utc_now()
    prompt: str
    schema: dict[str, object] | None
    if isinstance(case, FindCase):
        candidates = list(find_corpus.candidates)
        prompt = _build_find_prompt(case.query, candidates, 5)
        schema = _find_output_schema(5, candidates)
    else:
        prompt = _build_query_prompt(
            query_corpus.source_name,
            query_corpus.source_content,
            case.question,
        )
        schema = None

    connection_started = time.perf_counter()
    provider: SemanticProvider | None = None
    recording: _RecordingProvider | None = None
    status = "PROVIDER_ERROR"
    score: dict[str, object] | None = None
    result: dict[str, object] | None = None
    failure: dict[str, str] | None = None
    validation_seconds = 0.0
    try:
        provider = connector(
            timeout=timeout,
            model=cell["model"],
            reasoning_effort=cell["effort"],
        )
        connection_seconds = time.perf_counter() - connection_started
        recording = _RecordingProvider(provider)
        validation_started = 0.0
        if isinstance(case, FindCase):
            matches = rank_candidates(
                case.query,
                list(find_corpus.candidates),
                recording,
                limit=5,
            )
            validation_started = time.perf_counter()
            if recording.call_count != 1:
                raise FindError(
                    "Matrix corpus unexpectedly used staged Find execution; "
                    f"observed {recording.call_count} provider calls."
                )
            score = score_find(case, matches, find_corpus)
            result = {
                "matches": [
                    {
                        "candidate_id": match.candidate.candidate_id,
                        "relevance": match.relevance,
                        "related_query": match.related_query,
                    }
                    for match in matches
                ]
            }
        else:
            answer = recording.complete(prompt, operation="query")
            validation_started = time.perf_counter()
            score = score_query(case, answer)
            result = {"answer": answer}
        validation_seconds = time.perf_counter() - validation_started
        status = "VALID"
    except FindError as error:
        connection_seconds = time.perf_counter() - connection_started
        status = "INVALID_RESPONSE" if recording and recording.raw_response else "PROVIDER_ERROR"
        failure = {"type": type(error).__name__, "message": str(error)}
    except QueryProviderError as error:
        connection_seconds = time.perf_counter() - connection_started
        failure = {"type": type(error).__name__, "message": str(error)}
    except Exception as error:  # Preserve a cell-level failure and continue the matrix.
        connection_seconds = time.perf_counter() - connection_started
        failure = {"type": type(error).__name__, "message": str(error)}

    raw_response = recording.raw_response if recording is not None else None
    schema_text = (
        json.dumps(schema, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        if schema is not None
        else ""
    )
    return {
        "cell_id": cell["cell_id"],
        "case_id": case.case_id,
        "operation": cell["operation"],
        "model": cell["model"],
        "effort": cell["effort"],
        "status": status,
        "started_at": started_at,
        "finished_at": _utc_now(),
        "provider_identity": _identity_dict(provider) if provider is not None else None,
        "timing": {
            "connection_seconds": connection_seconds,
            "provider_seconds": recording.provider_seconds if recording else 0.0,
            "validation_seconds": validation_seconds,
            "total_seconds": time.perf_counter() - cell_started,
        },
        "sizes": {
            "prompt_chars": len(prompt),
            "schema_chars": len(schema_text),
            "response_chars": len(raw_response) if raw_response is not None else 0,
        },
        "digests": {
            "prompt_sha256": _digest_text(prompt),
            "schema_sha256": _digest_text(schema_text),
            "response_sha256": _digest_text(raw_response) if raw_response else None,
        },
        "provider_call_count": recording.call_count if recording else 0,
        "raw_response": raw_response,
        "result": result,
        "score": score,
        "failure": failure,
    }


def _mean(values: Sequence[float]) -> float | None:
    return statistics.fmean(values) if values else None


def _median(values: Sequence[float]) -> float | None:
    return statistics.median(values) if values else None


def summarize_attempts(attempts: Sequence[Mapping[str, object]]) -> dict[str, object]:
    by_condition: dict[str, dict[str, object]] = {}
    for model in MATRIX_MODELS:
        for effort in MATRIX_EFFORTS:
            condition_id = f"{model}:{effort}"
            rows = [
                attempt
                for attempt in attempts
                if attempt.get("model") == model and attempt.get("effort") == effort
            ]
            if not rows:
                continue
            find_rows = [row for row in rows if row.get("operation") == "find"]
            query_rows = [row for row in rows if row.get("operation") == "query"]
            provider_times = [
                float(row["timing"]["provider_seconds"])  # type: ignore[index]
                for row in rows
                if isinstance(row.get("timing"), Mapping)
            ]
            find_provider_times = [
                float(row["timing"]["provider_seconds"])  # type: ignore[index]
                for row in find_rows
                if isinstance(row.get("timing"), Mapping)
            ]
            query_provider_times = [
                float(row["timing"]["provider_seconds"])  # type: ignore[index]
                for row in query_rows
                if isinstance(row.get("timing"), Mapping)
            ]
            find_pairs = [
                (row, row["score"])
                for row in find_rows
                if row.get("status") == "VALID" and isinstance(row.get("score"), Mapping)
            ]
            find_scores = [score for _row, score in find_pairs]
            query_scores = [
                row["score"]
                for row in query_rows
                if row.get("status") == "VALID" and isinstance(row.get("score"), Mapping)
            ]
            historical_recalls = [
                float(score["historical_result_recall"])
                for score in find_scores
                if score.get("historical_result_recall") is not None
            ]
            selected_recalls = [
                float(score["study_selected_recall"])
                for score in find_scores
                if score.get("study_selected_recall") is not None
            ]
            query_recalls = [float(score["concept_recall"]) for score in query_scores]
            unsupported_find = next(
                (
                    score.get("empty_primary_correct")
                    for row, score in find_pairs
                    if row.get("case_id") == "find-unsupported"
                ),
                None,
            )
            by_condition[condition_id] = {
                "attempts": len(rows),
                "valid": sum(row.get("status") == "VALID" for row in rows),
                "invalid_response": sum(
                    row.get("status") == "INVALID_RESPONSE" for row in rows
                ),
                "provider_error": sum(
                    row.get("status") == "PROVIDER_ERROR" for row in rows
                ),
                "provider_seconds_median": _median(provider_times),
                "provider_seconds_max": max(provider_times) if provider_times else None,
                "find_provider_seconds_median": _median(find_provider_times),
                "find_provider_seconds_max": (
                    max(find_provider_times) if find_provider_times else None
                ),
                "query_provider_seconds_median": _median(query_provider_times),
                "query_provider_seconds_max": (
                    max(query_provider_times) if query_provider_times else None
                ),
                "find_historical_recall_mean": _mean(historical_recalls),
                "find_study_selected_recall_mean": _mean(selected_recalls),
                "find_unsupported_empty_primary": unsupported_find,
                "query_concept_recall_mean": _mean(query_recalls),
                "query_concept_recall_min": min(query_recalls) if query_recalls else None,
                "query_forbidden_violations": sum(
                    bool(score.get("forbidden_violation")) for score in query_scores
                ),
            }
    return {
        "attempts": len(attempts),
        "valid": sum(row.get("status") == "VALID" for row in attempts),
        "invalid_response": sum(
            row.get("status") == "INVALID_RESPONSE" for row in attempts
        ),
        "provider_error": sum(
            row.get("status") == "PROVIDER_ERROR" for row in attempts
        ),
        "by_condition": by_condition,
    }


def _campaign_basis(
    *,
    cases: Sequence[FindCase | QueryCase],
    conditions: Sequence[MatrixCondition],
    schedule: Sequence[Mapping[str, str]],
    find_corpus: FrozenFindCorpus,
    query_corpus: FrozenQueryCorpus,
) -> dict[str, object]:
    return {
        "kind": CAMPAIGN_KIND,
        "version": CAMPAIGN_VERSION,
        "cases": [_case_definition(case) for case in cases],
        "conditions": [asdict(condition) for condition in conditions],
        "schedule": list(schedule),
        "corpora": {
            "find": {
                "dataset": FIND_DATASET,
                "records": find_corpus.record_count,
                "sha256": find_corpus.digest,
            },
            "query": {
                "dataset": QUERY_DATASET,
                "records": query_corpus.record_count,
                "sha256": query_corpus.digest,
            },
        },
    }


def run_campaign(
    output: Path,
    *,
    timeout: float = 600,
    resume: bool = False,
    cases: Sequence[FindCase | QueryCase] = ALL_CASES,
    conditions: Sequence[MatrixCondition] = DEFAULT_CONDITIONS,
    connector: ProviderConnector = CodexChatGPTProvider.connect,
) -> dict[str, object]:
    """Run or resume the matrix, atomically publishing every completed cell."""
    if timeout <= 0:
        raise ValueError("Provider timeout must be positive.")
    if len({case.case_id for case in cases}) != len(cases):
        raise ValueError("Matrix case IDs must be unique.")
    if len({condition.condition_id for condition in conditions}) != len(conditions):
        raise ValueError("Matrix conditions must be unique.")

    find_corpus = build_find_corpus()
    query_corpus = build_query_corpus()
    schedule = build_schedule(cases, conditions)
    basis = _campaign_basis(
        cases=cases,
        conditions=conditions,
        schedule=schedule,
        find_corpus=find_corpus,
        query_corpus=query_corpus,
    )
    fingerprint = _json_digest(basis)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        if not resume:
            raise ValueError(f"Output already exists; pass --resume: {output}")
        ledger = json.loads(output.read_text(encoding="utf-8"))
        if ledger.get("campaign_fingerprint") != fingerprint:
            raise ValueError("Existing ledger does not match this matrix definition.")
        attempts = list(ledger.get("attempts", []))
        started_at = str(ledger.get("started_at", _utc_now()))
    else:
        attempts = []
        started_at = _utc_now()

    by_case = {case.case_id: case for case in cases}
    completed = {
        str(attempt["cell_id"])
        for attempt in attempts
        if isinstance(attempt, Mapping) and attempt.get("cell_id")
    }
    ledger: dict[str, object] = {
        **basis,
        "campaign_fingerprint": fingerprint,
        "status": "RUNNING",
        "started_at": started_at,
        "updated_at": _utc_now(),
        "finished_at": None,
        "timeout_seconds": timeout,
        "attempts": attempts,
        "summary": summarize_attempts(attempts),
    }
    _atomic_write_json(output, ledger)

    total = len(schedule)
    for index, cell in enumerate(schedule, start=1):
        if cell["cell_id"] in completed:
            continue
        print(
            f"START {index}/{total} {cell['case_id']} "
            f"{cell['model']} {cell['effort']}",
            flush=True,
        )
        attempt = _run_cell(
            cell,
            by_case[cell["case_id"]],
            find_corpus=find_corpus,
            query_corpus=query_corpus,
            connector=connector,
            timeout=timeout,
        )
        attempts.append(attempt)
        ledger["attempts"] = attempts
        ledger["updated_at"] = _utc_now()
        ledger["summary"] = summarize_attempts(attempts)
        _atomic_write_json(output, ledger)
        timing = attempt["timing"]
        score = attempt.get("score")
        score_label = ""
        if isinstance(score, Mapping):
            metric = (
                score.get("historical_result_recall")
                if cell["operation"] == "find"
                else score.get("concept_recall")
            )
            if metric is not None:
                score_label = f" score={float(metric):.3f}"
        print(
            f"DONE  {index}/{total} {attempt['status']} "
            f"provider={float(timing['provider_seconds']):.3f}s{score_label}",
            flush=True,
        )

    ledger["status"] = "COMPLETED"
    ledger["updated_at"] = _utc_now()
    ledger["finished_at"] = _utc_now()
    ledger["summary"] = summarize_attempts(attempts)
    _atomic_write_json(output, ledger)
    return ledger


def rescore_campaign(
    output: Path,
    *,
    cases: Sequence[FindCase | QueryCase] = ALL_CASES,
    conditions: Sequence[MatrixCondition] = DEFAULT_CONDITIONS,
) -> dict[str, object]:
    """Reapply current diagnostics to retained answers without provider calls."""
    ledger = json.loads(output.read_text(encoding="utf-8"))
    if ledger.get("kind") != CAMPAIGN_KIND:
        raise ValueError("Ledger is not a Find/Query provider matrix.")
    find_corpus = build_find_corpus()
    query_corpus = build_query_corpus()
    schedule = build_schedule(cases, conditions)
    basis = _campaign_basis(
        cases=cases,
        conditions=conditions,
        schedule=schedule,
        find_corpus=find_corpus,
        query_corpus=query_corpus,
    )
    if ledger.get("schedule") != basis["schedule"]:
        raise ValueError("Ledger schedule differs from the current matrix.")
    if ledger.get("conditions") != basis["conditions"]:
        raise ValueError("Ledger conditions differ from the current matrix.")
    if ledger.get("corpora") != basis["corpora"]:
        raise ValueError("Ledger corpora differ from the current fixtures.")
    old_inputs = {
        (case["case_id"], case.get("query"), case.get("question"))
        for case in ledger.get("cases", [])
    }
    new_inputs = {
        (case["case_id"], case.get("query"), case.get("question"))
        for case in basis["cases"]
    }
    if old_inputs != new_inputs:
        raise ValueError("Ledger prompts differ from the current matrix cases.")

    query_by_id = {
        case.case_id: case for case in cases if isinstance(case, QueryCase)
    }
    attempts = ledger.get("attempts")
    if not isinstance(attempts, list):
        raise ValueError("Ledger attempts are invalid.")
    for attempt in attempts:
        if not isinstance(attempt, dict) or attempt.get("operation") != "query":
            continue
        answer = attempt.get("raw_response")
        case = query_by_id.get(str(attempt.get("case_id")))
        if case is None or not isinstance(answer, str) or not answer:
            continue
        attempt["score"] = score_query(case, answer)

    ledger.update(basis)
    ledger["campaign_fingerprint"] = _json_digest(basis)
    ledger["updated_at"] = _utc_now()
    ledger["rescored_at"] = _utc_now()
    ledger["rescoring_note"] = (
        "Scoring probes were broadened after raw-answer audit; prompts, "
        "provider outputs, statuses, and timings are unchanged."
    )
    ledger["summary"] = summarize_attempts(attempts)
    _atomic_write_json(output, ledger)
    return ledger


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=600)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--rescore", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.rescore:
        if args.resume:
            raise ValueError("Choose either --resume or --rescore, not both.")
        ledger = rescore_campaign(args.output)
    else:
        ledger = run_campaign(
            args.output,
            timeout=args.timeout,
            resume=args.resume,
        )
    summary = ledger["summary"]
    print(
        f"COMPLETED {summary['attempts']} cells: {summary['valid']} valid, "
        f"{summary['invalid_response']} invalid, "
        f"{summary['provider_error']} provider errors",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
