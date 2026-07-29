"""Strict provider boundary for one interactive Find follow-up."""
from __future__ import annotations

import json

import pytest

from memcommit.commands.find_chat_shell import (
    FindChatMessage,
    FindChatResult,
    FindChatState,
)
from memcommit.find_turn_dialogue import (
    FIND_TURN_OPERATION,
    FindTurnAction,
    FindTurnAsk,
    FindTurnError,
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
            "selector": "m1",
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
    assert schema["properties"]["selector"]["enum"] == ["", "m1", "m2"]
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
            "selector": "",
        }
    )

    turn = interpret_find_turn(_state(), "show it", provider)

    assert turn == FindTurnAsk(
        understanding="You want to inspect a result.",
        question="Which visible result should I show?",
    )


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
        status="WAITING FOR CLARIFICATION · RESULTS UNCHANGED",
    )
    provider = Provider(
        {
            "kind": "SHOW_RESULT",
            "understanding": "By the latter, you mean m2.",
            "question": "What would you like to inspect next?",
            "selector": "m2",
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
            "selector": "m99",
        },
        {
            "kind": "ASK",
            "understanding": "Inspect a result.",
            "question": "Which one?",
            "selector": "m1",
        },
        {
            "kind": "RUN_COMMAND",
            "understanding": "Run something.",
            "question": "Done?",
            "selector": "m1",
        },
        {
            "kind": "SHOW_RESULT",
            "understanding": "Inspect a result.",
            "question": "Next?",
            "selector": "m1",
            "command": "mem delete unsafe",
        },
    ],
)
def test_unknown_alias_action_or_command_authority_fails_closed(response):
    with pytest.raises(FindTurnError):
        interpret_find_turn(_state(), "show a result", Provider(response))


def test_empty_results_allow_only_ask():
    state = FindChatState(context_name="task-1")
    schema = find_turn_output_schema(state)
    provider = Provider(
        {
            "kind": "ASK",
            "understanding": "There are no visible results.",
            "question": "What should the next search look for?",
            "selector": "",
        }
    )

    turn = interpret_find_turn(state, "show one", provider)

    assert schema["properties"]["kind"]["enum"] == ["ASK"]
    assert isinstance(turn, FindTurnAsk)


def test_provider_factory_connects_once():
    provider = Provider(
        {
            "kind": "ASK",
            "understanding": "The referent is ambiguous.",
            "question": "Which result?",
            "selector": "",
        }
    )
    calls: list[str] = []

    def factory():
        calls.append("connect")
        return provider

    interpret_find_turn(_state(), "show it", factory)

    assert calls == ["connect"]
