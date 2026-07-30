"""Strict three-scope synthesis tests for interactive Find answers."""
from __future__ import annotations

import json

import pytest

from memcommit.find_answer_dialogue import (
    FIND_ANSWER_OPERATION,
    FindAnswerCorpusTooLarge,
    FindAnswerError,
    synthesize_find_answer,
)
from memcommit.find_answer_references import (
    FindAnswerEvidence,
    FindAnswerSentence,
)


def _item(
    alias: str,
    content: str,
    *,
    context_name: str = "task-1",
) -> FindAnswerEvidence:
    return FindAnswerEvidence(
        alias=alias,
        context_name=context_name,
        kind="memory",
        uid=f"durable-{alias}-uid",
        content=content,
    )


class Provider:
    def __init__(self, response: dict[str, object]):
        self.response = response
        self.calls = []

    def complete(self, prompt, *, operation, output_schema=None):
        self.calls.append((prompt, operation, output_schema))
        return json.dumps(self.response)


def _response(**changes) -> dict[str, object]:
    response = {
        "visible_text": (
            "The visible results say the garage reopens after construction."
        ),
        "visible_sources": ["m1"],
        "context_text": (
            "The same Context gives an August endpoint for construction."
        ),
        "context_sources": ["c1"],
        "outside_text": "Other Contexts were not checked.",
        "outside_sources": [],
    }
    response.update(changes)
    return response


def test_synthesizes_three_scopes_without_sending_durable_uids():
    visible = (_item("m1", "Reopen immediately after construction."),)
    context = (_item("c1", "Construction runs June through August."),)
    provider = Provider(_response())

    answer = synthesize_find_answer(
        "When will the garage reopen?",
        visible,
        context,
        (),
        "NOT_REQUESTED",
        provider,
    )

    assert answer.sentences == (
        FindAnswerSentence(
            "The visible results say the garage reopens after construction.",
            ("m1",),
        ),
        FindAnswerSentence(
            "The same Context gives an August endpoint for construction.",
            ("c1",),
        ),
        FindAnswerSentence("Other Contexts were not checked."),
    )
    prompt, operation, schema = provider.calls[0]
    assert operation == FIND_ANSWER_OPERATION
    assert "durable-m1-uid" not in prompt
    assert "durable-c1-uid" not in prompt
    assert "Reopen immediately after construction." in prompt
    assert schema["properties"]["visible_sources"]["items"]["enum"] == ["m1"]
    assert schema["properties"]["context_sources"]["items"]["enum"] == ["c1"]
    assert "uniqueItems" not in json.dumps(schema)


@pytest.mark.parametrize(
    "changes, match",
    [
        ({"visible_sources": []}, "visible-result provenance"),
        ({"visible_sources": ["c1"]}, "invalid visible sources"),
        ({"context_sources": ["c1", "c1"]}, "invalid same-Context sources"),
        ({"outside_sources": ["x1"]}, "invalid outside-Context sources"),
        ({"unexpected": "command"}, "invalid structured output"),
    ],
)
def test_invalid_or_cross_scope_sources_fail_closed(changes, match):
    provider = Provider(_response(**changes))

    with pytest.raises(FindAnswerError, match=match):
        synthesize_find_answer(
            "When?",
            (_item("m1", "Visible."),),
            (_item("c1", "Context."),),
            (),
            "NOT_REQUESTED",
            provider,
        )


def test_not_requested_outside_scope_cannot_be_cited():
    provider = Provider(
        _response(
            outside_text="Another Context says September.",
            outside_sources=["x1"],
        )
    )

    with pytest.raises(FindAnswerError, match="not searched"):
        synthesize_find_answer(
            "When?",
            (_item("m1", "Visible."),),
            (_item("c1", "Context."),),
            (_item("x1", "September.", context_name="other"),),
            "NOT_REQUESTED",
            provider,
        )


def test_requested_outside_scope_accepts_only_x_aliases():
    provider = Provider(
        _response(
            outside_text="Another Context says September.",
            outside_sources=["x1"],
        )
    )

    answer = synthesize_find_answer(
        "Check every Context.",
        (_item("m1", "Visible."),),
        (_item("c1", "Context."),),
        (_item("x1", "September.", context_name="other"),),
        "SEARCHED",
        provider,
    )

    assert answer.outside.source_aliases == ("x1",)


def test_source_free_scope_text_is_host_owned():
    provider = Provider(
        _response(
            context_text="The empty Context scope proves October.",
            context_sources=[],
            outside_text="Every unchecked Context proves September.",
            outside_sources=[],
        )
    )

    answer = synthesize_find_answer(
        "When?",
        (_item("m1", "Visible."),),
        (),
        (),
        "NOT_REQUESTED",
        provider,
    )

    assert answer.context == FindAnswerSentence(
        "No additional evidence supporting this answer was found in the "
        "remainder of the same Context frame."
    )
    assert answer.outside == FindAnswerSentence(
        "Other Contexts were not checked."
    )
    assert "October" not in answer.context.text
    assert "September" not in answer.outside.text


def test_host_scope_status_uses_korean_for_a_korean_question():
    provider = Provider(
        _response(
            context_text="Unsupported generated status.",
            context_sources=[],
            outside_text="Unsupported generated status.",
            outside_sources=[],
        )
    )

    answer = synthesize_find_answer(
        "주차장은 언제까지 닫혀 있어?",
        (_item("m1", "Visible."),),
        (),
        (),
        "NOT_REQUESTED",
        provider,
    )

    assert answer.context.text.startswith("같은 Context")
    assert answer.outside.text == "다른 Context는 확인하지 않았습니다."


def test_pending_clarification_and_interpreted_request_reach_synthesis():
    provider = Provider(_response())

    synthesize_find_answer(
        "yes",
        (_item("m1", "Visible."),),
        (_item("c1", "Context."),),
        (),
        "NOT_REQUESTED",
        provider,
        interpreted_request="The user confirmed the closure-date question.",
        pending_clarification=(
            "Do you want to know when the garage closure ends?"
        ),
    )

    prompt = provider.calls[0][0]
    assert "The user confirmed the closure-date question." in prompt
    assert "Do you want to know when the garage closure ends?" in prompt
    assert '"latest_user_text": "yes"' in prompt


@pytest.mark.parametrize(
    "field",
    ["visible_text", "context_text", "outside_text"],
)
def test_generated_sentence_cannot_forge_a_host_citation(field):
    provider = Provider(_response(**{field: "Fabricated claim. [77]"}))

    with pytest.raises(FindAnswerError, match="invalid"):
        synthesize_find_answer(
            "When?",
            (_item("m1", "Visible."),),
            (_item("c1", "Context."),),
            (),
            "NOT_REQUESTED",
            provider,
        )


def test_oversized_scope_fails_before_provider_work(monkeypatch):
    provider = Provider(_response())
    monkeypatch.setattr(
        "memcommit.find_answer_dialogue.FIND_ANSWER_CORPUS_LIMIT",
        20,
    )

    with pytest.raises(FindAnswerCorpusTooLarge):
        synthesize_find_answer(
            "When?",
            (_item("m1", "Visible."),),
            (),
            (),
            "NOT_REQUESTED",
            provider,
        )

    assert provider.calls == []
