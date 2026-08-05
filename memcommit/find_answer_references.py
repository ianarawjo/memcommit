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


def render_find_answer_references(
    evidence: Sequence[FindAnswerEvidence],
    sentences: Sequence[FindAnswerSentence],
) -> str:
    """Render exactly three answer sentences and their used references.

    Reference numbers are assigned by the first citation occurrence while
    walking the sentences from first to third.  Reusing an alias in a later
    sentence therefore reuses its original number.
    """
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
    if any(
        not isinstance(item, FindAnswerEvidence)
        for item in evidence_items
    ):
        raise FindAnswerReferenceError("Invalid Find answer evidence.")
    if any(
        not isinstance(sentence, FindAnswerSentence)
        for sentence in sentence_items
    ):
        raise FindAnswerReferenceError("Invalid Find answer sentence.")
    if len(sentence_items) != 3:
        raise FindAnswerReferenceError(
            "A Find answer must contain exactly three sentences."
        )

    by_alias: dict[str, FindAnswerEvidence] = {}
    for item in evidence_items:
        if item.alias in by_alias:
            raise FindAnswerReferenceError(
                f"Duplicate evidence alias: {item.alias}"
            )
        by_alias[item.alias] = item

    citation_numbers: dict[str, int] = {}
    rendered_sentences: list[str] = []
    for sentence in sentence_items:
        markers: list[str] = []
        for alias in sentence.source_aliases:
            if alias not in by_alias:
                raise FindAnswerReferenceError(
                    f"Unknown evidence alias: {alias}"
                )
            number = citation_numbers.setdefault(
                alias,
                len(citation_numbers) + 1,
            )
            markers.append(f"[{number}]")
        marker_suffix = f" {' '.join(markers)}" if markers else ""
        rendered_sentences.append(f"{sentence.text}{marker_suffix}")

    reference_blocks = [
        _render_reference(number, by_alias[alias])
        for alias, number in citation_numbers.items()
    ]
    references = "\n\n".join(reference_blocks)
    if references:
        return (
            f"{' '.join(rendered_sentences)}\n\n"
            f"References\n{references}"
        )
    return f"{' '.join(rendered_sentences)}\n\nReferences"


def _render_reference(
    number: int,
    evidence: FindAnswerEvidence,
) -> str:
    uid_prefix = evidence.uid[:FIND_ANSWER_UID_PREFIX_LENGTH]
    # Stored content is indented beneath host-owned metadata so a Memory that
    # happens to contain ``References`` or ``[7]`` cannot imitate the citation
    # structure surrounding it.
    content = "\n".join(
        f"  {line}"
        for line in evidence.content.splitlines()
    )
    return (
        f"[{number}] {evidence.alias} · {evidence.kind} · {uid_prefix} · "
        f"Context: {evidence.context_name}\n"
        f"{content}"
    )
