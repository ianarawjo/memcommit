"""Terminal-independent application boundary for ordinary Query answers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from memcommit.find_answer_references import FindAnswerReferenceDocument
from memcommit.find_scope_evidence import (
    compact_artifact_references,
    compact_reference_content,
    visible_result_evidence,
)
from memcommit.ordinary_query_answer import (
    build_ordinary_query_reference_document,
    complete_ordinary_query_answer,
    prepare_ordinary_query_answer,
)
from memcommit.search import SearchCandidate


OrdinaryQueryStage = Literal[
    "INPUTS_FROZEN",
    "CONNECTING_PROVIDER",
    "ANSWERING",
]


@dataclass(frozen=True)
class OrdinaryQueryRequest:
    """One grounded answer request over an exact readable Context set."""

    question: str
    target_names: tuple[str, ...]
    include_descendants: bool = False
    follow_embeds: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.question, str) or not self.question.strip():
            raise ValueError("Enter a nonblank Query question.")
        if (
            not self.target_names
            or len(set(self.target_names)) != len(self.target_names)
            or any(not isinstance(name, str) or not name for name in self.target_names)
        ):
            raise ValueError("Select at least one distinct readable Context.")
        if not isinstance(self.include_descendants, bool) or not isinstance(
            self.follow_embeds, bool
        ):
            raise ValueError("Query scope choices must be explicit booleans.")


@dataclass(frozen=True)
class OrdinaryQueryResponse:
    """One read-only answer tied to the exact request and frozen evidence."""

    request: OrdinaryQueryRequest
    answer: str
    grounded: bool
    reference_document: FindAnswerReferenceDocument | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.request, OrdinaryQueryRequest):
            raise ValueError("Ordinary Query response requires its frozen request.")
        if not isinstance(self.answer, str) or not self.answer.strip():
            raise ValueError("Ordinary Query returned an empty answer.")
        if not isinstance(self.grounded, bool):
            raise ValueError("Ordinary Query grounded state must be boolean.")
        if self.reference_document is not None:
            if not isinstance(
                self.reference_document,
                FindAnswerReferenceDocument,
            ):
                raise ValueError("Ordinary Query reference document is invalid.")
            if not self.grounded:
                raise ValueError(
                    "An ungrounded Query cannot expose evidence references."
                )
            if self.reference_document.text != self.answer:
                raise ValueError(
                    "Ordinary Query answer and reference document disagree."
                )


@dataclass(frozen=True)
class FrozenOrdinaryQuerySource:
    """One authorized, complete candidate frame frozen before provider use."""

    label: str
    candidates: tuple[SearchCandidate, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.label, str) or not self.label.strip():
            raise ValueError("Ordinary Query source requires a display label.")
        if not isinstance(self.candidates, tuple) or any(
            not isinstance(candidate, SearchCandidate) for candidate in self.candidates
        ):
            raise ValueError("Ordinary Query source candidates must be frozen.")


class OrdinaryQuerySourcePort(Protocol):
    """Freeze readable evidence before semantic provider construction."""

    def freeze(self, request: OrdinaryQueryRequest) -> FrozenOrdinaryQuerySource:
        """Return the complete authorized candidate frame for one request."""


class OrdinaryQueryProvider(Protocol):
    def complete(
        self,
        prompt: str,
        *,
        operation: str,
        output_schema: dict[str, object] | None = None,
    ) -> str: ...


class OrdinaryQueryProviderFactory(Protocol):
    """Construct a provider only after source freezing and preflight."""

    def __call__(self) -> OrdinaryQueryProvider: ...


class OrdinaryQueryObserver(Protocol):
    def __call__(self, stage: OrdinaryQueryStage) -> None: ...


def _observe(
    observer: OrdinaryQueryObserver | None,
    stage: OrdinaryQueryStage,
) -> None:
    if observer is not None:
        observer(stage)


def run_ordinary_query(
    request: OrdinaryQueryRequest,
    *,
    source_port: OrdinaryQuerySourcePort,
    provider_factory: OrdinaryQueryProviderFactory,
    observer: OrdinaryQueryObserver | None = None,
) -> OrdinaryQueryResponse:
    """Answer once without argv, terminal, session, or persistence concerns."""

    frozen = source_port.freeze(request)
    _observe(observer, "INPUTS_FROZEN")
    if not frozen.candidates:
        return OrdinaryQueryResponse(
            request,
            f"{frozen.label}\n  (no grounded answer found)",
            False,
        )

    # Whole-frame preflight must complete before provider construction. Query
    # cannot silently rank or batch away evidence merely to fit one turn.
    evidence = visible_result_evidence(frozen.candidates)
    plan = prepare_ordinary_query_answer(request.question, evidence)
    _observe(observer, "CONNECTING_PROVIDER")
    provider = provider_factory()
    _observe(observer, "ANSWERING")
    answer = complete_ordinary_query_answer(plan, provider)
    if not answer.grounded:
        rendered = answer.text
        if answer.outcome_kind == "NO_ANSWER":
            rendered = f"{frozen.label}\n  {rendered}"
        return OrdinaryQueryResponse(
            request,
            rendered,
            False,
        )

    reference_document = build_ordinary_query_reference_document(
        compact_reference_content(
            compact_artifact_references(evidence, frozen.candidates)
        ),
        answer,
    )
    return OrdinaryQueryResponse(
        request,
        reference_document.text,
        True,
        reference_document,
    )


__all__ = [
    "FrozenOrdinaryQuerySource",
    "OrdinaryQueryObserver",
    "OrdinaryQueryProvider",
    "OrdinaryQueryProviderFactory",
    "OrdinaryQueryRequest",
    "OrdinaryQueryResponse",
    "OrdinaryQuerySourcePort",
    "OrdinaryQueryStage",
    "run_ordinary_query",
]
