"""Contracts for the preview-only ``mem impact atomize`` operation."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest
from typer.testing import CliRunner

import memcommit.atomize as atomize_module
import memcommit.ops as ops
from memcommit.atomize import (
    AtomizeAnalysisSession,
    AtomizeImpactError,
    atomize_lint,
    impact_atomize,
    sentence_like_segment_count,
)
from memcommit.cli import app
from memcommit.commands.atomize.sessions import (
    atomize_session_entries,
    revalidate_saved_atomize_analysis,
)
from memcommit.context import (
    AutoCheckpoint,
    Context,
    Memory,
    MemoryRef,
    QueryContextRef,
)
from memcommit.store import MemoryStore


runner = CliRunner(mix_stderr=False)
PAYLOAD_MARKER = "ATOMIZE IMPACT PAYLOAD:\n"


@pytest.fixture(autouse=True)
def _share_cli_atomize_provider(monkeypatch):
    """Saved Apply uses the same fake endpoint configured for its preview."""

    from memcommit.commands.impact import command as impact_command

    monkeypatch.setattr(
        "memcommit.commands.atomize.command.connect_codex_chatgpt_provider",
        lambda: impact_command.connect_codex_chatgpt_provider(),
    )


def _aggregate_response(payload: dict, response: dict) -> dict:
    """Wrap legacy item-focused fakes in the current one-shot envelope."""
    candidate_ids = [memory["candidate_id"] for memory in payload["memories"]]
    return {
        "overview": {
            "understood": {
                "text": "The test response covers the supplied source Memories.",
                "source_ids": candidate_ids,
            },
            "changed": {
                "text": "The test response records the proposed atomization.",
                "source_ids": candidate_ids,
            },
            "unresolved": {
                "text": "",
                "source_ids": [],
            },
        },
        "items": response["items"],
        "quality_issues": [],
    }


class AtomizeProvider:
    def __init__(self, responder):
        self.responder = responder
        self.calls: list[tuple[str, str, dict[str, object], dict]] = []

    def complete(self, prompt, *, operation, output_schema=None):
        if operation == "find_duplicates":
            payload = json.loads(prompt.split("QUALITY FIND PAYLOAD:\n", 1)[1])
            self.calls.append((prompt, operation, output_schema, payload))
            return json.dumps({"findings": []})
        payload = json.loads(prompt.split(PAYLOAD_MARKER, 1)[1])
        self.calls.append((prompt, operation, output_schema, payload))
        response = (
            _all_atomic(payload)
            if payload.get("phase") == "normal_form_validation"
            else self.responder(payload)
        )
        if isinstance(response, dict) and set(response) == {"items"}:
            response = _aggregate_response(payload, response)
        return response if isinstance(response, str) else json.dumps(response)


class ForbiddenProvider:
    def __call__(self):
        raise AssertionError("provider should not be connected")


class AtomizeNormalFormProvider:
    """Exercise split, semantic Dedun, and final validation in one fixture."""

    def __init__(self):
        self.operations: list[str] = []

    def complete(self, prompt, *, operation, output_schema=None):
        self.operations.append(operation)
        if operation == "find_duplicates":
            payload = json.loads(prompt.split("QUALITY FIND PAYLOAD:\n", 1)[1])
            by_content = {
                item["content"]: item["candidate_id"]
                for item in payload["memories"]
            }
            findings = []
            if "hi" in by_content and "hi." in by_content:
                findings.append(
                    {
                        "candidate_ids": [by_content["hi"], by_content["hi."]],
                        "relation": "SEMANTIC_EQUIVALENT",
                        "reason": "The punctuation-only variants are substitutable.",
                    }
                )
            return json.dumps({"findings": findings})

        assert operation == "impact_atomize"
        payload = json.loads(prompt.split(PAYLOAD_MARKER, 1)[1])
        items = []
        for memory in payload["memories"]:
            if memory["content"] == "hi. Bye.":
                items.append(
                    _item(
                        memory["candidate_id"],
                        "COMPOSITE",
                        children=[
                            {"content": "hi.", "source_spans": ["hi."]},
                            {"content": "Bye.", "source_spans": ["Bye."]},
                        ],
                    )
                )
            else:
                items.append(_item(memory["candidate_id"]))
        return json.dumps(_aggregate_response(payload, {"items": items}))


class RejectingNormalFormProvider(AtomizeNormalFormProvider):
    def complete(self, prompt, *, operation, output_schema=None):
        if operation != "impact_atomize":
            return super().complete(
                prompt,
                operation=operation,
                output_schema=output_schema,
            )
        payload = json.loads(prompt.split(PAYLOAD_MARKER, 1)[1])
        if payload.get("phase") != "normal_form_validation":
            return super().complete(
                prompt,
                operation=operation,
                output_schema=output_schema,
            )
        self.operations.append(operation)
        return json.dumps(
            _aggregate_response(
                payload,
                {
                    "items": [
                        _item(
                            memory["candidate_id"],
                            "UNCERTAIN",
                            reason_codes=["A06_NO_HIDDEN_CONTEXT"],
                        )
                        for memory in payload["memories"]
                    ]
                },
            )
        )


def _item(
    candidate_id: str,
    classification: str = "ATOMIC",
    *,
    children: list[dict[str, object]] | None = None,
    reason_codes: list[str] | None = None,
    reason: str = "The source has one independently revisable focus.",
) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "classification": classification,
        "reason_codes": reason_codes or ["A01_ONE_FOCUS"],
        "children": children or [],
        "reason": reason,
    }


def _all_atomic(payload: dict) -> dict[str, object]:
    return {"items": [_item(memory["candidate_id"]) for memory in payload["memories"]]}


def test_focused_atomize_keeps_neighbors_context_only_and_applies_selected_memory():
    ctx = ops.init("focused/atomize")
    before = ops.add(ctx, "The lobby closes at five.")
    selected = ops.add(ctx, "Parking closes. The stairwell stays open.")
    after = ops.add(ctx, "Security remains on site.")

    def respond(payload):
        candidate = payload["memories"][0]
        return {
            "items": [
                _item(
                    candidate["candidate_id"],
                    "COMPOSITE",
                    children=[
                        {
                            "content": "Parking closes.",
                            "source_spans": ["Parking closes"],
                        },
                        {
                            "content": "The stairwell stays open.",
                            "source_spans": ["The stairwell stays open"],
                        },
                    ],
                    reason_codes=["A01_ONE_FOCUS", "A04_SOURCE_GROUNDED"],
                )
            ]
        }

    provider = AtomizeProvider(respond)
    report = impact_atomize(
        ctx,
        lambda: provider,
        memory_selector=selected.uid[:8],
    )
    payload = provider.calls[0][3]

    assert [item.memory.uid for item in report.items] == [selected.uid]
    assert [item["content"] for item in payload["memories"]] == [selected.content]
    assert {item["content"] for item in payload["context_evidence"]} == {
        before.content,
        after.content,
    }
    assert "context_id" not in json.dumps(provider.calls[0][2])

    analysis = atomize_module.create_atomize_analysis(ctx, report)
    result = atomize_module.apply_atomize_analysis(ctx, analysis)

    assert result.split_count == 1
    assert [item.content for item in ctx.iter_items()] == [
        before.content,
        "Parking closes.",
        "The stairwell stays open.",
        after.content,
    ]


def test_focused_atomize_save_as_preserves_unselected_memories(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = ops.init("focused/atomize-save-as")
    neighbor = ops.add(source, "Security remains on site.")
    selected = ops.add(source, "Parking closes. The stairwell stays open.")
    store.save(source)
    store.set_current(source.name)

    def respond(payload):
        candidate = payload["memories"][0]
        return {
            "items": [
                _item(
                    candidate["candidate_id"],
                    "COMPOSITE",
                    children=[
                        {
                            "content": "Parking closes.",
                            "source_spans": ["Parking closes"],
                        },
                        {
                            "content": "The stairwell stays open.",
                            "source_spans": ["The stairwell stays open"],
                        },
                    ],
                    reason_codes=["A01_ONE_FOCUS", "A04_SOURCE_GROUNDED"],
                )
            ]
        }

    monkeypatch.setattr(
        "memcommit.commands.atomize.command.connect_codex_chatgpt_provider",
        lambda: AtomizeProvider(respond),
    )

    preview = runner.invoke(
        app,
        ["atomize", "--memory", selected.uid[:8]],
    )
    applied = runner.invoke(
        app,
        ["atomize", "--save-as", "focused/atomize-derived"],
    )

    assert preview.exit_code == 0, preview.output
    assert applied.exit_code == 0, applied.output
    assert [item.content for item in store.load_direct(source.name).iter_items()] == [
        neighbor.content,
        selected.content,
    ]
    assert [
        item.content
        for item in store.load_direct("focused/atomize-derived").iter_items()
    ] == [
        neighbor.content,
        "Parking closes.",
        "The stairwell stays open.",
    ]


def test_atomize_publishes_split_and_dedun_as_one_undo_unit(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = ops.init("atomize/normal-form")
    ops.add(source, "hi")
    ops.add(source, "hi. Bye.")
    store.save(
        source,
        AutoCheckpoint(
            command="init",
            args={"name": source.name},
            description=f"Initialized context '{source.name}'",
        ),
    )
    store.set_current(source.name)
    before = source.to_dict()
    provider = AtomizeNormalFormProvider()
    monkeypatch.setattr(
        "memcommit.commands.impact.command.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    monkeypatch.setattr(
        "memcommit.commands.atomize.command.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    preview = runner.invoke(app, ["impact", "atomize"])
    applied = runner.invoke(app, ["atomize", "--save"])

    assert preview.exit_code == 0, preview.output
    assert applied.exit_code == 0, applied.output
    assert "DEDUN GROUPS 1 · ABSORBED 1" in applied.output
    assert "NORMAL FORM · SEMANTIC CHUNK + DEDUN · VERIFIED" in applied.output
    assert [
        item.content for item in store.load_direct(source.name).iter_items()
    ] == ["hi", "Bye."]
    atomize_checkpoints = [
        checkpoint
        for checkpoint in store.list_checkpoints(source.name)
        if checkpoint["command"] == "atomize"
    ]
    assert len(atomize_checkpoints) == 1
    checkpoint = atomize_checkpoints[0]
    assert checkpoint["args"]["normal_form_verified"] is True
    assert checkpoint["args"]["dedun_group_count"] == 1
    assert checkpoint["args"]["absorbed_count"] == 1
    assert checkpoint["args"]["trace"]["schema_version"] == 4
    assert provider.operations == [
        "impact_atomize",
        "find_duplicates",
        "impact_atomize",
        "find_duplicates",
    ]

    undone = runner.invoke(app, ["undo"])
    assert undone.exit_code == 0, undone.output
    assert store.load_direct(source.name).to_dict() == before


def test_atomize_normal_form_failure_publishes_no_partial_split(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = ops.init("atomize/rejected-normal-form")
    ops.add(source, "hi")
    ops.add(source, "hi. Bye.")
    store.save(source)
    store.set_current(source.name)
    before = store.load_direct(source.name).to_dict()
    checkpoints_before = store.list_checkpoints(source.name)
    provider = RejectingNormalFormProvider()
    monkeypatch.setattr(
        "memcommit.commands.impact.command.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    monkeypatch.setattr(
        "memcommit.commands.atomize.command.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    assert runner.invoke(app, ["impact", "atomize"]).exit_code == 0
    rejected = runner.invoke(app, ["atomize", "--save"])

    assert rejected.exit_code == 1
    assert "did not reach semantic chunk normal form" in rejected.stderr
    assert store.load_direct(source.name).to_dict() == before
    assert store.list_checkpoints(source.name) == checkpoints_before


def test_focused_atomize_dedun_prefers_unchanged_neighbor(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = ops.init("atomize/focused-normal-form")
    existing = ops.add(source, "hi")
    selected = ops.add(source, "hi. Bye.")
    store.save(source)
    store.set_current(source.name)
    provider = AtomizeNormalFormProvider()
    monkeypatch.setattr(
        "memcommit.commands.impact.command.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    monkeypatch.setattr(
        "memcommit.commands.atomize.command.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    preview = runner.invoke(
        app,
        ["impact", "atomize", "--memory", selected.uid[:8]],
    )
    applied = runner.invoke(app, ["atomize", "--save"])

    assert preview.exit_code == 0, preview.output
    assert applied.exit_code == 0, applied.output
    final = tuple(store.load_direct(source.name).iter_items())
    assert [item.content for item in final] == ["hi", "Bye."]
    assert final[0].uid == existing.uid


def test_impact_atomize_auto_types_bare_memory_and_finds_its_owner(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = ops.init("impact/source")
    selected = ops.add(source, "Parking closes. The stairwell stays open.")
    neighbor = ops.add(source, "Security remains on site.")
    current = ops.init("impact/current")
    for context in (source, current):
        store.save(context)
    store.set_current(current.name)
    provider = AtomizeProvider(_all_atomic)
    monkeypatch.setattr(
        "memcommit.commands.impact.command.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    result = runner.invoke(app, ["impact", "atomize", selected.uid[:7]])

    assert result.exit_code == 0, result.output
    analysis = store.load_atomize_analysis(source.uid)
    assert analysis is not None
    assert analysis.context_name == source.name
    assert analysis.memory_count == 1
    assert tuple(item.memory_uid for item in analysis.items) == (selected.uid,)
    assert [item["content"] for item in provider.calls[0][3]["memories"]] == [
        selected.content
    ]
    assert [
        item["content"] for item in provider.calls[0][3]["context_evidence"]
    ] == [neighbor.content]
    assert store.current_context_name() == current.name


def test_atomize_overview_prompt_requires_short_report_paragraphs() -> None:
    ctx = ops.init("overview/report-contract")
    ops.add(ctx, "The main entrance closes at 5 p.m.")
    provider = AtomizeProvider(_all_atomic)

    impact_atomize(ctx, lambda: provider)

    prompt, _, output_schema, _ = provider.calls[0]
    assert "one short natural-language report paragraph" in prompt
    assert "Do not use bullets, numbered lists, headings" in prompt
    assert "roughly 40-50 English words at most" in prompt
    assert (
        "Do not use bullets, numbered lists, headings, key-value records"
        in output_schema["properties"]["overview"]["properties"]["understood"][
            "properties"
        ]["text"]["description"]
    )
    for section in ("understood", "changed", "unresolved"):
        assert output_schema["properties"]["overview"]["properties"][section][
            "properties"
        ]["source_ids"]["minItems"] == 1


def test_atomize_overview_schema_does_not_admit_ungrounded_report_text() -> None:
    ctx = ops.init("overview/source-contract")
    ops.add(ctx, "The main entrance closes at 5 p.m.")

    def respond(payload: dict) -> dict[str, object]:
        response = _aggregate_response(
            payload,
            {
                "items": [
                    _item(payload["memories"][0]["candidate_id"]),
                ]
            },
        )
        response["overview"]["changed"] = {
            "text": "The source is preserved as one atomic Memory.",
            "source_ids": [],
        }
        return response

    with pytest.raises(AtomizeImpactError, match="source-linked overview"):
        impact_atomize(ctx, lambda: AtomizeProvider(respond))


def test_atomize_overview_collapses_duplicate_source_citations() -> None:
    ctx = ops.init("overview/duplicate-source")
    source = ops.add(ctx, "The main entrance closes at 5 p.m.")
    other = ops.add(ctx, "The café remains open.")

    def respond(payload: dict) -> dict[str, object]:
        candidate_id = payload["memories"][0]["candidate_id"]
        response = _aggregate_response(
            payload,
            {
                "items": [
                    _item(candidate_id),
                    _item(payload["memories"][1]["candidate_id"]),
                ]
            },
        )
        response["overview"]["understood"]["source_ids"] = [
            candidate_id,
            candidate_id,
        ]
        response["overview"]["changed"]["source_ids"] = [
            candidate_id,
            candidate_id,
        ]
        return response

    report = impact_atomize(ctx, lambda: AtomizeProvider(respond))

    assert report.overview.understood.source_uids == (source.uid,)
    assert report.overview.changed.source_uids == (source.uid,)
    assert tuple(item.memory.uid for item in report.items) == (source.uid, other.uid)


def test_atomize_overview_rejects_a_multiline_navigation_list() -> None:
    ctx = ops.init("overview/reject-list")
    ops.add(ctx, "The main entrance closes at 5 p.m.")

    def respond(payload: dict) -> dict[str, object]:
        response = _aggregate_response(
            payload,
            {
                "items": [
                    _item(payload["memories"][0]["candidate_id"]),
                ]
            },
        )
        response["overview"]["understood"]["text"] = (
            "- The entrance closes.\n- Staff access remains available."
        )
        return response

    with pytest.raises(AtomizeImpactError, match="report paragraph"):
        impact_atomize(ctx, lambda: AtomizeProvider(respond))


def test_atomize_impact_is_one_shot_exhaustive_and_context_ordered():
    ctx = ops.init("intake")
    first = ops.add(ctx, "The main entrance closes at 5 p.m.")
    second = ops.add(ctx, "The store closes. The café remains open.")
    third = ops.add(ctx, "Use the same card.")
    fourth = ops.add(ctx, "Summer construction notes")

    def respond(payload):
        ids = {
            memory["content"]: memory["candidate_id"] for memory in payload["memories"]
        }
        return {
            "items": [
                _item(
                    ids[fourth.content],
                    "NON_PROPOSITIONAL",
                    reason_codes=["A07_RETAIN_NON_CLAIMS"],
                ),
                _item(
                    ids[third.content],
                    "UNCERTAIN",
                    reason_codes=["A06_NO_HIDDEN_CONTEXT"],
                ),
                _item(
                    ids[second.content],
                    "COMPOSITE",
                    children=[
                        {
                            "content": "The store closes.",
                            "source_spans": ["The store closes"],
                        },
                        {
                            "content": "The café remains open.",
                            "source_spans": ["The café remains open"],
                        },
                    ],
                    reason_codes=[
                        "A01_ONE_FOCUS",
                        "A04_SOURCE_GROUNDED",
                    ],
                ),
                _item(ids[first.content]),
            ]
        }

    provider = AtomizeProvider(respond)
    report = impact_atomize(ctx, lambda: provider)

    assert len(provider.calls) == 1
    prompt, operation, schema, payload = provider.calls[0]
    assert operation == "impact_atomize"
    assert [memory["content"] for memory in payload["memories"]] == [
        first.content,
        second.content,
        third.content,
        fourth.content,
    ]
    assert "For the ATOMIZE CLASSIFICATION AND CHILDREN" in prompt
    assert "an UNCERTAIN atomize classification does not itself prove" in prompt
    assert "clean SINGLE/NONE and MUST be omitted" in prompt
    assert "after that time a card is required" in prompt
    assert "normally 2-10 English words and never more than 20" in prompt
    assert "Give students a physical card" in prompt
    assert "Never expose candidate IDs such as m000007" in prompt
    assert payload["context"]["declared_frame"] is None
    assert set(payload["context"]) == {
        "direct_memory_count",
        "declared_frame",
    }
    assert payload["ruleset_version"] == "atomize-v2-reviewed-frame-draft"
    assert set(payload["rules"]) == atomize_module.ATOMIZE_RULE_CODES
    assert all(payload["rules"].values())
    assert payload["calibration_cases"]
    assert all(
        case["id"] != "declared-frame-grounds-shared-scope"
        for case in payload["calibration_cases"]
    )
    assert schema["properties"]["items"]["minItems"] == 4
    assert "uniqueItems" not in json.dumps(schema)
    reading_schema = schema["properties"]["quality_issues"]["items"]["properties"][
        "ordinary_readings"
    ]["items"]
    assert reading_schema["required"] == ["label", "text"]
    assert reading_schema["additionalProperties"] is False

    assert [item.memory for item in report.items] == [
        first,
        second,
        third,
        fourth,
    ]
    assert [item.classification for item in report.items] == [
        "ATOMIC",
        "COMPOSITE",
        "UNCERTAIN",
        "NON_PROPOSITIONAL",
    ]
    assert [item.action for item in report.items] == [
        "KEEP",
        "SPLIT",
        "RECONCILE",
        "KEEP_CLASSIFIED",
    ]
    assert report.memory_count == 4
    assert report.projected_memory_count == 5


def test_quality_reading_labels_over_twenty_words_fail_closed():
    ctx = ops.init("quality-reading-length")
    memory = ops.add(ctx, "Ask the coordinator.")

    def respond(payload):
        candidate_id = payload["memories"][0]["candidate_id"]
        response = _aggregate_response(
            payload,
            {"items": [_item(candidate_id)]},
        )
        response["quality_issues"] = [
            {
                "kind": "AMBIGUITY",
                "source_ids": [candidate_id],
                "interpretation": "SINGLE",
                "clarification": "REQUIRED",
                "conflict": "NONE",
                "ordinary_readings": [
                    {
                        "label": " ".join(f"word{index}" for index in range(21)),
                        "text": "Contact the responsible coordinator.",
                    }
                ],
                "scope_dimensions": [],
                "reason": "The responsible contact route is absent.",
                "question": "How should the coordinator be contacted?",
            }
        ]
        return response

    with pytest.raises(
        AtomizeImpactError,
        match="invalid ordinary reading label",
    ):
        impact_atomize(ctx, lambda: AtomizeProvider(respond))

    assert memory.content == "Ask the coordinator."


def test_atomize_preview_neutralizes_terminal_control_characters(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx = ops.init("terminal-safe")
    source = ops.add(ctx, "First \x1b fact. Second \x07 fact.")
    store.save(ctx)
    store.set_current(ctx.name)

    def respond(payload):
        return {
            "items": [
                _item(
                    payload["memories"][0]["candidate_id"],
                    "COMPOSITE",
                    children=[
                        {
                            "content": "First \x1b fact.",
                            "source_spans": ["First \x1b fact"],
                        },
                        {
                            "content": "Second \x07 fact.",
                            "source_spans": ["Second \x07 fact"],
                        },
                    ],
                    reason="Two \x1b independent commitments.",
                )
            ]
        }

    monkeypatch.setattr(
        "memcommit.commands.impact.command.connect_codex_chatgpt_provider",
        lambda: AtomizeProvider(respond),
    )

    result = runner.invoke(app, ["impact", "atomize"])

    assert result.exit_code == 0, result.output
    assert "\x1b" not in result.output
    assert "\x07" not in result.output
    assert "First � fact." in result.output
    assert "Second � fact." in result.output
    assert source.uid[:8] in result.output


def test_empty_context_returns_without_loading_fixture_or_provider(monkeypatch):
    ctx = ops.init("empty")
    monkeypatch.setattr(
        atomize_module,
        "_load_calibration",
        lambda: pytest.fail("empty input should not load calibration"),
    )

    report = impact_atomize(ctx, ForbiddenProvider())

    assert report.memory_count == 0
    assert report.projected_memory_count == 0
    assert report.items == ()


@pytest.mark.parametrize(
    ("content", "segments"),
    [
        ("", 0),
        ("A", 1),
        ("A. B.", 2),
        ("A!\r\n\r\nB？\rC", 3),
        ("* first\n* second\n* third", 3),
        ("version 1.2 remains", 1),
    ],
)
def test_sentence_like_segmenter_is_deterministic(content, segments):
    assert sentence_like_segment_count(content) == segments


def test_size_is_only_a_locally_computed_review_lint():
    assert atomize_lint("x" * 81) == ("SIZE_REVIEW",)
    assert atomize_lint("A. B. C.") == ("SIZE_REVIEW",)
    assert atomize_lint("주차장에는 차량이 들어갈 수 없고 보행문은 열린다.") == ()


def test_parser_preserves_repeated_occurrence_children():
    ctx = ops.init("repeated")
    ops.add(ctx, "The gate is closed. The gate is closed.")

    def respond(payload):
        candidate_id = payload["memories"][0]["candidate_id"]
        child = {
            "content": "The gate is closed.",
            "source_spans": ["The gate is closed"],
        }
        return {
            "items": [
                _item(
                    candidate_id,
                    "COMPOSITE",
                    children=[child, child],
                    reason_codes=[
                        "A01_ONE_FOCUS",
                        "A08_PRESERVE_OCCURRENCES",
                    ],
                )
            ]
        }

    report = impact_atomize(ctx, lambda: AtomizeProvider(respond))

    assert len(report.items[0].children) == 2
    assert report.items[0].children[0].content == report.items[0].children[1].content


@pytest.mark.parametrize(
    "mutate",
    [
        lambda response, payload: response["items"].clear(),
        lambda response, payload: response["items"].append(dict(response["items"][0])),
        lambda response, payload: response["items"][0].update(candidate_id="unknown"),
        lambda response, payload: response["items"][0].update(classification="OTHER"),
        lambda response, payload: response["items"][0].update(
            reason_codes=["A01_ONE_FOCUS", "A01_ONE_FOCUS"]
        ),
        lambda response, payload: response["items"][0].update(extra=True),
        lambda response, payload: response["items"][0].update(
            classification="COMPOSITE",
            children=[
                {
                    "content": "Only one child.",
                    "source_spans": ["one source"],
                }
            ],
        ),
        lambda response, payload: response["items"][0].update(
            children=[
                {
                    "content": "A child.",
                    "source_spans": ["one source"],
                },
                {
                    "content": "Another child.",
                    "source_spans": ["one source"],
                },
            ]
        ),
    ],
)
def test_invalid_provider_records_fail_closed(mutate):
    ctx = ops.init("invalid")
    ops.add(ctx, "one source")

    def respond(payload):
        response = _all_atomic(payload)
        mutate(response, payload)
        return response

    with pytest.raises(AtomizeImpactError):
        impact_atomize(ctx, lambda: AtomizeProvider(respond))


def test_ungrounded_child_span_and_duplicate_json_keys_fail_closed():
    ctx = ops.init("invalid")
    ops.add(ctx, "A source. Another source.")

    def ungrounded(payload):
        return {
            "items": [
                _item(
                    payload["memories"][0]["candidate_id"],
                    "COMPOSITE",
                    children=[
                        {
                            "content": "A source.",
                            "source_spans": ["A source"],
                        },
                        {
                            "content": "Invented.",
                            "source_spans": ["not in the source"],
                        },
                    ],
                )
            ]
        }

    with pytest.raises(AtomizeImpactError, match="ungrounded"):
        impact_atomize(ctx, lambda: AtomizeProvider(ungrounded))

    duplicate_keys = '{"items":[],"items":[]}'
    with pytest.raises(AtomizeImpactError, match="structured output"):
        impact_atomize(
            ctx,
            lambda: AtomizeProvider(lambda payload: duplicate_keys),
        )


def test_payload_limit_fails_before_provider_connection(monkeypatch):
    ctx = ops.init("large")
    ops.add(ctx, "one source")
    monkeypatch.setattr(atomize_module, "ATOMIZE_INPUT_CHAR_LIMIT", 10)

    with pytest.raises(AtomizeImpactError, match="too large"):
        impact_atomize(ctx, ForbiddenProvider())


def test_cli_preview_is_direct_only_and_saves_only_analysis(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = ops.init("source")
    referenced = ops.add(source, "secret reference target")
    child = ops.init("child")
    ops.add(child, "nested content")
    root = ops.init("root")
    first = ops.add(root, "The entrance closes at 5 p.m.")
    root.add(
        MemoryRef(
            uid="memory-ref",
            target_context_uid=source.uid,
            target_context_name=source.name,
            target_memory_uid=referenced.uid,
            target=referenced,
        )
    )
    root.add(
        QueryContextRef(
            uid="query-ref",
            name="restricted",
            target_source_uid="query-source",
            provider="codex_chatgpt",
        )
    )
    root.add(child)
    second = ops.add(root, "Summer construction notes")
    for context in [source, child, root]:
        store.save(context)
    store.set_current(root.name)

    store._context_file(source.name).write_text("{invalid")
    store._context_file(child.name).write_text("{invalid")
    context_path = store._context_file(root.name)
    context_before = context_path.read_bytes()
    state_before = (isolated_store / "state.json").read_bytes()
    checkpoints_before = store.list_checkpoints(root.name)
    impact_path = isolated_store / "impact-plan.json"
    impact_path.write_bytes(b"existing directional impact sentinel")

    def respond(payload):
        assert [memory["content"] for memory in payload["memories"]] == [
            first.content,
            second.content,
        ]
        return {
            "items": [
                _item(payload["memories"][0]["candidate_id"]),
                _item(
                    payload["memories"][1]["candidate_id"],
                    "NON_PROPOSITIONAL",
                    reason_codes=["A07_RETAIN_NON_CLAIMS"],
                ),
            ]
        }

    provider = AtomizeProvider(respond)
    monkeypatch.setattr(
        MemoryStore,
        "load_query_source",
        lambda *args, **kwargs: pytest.fail(
            "atomize impact must never open a query-only source"
        ),
    )
    monkeypatch.setattr(
        "memcommit.commands.impact.command.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    result = runner.invoke(app, ["impact", "atomize"])

    assert result.exit_code == 0, result.output
    assert "RESULT · atomize · root" in result.output
    assert "sources=2 · projected=2" in result.output
    assert "splits=0 · children=0" in result.output
    assert "WHAT MEM UNDERSTOOD" in result.output
    assert "WHAT HAPPENED" in result.output
    assert "WHAT REMAINS UNRESOLVED" in result.output
    assert "REPRESENTATIVE / BOUNDARY CASES" in result.output
    assert (
        "No Memory changes have been applied. No checkpoint was created."
        in result.output
    )
    assert "Analysis saved" in result.output
    # The compact result workbench shows direct representative/boundary cases
    # so a person can assess the semantic pass without opening every record.
    # Referenced and embedded Context contents remain outside this operation.
    assert f"KEEP: {first.content}" in result.output
    assert f"KEEP_CLASSIFIED: {second.content}" in result.output
    assert "secret reference target" not in result.output
    assert "nested content" not in result.output
    assert len(provider.calls) == 1
    assert context_path.read_bytes() == context_before
    assert (isolated_store / "state.json").read_bytes() == state_before
    assert store.list_checkpoints(root.name) == checkpoints_before
    assert impact_path.read_bytes() == b"existing directional impact sentinel"
    assert store.current_context_name() == root.name
    analysis = store.load_atomize_analysis(root.uid)
    assert analysis is not None
    assert f"REOPEN · mem impact atomize --session {analysis.uid}" in result.output
    assert "BROWSE ATOMIZE · mem impact atomize --sessions" in result.output
    assert "BROWSE ALL IMPACT · mem impact --sessions" in result.output
    assert analysis.context_uid == root.uid
    assert [item.memory_uid for item in analysis.items] == [
        first.uid,
        second.uid,
    ]

    monkeypatch.setattr(
        "memcommit.commands.impact.command.connect_codex_chatgpt_provider",
        ForbiddenProvider(),
    )
    reopened = runner.invoke(
        app,
        ["impact", "atomize", "--session", analysis.uid],
    )

    assert reopened.exit_code == 0, reopened.output + reopened.stderr
    assert "WHAT MEM UNDERSTOOD" in reopened.output
    assert f"Resumed saved analysis [{analysis.uid[:8]}]" in reopened.output
    assert "the provider was not called" in reopened.output
    assert len(provider.calls) == 1


def test_cli_all_shows_atomic_items_and_explicit_context_does_not_switch(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    active = ops.init("active")
    target = ops.init("target")
    memory = ops.add(target, "One atomic fact.")
    store.save(active)
    store.save(target)
    store.set_current(active.name)
    provider = AtomizeProvider(_all_atomic)
    monkeypatch.setattr(
        "memcommit.commands.impact.command.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    result = runner.invoke(
        app,
        ["impact", "atomize", "target", "--all"],
    )

    assert result.exit_code == 0, result.output
    assert "RESULT · atomize · target" in result.output
    assert memory.content in result.output
    assert "ATOMIC" in result.output
    assert store.current_context_name() == active.name


def test_preview_refuses_to_save_if_context_changes_during_provider_call(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx = ops.init("changing")
    ops.add(ctx, "Original fact.")
    store.save(ctx)
    store.set_current(ctx.name)

    def respond(payload):
        changed = store.load(ctx.name)
        ops.add(changed, "Concurrent fact.")
        store.save(changed)
        return {"items": [_item(payload["memories"][0]["candidate_id"])]}

    monkeypatch.setattr(
        "memcommit.commands.impact.command.connect_codex_chatgpt_provider",
        lambda: AtomizeProvider(respond),
    )

    result = runner.invoke(app, ["impact", "atomize"])

    assert result.exit_code == 1
    assert "Context changed while atomize analysis was running" in result.stderr
    assert store.load_atomize_analysis(ctx.uid) is None
    assert len(store.load_direct(ctx.name).memories) == 2


def test_cli_empty_context_does_not_connect_provider(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx = ops.init("empty")
    store.save(
        ctx,
        AutoCheckpoint(
            command="init",
            args={"name": ctx.name},
            description=f"Initialized context '{ctx.name}'",
        ),
    )
    store.set_current(ctx.name)
    monkeypatch.setattr(
        "memcommit.commands.impact.command.connect_codex_chatgpt_provider",
        ForbiddenProvider(),
    )

    result = runner.invoke(app, ["impact", "atomize"])

    assert result.exit_code == 0, result.output
    assert "sources=0 · projected=0" in result.output
    assert (
        "No Memory changes have been applied. No checkpoint was created."
        in result.output
    )


def test_cli_rejects_mixed_or_incomplete_impact_forms_before_provider(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = ops.init("source")
    target = ops.init("target")
    ops.add(source, "source")
    store.save(source)
    store.save(target)
    store.set_current(source.name)
    monkeypatch.setattr(
        "memcommit.commands.impact.command.connect_codex_chatgpt_provider",
        ForbiddenProvider(),
    )

    mixed = runner.invoke(
        app,
        ["impact", "atomize", "--to", "target"],
    )
    mixed_from = runner.invoke(
        app,
        ["impact", "atomize", "--from", "source"],
    )
    missing = runner.invoke(app, ["impact"])
    wrong_options = runner.invoke(
        app,
        ["impact", "--to", "target", "--all"],
    )

    assert mixed.exit_code == 2
    assert "No such option" in mixed.stderr
    assert "--to" in mixed.stderr
    assert mixed_from.exit_code == 2
    assert "No such option" in mixed_from.stderr
    assert "--from" in mixed_from.stderr
    assert missing.exit_code == 2
    assert "choose an endpoint" in missing.stderr
    assert wrong_options.exit_code == 2
    assert "No such option" in wrong_options.stderr
    assert "--all" in wrong_options.stderr


def test_saved_atomize_analysis_applies_once_with_recorded_lineage(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx = ops.init("apply")
    atomic = ops.add(ctx, "The entrance closes at 5 p.m.")
    composite = ops.add(ctx, "The store closes. The café remains open.")
    uncertain = ops.add(ctx, "Use the same card.")
    store.save(
        ctx,
        AutoCheckpoint(
            command="init",
            args={"name": ctx.name},
            description=f"Initialized context '{ctx.name}'",
        ),
    )
    store.set_current(ctx.name)

    def respond(payload):
        ids = {
            memory["content"]: memory["candidate_id"] for memory in payload["memories"]
        }
        return {
            "items": [
                _item(ids[atomic.content]),
                _item(
                    ids[composite.content],
                    "COMPOSITE",
                    children=[
                        {
                            "content": "The store closes.",
                            "source_spans": ["The store closes"],
                        },
                        {
                            "content": "The café remains open.",
                            "source_spans": ["The café remains open"],
                        },
                    ],
                ),
                _item(
                    ids[uncertain.content],
                    "UNCERTAIN",
                    reason_codes=["A06_NO_HIDDEN_CONTEXT"],
                ),
            ]
        }

    monkeypatch.setattr(
        "memcommit.commands.impact.command.connect_codex_chatgpt_provider",
        lambda: AtomizeProvider(respond),
    )
    preview = runner.invoke(app, ["impact", "atomize"])
    assert preview.exit_code == 0, preview.output
    checkpoints_before = len(store.list_checkpoints(ctx.name))
    context_before_apply = store.load_direct(ctx.name).to_dict()

    applied = runner.invoke(app, ["atomize", "--save"])

    assert applied.exit_code == 0, applied.output
    assert "EFFECTS · SPLIT 1 · CHILDREN 2 · KEEP 2" in applied.output
    current = [
        item
        for item in store.load_direct(ctx.name).iter_items()
        if not isinstance(item, (MemoryRef, QueryContextRef))
    ]
    assert [item.content for item in current] == [
        atomic.content,
        "The store closes.",
        "The café remains open.",
        uncertain.content,
    ]
    assert current[0].uid == atomic.uid
    assert current[-1].uid == uncertain.uid
    assert composite.uid not in {item.uid for item in current}
    assert len(store.list_checkpoints(ctx.name)) == checkpoints_before + 1
    checkpoint = store.list_checkpoints(ctx.name)[0]
    assert checkpoint["command"] == "atomize"
    assert checkpoint["args"]["analysis_uid"] == (
        store.load_atomize_analysis(ctx.uid).uid
    )
    context_after_apply = store.load_direct(ctx.name).to_dict()
    changes = checkpoint["args"]["trace"]["changes"]
    assert [change["kind"] for change in changes] == [
        "KEEP",
        "SPLIT",
        "PRESERVE",
    ]

    repeated = runner.invoke(app, ["atomize", "--save"])
    assert repeated.exit_code == 0
    assert "already applied" in repeated.output
    assert len(store.list_checkpoints(ctx.name)) == checkpoints_before + 1

    traced = runner.invoke(
        app, ["trace", composite.uid[:8], "--verbose", "--plain"]
    )
    assert traced.exit_code == 0
    assert "SPLIT · RECORDED" in traced.output
    assert "ATOMIZE_PREVIEW  APPLIED" in traced.output
    assert "The store closes." in traced.output

    undone = runner.invoke(app, ["undo"])
    assert undone.exit_code == 0, undone.output
    assert store.load_direct(ctx.name).to_dict() == context_before_apply
    _current, projected_applied = revalidate_saved_atomize_analysis(
        store,
        store.load_atomize_analysis(ctx.uid),
    )
    # Undo restores Context content, not eligibility to apply the same
    # reviewed Atomize session a second time.
    assert projected_applied

    checkpoints_after_undo = len(store.list_checkpoints(ctx.name))
    repeated_after_undo = runner.invoke(app, ["atomize", "--save"])
    assert repeated_after_undo.exit_code == 0, repeated_after_undo.output
    assert "already applied" in repeated_after_undo.output
    assert len(store.list_checkpoints(ctx.name)) == checkpoints_after_undo
    assert store.load_direct(ctx.name).to_dict() == context_before_apply

    redone = runner.invoke(app, ["redo"])
    assert redone.exit_code == 0, redone.output
    assert store.load_direct(ctx.name).to_dict() == context_after_apply
    _current, projected_applied = revalidate_saved_atomize_analysis(
        store,
        store.load_atomize_analysis(ctx.uid),
    )
    assert projected_applied
    assert [entry["command"] for entry in store.list_checkpoints(ctx.name)[:3]] == [
        "redo",
        "undo",
        "atomize",
    ]


def test_planned_atomize_output_is_shared_and_save_materializes_it_once(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = ops.init("planned/input")
    ops.add(source, "The entrance closes at 5 p.m.")
    store.save(source)
    store.set_current(source.name)

    provider = AtomizeProvider(
        lambda payload: {"items": [_item(payload["memories"][0]["candidate_id"])]}
    )
    monkeypatch.setattr(
        "memcommit.commands.atomize.command.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    opened = runner.invoke(
        app,
        [
            "atomize",
            "--context",
            source.name,
            "--output",
            "planned/output",
        ],
    )
    assert opened.exit_code == 0, opened.output
    analysis = store.load_atomize_analysis(source.uid)
    assert analysis is not None
    workbench = store.load_atomize_workbench(analysis)
    assert workbench is not None
    assert workbench.output_context_name == "planned/output"
    assert not store.context_exists("planned/output")

    applied = runner.invoke(
        app,
        ["atomize", "--context", source.name, "--save"],
    )
    assert applied.exit_code == 0, applied.output
    assert "ATOMIZE APPLIED · planned/output" in applied.output
    assert "CONTEXT · CREATED AND CURRENT · planned/output" in applied.output
    assert store.load_direct(source.name).memories
    output = store.load_direct("planned/output")
    assert store.load_atomize_analysis(output.uid).uid == analysis.uid
    terminal_workbench = store.load_atomize_workbench(analysis)
    assert terminal_workbench is not None
    assert terminal_workbench.application is not None
    assert terminal_workbench.application.output_context_name == "planned/output"
    entries = atomize_session_entries(store)
    assert len(entries) == 1
    assert entries[0].key == analysis.uid
    assert entries[0].status == "APPLIED"
    assert "planned/input → planned/output" in entries[0].subtitle

    reopened = runner.invoke(
        app,
        ["atomize", "--context", source.name],
    )
    assert reopened.exit_code == 0, reopened.output
    assert "already applied" in reopened.output

    repeated = runner.invoke(
        app,
        ["atomize", "--context", source.name, "--save"],
    )
    assert repeated.exit_code == 0, repeated.output
    assert "already applied" in repeated.output
    assert [call[1] for call in provider.calls] == [
        "impact_atomize",
        "impact_atomize",
    ]

    diverged_output = store.load_direct("planned/output")
    ops.add(diverged_output, "A local follow-up was added after Atomize.")
    store.save(diverged_output)
    checkpoints_after_divergence = len(store.list_checkpoints("planned/output"))

    repeated_after_divergence = runner.invoke(
        app,
        ["atomize", "--context", source.name, "--save"],
    )

    assert repeated_after_divergence.exit_code == 0, repeated_after_divergence.output
    assert "already applied" in repeated_after_divergence.output
    assert len(store.list_checkpoints("planned/output")) == checkpoints_after_divergence
    assert atomize_session_entries(store)[0].status == "APPLIED"
    assert len(provider.calls) == 2


def test_atomize_save_as_rejects_conflicts_and_preserves_published_failure(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = ops.init("source")
    memory = ops.add(source, "First fact. Second fact.")
    store.save(
        source,
        AutoCheckpoint(
            command="init",
            args={"name": source.name},
            description="Initialized source",
        ),
    )
    store.set_current(source.name)

    def respond(payload):
        return {
            "items": [
                _item(
                    payload["memories"][0]["candidate_id"],
                    "COMPOSITE",
                    children=[
                        {
                            "content": "First fact.",
                            "source_spans": ["First fact"],
                        },
                        {
                            "content": "Second fact.",
                            "source_spans": ["Second fact"],
                        },
                    ],
                )
            ]
        }

    monkeypatch.setattr(
        "memcommit.commands.impact.command.connect_codex_chatgpt_provider",
        lambda: AtomizeProvider(respond),
    )
    assert runner.invoke(app, ["impact", "atomize"]).exit_code == 0
    source_bytes = store._context_file(source.name).read_bytes()
    existing = ops.init("existing")
    store.save(existing)

    mutually_exclusive = runner.invoke(
        app,
        ["atomize", "--save", "--save-as", "new"],
    )
    occupied = runner.invoke(
        app,
        ["atomize", "--save-as", existing.name],
    )

    assert mutually_exclusive.exit_code == 2
    assert "either --save or --save-as" in mutually_exclusive.stderr
    assert occupied.exit_code == 1
    assert "already exists" in occupied.stderr
    assert store.current_context_name() == source.name
    assert store._context_file(source.name).read_bytes() == source_bytes

    def fail_apply(*args, **kwargs):
        raise AtomizeImpactError("injected apply failure")

    monkeypatch.setattr(
        "memcommit.atomize_normal_form.apply_atomize_analysis",
        fail_apply,
    )
    failed = runner.invoke(app, ["atomize", "--save-as", "rolled-back"])

    assert failed.exit_code == 1
    assert "injected apply failure" in failed.stderr
    assert not store.context_exists("rolled-back")
    assert store.list_context_names() == ["existing", "source"]
    assert not any(store.atomize_analyses_dir.glob("*.json")) or list(
        store.atomize_analyses_dir.glob("*.json")
    ) == [store._atomize_analysis_path(source.uid)]
    assert store.current_context_name() == source.name
    assert store._context_file(source.name).read_bytes() == source_bytes
    assert memory.uid in store.load_direct(source.name).memories


def test_atomize_save_as_preserves_destination_when_final_switch_fails(
    isolated_store,
    monkeypatch,
):
    import memcommit.store as store_module

    store = MemoryStore()
    source = ops.init("switch-source")
    memory = ops.add(source, "First fact. Second fact.")
    store.save(source)
    store.set_current(source.name)

    def respond(payload):
        return {
            "items": [
                _item(
                    payload["memories"][0]["candidate_id"],
                    "COMPOSITE",
                    children=[
                        {
                            "content": "First fact.",
                            "source_spans": ["First fact"],
                        },
                        {
                            "content": "Second fact.",
                            "source_spans": ["Second fact"],
                        },
                    ],
                )
            ]
        }

    monkeypatch.setattr(
        "memcommit.commands.impact.command.connect_codex_chatgpt_provider",
        lambda: AtomizeProvider(respond),
    )
    assert runner.invoke(app, ["impact", "atomize"]).exit_code == 0
    source_bytes = store._context_file(source.name).read_bytes()
    state_bytes = store_module.STATE_FILE.read_bytes()
    original_write = store_module._write_json_atomic

    def fail_state_switch(path, data):
        if path == store_module.STATE_FILE and data.get("current") == "derived":
            raise OSError("injected state switch failure")
        return original_write(path, data)

    monkeypatch.setattr(
        store_module,
        "_write_json_atomic",
        fail_state_switch,
    )
    result = runner.invoke(app, ["atomize", "--save-as", "derived"])

    assert result.exit_code == 1
    assert "injected state switch failure" in result.stderr
    assert "final Atomize output and receipt are retained" in result.stderr
    assert store.context_exists("derived")
    assert len(store.list_checkpoints("derived")) == 1
    assert store.current_context_name() == source.name
    assert store_module.STATE_FILE.read_bytes() == state_bytes
    assert store._context_file(source.name).read_bytes() == source_bytes
    assert memory.uid in store.load_direct(source.name).memories


def test_atomize_save_as_retry_completes_receipt_without_duplicate_checkpoint(
    isolated_store,
    monkeypatch,
):
    from memcommit.operations.atomize.runtime import (
        MemoryStoreAtomizeSessionRepository,
    )

    store = MemoryStore()
    source = ops.init("retry-source")
    ops.add(source, "First fact. Second fact.")
    store.save(source)
    store.set_current(source.name)

    def respond(payload):
        return {
            "items": [
                _item(
                    payload["memories"][0]["candidate_id"],
                    "COMPOSITE",
                    children=[
                        {
                            "content": "First fact.",
                            "source_spans": ["First fact"],
                        },
                        {
                            "content": "Second fact.",
                            "source_spans": ["Second fact"],
                        },
                    ],
                )
            ]
        }

    monkeypatch.setattr(
        "memcommit.commands.impact.command.connect_codex_chatgpt_provider",
        lambda: AtomizeProvider(respond),
    )
    assert runner.invoke(app, ["impact", "atomize"]).exit_code == 0
    analysis = store.load_atomize_analysis(source.uid)
    assert analysis is not None
    original = MemoryStoreAtomizeSessionRepository.replace_application
    failed_once = False

    def fail_once(repository, *args, **kwargs):
        nonlocal failed_once
        if not failed_once:
            failed_once = True
            raise OSError("injected receipt failure")
        return original(repository, *args, **kwargs)

    monkeypatch.setattr(
        MemoryStoreAtomizeSessionRepository,
        "replace_application",
        fail_once,
    )

    failed = runner.invoke(app, ["atomize", "--save-as", "retry-output"])

    assert failed.exit_code == 1
    assert "injected receipt failure" in failed.stderr
    assert "retained" in failed.stderr
    assert store.context_exists("retry-output")
    first_checkpoints = store.list_checkpoints("retry-output")
    assert [checkpoint["command"] for checkpoint in first_checkpoints] == [
        "atomize"
    ]
    workbench = store.load_atomize_workbench(analysis)
    assert workbench is not None
    assert workbench.application is None
    assert store.current_context_name() == source.name

    retried = runner.invoke(
        app,
        ["atomize", "--context", source.name, "--save-as", "retry-output"],
    )

    assert retried.exit_code == 0, retried.output
    assert "RECOVERY STATUS · prior checkpoint recovered" in retried.output
    assert store.list_checkpoints("retry-output") == first_checkpoints
    workbench = store.load_atomize_workbench(analysis)
    assert workbench is not None
    assert workbench.application is not None
    assert workbench.application.checkpoint_uid == first_checkpoints[0]["uid"]
    assert store.current_context_name() == "retry-output"


def test_atomize_save_as_preserves_concurrent_current_selection(
    isolated_store,
    monkeypatch,
):
    from memcommit.atomize import apply_atomize_analysis as apply_analysis

    store = MemoryStore()
    source = ops.init("source")
    ops.add(source, "First fact. Second fact.")
    store.save(source)
    store.save(ops.init("other"))
    store.set_current(source.name)

    def respond(payload):
        return {
            "items": [
                _item(
                    payload["memories"][0]["candidate_id"],
                    "COMPOSITE",
                    children=[
                        {
                            "content": "First fact.",
                            "source_spans": ["First fact"],
                        },
                        {
                            "content": "Second fact.",
                            "source_spans": ["Second fact"],
                        },
                    ],
                )
            ]
        }

    monkeypatch.setattr(
        "memcommit.commands.impact.command.connect_codex_chatgpt_provider",
        lambda: AtomizeProvider(respond),
    )
    assert runner.invoke(app, ["impact", "atomize"]).exit_code == 0

    def switch_then_apply(context, analysis):
        store.set_current("other")
        return apply_analysis(context, analysis)

    monkeypatch.setattr(
        "memcommit.atomize_normal_form.apply_atomize_analysis",
        switch_then_apply,
    )

    result = runner.invoke(app, ["atomize", "--save-as", "derived"])

    assert result.exit_code == 1
    assert "current Context changed" in result.stderr
    assert "final Atomize output and receipt are retained" in result.stderr
    assert store.current_context_name() == "other"
    assert store.context_exists("derived")


def test_atomize_save_as_does_not_overwrite_concurrent_destination(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = ops.init("source")
    ops.add(source, "One atomic fact.")
    store.save(source)
    store.set_current(source.name)
    monkeypatch.setattr(
        "memcommit.commands.impact.command.connect_codex_chatgpt_provider",
        lambda: AtomizeProvider(_all_atomic),
    )
    assert runner.invoke(app, ["impact", "atomize"]).exit_code == 0
    original_projection = ops._atomize_projection
    competitor = None

    def create_competitor(context, name):
        nonlocal competitor
        result = original_projection(context, name)
        competitor = ops.init(name)
        ops.add(competitor, "concurrent owner")
        store.create_context(competitor)
        return result

    monkeypatch.setattr(
        "memcommit.atomize_runtime.ops._atomize_projection",
        create_competitor,
    )

    result = runner.invoke(app, ["atomize", "--save-as", "derived"])

    assert result.exit_code == 1
    assert "already exists" in result.stderr
    assert competitor is not None
    loaded = store.load_direct("derived")
    assert loaded.uid == competitor.uid
    assert [item.content for item in loaded.iter_items()] == ["concurrent owner"]
    assert store.current_context_name() == source.name


def test_atomize_split_fails_closed_when_catalog_is_incomplete(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = ops.init("source")
    memory = ops.add(source, "First fact. Second fact.")
    store.save(source)
    store.set_current(source.name)

    def respond(payload):
        return {
            "items": [
                _item(
                    payload["memories"][0]["candidate_id"],
                    "COMPOSITE",
                    children=[
                        {
                            "content": "First fact.",
                            "source_spans": ["First fact"],
                        },
                        {
                            "content": "Second fact.",
                            "source_spans": ["Second fact"],
                        },
                    ],
                )
            ]
        }

    monkeypatch.setattr(
        "memcommit.commands.impact.command.connect_codex_chatgpt_provider",
        lambda: AtomizeProvider(respond),
    )
    assert runner.invoke(app, ["impact", "atomize"]).exit_code == 0
    before = store._context_file(source.name).read_bytes()
    history = store.list_checkpoints(source.name)
    malformed = isolated_store / "contexts" / "malformed" / "context.json"
    malformed.parent.mkdir()
    malformed.write_text("{", encoding="utf-8")

    result = runner.invoke(app, ["atomize", "--save"])

    assert result.exit_code == 1
    assert "invalid" in result.stderr.lower()
    assert store._context_file(source.name).read_bytes() == before
    assert store.list_checkpoints(source.name) == history
    assert memory.uid in store.load_direct(source.name).memories


def test_atomize_save_rejects_unavailable_embedded_context_without_data_loss(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    child = ops.init("child")
    store.save(child)
    parent = ops.init("parent")
    memory = ops.add(parent, "One atomic fact.")
    ops.embed(child, parent)
    store.save(
        parent,
        AutoCheckpoint(
            command="init",
            args={"name": parent.name},
            description="Initialized parent",
        ),
    )
    store.set_current(parent.name)
    monkeypatch.setattr(
        "memcommit.commands.impact.command.connect_codex_chatgpt_provider",
        lambda: AtomizeProvider(_all_atomic),
    )
    assert runner.invoke(app, ["impact", "atomize"]).exit_code == 0
    store.delete(child.name)
    before = store._context_file(parent.name).read_bytes()
    checkpoints = store.list_checkpoints(parent.name)

    result = runner.invoke(app, ["atomize", "--save"])

    assert result.exit_code == 1
    assert "unavailable embedded Context reference" in result.stderr
    assert store._context_file(parent.name).read_bytes() == before
    assert store.list_checkpoints(parent.name) == checkpoints
    assert memory.uid in store.load_direct(parent.name).memories


@pytest.mark.parametrize(
    ("apply_args", "expected_name"),
    [
        (["atomize", "--save"], "interleaved"),
        (
            ["atomize", "--save-as", "interleaved-derived"],
            "interleaved-derived",
        ),
    ],
)
def test_atomize_apply_uses_direct_memory_ordinals_around_embedded_contexts(
    isolated_store,
    monkeypatch,
    apply_args,
    expected_name,
):
    store = MemoryStore()
    child = ops.init("shared/child")
    ops.add(child, "Child content is outside the atomize frame.")
    store.save(child)

    source = ops.init("interleaved")
    first = ops.add(source, "First direct Memory.")
    ops.embed(child, source)
    second = ops.add(source, "Second direct Memory.")
    store.save(source)
    store.set_current(source.name)
    source_bytes = store._context_file(source.name).read_bytes()
    monkeypatch.setattr(
        "memcommit.commands.impact.command.connect_codex_chatgpt_provider",
        lambda: AtomizeProvider(_all_atomic),
    )

    preview = runner.invoke(app, ["impact", "atomize"])
    analysis = store.load_atomize_analysis(source.uid)
    applied = runner.invoke(app, apply_args)

    assert preview.exit_code == 0, preview.output
    assert analysis is not None
    assert [item.position for item in analysis.items] == [0, 1]
    assert applied.exit_code == 0, applied.output
    result = store.load(expected_name)
    assert [
        (
            "memory"
            if isinstance(item, Memory)
            else "context"
            if isinstance(item, Context)
            else type(item).__name__
        )
        for item in result.iter_items()
    ] == ["memory", "context", "memory"]
    assert [item.uid for item in result.iter_items() if isinstance(item, Memory)] == [
        first.uid,
        second.uid,
    ]
    if expected_name != source.name:
        assert store._context_file(source.name).read_bytes() == source_bytes


def test_atomize_revert_keep_does_not_rearm_an_applied_analysis(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx = ops.init("revertable")
    source = ops.add(ctx, "First fact. Second fact.")
    store.save(
        ctx,
        AutoCheckpoint(
            command="init",
            args={"name": ctx.name},
            description="Initialized revertable",
        ),
    )
    store.set_current(ctx.name)

    def respond(payload):
        return {
            "items": [
                _item(
                    payload["memories"][0]["candidate_id"],
                    "COMPOSITE",
                    children=[
                        {
                            "content": "First fact.",
                            "source_spans": ["First fact"],
                        },
                        {
                            "content": "Second fact.",
                            "source_spans": ["Second fact"],
                        },
                    ],
                )
            ]
        }

    monkeypatch.setattr(
        "memcommit.commands.impact.command.connect_codex_chatgpt_provider",
        lambda: AtomizeProvider(respond),
    )
    assert runner.invoke(app, ["impact", "atomize"]).exit_code == 0
    assert runner.invoke(app, ["atomize", "--save"]).exit_code == 0
    init_uid = next(
        checkpoint["uid"]
        for checkpoint in store.list_checkpoints(ctx.name)
        if checkpoint["command"] == "init"
    )
    reverted = runner.invoke(app, ["revert", init_uid[:8], "--keep"])
    assert reverted.exit_code == 0, reverted.output
    assert source.uid in store.load_direct(ctx.name).memories

    inspected = runner.invoke(app, ["atomize"])
    assert inspected.exit_code == 0, inspected.output
    assert "already applied" in inspected.output

    checkpoints_after_revert = len(store.list_checkpoints(ctx.name))
    rejected_reapply = runner.invoke(app, ["atomize", "--save"])
    assert rejected_reapply.exit_code == 0, rejected_reapply.output
    assert "already applied" in rejected_reapply.output
    assert len(store.list_checkpoints(ctx.name)) == checkpoints_after_revert
    assert source.uid in store.load_direct(ctx.name).memories


def test_saved_atomize_analysis_revalidates_grounding_and_projected_count(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx = ops.init("validated")
    ops.add(ctx, "First fact. Second fact.")
    store.save(ctx)
    store.set_current(ctx.name)

    def respond(payload):
        return {
            "items": [
                _item(
                    payload["memories"][0]["candidate_id"],
                    "COMPOSITE",
                    children=[
                        {
                            "content": "First fact.",
                            "source_spans": ["First fact"],
                        },
                        {
                            "content": "Second fact.",
                            "source_spans": ["Second fact"],
                        },
                    ],
                )
            ]
        }

    monkeypatch.setattr(
        "memcommit.commands.impact.command.connect_codex_chatgpt_provider",
        lambda: AtomizeProvider(respond),
    )
    assert runner.invoke(app, ["impact", "atomize"]).exit_code == 0
    analysis = store.load_atomize_analysis(ctx.uid)
    assert analysis is not None

    ungrounded = analysis.to_dict()
    ungrounded["items"][0]["children"][0]["source_spans"] = [
        "Text absent from the source"
    ]
    with pytest.raises(
        AtomizeImpactError,
        match="Invalid saved atomize analysis child",
    ):
        AtomizeAnalysisSession.from_dict(ungrounded)

    wrong_count = analysis.to_dict()
    wrong_count["projected_memory_count"] = 99
    with pytest.raises(
        AtomizeImpactError,
        match="Invalid saved atomize analysis",
    ):
        AtomizeAnalysisSession.from_dict(wrong_count)


def test_atomize_store_rejects_tampered_saved_source_positions(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx = ops.init("position-bound")
    ops.add(ctx, "First fact.")
    ops.add(ctx, "Second fact.")
    store.save(ctx)
    store.set_current(ctx.name)
    monkeypatch.setattr(
        "memcommit.commands.impact.command.connect_codex_chatgpt_provider",
        lambda: AtomizeProvider(_all_atomic),
    )
    assert runner.invoke(app, ["impact", "atomize"]).exit_code == 0
    analysis = store.load_atomize_analysis(ctx.uid)
    assert analysis is not None
    analysis_before = store._atomize_analysis_path(ctx.uid).read_bytes()
    tampered = replace(
        analysis,
        items=tuple(
            replace(item, position=item.position + 10) for item in analysis.items
        ),
    )
    with pytest.raises(ValueError, match="analysis is invalid"):
        store.save_atomize_analysis(tampered)

    assert store._atomize_analysis_path(ctx.uid).read_bytes() == analysis_before
    assert [
        item.content
        for item in store.load_direct(ctx.name).iter_items()
        if isinstance(item, Memory)
    ] == ["First fact.", "Second fact."]
    assert store.list_checkpoints(ctx.name) == []


def test_atomize_save_blocks_stale_analysis_and_inbound_split_reference(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = ops.init("source")
    composite = ops.add(source, "First fact. Second fact.")
    store.save(source)
    store.set_current(source.name)

    def respond(payload):
        return {
            "items": [
                _item(
                    payload["memories"][0]["candidate_id"],
                    "COMPOSITE",
                    children=[
                        {
                            "content": "First fact.",
                            "source_spans": ["First fact"],
                        },
                        {
                            "content": "Second fact.",
                            "source_spans": ["Second fact"],
                        },
                    ],
                )
            ]
        }

    monkeypatch.setattr(
        "memcommit.commands.impact.command.connect_codex_chatgpt_provider",
        lambda: AtomizeProvider(respond),
    )
    assert runner.invoke(app, ["impact", "atomize"]).exit_code == 0

    target = ops.init("target")
    ops.embed_memory(composite, source, target)
    store.save(target)
    context_before = store._context_file(source.name).read_bytes()
    checkpoints_before = store.list_checkpoints(source.name)

    blocked = runner.invoke(app, ["atomize", "--save"])

    assert blocked.exit_code == 1
    assert "inbound memory references" in blocked.stderr
    assert store._context_file(source.name).read_bytes() == context_before
    assert store.list_checkpoints(source.name) == checkpoints_before

    target.clear()
    store.save(target)
    changed = store.load(source.name)
    ops.edit(changed, composite.uid, "Changed after preview.")
    store.save(
        changed,
        AutoCheckpoint(
            command="edit",
            args={"uid": composite.uid, "content": "Changed after preview."},
            description="Changed source",
        ),
    )

    stale = runner.invoke(app, ["atomize", "--save"])

    assert stale.exit_code == 1
    assert "stale" in stale.stderr


def test_atomize_save_as_is_one_creation_command_with_lifecycle_undo_redo(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = ops.init("source")
    atomic = ops.add(source, "The entrance closes at 5 p.m.")
    composite = ops.add(source, "The store closes. The café remains open.")
    query_ref = ops.reference_query_context(
        "organization/wiki",
        "7a9f2582-86aa-4650-8d72-287e82cc7942",
        source,
    )
    child = ops.init("shared/policy")
    ops.add(child, "The policy remains available.")
    store.save(child)
    ops.embed(child, source)
    store.save(
        source,
        AutoCheckpoint(
            command="init",
            args={"name": source.name},
            description="Initialized source",
        ),
    )
    store.set_current(source.name)

    observer = ops.init("observer")
    reference = ops.embed_memory(composite, source, observer)
    store.save(observer)

    def respond(payload):
        ids = {
            memory["content"]: memory["candidate_id"] for memory in payload["memories"]
        }
        return {
            "items": [
                _item(ids[atomic.content]),
                _item(
                    ids[composite.content],
                    "COMPOSITE",
                    children=[
                        {
                            "content": "The store closes.",
                            "source_spans": ["The store closes"],
                        },
                        {
                            "content": "The café remains open.",
                            "source_spans": ["The café remains open"],
                        },
                    ],
                ),
            ]
        }

    monkeypatch.setattr(
        "memcommit.commands.impact.command.connect_codex_chatgpt_provider",
        lambda: AtomizeProvider(respond),
    )
    monkeypatch.setattr(
        MemoryStore,
        "load_query_source",
        lambda *args, **kwargs: pytest.fail(
            "atomize save-as must not open query-only content"
        ),
    )
    preview = runner.invoke(app, ["impact", "atomize"])
    assert preview.exit_code == 0, preview.output
    source_bytes = store._context_file(source.name).read_bytes()
    source_checkpoints = store.list_checkpoints(source.name)
    source_analysis = store.load_atomize_analysis(source.uid)

    saved = runner.invoke(
        app,
        ["atomize", "--save-as", "derived/atomized"],
    )

    assert saved.exit_code == 0, saved.output
    assert "ATOMIZE APPLIED · derived/atomized" in saved.output
    assert "CONTEXT · CREATED AND CURRENT · derived/atomized" in saved.output
    assert store.current_context_name() == "derived/atomized"
    assert store._context_file(source.name).read_bytes() == source_bytes
    assert store.list_checkpoints(source.name) == source_checkpoints
    assert isinstance(
        store.load_direct(source.name).memories[composite.uid],
        Memory,
    )

    destination = store.load("derived/atomized")
    assert destination.uid != source.uid
    direct_memories = [
        item for item in destination.iter_items() if isinstance(item, Memory)
    ]
    assert [item.content for item in direct_memories] == [
        atomic.content,
        "The store closes.",
        "The café remains open.",
    ]
    assert direct_memories[0].uid == atomic.uid
    assert composite.uid not in {item.uid for item in direct_memories}
    assert all(
        item.uid not in {atomic.uid, composite.uid} for item in direct_memories[1:]
    )
    assert any(
        isinstance(item, QueryContextRef) and item.uid == query_ref.uid
        for item in destination.iter_items()
    )
    assert any(
        isinstance(item, Context) and item.name == child.name
        for item in destination.iter_items()
    )
    assert [
        checkpoint["command"] for checkpoint in store.list_checkpoints(destination.name)
    ] == ["atomize"]
    destination_after_apply = destination.to_dict()
    destination_uid = destination.uid
    checkpoint_uid = store.list_checkpoints(destination.name)[0]["uid"]

    destination_analysis = store.load_atomize_analysis(destination.uid)
    assert source_analysis is not None
    assert destination_analysis is not None
    assert destination_analysis.uid == source_analysis.uid
    assert destination_analysis.context_uid == destination.uid
    assert store.load_atomize_analysis(source.uid).context_uid == source.uid

    observer_ref = store.load(observer.name).memories[reference.uid]
    assert isinstance(observer_ref, MemoryRef)
    assert observer_ref.target_context_uid == source.uid
    assert observer_ref.target is not None
    assert observer_ref.target.uid == composite.uid

    traced = runner.invoke(
        app,
        [
            "trace",
            composite.uid[:8],
            "--context",
            destination.name,
                "--verbose",
                "--plain",
            ],
    )
    assert traced.exit_code == 0, traced.output
    assert "CREATED+SPLIT · RECORDED" in traced.output
    assert "ATOMIZE_PREVIEW  APPLIED" in traced.output

    undone = runner.invoke(app, ["undo"])
    assert undone.exit_code == 0, undone.output
    assert not store.context_exists(destination.name)
    assert store.current_context_name() == source.name
    source_workbench = store.load_atomize_workbench(source_analysis)
    assert source_workbench is not None
    assert source_workbench.application is None

    redone = runner.invoke(app, ["redo"])
    assert redone.exit_code == 0, redone.output
    assert store.load_direct(destination.name).to_dict() == destination_after_apply
    assert store.load_direct(destination.name).uid == destination_uid
    restored_analysis = store.load_atomize_analysis(destination_uid)
    assert restored_analysis is not None
    assert restored_analysis.uid == source_analysis.uid
    source_workbench = store.load_atomize_workbench(source_analysis)
    assert source_workbench is not None
    assert source_workbench.application is not None
    assert source_workbench.application.checkpoint_uid == checkpoint_uid
    assert [
        checkpoint["command"]
        for checkpoint in store.list_checkpoints(destination.name)[:3]
    ] == ["redo", "undo", "atomize"]
