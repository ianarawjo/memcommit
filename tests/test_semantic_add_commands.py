"""Directional Add contracts for standalone Distill and Elaborate."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

import memcommit.adapters.console.commands.distill.command as distill_command
import memcommit.adapters.console.commands.elaborate.command as elaborate_command
import memcommit.adapters.console.commands.impact.process_local as impact_process_local
import memcommit.application.ops as ops
from memcommit.adapters.console.entrypoint import app
from memcommit.application.operations.distill.model import DISTILL_OPERATION, DISTILL_PAYLOAD_MARKER
from memcommit.application.operations.distill.goal_fit import (
    DISTILL_GOAL_FIT_OPERATION,
    DISTILL_GOAL_FIT_PAYLOAD_MARKER,
)
from memcommit.application.operations.elaborate.model import ELABORATE_OPERATION, ELABORATE_PAYLOAD_MARKER
from memcommit.persistence.store import MemoryStore, context_record_digest
from tests.distill_goal_fit_support import passing_distill_goal_fit_response
from tests.elaborate_validation_support import (
    passing_elaborate_validation_response,
)


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
        validation = passing_elaborate_validation_response(prompt, operation)
        if validation is not None:
            return validation
        assert operation == ELABORATE_OPERATION
        payload = json.loads(prompt.split(ELABORATE_PAYLOAD_MARKER, 1)[1])
        type(self).calls.append(payload)
        number = payload["number"]
        target_refs = (
            {"target_context_refs": []}
            if "target_context" in payload
            else {}
        )
        if payload["mode"] == "GOAL_TO_RULES":
            rule_specs = (
                (
                    "Confirm the selected ticker before acting.",
                    "This operationalizes the stated Goal.",
                ),
                (
                    "Record the exact ticker that was confirmed.",
                    "This keeps the chosen ticker reviewable.",
                ),
                (
                    "Ask again when the ticker selection changes.",
                    "This prevents stale confirmation from authorizing a new ticker.",
                ),
                (
                    "Do not act on an ambiguous ticker selection.",
                    "This defines the safe confirmation boundary.",
                ),
            )
            rule_specs += tuple(
                (
                    f"Generated operational Rule {index}.",
                    f"This is distinct exact-count rationale {index}.",
                )
                for index in range(len(rule_specs) + 1, number + 1)
            )
            return json.dumps(
                {
                    "overview": f"Exactly {number} Rules make the Goal concrete.",
                    "rules": [
                        {
                            "content": content,
                            "rationale": rationale,
                            **target_refs,
                        }
                        for content, rationale in rule_specs[:number]
                    ],
                }
            )
        case_specs = (
            (
                "The user explicitly confirms ticker AAPL.",
                "Proceed with AAPL.",
                "This is a fitting Case.",
                "FIT",
            ),
            (
                "The user mentions AAPL without confirming it.",
                "Ask for confirmation.",
                "This is a boundary Case.",
                "BOUNDARY",
            ),
            (
                "The user confirms AAPL and then changes the selection to MSFT, so "
                "the system asks for fresh confirmation before proceeding.",
                "Proceed only after MSFT is confirmed.",
                "This contrasts fresh and stale confirmation.",
                "CONTRAST",
            ),
        )
        case_specs += tuple(
            (
                f"The user confirms generated ticker CASE{index} before acting.",
                f"Proceed with CASE{index}.",
                f"This is distinct exact-count Case {index}.",
                ("FIT", "BOUNDARY", "CONTRAST")[(index - 1) % 3],
            )
            for index in range(len(case_specs) + 1, number + 1)
        )
        return json.dumps(
            {
                "overview": f"Exactly {number} Cases make the Rule concrete.",
                "cases": [
                    {
                        "proposition": proposition,
                        "expected": expected,
                        "rationale": rationale,
                        "case_role": role,
                        "rule_checks": [
                            {
                                "source_rule_index": index,
                                "evidence": "The proposition satisfies this Rule.",
                            }
                            for index, _rule in enumerate(payload["inputs"], 1)
                        ],
                        **target_refs,
                    }
                    for proposition, expected, rationale, role in case_specs[:number]
                ],
            }
        )


class _DistillProvider:
    calls: list[dict[str, object]] = []

    def complete(self, prompt, *, operation, output_schema=None):
        validation = passing_distill_goal_fit_response(prompt, operation)
        if validation is not None:
            return validation
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
    assert "EFFECTS · ADD 3 MEMORIES" in result.output
    for name, count in before.items():
        expected = count + 3 if name == expected_target else count
        assert len(store.load_direct(name).order) == expected
    target = store.load_direct(expected_target)
    for uid in target.ordered_uids()[before[expected_target] :]:
        memory = target.memories[uid]
        assert f"  [memory {uid[:8]}] {memory.content}" in result.output
    checkpoint = store.list_checkpoints(expected_target)[0]
    assert checkpoint["command"] == "elaborate"
    assert checkpoint["args"]["elaborate"]["effect"] == "ADD"
    assert checkpoint["args"]["elaborate"]["quality_policy"] == "BEST_EFFORT"
    assert checkpoint["args"]["elaborate"]["case_validation"] == "NOT_RUN"
    assert len(checkpoint["args"]["elaborate"]["result_memory_uids"]) == 3
    assert (
        f"REVIEW · mem review elaborate --receipt {checkpoint['uid']}" in result.output
    )
    assert "UNDO · mem undo" in result.output
    assert not any(
        line.startswith(("RECEIPT ·", "CHECKPOINT ·", "RECOVERY ·"))
        for line in result.output.splitlines()
    )
    assert len(_ElaborateProvider.calls[0]["inputs"]) == 1


def test_mem_elaborate_number_is_an_exact_cli_and_checkpoint_contract(
    isolated_store,
    monkeypatch,
) -> None:
    store = MemoryStore()
    target = _create(store, "number/target", "Existing destination language.")
    source = _create(store, "number/source", "Confirm a ticker before acting.")
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
            "--from",
            source.name,
            "--n",
            "5",
            "--strict",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "EFFECTS · ADD 5 MEMORIES" in result.output
    assert "QUALITY · STRICT" in result.output
    assert _ElaborateProvider.calls[0]["number"] == 5
    checkpoint = store.list_checkpoints(target.name)[0]
    assert checkpoint["args"]["elaborate"]["number"] == 5
    assert checkpoint["args"]["elaborate"]["quality_policy"] == "STRICT"


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


def test_elaborate_combines_rule_source_with_context_goal_focus(
    isolated_store,
    monkeypatch,
) -> None:
    store = MemoryStore()
    source = _create(
        store,
        "coffee-advice",
        "Manage the cafe's social feed consistently.",
        "Maintain good supplier and customer relationships.",
        "Manage staff well.",
    )
    _create(
        store,
        "coffee-advice/goal",
        "Give practical advice to a friend who owns a cafe.",
    )
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
            "--from",
            source.name,
            "--to",
            source.name,
            "--goal",
            "coffee-advice/goal",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = _ElaborateProvider.calls[0]
    assert payload["mode"] == "RULES_TO_CASES"
    assert payload["goal_focus"]["kind"] == "CONTEXT"
    assert payload["goal_focus"]["items"][0]["content"] == (
        "Give practical advice to a friend who owns a cafe."
    )
    checkpoint = store.list_checkpoints(source.name)[0]
    assert checkpoint["args"]["elaborate"]["goal_focus"]["kind"] == "CONTEXT"


@pytest.mark.parametrize(
    ("goal_kind", "expected_kind"),
    (("context", "CONTEXT"), ("memory", "MEMORY"), ("inline", "INLINE")),
)
def test_distill_goal_accepts_context_memory_or_inline_operand(
    isolated_store,
    monkeypatch,
    goal_kind,
    expected_kind,
) -> None:
    store = MemoryStore()
    source = _create(
        store,
        "goal-operands/source",
        "Apple Inc. is listed under AAPL.",
        "Microsoft Corporation is listed under MSFT.",
    )
    target = _create(store, "goal-operands/target", "Existing target content.")
    goal_context = _create(
        store,
        "goal-operands/focus",
        "Focus on identifiers useful to a cafe inventory manager.",
    )
    goal_memory = next(iter(goal_context.memories.values()))
    goal_operand = {
        "context": goal_context.name,
        "memory": f"{goal_context.name}:{goal_memory.uid[:8]}",
        "inline": "Focus on identifiers useful to a cafe inventory manager.",
    }[goal_kind]
    _DistillProvider.calls = []
    monkeypatch.setattr(
        distill_command,
        "connect_semantic_provider",
        _DistillProvider,
    )

    result = runner.invoke(
        app,
        [
            "distill",
            "--from",
            source.name,
            "--to",
            target.name,
            "--goal",
            goal_operand,
        ],
    )

    assert result.exit_code == 0, result.output
    checkpoint = store.list_checkpoints(target.name)[0]
    focus = checkpoint["args"]["distill"]["goal_focus"]
    assert focus["kind"] == expected_kind
    assert focus["items"][0]["content"] == (
        "Focus on identifiers useful to a cafe inventory manager."
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
    target = store.load_direct(expected_target)
    added_uid = target.ordered_uids()[before[expected_target]]
    added_memory = target.memories[added_uid]
    assert f"  [memory {added_uid[:8]}] {added_memory.content}" in result.output
    checkpoint = store.list_checkpoints(expected_target)[0]
    assert checkpoint["command"] == "distill"
    assert checkpoint["args"]["distill"]["effect"] == "ADD"
    assert checkpoint["args"]["distill"]["target_context"] == expected_target
    assert f"REVIEW · mem review distill --receipt {checkpoint['uid']}" in result.output
    assert "UNDO · mem undo" in result.output
    assert not any(
        line.startswith(("RECEIPT ·", "CHECKPOINT ·", "RECOVERY ·"))
        for line in result.output.splitlines()
    )


def test_distill_goal_not_fit_blocks_direct_add(
    isolated_store,
    monkeypatch,
) -> None:
    store = MemoryStore()
    source = _create(
        store,
        "goal-fit/source",
        "Apple trades as AAPL on Nasdaq.",
        "Microsoft trades as MSFT on Nasdaq.",
    )
    target = _create(store, "goal-fit/target", "Existing target content.")
    store.set_current(target.name)

    class _NotFitProvider(_DistillProvider):
        def complete(self, prompt, *, operation, output_schema=None):
            if operation == DISTILL_GOAL_FIT_OPERATION:
                payload = json.loads(
                    prompt.split(DISTILL_GOAL_FIT_PAYLOAD_MARKER, 1)[1]
                )
                aliases = [rule["rule_id"] for rule in payload["rules"]]
                return json.dumps(
                    {
                        "verdict": "NOT_FIT",
                        "reason": "The proposed ticker Rule conflicts with the Goal.",
                        "considered_rule_ids": aliases,
                        "material_rule_ids": aliases,
                    }
                )
            return super().complete(
                prompt,
                operation=operation,
                output_schema=output_schema,
            )

    monkeypatch.setattr(
        distill_command,
        "connect_semantic_provider",
        _NotFitProvider,
    )

    result = runner.invoke(
        app,
        [
            "distill",
            "--from",
            source.name,
            "--to",
            target.name,
            "--goal",
            "Recommend only a non-ticker identifier.",
        ],
    )

    assert result.exit_code == 1
    assert "do not fit the Goal" in result.output
    assert [
        memory.content for memory in store.load_direct(target.name).memories.values()
    ] == ["Existing target content."]
    assert store.list_checkpoints(target.name) == []


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
    assert f"TARGET · {target.name} · EXISTING" in result.output
    if operation == "distill":
        assert "PROPOSED RULES" in result.output
        assert "IMPACT · DISTILL ADD" not in result.output
    else:
        assert "PROPOSED CASES" in result.output
        assert "ENDPOINTS UNCHANGED" not in result.output
        assert "[ADD]" not in result.output
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
            if operation == ELABORATE_OPERATION:
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
    assert [len(call["inputs"]) for call in _ElaborateProvider.calls] == [1, 4]
    assert len(store.load_direct(current.name).order) == 7
