"""Authored natural-language Rationale rules and production regressions."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from memcommit.cli import app
from memcommit.context import Memory
from memcommit.provenance import MemoryState, TraceEvent, TraceReport
from memcommit.rationale_rules import (
    RATIONALE_RULESET_VERSION,
    RationaleLimitUnit,
    rationale_ruleset,
    rationale_ruleset_prompt_payload,
)
from memcommit.rationale_semantic import (
    RATIONALE_PROVENANCE_OPERATION,
    RationaleSynthesisError,
    rationale_provenance_payload,
    synthesize_rationale_provenance,
)
from memcommit.store import MemoryStore


runner = CliRunner()


def _state(raw: dict[str, object]) -> MemoryState:
    return MemoryState(
        uid=str(raw["id"]),
        content=str(raw["content"]),
        position=int(raw["position"]),
    )


def _case_trace(case: dict[str, object]) -> TraceReport:
    input_value = case["input"]
    assert isinstance(input_value, dict)
    raw_events = input_value["events"]
    assert isinstance(raw_events, list)
    events = tuple(
        TraceEvent(
            kind=raw_event["kind"],
            evidence="RECORDED",
            timestamp=None,
            checkpoint_uid=None,
            command=raw_event["command"],
            description=raw_event["description"],
            before=tuple(_state(item) for item in raw_event["before"]),
            after=tuple(_state(item) for item in raw_event["after"]),
            reason=raw_event["reason"],
        )
        for raw_event in raw_events
    )
    selected = str(input_value["selected_memory_id"])
    component_uids = tuple(
        sorted(
            {
                selected,
                *(
                    state.uid
                    for event in events
                    for state in (*event.before, *event.after)
                ),
            }
        )
    )
    return TraceReport(
        context_uid="context",
        context_name="case",
        selected_uid=selected,
        component_uids=component_uids,
        originals=tuple(_state(item) for item in input_value["originals"]),
        current=tuple(_state(item) for item in input_value["current"]),
        events=events,
        analyses=(),
        warnings=(),
    )


class _CapturingProvider:
    def __init__(self, provenance: str):
        self.provenance = provenance
        self.prompts: list[str] = []
        self.schemas: list[dict[str, object]] = []

    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == RATIONALE_PROVENANCE_OPERATION
        assert output_schema is not None
        self.prompts.append(prompt)
        self.schemas.append(output_schema)
        return json.dumps({"provenance": self.provenance}, ensure_ascii=False)


def _case(case_id: str) -> dict[str, object]:
    return next(
        case
        for case in rationale_ruleset()["cases"]
        if isinstance(case, dict) and case["id"] == case_id
    )


def test_every_rule_exact_case_and_known_wrong_enters_the_production_prompt():
    authored = rationale_ruleset()
    prompt = rationale_ruleset_prompt_payload()

    assert authored["ruleset_version"] == RATIONALE_RULESET_VERSION
    assert len(authored["rules"]) == 9
    assert prompt == {
        "ruleset_version": RATIONALE_RULESET_VERSION,
        "rules": authored["rules"],
        "cases": authored["cases"],
    }
    assert all(case["known_wrong"] for case in prompt["cases"])


def test_um_case_runs_through_the_same_whole_trace_production_synthesizer():
    case = _case("um-sentence-chunk-lifecycle")
    expected = case["expected"]
    input_value = case["input"]
    provider = _CapturingProvider(expected["provenance"])

    projection = synthesize_rationale_provenance(
        _case_trace(case),
        provider_factory=lambda: provider,
        history_available=input_value["history_available"],
        limit=input_value["limit"],
        unit=RationaleLimitUnit(input_value["unit"]),
    )

    assert projection.status.value == expected["status"]
    assert projection.text == expected["provenance"]
    assert projection.length == 33
    assert len(provider.prompts) == 1
    prompt_payload = json.loads(provider.prompts[0].split("RATIONALE PAYLOAD:\n", 1)[1])
    assert prompt_payload["ruleset"] == rationale_ruleset_prompt_payload()
    request = prompt_payload["request"]
    assert request["originals"][0]["content"].startswith(
        "When I ask to change one expression"
    )
    assert request["events"][0]["after"][1] == {
        "memory_id": "selected",
        "content": "Um...",
        "position": 3,
    }
    assert [event["kind"] for event in request["events"]][-2:] == [
        "ATOMIZE_KEEP",
        "ATOMIZE_PRESERVED",
    ]


def test_payload_uses_aliases_but_retains_parent_and_sibling_context():
    case = _case("um-sentence-chunk-lifecycle")
    payload = rationale_provenance_payload(_case_trace(case))
    request = payload["request"]

    assert request["selected_memory_id"] == "selected"
    assert request["selected_content"] == "Um..."
    assert request["selected_status"] == "HISTORICAL"
    assert request["events"][0]["before"][0]["memory_id"] != "selected"
    assert "c9e05f9a" not in json.dumps(payload)


def test_hidden_history_returns_without_connecting_a_provider():
    case = _case("grant-hidden-history")

    projection = synthesize_rationale_provenance(
        _case_trace(case),
        provider_factory=lambda: pytest.fail("hidden history connected a provider"),
        history_available=False,
    )

    assert projection.status.value == "HIDDEN"
    assert projection.text == ""


@pytest.mark.parametrize(
    ("provenance", "limit", "unit", "message"),
    [
        (
            "CREATED via chunk → REMOVED via undo",
            40,
            RationaleLimitUnit.WORDS,
            "non-narrative",
        ),
        (
            "This narrative contains too many words for this very small bound.",
            4,
            RationaleLimitUnit.WORDS,
            "exceeded",
        ),
    ],
)
def test_provider_output_must_be_complete_narrative_within_the_exact_bound(
    provenance,
    limit,
    unit,
    message,
):
    case = _case("direct-add-remove-undo")
    provider = _CapturingProvider(provenance)

    with pytest.raises(RationaleSynthesisError, match=message):
        synthesize_rationale_provenance(
            _case_trace(case),
            provider_factory=lambda: provider,
            limit=limit,
            unit=unit,
        )


def test_cli_renders_a_natural_language_receipt_for_remove_and_undo(
    isolated_store,
    monkeypatch,
):
    case = _case("direct-add-remove-undo")
    expected = case["expected"]["provenance"]
    monkeypatch.setattr(
        "memcommit.commands.rationale.connect_semantic_provider",
        lambda: _CapturingProvider(expected),
    )
    assert runner.invoke(app, ["init", "lifecycle"]).exit_code == 0
    assert runner.invoke(app, ["add", "Keep the selected terminology."]).exit_code == 0
    target = next(
        item
        for item in MemoryStore().load_current_direct().iter_items()
        if isinstance(item, Memory)
    )
    assert runner.invoke(app, ["remove", target.uid]).exit_code == 0
    assert runner.invoke(app, ["undo"]).exit_code == 0

    result = runner.invoke(app, ["rationale", target.uid])

    assert result.exit_code == 0, result.output
    assert "PROVENANCE\n" in result.output
    assert expected in result.output
    assert "CREATED via" not in result.output
    assert "retained transition" not in result.output


def test_compare_source_rationale_uses_the_same_semantic_rules(
    isolated_store,
    monkeypatch,
    capsys,
):
    from memcommit.commands import compare as compare_command

    assert runner.invoke(app, ["init", "compare-source"]).exit_code == 0
    assert runner.invoke(app, ["add", "Source claim."]).exit_code == 0
    target = next(
        item
        for item in MemoryStore().load_current_direct().iter_items()
        if isinstance(item, Memory)
    )
    expected = "This Memory was added directly and has no later retained change."
    monkeypatch.setattr(
        compare_command,
        "connect_codex_chatgpt_provider",
        lambda: _CapturingProvider(expected),
    )

    compare_command._render_selected_rationale(
        store=MemoryStore(),
        context_name="compare-source",
        memory_uid=target.uid,
    )

    output = capsys.readouterr().out
    assert "Source claim." in output
    assert expected in output


def test_help_exposes_natural_provenance_and_all_length_units(isolated_store):
    result = runner.invoke(app, ["rationale", "--help"])

    assert result.exit_code == 0, result.output
    assert "where one Memory came" in " ".join(result.output.split())
    assert "--limit" in result.output
    assert "--unit" in result.output
    assert "characters|bytes|words" in result.output
