"""Pure citation rendering for one evidence-backed Search answer.

This module deliberately knows nothing about terminal presentation, providers,
or storage.  In particular, it does not sanitize terminal controls: the
controller or shell that ultimately displays the returned text owns that
boundary.  Query evidence is already-public projection data supplied by the
caller; this layer never dereferences a query-only source.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Sequence

from memcommit.source_projection.model import SourceReferenceRow
from memcommit.source_projection.presentation import render_source_reference_row


SEARCH_ANSWER_SENTENCE_LIMIT = 4_000
SEARCH_ANSWER_EVIDENCE_CONTENT_LIMIT = 100_000
SEARCH_ANSWER_METADATA_LIMIT = 2_000
SEARCH_ANSWER_UID_PREFIX_LENGTH = 8
_EVIDENCE_ALIAS_PATTERN = re.compile(r"[mcx][1-9][0-9]*\Z")
_HOST_CITATION_PATTERN = re.compile(r"\[[0-9]+\]")

SearchAnswerEvidenceKind = Literal["memory", "ref", "query", "artifact"]


class SearchAnswerReferenceError(ValueError):
    """Invalid evidence or answer input at the pure rendering boundary."""


def _bounded_nonblank_text(
    value: object,
    *,
    label: str,
    limit: int,
) -> str:
    if not isinstance(value, str):
        raise SearchAnswerReferenceError(f"{label} must be text.")
    text = value.strip()
    if not text:
        raise SearchAnswerReferenceError(f"{label} must be nonblank.")
    if len(text) > limit:
        raise SearchAnswerReferenceError(f"{label} must be at most {limit} characters.")
    return text


@dataclass(frozen=True)
class SearchAnswerEvidence:
    """One locally obtained source available to a three-sentence answer."""

    alias: str
    context_name: str
    kind: SearchAnswerEvidenceKind
    uid: str
    content: str

    def __post_init__(self) -> None:
        alias = _bounded_nonblank_text(
            self.alias,
            label="Evidence alias",
            limit=SEARCH_ANSWER_METADATA_LIMIT,
        )
        if _EVIDENCE_ALIAS_PATTERN.fullmatch(alias) is None:
            raise SearchAnswerReferenceError(
                "Evidence alias must look like m1, c1, or x1."
            )
        if self.kind not in {"memory", "ref", "query", "artifact"}:
            raise SearchAnswerReferenceError("Invalid evidence kind.")
        object.__setattr__(self, "alias", alias)
        object.__setattr__(
            self,
            "context_name",
            _bounded_nonblank_text(
                self.context_name,
                label="Evidence Context",
                limit=SEARCH_ANSWER_METADATA_LIMIT,
            ),
        )
        object.__setattr__(
            self,
            "uid",
            _bounded_nonblank_text(
                self.uid,
                label="Evidence UID",
                limit=SEARCH_ANSWER_METADATA_LIMIT,
            ),
        )
        object.__setattr__(
            self,
            "content",
            _bounded_nonblank_text(
                self.content,
                label="Evidence content",
                limit=SEARCH_ANSWER_EVIDENCE_CONTENT_LIMIT,
            ),
        )


@dataclass(frozen=True)
class SearchAnswerSentence:
    """One answer sentence and the local evidence aliases supporting it."""

    text: str
    source_aliases: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "text",
            _bounded_nonblank_text(
                self.text,
                label="Answer sentence",
                limit=SEARCH_ANSWER_SENTENCE_LIMIT,
            ),
        )
        if "\n" in self.text or "\r" in self.text:
            raise SearchAnswerReferenceError(
                "Answer sentences cannot contain line breaks."
            )
        if _HOST_CITATION_PATTERN.search(self.text):
            raise SearchAnswerReferenceError(
                "Answer sentences cannot contain host citation markers."
            )
        if isinstance(self.source_aliases, (str, bytes)):
            raise SearchAnswerReferenceError(
                "Sentence sources must be an alias sequence."
            )
        try:
            aliases = tuple(self.source_aliases)
        except TypeError as error:
            raise SearchAnswerReferenceError(
                "Sentence sources must be an alias sequence."
            ) from error
        if any(not isinstance(alias, str) for alias in aliases):
            raise SearchAnswerReferenceError(
                "Sentence sources must contain text aliases."
            )
        if any(_EVIDENCE_ALIAS_PATTERN.fullmatch(alias) is None for alias in aliases):
            raise SearchAnswerReferenceError(
                "Sentence source aliases must look like m1, c1, or x1."
            )
        if len(set(aliases)) != len(aliases):
            raise SearchAnswerReferenceError(
                "A sentence cannot cite the same alias twice."
            )
        object.__setattr__(self, "source_aliases", aliases)


@dataclass(frozen=True)
class NumberedSearchAnswerReference:
    """One used evidence item with its stable display citation number."""

    number: int
    evidence: SearchAnswerEvidence

    def __post_init__(self) -> None:
        if (
            not isinstance(self.number, int)
            or isinstance(self.number, bool)
            or self.number < 1
        ):
            raise SearchAnswerReferenceError(
                "Reference number must be a positive integer."
            )
        if not isinstance(self.evidence, SearchAnswerEvidence):
            raise SearchAnswerReferenceError("Invalid numbered answer evidence.")


@dataclass(frozen=True)
class SearchAnswerReferenceDocument:
    """Typed answer body and independently navigable citation blocks."""

    body: str
    references: tuple[NumberedSearchAnswerReference, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.body, str) or not self.body.strip():
            raise SearchAnswerReferenceError(
                "Rendered answer body must be nonblank text."
            )
        if not isinstance(self.references, tuple) or any(
            not isinstance(reference, NumberedSearchAnswerReference)
            for reference in self.references
        ):
            raise SearchAnswerReferenceError(
                "Rendered answer references must be typed."
            )
        if tuple(reference.number for reference in self.references) != tuple(
            range(1, len(self.references) + 1)
        ):
            raise SearchAnswerReferenceError(
                "Rendered answer reference numbers must be contiguous."
            )
        aliases = tuple(reference.evidence.alias for reference in self.references)
        if len(set(aliases)) != len(aliases):
            raise SearchAnswerReferenceError(
                "Rendered answer references must use distinct evidence aliases."
            )

    @property
    def text(self) -> str:
        references = "\n".join(
            render_numbered_search_answer_reference(reference)
            for reference in self.references
        )
        if references:
            return f"{self.body}\n\nReferences\n{references}"
        return f"{self.body}\n\nReferences"


def render_numbered_search_answer_reference(
    reference: NumberedSearchAnswerReference,
) -> str:
    """Render one typed citation row without losing its navigation identity."""

    if not isinstance(reference, NumberedSearchAnswerReference):
        raise SearchAnswerReferenceError("Invalid numbered answer reference.")
    return _render_reference(reference.number, reference.evidence)


def build_search_answer_reference_document(
    evidence: Sequence[SearchAnswerEvidence],
    sentences: Sequence[SearchAnswerSentence],
) -> SearchAnswerReferenceDocument:
    """Validate and retain the same structure used by the plain-text renderer."""

    if isinstance(evidence, (str, bytes)):
        raise SearchAnswerReferenceError("Evidence must be a sequence.")
    if isinstance(sentences, (str, bytes)):
        raise SearchAnswerReferenceError("Answer sentences must be a sequence.")
    try:
        evidence_items = tuple(evidence)
        sentence_items = tuple(sentences)
    except TypeError as error:
        raise SearchAnswerReferenceError(
            "Evidence and answer sentences must be sequences."
        ) from error
    if any(not isinstance(item, SearchAnswerEvidence) for item in evidence_items):
        raise SearchAnswerReferenceError("Invalid Search answer evidence.")
    if any(
        not isinstance(sentence, SearchAnswerSentence) for sentence in sentence_items
    ):
        raise SearchAnswerReferenceError("Invalid Search answer sentence.")
    if len(sentence_items) != 3:
        raise SearchAnswerReferenceError(
            "A Search answer must contain exactly three sentences."
        )

    by_alias: dict[str, SearchAnswerEvidence] = {}
    for item in evidence_items:
        if item.alias in by_alias:
            raise SearchAnswerReferenceError(f"Duplicate evidence alias: {item.alias}")
        by_alias[item.alias] = item

    citation_numbers: dict[str, int] = {}
    rendered_sentences: list[str] = []
    for sentence in sentence_items:
        markers: list[str] = []
        for alias in sentence.source_aliases:
            if alias not in by_alias:
                raise SearchAnswerReferenceError(f"Unknown evidence alias: {alias}")
            number = citation_numbers.setdefault(alias, len(citation_numbers) + 1)
            markers.append(f"[{number}]")
        marker_suffix = f" {' '.join(markers)}" if markers else ""
        rendered_sentences.append(f"{sentence.text}{marker_suffix}")

    references = tuple(
        NumberedSearchAnswerReference(number, by_alias[alias])
        for alias, number in citation_numbers.items()
    )
    return SearchAnswerReferenceDocument(
        body=" ".join(rendered_sentences),
        references=references,
    )


def render_search_answer_references(
    evidence: Sequence[SearchAnswerEvidence],
    sentences: Sequence[SearchAnswerSentence],
) -> str:
    """Render exactly three answer sentences and their used references.

    Reference numbers are assigned by the first citation occurrence while
    walking the sentences from first to third.  Reusing an alias in a later
    sentence therefore reuses its original number.
    """
    return build_search_answer_reference_document(evidence, sentences).text


def _render_reference(
    number: int,
    evidence: SearchAnswerEvidence,
) -> str:
    return render_source_reference_row(
        SourceReferenceRow(
            number=number,
            content=evidence.content,
            uid=evidence.uid,
            context_name=evidence.context_name,
            alias=evidence.alias,
        ),
        uid_prefix_length=SEARCH_ANSWER_UID_PREFIX_LENGTH,
    )
