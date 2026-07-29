"""Contracts for the preview-only ``mem impact atomize`` operation."""
from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

import memcommit.atomize as atomize_module
import memcommit.ops as ops
from memcommit.atomize import (
    AtomizeImpactError,
    atomize_lint,
    impact_atomize,
    sentence_like_segment_count,
)
from memcommit.cli import app
from memcommit.context import MemoryRef, QueryContextRef
from memcommit.store import MemoryStore


runner = CliRunner()
PAYLOAD_MARKER = "ATOMIZE IMPACT PAYLOAD:\n"


class AtomizeProvider:
    def __init__(self, responder):
        self.responder = responder
        self.calls: list[tuple[str, str, dict[str, object], dict]] = []

    def complete(self, prompt, *, operation, output_schema=None):
        payload = json.loads(prompt.split(PAYLOAD_MARKER, 1)[1])
        self.calls.append((prompt, operation, output_schema, payload))
        response = self.responder(payload)
        return response if isinstance(response, str) else json.dumps(response)


class ForbiddenProvider:
    def __call__(self):
        raise AssertionError("provider should not be connected")


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
    return {
        "items": [
            _item(memory["candidate_id"])
            for memory in payload["memories"]
        ]
    }


def test_atomize_impact_is_one_shot_exhaustive_and_context_ordered():
    ctx = ops.init("intake")
    first = ops.add(ctx, "The main entrance closes at 5 p.m.")
    second = ops.add(ctx, "The store closes. The café remains open.")
    third = ops.add(ctx, "Use the same card.")
    fourth = ops.add(ctx, "Summer construction notes")

    def respond(payload):
        ids = {
            memory["content"]: memory["candidate_id"]
            for memory in payload["memories"]
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
    assert "Judge each candidate ONLY" in prompt
    assert payload["context"]["declared_frame"] is None
    assert set(payload["context"]) == {
        "direct_memory_count",
        "declared_frame",
    }
    assert payload["ruleset_version"] == "atomize-v1-draft"
    assert set(payload["rules"]) == atomize_module.ATOMIZE_RULE_CODES
    assert all(payload["rules"].values())
    assert payload["calibration_cases"]
    assert all(
        case["id"] != "declared-frame-grounds-shared-scope"
        for case in payload["calibration_cases"]
    )
    assert schema["properties"]["items"]["minItems"] == 4
    assert "uniqueItems" not in json.dumps(schema)

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
    assert (
        report.items[0].children[0].content
        == report.items[0].children[1].content
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda response, payload: response["items"].clear(),
        lambda response, payload: response["items"].append(
            dict(response["items"][0])
        ),
        lambda response, payload: response["items"][0].update(
            candidate_id="unknown"
        ),
        lambda response, payload: response["items"][0].update(
            classification="OTHER"
        ),
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

    duplicate_keys = (
        '{"items":[],"items":[]}'
    )
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


def test_cli_preview_is_direct_only_and_writes_nothing(
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
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    result = runner.invoke(app, ["impact", "atomize"])

    assert result.exit_code == 0, result.output
    assert "Atomize impact: root" in result.output
    assert "2 direct Memories -> 2 projected" in result.output
    assert "1 atomic, 0 composite, 0 uncertain, 1 non-propositional" in (
        result.output
    )
    assert "No changes applied. No checkpoint created." in result.output
    assert first.content not in result.output
    assert second.content in result.output
    assert len(provider.calls) == 1
    assert context_path.read_bytes() == context_before
    assert (isolated_store / "state.json").read_bytes() == state_before
    assert store.list_checkpoints(root.name) == checkpoints_before
    assert impact_path.read_bytes() == b"existing directional impact sentinel"
    assert store.current_context_name() == root.name


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
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    result = runner.invoke(
        app,
        ["impact", "atomize", "--context", "target", "--all"],
    )

    assert result.exit_code == 0, result.output
    assert "Atomize impact: target" in result.output
    assert memory.content in result.output
    assert "KEEP" in result.output
    assert store.current_context_name() == active.name


def test_cli_empty_context_does_not_connect_provider(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx = ops.init("empty")
    store.save(ctx)
    store.set_current(ctx.name)
    monkeypatch.setattr(
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
        ForbiddenProvider(),
    )

    result = runner.invoke(app, ["impact", "atomize"])

    assert result.exit_code == 0, result.output
    assert "0 direct Memories -> 0 projected" in result.output
    assert "No changes applied. No checkpoint created." in result.output


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
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
        ForbiddenProvider(),
    )

    mixed = runner.invoke(
        app,
        ["impact", "atomize", "--to", "target"],
    )
    missing = runner.invoke(app, ["impact"])
    wrong_options = runner.invoke(
        app,
        ["impact", "--to", "target", "--all"],
    )

    assert mixed.exit_code == 2
    assert "cannot be combined" in mixed.stderr
    assert missing.exit_code == 2
    assert "choose a target" in missing.stderr
    assert wrong_options.exit_code == 2
    assert "only valid" in wrong_options.stderr
