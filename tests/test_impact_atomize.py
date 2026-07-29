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


def _aggregate_response(payload: dict, response: dict) -> dict:
    """Wrap legacy item-focused fakes in the current one-shot envelope."""
    candidate_ids = [
        memory["candidate_id"] for memory in payload["memories"]
    ]
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
        payload = json.loads(prompt.split(PAYLOAD_MARKER, 1)[1])
        self.calls.append((prompt, operation, output_schema, payload))
        response = self.responder(payload)
        if isinstance(response, dict) and set(response) == {"items"}:
            response = _aggregate_response(payload, response)
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
    assert "For the ATOMIZE CLASSIFICATION AND CHILDREN" in prompt
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
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
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
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    result = runner.invoke(app, ["impact", "atomize"])

    assert result.exit_code == 0, result.output
    assert "MEM IMPACT · ATOMIZE · root" in result.output
    assert "2 source Memories → 2 projected" in result.output
    assert "0 proposed splits → 0 children" in result.output
    assert "WHAT MEM UNDERSTOOD" in result.output
    assert "WHAT CHANGED / REMAINS UNRESOLVED" in result.output
    assert (
        "No Memory changes have been applied. No checkpoint was created."
        in result.output
    )
    assert "Analysis saved" in result.output
    assert first.content not in result.output
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
    assert analysis.context_uid == root.uid
    assert [item.memory_uid for item in analysis.items] == [
        first.uid,
        second.uid,
    ]


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
    assert "MEM IMPACT · ATOMIZE · target" in result.output
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
        return {
            "items": [
                _item(payload["memories"][0]["candidate_id"])
            ]
        }

    monkeypatch.setattr(
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
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
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
        ForbiddenProvider(),
    )

    result = runner.invoke(app, ["impact", "atomize"])

    assert result.exit_code == 0, result.output
    assert "0 source Memories → 0 projected" in result.output
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
            memory["content"]: memory["candidate_id"]
            for memory in payload["memories"]
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
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
        lambda: AtomizeProvider(respond),
    )
    preview = runner.invoke(app, ["impact", "atomize"])
    assert preview.exit_code == 0, preview.output
    checkpoints_before = len(store.list_checkpoints(ctx.name))

    applied = runner.invoke(app, ["atomize", "--save"])

    assert applied.exit_code == 0, applied.output
    assert "1 split -> 2 children" in applied.output
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

    traced = runner.invoke(app, ["trace", composite.uid[:8]])
    assert traced.exit_code == 0
    assert "SPLIT  RECORDED" in traced.output
    assert "ATOMIZE_PREVIEW  APPLIED" in traced.output
    assert "The store closes." in traced.output


def test_atomize_save_as_rejects_conflicts_and_rolls_back_failure(
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
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
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
        "memcommit.commands.atomize.apply_atomize_analysis",
        fail_apply,
    )
    failed = runner.invoke(app, ["atomize", "--save-as", "rolled-back"])

    assert failed.exit_code == 1
    assert "injected apply failure" in failed.stderr
    assert not store.context_exists("rolled-back")
    assert store.list_context_names() == ["existing", "source"]
    assert store.current_context_name() == source.name
    assert store._context_file(source.name).read_bytes() == source_bytes
    assert memory.uid in store.load_direct(source.name).memories


def test_atomize_save_as_rolls_back_when_final_state_switch_fails(
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
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
        lambda: AtomizeProvider(respond),
    )
    assert runner.invoke(app, ["impact", "atomize"]).exit_code == 0
    source_bytes = store._context_file(source.name).read_bytes()
    state_bytes = store_module.STATE_FILE.read_bytes()
    original_write = store_module._write_json_atomic

    def fail_state_switch(path, data):
        if (
            path == store_module.STATE_FILE
            and data.get("current") == "derived"
        ):
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
    assert not store.context_exists("derived")
    assert store.current_context_name() == source.name
    assert store_module.STATE_FILE.read_bytes() == state_bytes
    assert store._context_file(source.name).read_bytes() == source_bytes
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
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
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
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
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
    assert [
        item.uid
        for item in result.iter_items()
        if isinstance(item, Memory)
    ] == [first.uid, second.uid]
    if expected_name != source.name:
        assert store._context_file(source.name).read_bytes() == source_bytes


def test_atomize_revert_keep_makes_saved_analysis_current_again(
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
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
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
    assert "CURRENT" in inspected.output
    assert "APPLIED" not in inspected.output

    reapplied = runner.invoke(app, ["atomize", "--save"])
    assert reapplied.exit_code == 0, reapplied.output
    assert "1 split -> 2 children" in reapplied.output


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
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
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
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
        lambda: AtomizeProvider(_all_atomic),
    )
    assert runner.invoke(app, ["impact", "atomize"]).exit_code == 0
    analysis = store.load_atomize_analysis(ctx.uid)
    assert analysis is not None
    analysis_before = store._atomize_analysis_path(ctx.uid).read_bytes()
    tampered = replace(
        analysis,
        items=tuple(
            replace(item, position=item.position + 10)
            for item in analysis.items
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
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
        lambda: AtomizeProvider(respond),
    )
    assert runner.invoke(app, ["impact", "atomize"]).exit_code == 0

    target = ops.init("target")
    ops.reference_memory(composite, source, target)
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


def test_atomize_save_as_preserves_source_and_records_base_then_apply(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = ops.init("source")
    atomic = ops.add(source, "The entrance closes at 5 p.m.")
    composite = ops.add(source, "The store closes. The café remains open.")
    query_ref = ops.reference_query_context(
        "campus/wiki",
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
    reference = ops.reference_memory(composite, source, observer)
    store.save(observer)

    def respond(payload):
        ids = {
            memory["content"]: memory["candidate_id"]
            for memory in payload["memories"]
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
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
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
    assert "Created and atomized 'derived/atomized'" in saved.output
    assert "Two checkpoints created" in saved.output
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
        item.uid not in {atomic.uid, composite.uid}
        for item in direct_memories[1:]
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
        checkpoint["command"]
        for checkpoint in store.list_checkpoints(destination.name)
    ] == ["atomize", "init"]

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
        ],
    )
    assert traced.exit_code == 0, traced.output
    assert "CREATED  RECORDED" in traced.output
    assert "SPLIT  RECORDED" in traced.output
    assert "ATOMIZE_PREVIEW  APPLIED" in traced.output
