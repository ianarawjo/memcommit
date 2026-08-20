"""Directional Add contracts for standalone Distill and Elaborate."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

import memcommit.commands.distill as distill_command
import memcommit.commands.elaborate as elaborate_command
import memcommit.commands.impact_process_local as impact_process_local
import memcommit.ops as ops
from memcommit.cli import app
from memcommit.distill import DISTILL_OPERATION, DISTILL_PAYLOAD_MARKER
from memcommit.elaborate import ELABORATE_OPERATION, ELABORATE_PAYLOAD_MARKER
from memcommit.store import MemoryStore, context_record_digest


runner = CliRunner()


def _create(
    store: MemoryStore,
    name: str,
    *contents: str,
):
    context = ops.init(name)
    for content in contents:
        ops.add(context, content)
    store.create_context(context)
    return context


class _ElaborateProvider:
    calls: list[dict[str, object]] = []

    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == ELABORATE_OPERATION
        payload = json.loads(prompt.split(ELABORATE_PAYLOAD_MARKER, 1)[1])
        type(self).calls.append(payload)
        if payload["mode"] == "GOAL_TO_RULES":
            return json.dumps(
                {
                    "overview": "One operational Rule makes the Goal concrete.",
                    "rules": [
                        {
                            "content": "Confirm the selected ticker before acting.",
                            "rationale": "This operationalizes the stated Goal.",
                        }
                    ],
                }
            )
        return json.dumps(
            {
                "overview": "A fit and boundary Case make the Rule concrete.",
                "cases": [
                    {
                        "proposition": "The user explicitly confirms ticker AAPL.",
                        "expected": "Proceed with AAPL.",
                        "rationale": "This is a fitting Case.",
                        "case_role": "FIT",
                        "rule_checks": [
                            {
                                "source_rule_index": index,
                                "evidence": "The proposition satisfies this Rule.",
                            }
                            for index, _rule in enumerate(payload["inputs"], 1)
                        ],
                    },
                    {
                        "proposition": "The user mentions AAPL without confirming it.",
                        "expected": "Ask for confirmation.",
                        "rationale": "This is a boundary Case.",
                        "case_role": "BOUNDARY",
                        "rule_checks": [
                            {
                                "source_rule_index": index,
                                "evidence": "The proposition satisfies this Rule.",
                            }
                            for index, _rule in enumerate(payload["inputs"], 1)
                        ],
                    },
                ],
            }
        )


class _DistillProvider:
    calls: list[dict[str, object]] = []

    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == DISTILL_OPERATION
        payload = json.loads(prompt.split(DISTILL_PAYLOAD_MARKER, 1)[1])
        type(self).calls.append(payload)
        aliases = [
            item["memory_id"] for item in payload["source"]["memories"]
        ]
        return json.dumps(
            {
                "overview": "The observations support one bounded ticker Rule.",
                "rules": [
                    {
                        "content": "Use the exchange-confirmed ticker symbol.",
                        "rationale": "The Source observations support it.",
                        "support_memory_ids": aliases[:1],
                        "boundary_memory_ids": aliases[1:2],
                    }
                ],
                "outside_memory_ids": aliases[2:],
            }
        )


@pytest.mark.parametrize(
    ("argv", "current", "expected_source", "expected_target"),
    (
        ((), "matrix/current", "matrix/current", "matrix/current"),
        (("--to", "matrix/target"), "matrix/source", "matrix/source", "matrix/target"),
        (("--from", "matrix/source"), "matrix/target", "matrix/source", "matrix/target"),
        (
            ("--from", "matrix/source", "--to", "matrix/target"),
            "matrix/current",
            "matrix/source",
            "matrix/target",
        ),
    ),
)
def test_elaborate_endpoint_matrix_adds_atomically(
    isolated_store,
    monkeypatch,
    argv,
    current,
    expected_source,
    expected_target,
) -> None:
    store = MemoryStore()
    for name in ("matrix/source", "matrix/target", "matrix/current"):
        _create(store, name, "Confirm a ticker before acting.")
    store.set_current(current)
    before = {
        name: len(store.load_direct(name).order)
        for name in ("matrix/source", "matrix/target", "matrix/current")
    }
    _ElaborateProvider.calls = []
    monkeypatch.setattr(
        elaborate_command,
        "connect_semantic_provider",
        _ElaborateProvider,
    )

    result = runner.invoke(app, ["elaborate", *argv])

    assert result.exit_code == 0, result.output
    assert f"ELABORATE APPLIED · {expected_target}" in result.output
    assert f"SOURCE · {expected_source} · TARGET · {expected_target}" in result.output
    assert "EFFECTS · ADD 2 MEMORIES" in result.output
    for name, count in before.items():
        expected = count + 2 if name == expected_target else count
        assert len(store.load_direct(name).order) == expected
    checkpoint = store.list_checkpoints(expected_target)[0]
    assert checkpoint["command"] == "elaborate"
    assert checkpoint["args"]["elaborate"]["effect"] == "ADD"
    assert len(checkpoint["args"]["elaborate"]["result_memory_uids"]) == 2
    assert len(_ElaborateProvider.calls[0]["inputs"]) == 1


def test_mem_elaborate_number_is_an_exact_cli_and_checkpoint_contract(
    isolated_store,
    monkeypatch,
) -> None:
    store = MemoryStore()
    target = _create(store, "number/target", "Existing destination language.")
    store.set_current(target.name)
    _ElaborateProvider.calls = []
    monkeypatch.setattr(
        elaborate_command,
        "connect_semantic_provider",
        _ElaborateProvider,
    )

    result = runner.invoke(
        app,
        [
            "elaborate",
            "--goal",
            "Confirm a ticker before acting.",
            "--n",
            "1",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "EFFECTS · ADD 1 MEMORIES" in result.output
    assert _ElaborateProvider.calls[0]["number"] == 1
    checkpoint = store.list_checkpoints(target.name)[0]
    assert checkpoint["args"]["elaborate"]["number"] == 1


def test_elaborate_context_role_is_explicit_and_not_name_based(
    isolated_store,
    monkeypatch,
) -> None:
    store = MemoryStore()
    _create(store, "not-a-goal-name", "Require confirmation before a trade.")
    _create(store, "ordinary-output", "Existing target content.")
    store.set_current("ordinary-output")
    monkeypatch.setattr(
        elaborate_command,
        "connect_semantic_provider",
        _ElaborateProvider,
    )

    result = runner.invoke(
        app,
        [
            "elaborate",
            "--from",
            "not-a-goal-name",
            "--to",
            "ordinary-output",
            "--as",
            "goal",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "MODE · GOAL_TO_RULES · VERIFICATION · UNVERIFIED" in result.output
    assert "Confirm the selected ticker before acting." in (
        memory.content for memory in store.load_direct("ordinary-output").memories.values()
    )


@pytest.mark.parametrize(
    ("argv", "current", "expected_source", "expected_target"),
    (
        ((), "matrix/current", "matrix/current", "matrix/current"),
        (("--to", "matrix/target"), "matrix/source", "matrix/source", "matrix/target"),
        (("--from", "matrix/source"), "matrix/target", "matrix/source", "matrix/target"),
        (
            ("--from", "matrix/source", "--to", "matrix/target"),
            "matrix/current",
            "matrix/source",
            "matrix/target",
        ),
    ),
)
def test_distill_endpoint_matrix_adds_to_existing_target(
    isolated_store,
    monkeypatch,
    argv,
    current,
    expected_source,
    expected_target,
) -> None:
    store = MemoryStore()
    for name in ("matrix/source", "matrix/target", "matrix/current"):
        _create(
            store,
            name,
            "Apple trades as AAPL on Nasdaq.",
            "Microsoft trades as MSFT on Nasdaq.",
        )
    store.set_current(current)
    before = {
        name: len(store.load_direct(name).order)
        for name in ("matrix/source", "matrix/target", "matrix/current")
    }
    _DistillProvider.calls = []
    monkeypatch.setattr(
        distill_command,
        "connect_semantic_provider",
        _DistillProvider,
    )

    result = runner.invoke(app, ["distill", *argv])

    assert result.exit_code == 0, result.output
    assert (
        f"DISTILL APPLIED · {expected_source} → {expected_target}"
        in result.output
    )
    assert "EFFECTS · ADD 1 RULES" in result.output
    for name, count in before.items():
        expected = count + 1 if name == expected_target else count
        assert len(store.load_direct(name).order) == expected
    checkpoint = store.list_checkpoints(expected_target)[0]
    assert checkpoint["command"] == "distill"
    assert checkpoint["args"]["distill"]["effect"] == "ADD"
    assert checkpoint["args"]["distill"]["target_context"] == expected_target


@pytest.mark.parametrize("operation", ("elaborate", "distill"))
def test_impact_endpoint_preview_never_adds(
    isolated_store,
    monkeypatch,
    operation,
) -> None:
    store = MemoryStore()
    source = _create(
        store,
        "impact/source",
        "Apple trades as AAPL on Nasdaq.",
        "Microsoft trades as MSFT on Nasdaq.",
    )
    target = _create(store, "impact/target", "Existing target content.")
    store.set_current(target.name)
    before_source = context_record_digest(store.load_direct(source.name))
    before_target = context_record_digest(store.load_direct(target.name))
    provider = _ElaborateProvider if operation == "elaborate" else _DistillProvider
    monkeypatch.setattr(
        impact_process_local,
        "connect_semantic_provider",
        provider,
    )

    result = runner.invoke(
        app,
        [
            "impact",
            operation,
            "--from",
            source.name,
            "--to",
            target.name,
            *(["--number", "2"] if operation == "elaborate" else []),
        ],
    )

    assert result.exit_code == 0, result.output
    assert f"SOURCE · {source.name}" in result.output
    assert f"TARGET · {target.name} · EXISTING · UNCHANGED" in result.output
    if operation == "distill":
        assert "PROPOSED RULES" in result.output
        assert "IMPACT · DISTILL ADD" not in result.output
    else:
        assert "ENDPOINTS UNCHANGED" in result.output
        assert _ElaborateProvider.calls[-1]["number"] == 2
    assert context_record_digest(store.load_direct(source.name)) == before_source
    assert context_record_digest(store.load_direct(target.name)) == before_target
    assert store.list_checkpoints(target.name) == []


@pytest.mark.parametrize("operation", ("elaborate", "distill"))
def test_missing_target_fails_before_provider_construction(
    isolated_store,
    monkeypatch,
    operation,
) -> None:
    store = MemoryStore()
    source = _create(store, "missing/source", "Confirm a ticker before acting.")
    store.set_current(source.name)

    def unexpected_provider():
        raise AssertionError("provider must not be constructed")

    command = elaborate_command if operation == "elaborate" else distill_command
    monkeypatch.setattr(command, "connect_semantic_provider", unexpected_provider)

    result = runner.invoke(
        app,
        [operation, "--from", source.name, "--to", "missing/target"],
    )

    assert result.exit_code == 1
    assert "not found" in result.output
    assert store.list_checkpoints(source.name) == []


def test_elaborate_target_drift_publishes_no_generated_memory(
    isolated_store,
    monkeypatch,
) -> None:
    store = MemoryStore()
    source = _create(store, "drift/source", "Confirm a ticker before acting.")
    target = _create(store, "drift/target", "Existing target content.")
    store.set_current(target.name)

    class _DriftingProvider(_ElaborateProvider):
        def complete(self, prompt, *, operation, output_schema=None):
            changed = store.load_for_update(target.name)
            ops.add(changed, "Concurrent target change.")
            store.save(changed)
            return super().complete(
                prompt,
                operation=operation,
                output_schema=output_schema,
            )

    monkeypatch.setattr(
        elaborate_command,
        "connect_semantic_provider",
        _DriftingProvider,
    )

    result = runner.invoke(
        app,
        ["elaborate", "--from", source.name, "--to", target.name],
    )

    assert result.exit_code == 1
    contents = [memory.content for memory in store.load_direct(target.name).memories.values()]
    assert contents == ["Existing target content.", "Concurrent target change."]
    assert "no generated Memories were added" in result.output


def test_distill_source_drift_publishes_no_generated_rule(
    isolated_store,
    monkeypatch,
) -> None:
    store = MemoryStore()
    source = _create(
        store,
        "drift/source",
        "Apple trades as AAPL on Nasdaq.",
        "Microsoft trades as MSFT on Nasdaq.",
    )
    target = _create(store, "drift/target", "Existing target content.")
    store.set_current(target.name)

    class _DriftingProvider(_DistillProvider):
        def complete(self, prompt, *, operation, output_schema=None):
            changed = store.load_for_update(source.name)
            ops.add(changed, "Concurrent source change.")
            store.save(changed)
            return super().complete(
                prompt,
                operation=operation,
                output_schema=output_schema,
            )

    monkeypatch.setattr(
        distill_command,
        "connect_semantic_provider",
        _DriftingProvider,
    )

    result = runner.invoke(
        app,
        ["distill", "--from", source.name, "--to", target.name],
    )

    assert result.exit_code == 1
    assert [
        memory.content for memory in store.load_direct(target.name).memories.values()
    ] == ["Existing target content."]
    assert "changed while Distill was running" in result.output


def test_relative_endpoints_share_one_current_snapshot(
    isolated_store,
    monkeypatch,
) -> None:
    store = MemoryStore()
    source = _create(
        store,
        "relative/source",
        "Apple trades as AAPL on Nasdaq.",
        "Microsoft trades as MSFT on Nasdaq.",
    )
    target = _create(store, "relative/target", "Existing target content.")
    store.set_current(source.name)
    monkeypatch.setattr(
        distill_command,
        "connect_semantic_provider",
        _DistillProvider,
    )

    result = runner.invoke(
        app,
        ["distill", "--from", ".", "--to", "../target"],
    )

    assert result.exit_code == 0, result.output
    assert "DISTILL APPLIED · relative/source → relative/target" in result.output
    assert len(store.load_direct(target.name).order) == 2


@pytest.mark.parametrize("operation", ("elaborate", "distill"))
def test_bare_command_without_current_fails_before_provider(
    isolated_store,
    monkeypatch,
    operation,
) -> None:
    MemoryStore()

    def unexpected_provider():
        raise AssertionError("provider must not be constructed")

    command = elaborate_command if operation == "elaborate" else distill_command
    monkeypatch.setattr(command, "connect_semantic_provider", unexpected_provider)

    result = runner.invoke(app, [operation])

    assert result.exit_code == 1
    assert "No current Source Context" in result.output


def test_repeated_same_context_elaborate_sees_prior_output_only_later(
    isolated_store,
    monkeypatch,
) -> None:
    store = MemoryStore()
    current = _create(store, "repeat/current", "Confirm a ticker before acting.")
    store.set_current(current.name)
    _ElaborateProvider.calls = []
    monkeypatch.setattr(
        elaborate_command,
        "connect_semantic_provider",
        _ElaborateProvider,
    )

    first = runner.invoke(app, ["elaborate"])
    second = runner.invoke(app, ["elaborate"])

    assert first.exit_code == second.exit_code == 0
    assert [len(call["inputs"]) for call in _ElaborateProvider.calls] == [1, 3]
    assert len(store.load_direct(current.name).order) == 5
