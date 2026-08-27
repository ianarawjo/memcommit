"""Strict provider boundary for one interactive Find follow-up."""
from __future__ import annotations

import json

import pytest

from memcommit.adapters.console.commands.search.chat_shell import (
    FindChatMessage,
    FindChatResult,
    FindChatState,
)
from memcommit.application.operations.search.turn_dialogue import (
    FIND_TURN_OPERATION,
    FindTurnAction,
    FindTurnAnswer,
    FindTurnAsk,
    FindTurnError,
    FindTurnRefine,
    find_turn_output_schema,
    interpret_find_turn,
)


def _state() -> FindChatState:
    return FindChatState(
        context_name="task-1",
        current_query="cafe and store",
        results=(
            FindChatResult(
                alias="m1",
                context_name="task-1",
                kind="memory",
                uid="durable-secret-uid-one",
                content="The campus store will close.",
            ),
            FindChatResult(
                alias="m2",
                context_name="task-1",
                kind="query",
                uid="concealed-query-ref-uid",
                content="public-policy-name (query-only)",
            ),
        ),
    )


class Provider:
    def __init__(self, response: dict[str, object]):
        self.response = response
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    def complete(self, prompt, *, operation, output_schema=None):
        self.calls.append((prompt, operation, output_schema))
        return json.dumps(self.response)


def test_schema_and_prompt_expose_aliases_but_not_durable_uids():
    provider = Provider(
        {
            "kind": "SHOW_RESULT",
            "understanding": "You want to inspect the store result.",
            "question": "What would you like to inspect next?",
            "query": "",
            "selector": "m1",
            "scope": "NONE",
        }
    )

    turn = interpret_find_turn(
        _state(),
        "show the first result",
        provider,
    )

    assert turn == FindTurnAction(
        understanding="You want to inspect the store result.",
        question="What would you like to inspect next?",
        selector="m1",
    )
    assert len(provider.calls) == 1
    prompt, operation, schema = provider.calls[0]
    assert operation == FIND_TURN_OPERATION
    assert schema["properties"]["kind"]["enum"] == [
        "ASK",
        "REFINE",
        "ANSWER",
        "SHOW_RESULT",
    ]
    assert schema["properties"]["selector"]["enum"] == ["", "m1", "m2"]
    assert schema["properties"]["scope"]["enum"] == [
        "NONE",
        "CONTEXT",
        "ALL_CONTEXTS",
    ]
    assert "durable-secret-uid-one" not in prompt
    assert "concealed-query-ref-uid" not in prompt
    assert "public-policy-name (query-only)" in prompt
    assert "SHOW_RESULT" in prompt


def test_ask_requires_an_empty_selector():
    provider = Provider(
        {
            "kind": "ASK",
            "understanding": "You want to inspect a result.",
            "question": "Which visible result should I show?",
            "query": "",
            "selector": "",
            "scope": "NONE",
        }
    )

    turn = interpret_find_turn(_state(), "show it", provider)

    assert turn == FindTurnAsk(
        understanding="You want to inspect a result.",
        question="Which visible result should I show?",
    )


def test_answer_plans_same_context_research_without_answering():
    provider = Provider(
        {
            "kind": "ANSWER",
            "understanding": "You are asking when the campus store reopens.",
            "question": "",
            "query": "",
            "selector": "",
            "scope": "CONTEXT",
        }
    )

    turn = interpret_find_turn(
        _state(),
        "When will the campus store reopen?",
        provider,
    )

    assert turn == FindTurnAnswer(
        understanding="You are asking when the campus store reopens.",
        scope="CONTEXT",
    )
    prompt = provider.calls[0][0]
    assert "Do not turn a clear ordinary question" in prompt
    assert "do not answer it in this turn" in prompt


def test_answer_uses_all_contexts_only_for_an_explicit_request():
    provider = Provider(
        {
            "kind": "ANSWER",
            "understanding": "You want other Contexts checked too.",
            "question": "",
            "query": "",
            "selector": "",
            "scope": "ALL_CONTEXTS",
        }
    )

    turn = interpret_find_turn(
        _state(),
        "Check other contexts too.",
        provider,
    )

    assert turn == FindTurnAnswer(
        understanding="You want other Contexts checked too.",
        scope="ALL_CONTEXTS",
    )


def test_refine_turn_returns_a_standalone_same_frame_query_with_no_results():
    state = FindChatState(
        context_name="task-3",
        current_query="건강보험 관련 메모리",
    )
    provider = Provider(
        {
            "kind": "REFINE",
            "understanding": "You broadened the search to healthcare.",
            "question": "",
            "query": "health healthcare medicine",
            "selector": "",
            "scope": "CONTEXT",
        }
    )

    turn = interpret_find_turn(
        state,
        "related to health/healthcare/medicine",
        provider,
    )

    assert turn == FindTurnRefine(
        understanding="You broadened the search to healthcare.",
        query="health healthcare medicine",
    )
    prompt = provider.calls[0][0]
    assert "prefer REFINE over ASK" in prompt
    assert "건강보험 관련 메모리" in prompt


def test_related_fallback_can_be_inspected_or_refined_but_not_answered():
    state = FindChatState(
        context_name="task-3",
        current_query="health insurance memories",
        results=(
            FindChatResult(
                alias="m1",
                context_name="task-3/personal-memory/2024/03",
                kind="memory",
                uid="related-memory-uid",
                content="The instructions describe a medication time.",
                relevance="related",
            ),
        ),
        related_query="health and healthcare memories",
    )
    schema = find_turn_output_schema(state)
    provider = Provider(
        {
            "kind": "SHOW_RESULT",
            "understanding": "You want to inspect the related item.",
            "question": "What would you like to inspect next?",
            "query": "",
            "selector": "m1",
            "scope": "NONE",
        }
    )

    turn = interpret_find_turn(state, "show that related item", provider)

    assert schema["properties"]["kind"]["enum"] == [
        "ASK",
        "REFINE",
        "SHOW_RESULT",
    ]
    assert isinstance(turn, FindTurnAction)
    prompt = provider.calls[0][0]
    assert '"relevance": "related"' in prompt
    assert '"related_query": "health and healthcare memories"' in prompt
    assert "cannot support ANSWER" in prompt

    unsupported = Provider(
        {
            "kind": "ANSWER",
            "understanding": "Answer from a related item.",
            "question": "",
            "query": "",
            "selector": "",
            "scope": "CONTEXT",
        }
    )
    with pytest.raises(FindTurnError):
        interpret_find_turn(state, "answer it", unsupported)


def test_short_reply_receives_only_the_pending_visible_clarification():
    state = FindChatState(
        context_name="task-1",
        current_query="cafe and store",
        results=_state().results,
        messages=(
            FindChatMessage(
                role="STATUS",
                text="mem show secret-receipt-uid --context task-1",
            ),
            FindChatMessage(
                role="USER",
                text="show one of those",
            ),
            FindChatMessage(
                role="MEM",
                text=(
                    "You want one of two results.\n\n"
                    "Do you mean m1 or m2?"
                ),
            ),
        ),
        status="WAITING FOR CLARIFICATION",
    )
    provider = Provider(
        {
            "kind": "SHOW_RESULT",
            "understanding": "By the latter, you mean m2.",
            "question": "What would you like to inspect next?",
            "query": "",
            "selector": "m2",
            "scope": "NONE",
        }
    )

    turn = interpret_find_turn(state, "the latter", provider)

    prompt = provider.calls[0][0]
    assert isinstance(turn, FindTurnAction)
    assert turn.selector == "m2"
    assert "Do you mean m1 or m2?" in prompt
    assert "secret-receipt-uid" not in prompt


@pytest.mark.parametrize(
    "response",
    [
        {
            "kind": "SHOW_RESULT",
            "understanding": "Inspect a result.",
            "question": "Next?",
            "query": "",
            "selector": "m99",
            "scope": "NONE",
        },
        {
            "kind": "ASK",
            "understanding": "Inspect a result.",
            "question": "Which one?",
            "query": "",
            "selector": "m1",
            "scope": "NONE",
        },
        {
            "kind": "RUN_COMMAND",
            "understanding": "Run something.",
            "question": "Done?",
            "query": "",
            "selector": "m1",
            "scope": "NONE",
        },
        {
            "kind": "SHOW_RESULT",
            "understanding": "Inspect a result.",
            "question": "Next?",
            "query": "",
            "selector": "m1",
            "scope": "NONE",
            "command": "mem delete unsafe",
        },
        {
            "kind": "ANSWER",
            "understanding": "Answer from a result.",
            "question": "",
            "query": "",
            "selector": "",
            "scope": "EVERYWHERE",
        },
        {
            "kind": "ANSWER",
            "understanding": "Answer from a result.",
            "question": "This must be empty.",
            "query": "",
            "selector": "m1",
            "scope": "CONTEXT",
        },
        {
            "kind": "REFINE",
            "understanding": "Search again.",
            "question": "",
            "query": "",
            "selector": "",
            "scope": "CONTEXT",
        },
        {
            "kind": "SHOW_RESULT",
            "understanding": "Inspect a result.",
            "question": "Next?",
            "query": "",
            "selector": "",
            "scope": "CONTEXT",
        },
    ],
)
def test_unknown_alias_action_or_command_authority_fails_closed(response):
    with pytest.raises(FindTurnError):
        interpret_find_turn(_state(), "show a result", Provider(response))


def test_empty_results_allow_ask_or_refine():
    state = FindChatState(context_name="task-1")
    schema = find_turn_output_schema(state)
    provider = Provider(
        {
            "kind": "ASK",
            "understanding": "There are no visible results.",
            "question": "What should the next search look for?",
            "query": "",
            "selector": "",
            "scope": "NONE",
        }
    )

    turn = interpret_find_turn(state, "show one", provider)

    assert schema["properties"]["kind"]["enum"] == ["ASK", "REFINE"]
    assert isinstance(turn, FindTurnAsk)

    unsupported = Provider(
        {
            "kind": "ANSWER",
            "understanding": "There are no visible results.",
            "question": "",
            "query": "",
            "selector": "",
            "scope": "CONTEXT",
        }
    )
    with pytest.raises(FindTurnError):
        interpret_find_turn(state, "answer anyway", unsupported)


def test_provider_factory_connects_once():
    provider = Provider(
        {
            "kind": "ASK",
            "understanding": "The referent is ambiguous.",
            "question": "Which result?",
            "query": "",
            "selector": "",
            "scope": "NONE",
        }
    )
    calls: list[str] = []

    def factory():
        calls.append("connect")
        return provider

    interpret_find_turn(_state(), "show it", factory)

    assert calls == ["connect"]
