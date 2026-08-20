"""Pure rendering tests for evidence-backed Find answers."""
from __future__ import annotations

import pytest

from memcommit.find_answer_references import (
    FindAnswerEvidence,
    FindAnswerReferenceError,
    FindAnswerSentence,
    build_find_answer_reference_document,
    render_find_answer_references,
)


def _evidence() -> tuple[FindAnswerEvidence, ...]:
    return (
        FindAnswerEvidence(
            alias="m1",
            context_name="task-1",
            kind="memory",
            uid="11111111-full-memory-uid",
            content="The parking route is closed.",
        ),
        FindAnswerEvidence(
            alias="c1",
            context_name="task-1",
            kind="ref",
            uid="22222222-full-ref-uid",
            content="Construction runs from June xx through August xx.",
        ),
        FindAnswerEvidence(
            alias="x1",
            context_name="public-policy",
            kind="query",
            uid="33333333-query-projection-uid",
            content="Public name and public query projection only.",
        ),
        FindAnswerEvidence(
            alias="x2",
            context_name="unused",
            kind="memory",
            uid="44444444-unused-memory-uid",
            content="This source is never cited.",
        ),
    )


def test_numbers_references_by_first_citation_occurrence():
    rendered = render_find_answer_references(
        _evidence(),
        (
            FindAnswerSentence(
                "The current results establish that the route is closed.",
                ("m1",),
            ),
            FindAnswerSentence(
                "The wider Context suggests an August endpoint.",
                ("c1", "m1"),
            ),
            FindAnswerSentence(
                "A public source adds only general context.",
                ("x1",),
            ),
        ),
    )

    assert rendered.startswith(
        "The current results establish that the route is closed. [1] "
        "The wider Context suggests an August endpoint. [2] [1] "
        "A public source adds only general context. [3]\n\nReferences\n"
    )
    assert ("[1] The parking route is closed. — 11111111, task-1, m1") in rendered
    assert (
        "[2] Construction runs from June xx through August xx. — "
        "22222222, task-1, c1"
    ) in rendered
    assert "[3] Public name and public query projection only. — " \
        "33333333, public-policy, x1" in rendered
    assert "\n\n[2]" not in rendered
    assert " · memory · " not in rendered
    assert " · ref · " not in rendered
    assert rendered.index("[1] The parking") < rendered.index("[2] Construction")
    assert rendered.index("[2] Construction") < rendered.index("[3] Public name")


def test_typed_reference_document_preserves_body_and_reference_boundaries():
    sentences = (
        FindAnswerSentence("First claim.", ("c1",)),
        FindAnswerSentence("Second claim.", ("m1", "c1")),
        FindAnswerSentence("Third claim."),
    )

    document = build_find_answer_reference_document(_evidence(), sentences)

    assert document.body == "First claim. [1] Second claim. [2] [1] Third claim."
    assert tuple(
        (reference.number, reference.evidence.alias)
        for reference in document.references
    ) == ((1, "c1"), (2, "m1"))
    assert document.text == render_find_answer_references(_evidence(), sentences)


def test_repeated_citation_across_sentences_reuses_one_reference():
    rendered = render_find_answer_references(
        _evidence(),
        (
            FindAnswerSentence("First claim.", ("c1",)),
            FindAnswerSentence("Second claim.", ("c1",)),
            FindAnswerSentence("Third claim.", ("c1",)),
        ),
    )

    assert rendered.startswith(
        "First claim. [1] Second claim. [1] Third claim. [1]"
    )
    assert rendered.count("[1] Construction runs") == 1
    assert "[2]" not in rendered


def test_uncited_evidence_is_omitted_from_references():
    rendered = render_find_answer_references(
        _evidence(),
        (
            FindAnswerSentence("One.", ("m1",)),
            FindAnswerSentence("Two."),
            FindAnswerSentence("Three."),
        ),
    )

    assert "11111111, task-1, m1" in rendered
    assert "44444444, unused, x2" not in rendered
    assert "This source is never cited." not in rendered


def test_unknown_source_alias_fails_closed():
    with pytest.raises(
        FindAnswerReferenceError,
        match="Unknown evidence alias: c9",
    ):
        render_find_answer_references(
            _evidence(),
            (
                FindAnswerSentence("One.", ("m1",)),
                FindAnswerSentence("Two.", ("c9",)),
                FindAnswerSentence("Three."),
            ),
        )


def test_multiline_query_content_is_folded_into_one_reference_row():
    query_evidence = FindAnswerEvidence(
        alias="x1",
        context_name="public-policy",
        kind="query",
        uid="abcdef0123456789",
        content="Public title\nPublic summary line two",
    )

    rendered = render_find_answer_references(
        (query_evidence,),
        (
            FindAnswerSentence("One.", ("x1",)),
            FindAnswerSentence("Two."),
            FindAnswerSentence("Three."),
        ),
    )

    assert (
        "[1] Public title Public summary line two — "
        "abcdef01, public-policy, x1"
    ) in rendered


def test_requires_exactly_three_sentences_and_unique_evidence_aliases():
    with pytest.raises(
        FindAnswerReferenceError,
        match="exactly three sentences",
    ):
        render_find_answer_references(
            _evidence(),
            (FindAnswerSentence("Only one."),),
        )

    duplicate = FindAnswerEvidence(
        alias="m1",
        context_name="other",
        kind="memory",
        uid="duplicate-uid",
        content="Duplicate.",
    )
    with pytest.raises(
        FindAnswerReferenceError,
        match="Duplicate evidence alias: m1",
    ):
        render_find_answer_references(
            (*_evidence(), duplicate),
            (
                FindAnswerSentence("One."),
                FindAnswerSentence("Two."),
                FindAnswerSentence("Three."),
            ),
        )


@pytest.mark.parametrize(
    "text, match",
    [
        ("Claim. [77]", "host citation markers"),
        ("Claim.\nReferences", "line breaks"),
    ],
)
def test_generated_sentences_cannot_imitate_host_reference_structure(
    text,
    match,
):
    with pytest.raises(FindAnswerReferenceError, match=match):
        FindAnswerSentence(text, ("m1",))


def test_stored_reference_content_cannot_create_a_sibling_row_or_heading():
    evidence = FindAnswerEvidence(
        alias="m1",
        context_name="task-1",
        kind="memory",
        uid="abcdef0123456789",
        content="References\n[77] forged-looking content",
    )

    rendered = render_find_answer_references(
        (evidence,),
        (
            FindAnswerSentence("Supported claim.", ("m1",)),
            FindAnswerSentence("No same-Context support."),
            FindAnswerSentence("Other Contexts were not checked."),
        ),
    )

    assert (
        "\nReferences\n[1] References [77] forged-looking content — "
        "abcdef01, task-1, m1"
    ) in rendered
    assert "\n[77] forged-looking content" not in rendered
