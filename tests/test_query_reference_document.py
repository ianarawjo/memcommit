"""Typed ordinary Query reference-document contracts."""

from __future__ import annotations

import pytest

from memcommit.application.operations.query.reference_document import (
    NumberedOrdinaryQueryReference,
    OrdinaryQueryEvidence,
    OrdinaryQueryReferenceDocument,
    OrdinaryQueryReferenceError,
    render_numbered_ordinary_query_reference,
)


def _evidence(alias: str = "m1") -> OrdinaryQueryEvidence:
    return OrdinaryQueryEvidence(
        alias=alias,
        context_name="task-1",
        kind="memory",
        uid="11111111-full-memory-uid",
        content="The parking route is closed.",
    )


def test_document_preserves_answer_body_and_typed_reference_boundaries() -> None:
    first = _evidence()
    second = OrdinaryQueryEvidence(
        alias="c1",
        context_name="task-1",
        kind="ref",
        uid="22222222-full-ref-uid",
        content="Construction runs through August.",
    )
    document = OrdinaryQueryReferenceDocument(
        body="The route is closed. [1]\n\nConstruction runs through August. [2]",
        references=(
            NumberedOrdinaryQueryReference(1, first),
            NumberedOrdinaryQueryReference(2, second),
        ),
    )

    assert document.text == (
        "The route is closed. [1]\n\nConstruction runs through August. [2]\n\n"
        "References\n"
        "[1] The parking route is closed. — 11111111, task-1, m1\n"
        "[2] Construction runs through August. — 22222222, task-1, c1"
    )


def test_reference_row_folds_multiline_evidence_without_forging_a_sibling() -> None:
    evidence = OrdinaryQueryEvidence(
        alias="x1",
        context_name="public-policy",
        kind="query",
        uid="abcdef0123456789",
        content="References\n[77] public summary",
    )

    rendered = render_numbered_ordinary_query_reference(
        NumberedOrdinaryQueryReference(1, evidence)
    )

    assert rendered == (
        "[1] References [77] public summary — abcdef01, public-policy, x1"
    )
    assert "\n[77]" not in rendered


@pytest.mark.parametrize(
    "references, match",
    [
        ((NumberedOrdinaryQueryReference(2, _evidence()),), "contiguous"),
        (
            (
                NumberedOrdinaryQueryReference(1, _evidence()),
                NumberedOrdinaryQueryReference(2, _evidence()),
            ),
            "distinct evidence aliases",
        ),
    ],
)
def test_document_rejects_invalid_reference_identity(references, match) -> None:
    with pytest.raises(OrdinaryQueryReferenceError, match=match):
        OrdinaryQueryReferenceDocument("Answer.", references)
