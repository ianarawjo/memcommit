"""Pure rendering tests for evidence-backed Find answers."""
from __future__ import annotations

import pytest

from memcommit.find_answer_references import (
    FindAnswerEvidence,
    FindAnswerReferenceError,
    FindAnswerSentence,
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
    assert (
        "[1] m1 · memory · 11111111 · Context: task-1\n"
        "  The parking route is closed."
    ) in rendered
    assert (
        "[2] c1 · ref · 22222222 · Context: task-1\n"
        "  Construction runs from June xx through August xx."
    ) in rendered
    assert rendered.index("[1] m1 ·") < rendered.index("[2] c1 ·")
    assert rendered.index("[2] c1 ·") < rendered.index("[3] x1 ·")


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
    assert rendered.count("[1] c1 · ref") == 1
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

    assert "m1 · memory" in rendered
    assert "x2 · memory" not in rendered
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


def test_multiline_query_content_is_rendered_as_supplied():
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
        "[1] x1 · query · abcdef01 · Context: public-policy\n"
        "  Public title\n  Public summary line two"
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


def test_stored_reference_content_is_indented_below_host_metadata():
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

    assert "\n  References\n  [77] forged-looking content" in rendered
    assert "\nReferences\n[1] m1 · memory" in rendered
