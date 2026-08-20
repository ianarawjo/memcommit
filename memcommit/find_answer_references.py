"""Pure citation rendering for one evidence-backed Find answer.

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


FIND_ANSWER_SENTENCE_LIMIT = 4_000
FIND_ANSWER_EVIDENCE_CONTENT_LIMIT = 100_000
FIND_ANSWER_METADATA_LIMIT = 2_000
FIND_ANSWER_UID_PREFIX_LENGTH = 8
_EVIDENCE_ALIAS_PATTERN = re.compile(r"[mcx][1-9][0-9]*\Z")
_HOST_CITATION_PATTERN = re.compile(r"\[[0-9]+\]")

FindAnswerEvidenceKind = Literal["memory", "ref", "query", "artifact"]


class FindAnswerReferenceError(ValueError):
    """Invalid evidence or answer input at the pure rendering boundary."""


def _bounded_nonblank_text(
    value: object,
    *,
    label: str,
    limit: int,
) -> str:
    if not isinstance(value, str):
        raise FindAnswerReferenceError(f"{label} must be text.")
    text = value.strip()
    if not text:
        raise FindAnswerReferenceError(f"{label} must be nonblank.")
    if len(text) > limit:
        raise FindAnswerReferenceError(
            f"{label} must be at most {limit} characters."
        )
    return text


@dataclass(frozen=True)
class FindAnswerEvidence:
    """One locally obtained source available to a three-sentence answer."""

    alias: str
    context_name: str
    kind: FindAnswerEvidenceKind
    uid: str
    content: str

    def __post_init__(self) -> None:
        alias = _bounded_nonblank_text(
            self.alias,
            label="Evidence alias",
            limit=FIND_ANSWER_METADATA_LIMIT,
        )
        if _EVIDENCE_ALIAS_PATTERN.fullmatch(alias) is None:
            raise FindAnswerReferenceError(
                "Evidence alias must look like m1, c1, or x1."
            )
        if self.kind not in {"memory", "ref", "query", "artifact"}:
            raise FindAnswerReferenceError("Invalid evidence kind.")
        object.__setattr__(self, "alias", alias)
        object.__setattr__(
            self,
            "context_name",
            _bounded_nonblank_text(
                self.context_name,
                label="Evidence Context",
                limit=FIND_ANSWER_METADATA_LIMIT,
            ),
        )
        object.__setattr__(
            self,
            "uid",
            _bounded_nonblank_text(
                self.uid,
                label="Evidence UID",
                limit=FIND_ANSWER_METADATA_LIMIT,
            ),
        )
        object.__setattr__(
            self,
            "content",
            _bounded_nonblank_text(
                self.content,
                label="Evidence content",
                limit=FIND_ANSWER_EVIDENCE_CONTENT_LIMIT,
            ),
        )


@dataclass(frozen=True)
class FindAnswerSentence:
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
                limit=FIND_ANSWER_SENTENCE_LIMIT,
            ),
        )
        if "\n" in self.text or "\r" in self.text:
            raise FindAnswerReferenceError(
                "Answer sentences cannot contain line breaks."
            )
        if _HOST_CITATION_PATTERN.search(self.text):
            raise FindAnswerReferenceError(
                "Answer sentences cannot contain host citation markers."
            )
        if isinstance(self.source_aliases, (str, bytes)):
            raise FindAnswerReferenceError(
                "Sentence sources must be an alias sequence."
            )
        try:
            aliases = tuple(self.source_aliases)
        except TypeError as error:
            raise FindAnswerReferenceError(
                "Sentence sources must be an alias sequence."
            ) from error
        if any(not isinstance(alias, str) for alias in aliases):
            raise FindAnswerReferenceError(
                "Sentence sources must contain text aliases."
            )
        if any(
            _EVIDENCE_ALIAS_PATTERN.fullmatch(alias) is None
            for alias in aliases
        ):
            raise FindAnswerReferenceError(
                "Sentence source aliases must look like m1, c1, or x1."
            )
        if len(set(aliases)) != len(aliases):
            raise FindAnswerReferenceError(
                "A sentence cannot cite the same alias twice."
            )
        object.__setattr__(self, "source_aliases", aliases)


@dataclass(frozen=True)
class NumberedFindAnswerReference:
    """One used evidence item with its stable display citation number."""

    number: int
    evidence: FindAnswerEvidence

    def __post_init__(self) -> None:
        if (
            not isinstance(self.number, int)
            or isinstance(self.number, bool)
            or self.number < 1
        ):
            raise FindAnswerReferenceError(
                "Reference number must be a positive integer."
            )
        if not isinstance(self.evidence, FindAnswerEvidence):
            raise FindAnswerReferenceError("Invalid numbered answer evidence.")


@dataclass(frozen=True)
class FindAnswerReferenceDocument:
    """Typed answer body and independently navigable citation blocks."""

    body: str
    references: tuple[NumberedFindAnswerReference, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.body, str) or not self.body.strip():
            raise FindAnswerReferenceError(
                "Rendered answer body must be nonblank text."
            )
        if not isinstance(self.references, tuple) or any(
            not isinstance(reference, NumberedFindAnswerReference)
            for reference in self.references
        ):
            raise FindAnswerReferenceError(
                "Rendered answer references must be typed."
            )
        if tuple(reference.number for reference in self.references) != tuple(
            range(1, len(self.references) + 1)
        ):
            raise FindAnswerReferenceError(
                "Rendered answer reference numbers must be contiguous."
            )
        aliases = tuple(reference.evidence.alias for reference in self.references)
        if len(set(aliases)) != len(aliases):
            raise FindAnswerReferenceError(
                "Rendered answer references must use distinct evidence aliases."
            )

    @property
    def text(self) -> str:
        references = "\n".join(
            render_numbered_find_answer_reference(reference)
            for reference in self.references
        )
        if references:
            return f"{self.body}\n\nReferences\n{references}"
        return f"{self.body}\n\nReferences"


def render_numbered_find_answer_reference(
    reference: NumberedFindAnswerReference,
) -> str:
    """Render one typed citation row without losing its navigation identity."""

    if not isinstance(reference, NumberedFindAnswerReference):
        raise FindAnswerReferenceError("Invalid numbered answer reference.")
    return _render_reference(reference.number, reference.evidence)


def build_find_answer_reference_document(
    evidence: Sequence[FindAnswerEvidence],
    sentences: Sequence[FindAnswerSentence],
) -> FindAnswerReferenceDocument:
    """Validate and retain the same structure used by the plain-text renderer."""

    if isinstance(evidence, (str, bytes)):
        raise FindAnswerReferenceError("Evidence must be a sequence.")
    if isinstance(sentences, (str, bytes)):
        raise FindAnswerReferenceError("Answer sentences must be a sequence.")
    try:
        evidence_items = tuple(evidence)
        sentence_items = tuple(sentences)
    except TypeError as error:
        raise FindAnswerReferenceError(
            "Evidence and answer sentences must be sequences."
        ) from error
    if any(not isinstance(item, FindAnswerEvidence) for item in evidence_items):
        raise FindAnswerReferenceError("Invalid Find answer evidence.")
    if any(
        not isinstance(sentence, FindAnswerSentence) for sentence in sentence_items
    ):
        raise FindAnswerReferenceError("Invalid Find answer sentence.")
    if len(sentence_items) != 3:
        raise FindAnswerReferenceError(
            "A Find answer must contain exactly three sentences."
        )

    by_alias: dict[str, FindAnswerEvidence] = {}
    for item in evidence_items:
        if item.alias in by_alias:
            raise FindAnswerReferenceError(f"Duplicate evidence alias: {item.alias}")
        by_alias[item.alias] = item

    citation_numbers: dict[str, int] = {}
    rendered_sentences: list[str] = []
    for sentence in sentence_items:
        markers: list[str] = []
        for alias in sentence.source_aliases:
            if alias not in by_alias:
                raise FindAnswerReferenceError(f"Unknown evidence alias: {alias}")
            number = citation_numbers.setdefault(alias, len(citation_numbers) + 1)
            markers.append(f"[{number}]")
        marker_suffix = f" {' '.join(markers)}" if markers else ""
        rendered_sentences.append(f"{sentence.text}{marker_suffix}")

    references = tuple(
        NumberedFindAnswerReference(number, by_alias[alias])
        for alias, number in citation_numbers.items()
    )
    return FindAnswerReferenceDocument(
        body=" ".join(rendered_sentences),
        references=references,
    )


def render_find_answer_references(
    evidence: Sequence[FindAnswerEvidence],
    sentences: Sequence[FindAnswerSentence],
) -> str:
    """Render exactly three answer sentences and their used references.

    Reference numbers are assigned by the first citation occurrence while
    walking the sentences from first to third.  Reusing an alias in a later
    sentence therefore reuses its original number.
    """
    return build_find_answer_reference_document(evidence, sentences).text


def _render_reference(
    number: int,
    evidence: FindAnswerEvidence,
) -> str:
    return render_source_reference_row(
        SourceReferenceRow(
            number=number,
            content=evidence.content,
            uid=evidence.uid,
            context_name=evidence.context_name,
            alias=evidence.alias,
        ),
        uid_prefix_length=FIND_ANSWER_UID_PREFIX_LENGTH,
    )
