"""Authored natural-language Rationale rules and production regressions."""

from __future__ import annotations

from dataclasses import replace
import json

import pytest
from typer.testing import CliRunner

from memcommit.adapters.console.entrypoint import app
from memcommit.core.context import Memory
from memcommit.application.capabilities import ops
from memcommit.application.capabilities.history.verification import (
    MemoryHistoryCommandContext,
    MemoryHistoryContextTransition,
    MemoryState,
)
from memcommit.application.capabilities.history.model.memory_event import (
    MemoryHistoryEvent,
)
from memcommit.application.capabilities.history.query.memory_history_slicing import (
    MemoryHistory,
)
from memcommit.application.operations.rationale.rules import (
    RATIONALE_RULESET_VERSION,
    RationaleLimitUnit,
    rationale_ruleset,
    rationale_ruleset_prompt_payload,
)
from memcommit.application.operations.rationale.semantic import (
    RATIONALE_PROVENANCE_OPERATION,
    RATIONALE_PROVENANCE_REPAIR_OPERATION,
    RationaleSynthesisError,
    rationale_provenance_payload,
    synthesize_rationale_provenance,
)
from memcommit.application.capabilities.semantic.prompt_policy import GENERAL_SEMANTIC_PROMPT_POLICY
from memcommit.persistence.store import MemoryStore


runner = CliRunner()


@pytest.fixture(autouse=True)
def _freeze_general_prompt_policy(monkeypatch):
    """Keep ruleset unit tests independent of the developer's active Profile."""

    monkeypatch.setattr(
        "memcommit.application.operations.rationale.semantic.resolve_semantic_prompt_policy",
        lambda: GENERAL_SEMANTIC_PROMPT_POLICY,
    )


def _state(raw: dict[str, object]) -> MemoryState:
    return MemoryState(
        uid=str(raw["id"]),
        content=str(raw["content"]),
        position=int(raw["position"]),
    )


def _case_trace(case: dict[str, object]) -> MemoryHistory:
    input_value = case["input"]
    assert isinstance(input_value, dict)
    raw_events = input_value["events"]
    assert isinstance(raw_events, list)
    events: list[MemoryHistoryEvent] = []
    for raw_event in raw_events:
        route = raw_event.get("context_transition")
        transition = (
            MemoryHistoryContextTransition(
                source=MemoryHistoryCommandContext(
                    uid="source-context",
                    name=str(route["source"]),
                ),
                target=MemoryHistoryCommandContext(
                    uid="target-context",
                    name=str(route["target"]),
                ),
            )
            if isinstance(route, dict)
            else None
        )
        events.append(
            MemoryHistoryEvent(
                kind=raw_event["kind"],
                evidence="RECORDED",
                timestamp=None,
                checkpoint_uid=None,
                command=raw_event["command"],
                description=raw_event["description"],
                before=tuple(_state(item) for item in raw_event["before"]),
                after=tuple(_state(item) for item in raw_event["after"]),
                reason=raw_event["reason"],
                reason_codes=tuple(raw_event.get("reason_codes", ())),
                context_transition=transition,
            )
        )
    retained_events = tuple(events)
    selected = str(input_value["selected_memory_id"])
    component_uids = tuple(
        sorted(
            {
                selected,
                *(
                    state.uid
                    for event in retained_events
                    for state in (*event.before, *event.after)
                ),
            }
        )
    )
    return MemoryHistory(
        context_uid="context",
        context_name=str(input_value["context_name"]),
        selected_uid=selected,
        component_uids=component_uids,
        originals=tuple(_state(item) for item in input_value["originals"]),
        current=tuple(_state(item) for item in input_value["current"]),
        events=retained_events,
        analyses=(),
        warnings=tuple(str(item) for item in input_value["warnings"]),
    )


class _CapturingProvider:
    def __init__(self, provenance: str):
        self.provenance = provenance
        self.prompts: list[str] = []
        self.schemas: list[dict[str, object]] = []

    def complete(self, prompt, *, operation, output_schema=None):
        assert operation in {
            RATIONALE_PROVENANCE_OPERATION,
            RATIONALE_PROVENANCE_REPAIR_OPERATION,
        }
        assert output_schema is not None
        self.prompts.append(prompt)
        self.schemas.append(output_schema)
        return json.dumps({"provenance": self.provenance}, ensure_ascii=False)


class _SequenceProvider:
    def __init__(self, *provenances: str):
        self.provenances = provenances
        self.prompts: list[str] = []
        self.operations: list[str] = []
        self.schemas: list[dict[str, object]] = []

    def complete(self, prompt, *, operation, output_schema=None):
        expected_operation = (
            RATIONALE_PROVENANCE_OPERATION
            if not self.prompts
            else RATIONALE_PROVENANCE_REPAIR_OPERATION
        )
        assert operation == expected_operation
        assert output_schema is not None
        index = len(self.prompts)
        self.prompts.append(prompt)
        self.operations.append(operation)
        self.schemas.append(output_schema)
        return json.dumps(
            {"provenance": self.provenances[index]},
            ensure_ascii=False,
        )


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
    assert len(authored["rules"]) == 15
    assert prompt == {
        "ruleset_version": RATIONALE_RULESET_VERSION,
        "rules": authored["rules"],
        "cases": authored["cases"],
    }
    assert all(case["known_wrong"] for case in prompt["cases"])


@pytest.mark.parametrize(
    "case_id",
    [
        "atomize-parent-to-selected-and-sibling",
        "distilled-rule-then-edited",
        "branch-inherited-unchanged-memory",
        "merge-source-copied-to-fresh-target",
        "merge-target-inherits-source-history",
    ],
)
def test_refinement_cases_use_the_production_payload_schema_and_decoder(case_id):
    case = _case(case_id)
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

    assert projection.text == expected["provenance"]
    assert projection.length <= input_value["limit"]
    prompt_payload = json.loads(provider.prompts[0].split("RATIONALE PAYLOAD:\n", 1)[1])
    assert prompt_payload["ruleset"] == rationale_ruleset_prompt_payload()
    assert prompt_payload["request"]["selected_context"] == input_value["context_name"]
    assert prompt_payload["request"]["warnings"] == input_value["warnings"]
    if case_id == "branch-inherited-unchanged-memory":
        assert prompt_payload["request"]["events"][-1]["context_transition"] == {
            "source": "practice/1",
            "target": "practice/2",
        }
        assert prompt_payload["request"]["events"][-1]["kind"] == "BRANCHED"


def test_refinement_cases_encode_excerpt_operation_and_context_movement_rules():
    rules = {rule["id"]: rule for rule in rationale_ruleset()["rules"]}
    cases = {case["id"]: case for case in rationale_ruleset()["cases"]}

    assert "exact contiguous excerpts" in rules["R10_EXACT_EXCERPT_ANCHOR"]["invariant"]
    assert "Split or Atomize" in rules["R11_OPERATION_SHAPE"]["invariant"]
    assert "origin and destination" in rules["R12_CONTEXT_MOVEMENT"]["invariant"]
    assert (
        "distinct Source and Target occurrences"
        in rules["R12_CONTEXT_MOVEMENT"]["invariant"]
    )
    assert "KEEP_TARGET" in rules["R14_MERGE_DISPOSITION"]["invariant"]
    assert (
        "preferred target"
        in rules["R15_LENGTH_HEADROOM_AND_REPAIR"]["invariant"]
    )
    assert (
        "this “don't edit the draft immediately” instruction"
        in cases["atomize-parent-to-selected-and-sibling"]["expected"]["provenance"]
    )
    assert (
        "from practice/1 as"
        in cases["distilled-rule-then-edited"]["expected"]["provenance"]
    )
    assert (
        "inherited unchanged by practice/2"
        in cases["branch-inherited-unchanged-memory"]["expected"]["provenance"]
    )
    assert (
        "copied that wording unchanged into transform-scratch/source"
        in cases["merge-source-copied-to-fresh-target"]["expected"]["provenance"]
    )


def test_long_history_reads_every_event_but_compresses_material_phases():
    case = _case("long-edit-run-with-remove-undo-redo")
    expected = case["expected"]["provenance"]
    input_value = case["input"]
    provider = _CapturingProvider(expected)

    projection = synthesize_rationale_provenance(
        _case_trace(case),
        provider_factory=lambda: provider,
        limit=input_value["limit"],
        unit=RationaleLimitUnit(input_value["unit"]),
    )

    assert projection.text == expected
    assert projection.length == 37
    assert len(provider.prompts) == 1
    assert "remove–undo–redo–undo cycle" in projection.text
    assert "should” to “must" not in projection.text
    prompt_payload = json.loads(provider.prompts[0].split("RATIONALE PAYLOAD:\n", 1)[1])
    events = prompt_payload["request"]["events"]
    assert len(events) == 15
    assert [event["kind"] for event in events][8:12] == [
        "REMOVED",
        "RESTORED",
        "RESTORED",
        "RESTORED",
    ]
    rules = {rule["id"]: rule for rule in prompt_payload["ruleset"]["rules"]}
    assert (
        "material chronological phase"
        in rules["R13_MATERIAL_PHASE_COMPRESSION"]["invariant"]
    )


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
    assert request["selected_context"] == "practice/source"
    assert request["selected_content"] == "Um..."
    assert request["selected_status"] == "HISTORICAL"
    assert request["events"][0]["before"][0]["memory_id"] != "selected"
    assert "c9e05f9a" not in json.dumps(payload)
    assert request["warnings"] == []


@pytest.mark.parametrize(
    ("limit", "target"),
    [(1, 1), (2, 1), (9, 8), (10, 9), (11, 9), (40, 36), (80, 72), (120, 108)],
)
def test_payload_aims_ten_percent_below_any_hard_limit(limit, target):
    payload = rationale_provenance_payload(
        _case_trace(_case("direct-add-remove-undo")),
        limit=limit,
        unit=RationaleLimitUnit.WORDS,
    )

    assert payload["request"]["length"] == {
        "target": target,
        "limit": limit,
        "unit": "words",
    }


def test_over_limit_draft_gets_one_complete_trace_length_repair():
    case = _case("direct-add-remove-undo")
    rejected = next(
        item["provenance"]
        for item in case["known_wrong"]
        if "R15_LENGTH_HEADROOM_AND_REPAIR" in item["violates"]
    )
    repaired = case["expected"]["provenance"]
    provider = _SequenceProvider(rejected, repaired)
    factory_calls: list[object] = []

    def provider_factory():
        factory_calls.append(object())
        return provider

    projection = synthesize_rationale_provenance(
        _case_trace(case),
        provider_factory=provider_factory,
    )

    assert projection.text == repaired
    assert projection.length == 14
    assert len(factory_calls) == 1
    assert len(provider.prompts) == 2
    assert provider.operations == [
        RATIONALE_PROVENANCE_OPERATION,
        RATIONALE_PROVENANCE_REPAIR_OPERATION,
    ]
    first_payload = json.loads(
        provider.prompts[0].split("RATIONALE PAYLOAD:\n", 1)[1]
    )
    repair_payload = json.loads(
        provider.prompts[1].split("RATIONALE PAYLOAD:\n", 1)[1]
    )
    assert first_payload["request"]["length"] == {
        "target": 36,
        "limit": 40,
        "unit": "words",
    }
    assert repair_payload["request"] == first_payload["request"]
    assert repair_payload["ruleset"] == first_payload["ruleset"]
    assert repair_payload["repair"] == {
        "reason": "OVER_LIMIT",
        "rejected_provenance": rejected,
        "measured_length": 41,
        "target": 36,
        "limit": 40,
        "unit": "words",
    }
    assert "single allowed length-repair turn" in provider.prompts[1]


def test_length_repair_runs_at_most_once():
    case = _case("direct-add-remove-undo")
    first = next(
        item["provenance"]
        for item in case["known_wrong"]
        if "R15_LENGTH_HEADROOM_AND_REPAIR" in item["violates"]
    )
    second = first
    provider = _SequenceProvider(first, second)

    with pytest.raises(RationaleSynthesisError, match="after one whole-Trace"):
        synthesize_rationale_provenance(
            _case_trace(case),
            provider_factory=lambda: provider,
        )

    assert len(provider.prompts) == 2


def test_non_length_validation_failure_does_not_retry():
    provider = _SequenceProvider("null", "This response must not be requested.")

    with pytest.raises(RationaleSynthesisError, match="non-narrative"):
        synthesize_rationale_provenance(
            _case_trace(_case("direct-add-remove-undo")),
            provider_factory=lambda: provider,
        )

    assert len(provider.prompts) == 1


def test_hidden_history_returns_without_connecting_a_provider():
    case = _case("grant-hidden-history")

    projection = synthesize_rationale_provenance(
        _case_trace(case),
        provider_factory=lambda: pytest.fail("hidden history connected a provider"),
        history_available=False,
    )

    assert projection.status.value == "HIDDEN"
    assert projection.text == ""


def test_unrecorded_gap_returns_empty_without_connecting_a_provider():
    state = MemoryState(uid="selected-memory", content="Current only.", position=0)
    trace = MemoryHistory(
        context_uid="context",
        context_name="unrecorded",
        selected_uid=state.uid,
        component_uids=(state.uid,),
        originals=(),
        current=(state,),
        events=(
            MemoryHistoryEvent(
                kind="HISTORY_GAP",
                evidence="UNRECORDED",
                timestamp=None,
                checkpoint_uid=None,
                command="current",
                description="Current state has no retained checkpoint.",
                after=(state,),
            ),
        ),
        analyses=(),
        warnings=("The current Context has no retained checkpoint.",),
    )

    projection = synthesize_rationale_provenance(
        trace,
        provider_factory=lambda: pytest.fail("a history gap connected a provider"),
    )

    assert projection.status.value == "EMPTY"
    assert projection.text == ""
    assert projection.length == 0


def test_mixed_gap_sends_only_the_latest_retained_boundary():
    retained = _case_trace(_case("direct-add-remove-undo"))
    retained_selected = next(
        state for state in retained.current if state.uid == retained.selected_uid
    )
    unrecorded_selected = MemoryState(
        uid=retained_selected.uid,
        content="UNRECORDED LIVE TEXT",
        position=retained_selected.position,
    )
    warning = "The current Context contains an unrecorded edit."
    gap = MemoryHistoryEvent(
        kind="HISTORY_GAP",
        evidence="UNRECORDED",
        timestamp=None,
        checkpoint_uid=None,
        command="current",
        description="Current state differs from retained history.",
        before=(retained_selected,),
        after=(unrecorded_selected,),
    )
    trace = replace(
        retained,
        current=(unrecorded_selected,),
        events=(*retained.events, gap),
        warnings=(*retained.warnings, warning),
    )
    expected = "The retained operations explain only the earlier wording."
    provider = _CapturingProvider(expected)

    projection = synthesize_rationale_provenance(
        trace,
        provider_factory=lambda: provider,
    )

    assert projection.text == expected
    payload = json.loads(provider.prompts[0].split("RATIONALE PAYLOAD:\n", 1)[1])
    request = payload["request"]
    assert request["history_boundary"] == "UNRECORDED_CURRENT_OMITTED"
    assert request["warnings"][-1] == warning
    assert all(event["kind"] != "HISTORY_GAP" for event in request["events"])
    assert request["selected_content"] == retained_selected.content
    assert request["current"][0]["content"] == retained_selected.content
    assert "UNRECORDED LIVE TEXT" not in provider.prompts[0]


def test_cli_gap_receipt_and_json_are_provider_free(isolated_store, monkeypatch):
    store = MemoryStore()
    context = ops.init("unrecorded")
    memory = ops.add(context, "Only the current file retains this.")
    store.save(context)
    store.set_current(context.name)
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.rationale.command.connect_semantic_provider",
        lambda: pytest.fail("CLI gap receipt connected a provider"),
    )
    selector = f"{context.name}:{memory.uid}"

    receipt = runner.invoke(app, ["rationale", selector])
    machine = runner.invoke(app, ["rationale", selector, "--json"])

    assert receipt.exit_code == 0, receipt.output
    assert "PROVENANCE — no retained history" in receipt.output
    assert "ATTENTION" in receipt.output
    assert "no retained checkpoint" in receipt.output
    assert machine.exit_code == 0, machine.output
    payload = json.loads(machine.output)
    assert payload["provenance_projection"]["status"] == "EMPTY"
    assert payload["provenance_projection"]["text"] == ""


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
        ("/", 40, RationaleLimitUnit.WORDS, "non-narrative"),
        ("null", 40, RationaleLimitUnit.WORDS, "non-narrative"),
        (":null", 40, RationaleLimitUnit.WORDS, "non-narrative"),
        ("undefined", 40, RationaleLimitUnit.WORDS, "non-narrative"),
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
        "memcommit.adapters.console.commands.rationale.command.connect_semantic_provider",
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
    from memcommit.adapters.console.commands.compare import command as compare_command

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
