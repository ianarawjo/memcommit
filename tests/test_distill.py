"""Contracts for evidence-bound Context-to-Context Distill."""

from __future__ import annotations

import json
import ast
from pathlib import Path

import pytest
from typer.testing import CliRunner

import memcommit.ops as ops
import memcommit.commands.distill as distill_command
import memcommit.operations.distill.application as distill_application
from memcommit.cli import app
from memcommit.commands.help_inventory import COMMAND_FORMS
from memcommit.context import Context, Memory
from memcommit.distill import (
    DISTILL_OPERATION,
    DISTILL_PAYLOAD_MARKER,
    DistillError,
    analyze_distill,
    distill_execution_policy,
)
from memcommit.distill_goal_fit import (
    DISTILL_GOAL_FIT_OPERATION,
    DISTILL_GOAL_FIT_PAYLOAD_MARKER,
)
from memcommit.operations.distill.application import DistillApplyRequest, DistillRequest
from memcommit.distill_config import DistillSemanticConfig
from memcommit.operations.distill.runtime import execute_distill, execute_distill_apply
from memcommit.ground import (
    GroundTargetSpec,
    bind_ground_workbench,
    create_ground_session,
)
from memcommit.ground_distill import (
    apply_ground_distill_result,
    execute_ground_distill,
    freeze_ground_distill,
)
from memcommit.ground_workspace_application import (
    AddGroundWorkspaceMemoryRequest,
    CreateGroundWorkspaceRequest,
)
from memcommit.ground_workspace_runtime import (
    execute_ground_workspace_creation,
    execute_ground_workspace_memory_add,
    load_ground_workspace,
)
from memcommit.ground_workspace_history import (
    build_ground_workspace_command_stack,
    undo_ground_workspace_command,
)
from memcommit.store import MemoryStore
from memcommit.summarize import collect_summary_frame


runner = CliRunner()


class DistillProvider:
    def __init__(self, response=None, *, goal_fit_response=None):
        self.response = response
        self.goal_fit_response = goal_fit_response
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.goal_fit_calls: list[tuple[str, dict[str, object]]] = []

    def complete(self, prompt, *, operation, output_schema=None):
        assert output_schema is not None
        if operation == DISTILL_GOAL_FIT_OPERATION:
            self.goal_fit_calls.append((prompt, output_schema))
            payload = json.loads(
                prompt.split(DISTILL_GOAL_FIT_PAYLOAD_MARKER, 1)[1]
            )
            aliases = [item["rule_id"] for item in payload["rules"]]
            response = self.goal_fit_response or {
                "verdict": "FIT",
                "reason": "Every proposed Rule is relevant to the Goal.",
                "considered_rule_ids": aliases,
                "material_rule_ids": [],
            }
            return json.dumps(response)
        assert operation == DISTILL_OPERATION
        self.calls.append((prompt, output_schema))
        payload = json.loads(prompt.split(DISTILL_PAYLOAD_MARKER, 1)[1])
        aliases = [item["memory_id"] for item in payload["source"]["memories"]]
        response = self.response or {
            "overview": "The evidence supports one bounded interaction Rule.",
            "rules": [
                {
                    "content": (
                        "When conversation is the purpose, prefer a quiet setting "
                        "and confirm the final choice with the user."
                    ),
                    "rationale": (
                        "The Goal requires a recommendation and the examples "
                        "distinguish quiet from noisy settings."
                    ),
                    "support_memory_ids": aliases[:1],
                    "boundary_memory_ids": aliases[1:2],
                }
            ],
            "outside_memory_ids": aliases[2:],
        }
        return json.dumps(response)


def _frame() -> tuple[Context, object]:
    context = Context(uid="00000000-0000-4000-8000-000000000001", name="cases")
    context.add(
        Memory(
            uid="00000000-0000-4000-8000-000000000011",
            content="A quiet family meal made conversation easy.",
        )
    )
    context.add(
        Memory(
            uid="00000000-0000-4000-8000-000000000012",
            content="At a loud restaurant, the user left after 30 minutes.",
        )
    )
    return context, collect_summary_frame(context)


def test_distill_accepts_goal_and_context_evidence_as_one_rule_frame():
    _context, frame = _frame()
    provider = DistillProvider()

    analysis = analyze_distill(
        frame,
        goal="Recommend a setting for a family conversation.",
        provider=provider,
    )

    assert len(analysis.rules) == 1
    rule = analysis.rules[0]
    assert rule.support_memory_uids == (
        "00000000-0000-4000-8000-000000000011",
    )
    assert rule.boundary_memory_uids == (
        "00000000-0000-4000-8000-000000000012",
    )
    assert analysis.outside_memory_uids == ()
    payload = json.loads(provider.calls[0][0].split(DISTILL_PAYLOAD_MARKER, 1)[1])
    assert payload["goal"] == "Recommend a setting for a family conversation."
    assert analysis.goal_fit is not None
    assert analysis.goal_fit.verdict == "FIT"
    assert analysis.goal_fit.considered_rule_uids == (rule.uid,)
    fit_payload = json.loads(
        provider.goal_fit_calls[0][0].split(
            DISTILL_GOAL_FIT_PAYLOAD_MARKER, 1
        )[1]
    )
    assert fit_payload == {
        "contract_version": 1,
        "goal": "Recommend a setting for a family conversation.",
        "rules": [
            {
                "rule_id": "r000001",
                "content": rule.content,
            }
        ],
    }


def test_distill_goal_is_a_prompt_level_output_contract_not_host_branching():
    _context, frame = _frame()
    provider = DistillProvider()

    analyze_distill(
        frame,
        goal=(
            "Return one descriptive parent and at most three supporting criteria; "
            "exclude review formatting and do not invent operational duties."
        ),
        provider=provider,
    )

    prompt = provider.calls[0][0]
    assert "output-selection contract over evidence-supported parents" in prompt
    assert "Use one ordered reduction procedure for every domain" in prompt
    assert "requested global-versus-supporting hierarchy" in prompt
    assert "exact or maximum quantities" in prompt
    assert "smallest nonredundant set" in prompt
    assert "Do not optimize a literal character ratio" in prompt
    assert "must not turn observations into duties" in prompt
    assert "surface-form audit is mandatory as analysis" in prompt
    assert "If a semantic Goal excludes form" in prompt
    assert "do not depend on domain-specific branches" in prompt


def test_distill_without_goal_skips_goal_fit_audit():
    _context, frame = _frame()
    provider = DistillProvider()

    analysis = analyze_distill(frame, goal=None, provider=provider)

    assert analysis.goal_fit is None
    assert len(provider.calls) == 1
    assert provider.goal_fit_calls == []
    assert "complete generative-family Rule set when there is no Goal" in (
        provider.calls[0][0]
    )


def test_distill_goal_fit_rejects_incomplete_rule_coverage():
    _context, frame = _frame()
    provider = DistillProvider(
        goal_fit_response={
            "verdict": "FIT",
            "reason": "The provider silently skipped the proposed Rule.",
            "considered_rule_ids": [],
            "material_rule_ids": [],
        }
    )

    with pytest.raises(DistillError, match="omitted, duplicated, or reordered"):
        analyze_distill(
            frame,
            goal="Recommend a setting for a family conversation.",
            provider=provider,
        )


def test_distill_rejects_silent_source_omission():
    _context, frame = _frame()
    provider = DistillProvider(
        {
            "overview": "Incomplete accounting.",
            "rules": [
                {
                    "content": "Prefer quiet settings.",
                    "rationale": "One case supports it.",
                    "support_memory_ids": ["m000001"],
                    "boundary_memory_ids": [],
                }
            ],
            "outside_memory_ids": [],
        }
    )

    with pytest.raises(DistillError, match="account for every Source Memory"):
        analyze_distill(frame, goal=None, provider=provider)


def test_distill_schema_leaves_uniqueness_to_the_strict_local_decoder():
    _context, frame = _frame()
    provider = DistillProvider()

    analyze_distill(
        frame,
        goal="Recommend a setting for a family conversation.",
        provider=provider,
    )

    schema = provider.calls[0][1]
    encoded = json.dumps(schema, sort_keys=True)
    assert "uniqueItems" not in encoded


def test_distill_local_decoder_rejects_duplicate_source_aliases():
    _context, frame = _frame()
    provider = DistillProvider(
        {
            "overview": "Duplicate evidence is invalid.",
            "rules": [
                {
                    "content": "Prefer quiet settings.",
                    "rationale": "One case supports it.",
                    "support_memory_ids": ["m000001", "m000001"],
                    "boundary_memory_ids": ["m000002"],
                }
            ],
            "outside_memory_ids": [],
        }
    )

    with pytest.raises(DistillError, match="duplicate source aliases"):
        analyze_distill(frame, goal=None, provider=provider)


def test_distill_rejects_goal_only_empty_context_before_provider_connection():
    empty = Context(uid="00000000-0000-4000-8000-000000000021", name="empty")
    frame = collect_summary_frame(empty)
    provider = DistillProvider()

    with pytest.raises(DistillError, match="Case or Example proposition"):
        analyze_distill(
            frame,
            goal="Recommend an option, then confirm the final choice with the user.",
            provider=provider,
        )

    assert provider.calls == []


def test_distill_empty_source_fails_before_prepared_lookup_or_provider(
    isolated_store,
):
    store = MemoryStore()
    source = ops.init("distill/empty-application")
    store.save(source)
    lookup_calls = 0
    provider_constructions = 0

    def lookup(_frame, _goal, _config):
        nonlocal lookup_calls
        lookup_calls += 1
        return None

    def provider_factory():
        nonlocal provider_constructions
        provider_constructions += 1
        return DistillProvider()

    with pytest.raises(DistillError, match="Case or Example proposition"):
        execute_distill(
            DistillRequest(context_locator=source.name, goal="A Goal"),
            store=store,
            provider_factory=provider_factory,
            prepared_lookup=lookup,
        )

    assert lookup_calls == 0
    assert provider_constructions == 0


def test_distill_live_plan_rejects_oversized_frame_before_provider_construction(
    isolated_store,
):
    store = MemoryStore()
    source = ops.init("distill/oversized")
    ops.add(source, "A" * 600_000)
    ops.add(source, "B" * 600_000)
    store.save(source)
    provider_constructions = 0

    def provider_factory():
        nonlocal provider_constructions
        provider_constructions += 1
        return DistillProvider()

    with pytest.raises(DistillError, match="bounded one-turn plan"):
        execute_distill(
            DistillRequest(context_locator=source.name),
            store=store,
            provider_factory=provider_factory,
        )

    assert provider_constructions == 0


def test_execute_and_apply_distill_create_new_result_and_preserve_source(
    isolated_store,
):
    store = MemoryStore()
    source = ops.init("distill/cases")
    first = ops.add(source, "A quiet family meal made conversation easy.")
    second = ops.add(source, "At a loud restaurant, the user left early.")
    store.save(source)
    store.set_current(source.name)
    provider = DistillProvider()

    result = execute_distill(
        DistillRequest(
            context_locator=source.name,
            goal="Recommend a setting for a family conversation.",
        ),
        store=store,
        provider_factory=lambda: provider,
    )

    assert store.load_direct(source.name).ordered_uids() == [first.uid, second.uid]
    assert not store.context_exists("distill/rules")

    receipt = execute_distill_apply(
        DistillApplyRequest(result=result, output_name="distill/rules"),
        store=store,
    )

    output = store.load_direct("distill/rules")
    assert output.uid == receipt.output_context_uid
    assert output.ordered_uids() == list(receipt.result_memory_uids)
    assert "prefer a quiet setting" in next(iter(output.iter_items())).content
    assert store.load_direct(source.name).ordered_uids() == [first.uid, second.uid]
    checkpoints = store.list_checkpoints("distill/rules")
    assert checkpoints[0]["command"] == "distill"
    metadata = checkpoints[0]["args"]["distill"]
    assert metadata["source_context"] == source.name
    assert metadata["rules"][0]["support_memory_uids"] == [first.uid]
    assert metadata["rules"][0]["boundary_memory_uids"] == [second.uid]
    assert metadata["goal_fit"]["verdict"] == "FIT"


def test_distill_not_fit_goal_audit_blocks_apply(isolated_store):
    store = MemoryStore()
    source = ops.init("distill/not-fit")
    ops.add(source, "A quiet setting supported a long conversation.")
    store.save(source)
    provider = DistillProvider(
        goal_fit_response={
            "verdict": "NOT_FIT",
            "reason": "The proposed Rule conflicts with the requested setting.",
            "considered_rule_ids": ["r000001"],
            "material_rule_ids": ["r000001"],
        }
    )
    result = execute_distill(
        DistillRequest(
            context_locator=source.name,
            goal="Recommend only outdoor settings.",
        ),
        store=store,
        provider_factory=lambda: provider,
    )

    assert result.analysis.goal_fit is not None
    assert result.analysis.goal_fit.verdict == "NOT_FIT"
    with pytest.raises(DistillError, match="do not fit the Goal"):
        execute_distill_apply(
            DistillApplyRequest(result=result, output_name="distill/not-fit-result"),
            store=store,
        )
    assert not store.context_exists("distill/not-fit-result")


def test_distill_undetermined_goal_audit_does_not_block_apply(isolated_store):
    store = MemoryStore()
    source = ops.init("distill/undetermined")
    ops.add(source, "A quiet setting supported a long conversation.")
    store.save(source)
    provider = DistillProvider(
        goal_fit_response={
            "verdict": "UNDETERMINED",
            "reason": "The Goal leaves the intended setting ambiguous.",
            "considered_rule_ids": ["r000001"],
            "material_rule_ids": ["r000001"],
        }
    )
    result = execute_distill(
        DistillRequest(
            context_locator=source.name,
            goal="Recommend the appropriate setting.",
        ),
        store=store,
        provider_factory=lambda: provider,
    )

    receipt = execute_distill_apply(
        DistillApplyRequest(
            result=result,
            output_name="distill/undetermined-result",
        ),
        store=store,
    )

    assert result.analysis.goal_fit is not None
    assert result.analysis.goal_fit.verdict == "UNDETERMINED"
    assert receipt.result_memory_uids
    assert store.context_exists("distill/undetermined-result")


def test_distill_exact_prepared_analysis_avoids_provider_construction(
    isolated_store,
):
    store = MemoryStore()
    source = ops.init("distill/prepared")
    ops.add(source, "A quiet setting supported a long conversation.")
    store.save(source)
    store.set_current(source.name)
    first_provider = DistillProvider()
    live = execute_distill(
        DistillRequest(context_locator=source.name, goal="Focus on conversation."),
        store=store,
        provider_factory=lambda: first_provider,
    )

    def forbidden_provider():
        raise AssertionError("an exact prepared Distill hit must avoid the provider")

    prepared = execute_distill(
        DistillRequest(context_locator=source.name, goal=" Focus on conversation. "),
        store=store,
        provider_factory=forbidden_provider,
        prepared_lookup=lambda frame, goal, config: live.analysis,
    )

    assert prepared.analysis is live.analysis
    assert prepared.origin == "PREPARED_EXACT"
    assert len(first_provider.calls) == 1


def test_distill_rejects_nonexact_prepared_projection(isolated_store):
    store = MemoryStore()
    source = ops.init("distill/prepared-mismatch")
    ops.add(source, "A first Case proposition.")
    store.save(source)
    store.set_current(source.name)
    live = execute_distill(
        DistillRequest(context_locator=source.name),
        store=store,
        provider_factory=DistillProvider,
    )

    changed = store.load_direct(source.name)
    ops.add(changed, "A second Case proposition changes the global Rule frame.")
    store.save(changed)

    with pytest.raises(DistillError, match="does not exactly match"):
        execute_distill(
            DistillRequest(context_locator=source.name),
            store=store,
            provider_factory=lambda: (_ for _ in ()).throw(
                AssertionError("an invalid prepared candidate must fail closed")
            ),
            prepared_lookup=lambda frame, goal, config: live.analysis,
        )


def test_distill_uses_one_typed_limit_snapshot():
    _context, frame = _frame()
    provider = DistillProvider()
    config = DistillSemanticConfig(max_rules=1)

    analyze_distill(frame, goal=None, provider=provider, config=config)

    assert provider.calls[0][1]["properties"]["rules"]["maxItems"] == 1
    assert distill_execution_policy(config).one_shot_limits.max_output_items == 1


def test_distill_default_has_no_rule_count_ceiling():
    _context, frame = _frame()
    provider = DistillProvider(
        {
            "overview": "Every independent supported invariant is retained.",
            "rules": [
                {
                    "content": f"Independent supported Rule {index}.",
                    "rationale": "The first Source Memory supplies its evidence.",
                    "support_memory_ids": ["m000001"],
                    "boundary_memory_ids": [],
                }
                for index in range(1, 22)
            ],
            "outside_memory_ids": ["m000002"],
        }
    )

    analysis = analyze_distill(frame, goal=None, provider=provider)

    assert len(analysis.rules) == 21
    assert "maxItems" not in provider.calls[0][1]["properties"]["rules"]
    assert distill_execution_policy().one_shot_limits.max_output_items is None
    assert "There is no default Rule-count maximum" in provider.calls[0][0]


def test_distill_explicit_rule_ceiling_still_rejects_overflow():
    _context, frame = _frame()
    provider = DistillProvider(
        {
            "overview": "This response deliberately exceeds the explicit ceiling.",
            "rules": [
                {
                    "content": f"Explicitly bounded Rule {index}.",
                    "rationale": "The first Source Memory supplies its evidence.",
                    "support_memory_ids": ["m000001"],
                    "boundary_memory_ids": [],
                }
                for index in range(1, 3)
            ],
            "outside_memory_ids": ["m000002"],
        }
    )

    with pytest.raises(DistillError, match="too many Rules"):
        analyze_distill(
            frame,
            goal=None,
            provider=provider,
            config=DistillSemanticConfig(max_rules=1),
        )


@pytest.mark.parametrize("value", (0, -1, True))
def test_distill_rule_ceiling_must_be_positive_or_none(value):
    with pytest.raises(ValueError, match="positive integer or None"):
        DistillSemanticConfig(max_rules=value)


def test_distill_result_limits_follow_the_injected_config():
    _context, frame = _frame()
    long_rule = "R" * 4_100
    provider = DistillProvider(
        {
            "overview": "One long Rule is allowed by this explicit contract.",
            "rules": [
                {
                    "content": long_rule,
                    "rationale": "The first proposition supplies the evidence.",
                    "support_memory_ids": ["m000001"],
                    "boundary_memory_ids": ["m000002"],
                }
            ],
            "outside_memory_ids": [],
        }
    )

    analysis = analyze_distill(
        frame,
        goal=None,
        provider=provider,
        config=DistillSemanticConfig(rule_text_limit=4_200),
    )

    assert analysis.rules[0].content == long_rule


def test_distill_prepared_result_is_revalidated_against_current_config(
    isolated_store,
):
    store = MemoryStore()
    source = ops.init("distill/prepared-limit")
    ops.add(source, "One source proposition supports a reusable Rule.")
    store.save(source)
    live = execute_distill(
        DistillRequest(context_locator=source.name),
        store=store,
        provider_factory=DistillProvider,
    )

    with pytest.raises(DistillError, match="semantic config does not match"):
        execute_distill(
            DistillRequest(context_locator=source.name),
            store=store,
            provider_factory=lambda: (_ for _ in ()).throw(
                AssertionError("prepared validation must happen before provider")
            ),
            prepared_lookup=lambda frame, goal, config: live.analysis,
            config=DistillSemanticConfig(rule_text_limit=10),
        )


def test_distill_application_imports_no_terminal_or_command_adapter():
    source = Path(distill_application.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.append(node.module)

    assert tuple(
        name
        for name in imports
        if name == "typer"
        or name.startswith("prompt_toolkit")
        or name.startswith("memcommit.commands")
    ) == ()


def test_distill_apply_fails_closed_when_source_changed(isolated_store):
    store = MemoryStore()
    source = ops.init("distill/stale")
    ops.add(source, "One source case.")
    store.save(source)
    provider = DistillProvider(
        {
            "overview": "One Rule is supported.",
            "rules": [
                {
                    "content": "Retain the supported source condition.",
                    "rationale": "The single Source Memory supports it.",
                    "support_memory_ids": ["m000001"],
                    "boundary_memory_ids": [],
                }
            ],
            "outside_memory_ids": [],
        }
    )
    result = execute_distill(
        DistillRequest(context_locator=source.name),
        store=store,
        provider_factory=lambda: provider,
    )
    changed = store.load_direct(source.name)
    ops.add(changed, "A concurrent Source change.")
    store.save(changed)

    with pytest.raises(DistillError, match="Source changed before Apply"):
        execute_distill_apply(
            DistillApplyRequest(result=result, output_name="distill/stale-rules"),
            store=store,
        )
    assert not store.context_exists("distill/stale-rules")


def _ground_with_distill_source(store: MemoryStore):
    raw = Context(uid="00000000-0000-4000-8000-000000000201", name="distill/raw")
    candidates = Context(
        uid="00000000-0000-4000-8000-000000000202",
        name="distill/candidates",
    )
    candidates.add(
        Memory(
            uid="00000000-0000-4000-8000-000000000211",
            content="A quiet setting supported a long conversation.",
        )
    )
    target = Context(
        uid="00000000-0000-4000-8000-000000000203",
        name="distill/target",
    )
    for context in (raw, candidates, target):
        store.create_context(context)
    session = bind_ground_workbench(
        create_ground_session(
            "distill-ground",
            goal="Choose a setting that supports conversation.",
        ),
        description="Derive a reviewable setting Rule.",
        raw_context=raw,
        derived_context=candidates,
        target_contexts=(target,),
        target_requirements=(
            GroundTargetSpec(
                context_name=target.name,
                description="Publish a reviewed Rule.",
                role="PUBLICATION_TARGET",
            ),
        ),
    )
    store.save_ground_session(session)
    return session, (raw, candidates, target)


def test_ground_distill_uses_same_application_and_preserves_ground(isolated_store):
    store = MemoryStore()
    session, contexts = _ground_with_distill_source(store)
    frozen = freeze_ground_distill(store, ground_name=session.contract_name)

    result = execute_ground_distill(
        frozen,
        store=store,
        provider_factory=DistillProvider,
    )

    assert frozen.request == DistillRequest(
        context_locator="distill/candidates",
        goal=session.goal,
    )
    assert result.distill.analysis.source.context_name == "distill/candidates"
    assert store.load_ground_session(session.contract_name) == session
    assert all(store.list_checkpoints(context.name) == [] for context in contexts)


def test_ground_distill_rejects_stale_bound_candidate_before_provider(
    isolated_store,
):
    store = MemoryStore()
    session, (_raw, candidates, _target) = _ground_with_distill_source(store)
    frozen = freeze_ground_distill(store, ground_name=session.contract_name)
    changed = store.load_direct(candidates.name)
    changed.add(
        Memory(
            uid="00000000-0000-4000-8000-000000000212",
            content="A concurrent candidate proposition.",
        )
    )
    store.save(changed)
    provider = DistillProvider()

    with pytest.raises(DistillError, match="changed after Ground binding"):
        execute_ground_distill(
            frozen,
            store=store,
            provider_factory=lambda: provider,
        )

    assert provider.calls == []


def test_ground_distill_rejects_candidate_change_during_provider(
    isolated_store,
):
    store = MemoryStore()
    session, (_raw, candidates, _target) = _ground_with_distill_source(store)
    frozen = freeze_ground_distill(store, ground_name=session.contract_name)

    class ConcurrentProvider(DistillProvider):
        def complete(self, prompt, *, operation, output_schema=None):
            if operation == DISTILL_OPERATION:
                changed = store.load_direct(candidates.name)
                changed.add(
                    Memory(
                        uid="00000000-0000-4000-8000-000000000213",
                        content="A concurrent candidate proposition.",
                    )
                )
                store.save(changed)
            return super().complete(
                prompt,
                operation=operation,
                output_schema=output_schema,
            )

    provider = ConcurrentProvider()
    with pytest.raises(DistillError, match="changed while Distill was running"):
        execute_ground_distill(
            frozen,
            store=store,
            provider_factory=lambda: provider,
        )

    assert len(provider.calls) == 1
    assert all(
        store.list_checkpoints(name) == []
        for name in ("distill/raw", "distill/candidates", "distill/target")
    )


def test_mem_distill_ground_plain_uses_frozen_ground(monkeypatch, isolated_store):
    store = MemoryStore()
    session, _contexts = _ground_with_distill_source(store)
    monkeypatch.setattr(
        distill_command,
        "connect_semantic_provider",
        DistillProvider,
    )

    result = runner.invoke(
        app,
        ["distill", "--ground", session.contract_name, "--plain"],
    )

    assert result.exit_code == 0, result.output
    assert "DISTILL · distill/candidates" in result.output
    assert "GOAL · RELEVANCE FOCUS ONLY" in result.output


def test_mem_distill_ground_adopt_is_an_explicit_physical_write(
    monkeypatch,
    isolated_store,
):
    store = MemoryStore()
    _physical_ground_with_distill_examples(store)
    monkeypatch.setattr(
        distill_command,
        "connect_semantic_provider",
        DistillProvider,
    )

    result = runner.invoke(
        app,
        ["distill", "--ground", "physical-distill", "--adopt", "--plain"],
    )

    assert result.exit_code == 0, result.output
    assert "DISTILL ADOPTED · physical-distill/rules" in result.output
    assert "EFFECTS · ADD 1 RULES" in result.output
    assert len(tuple(load_ground_workspace(store, "physical-distill").rules.iter_items())) == 1


def _physical_ground_with_distill_examples(store: MemoryStore) -> None:
    execute_ground_workspace_creation(
        CreateGroundWorkspaceRequest(
            name="physical-distill",
            goal="Learn how real US ticker symbols are assigned.",
        ),
        store=store,
    )
    for content in (
        "Apple Inc. is listed under AAPL.",
        "Microsoft Corporation is listed under MSFT.",
    ):
        execute_ground_workspace_memory_add(
            AddGroundWorkspaceMemoryRequest(
                workspace_name="physical-distill",
                lane="examples",
                content=content,
            ),
            store=store,
        )


def test_physical_ground_distill_consumes_goal_and_example_memories(
    isolated_store,
):
    store = MemoryStore()
    _physical_ground_with_distill_examples(store)
    frozen = freeze_ground_distill(store, ground_name="physical-distill")
    provider = DistillProvider()

    result = execute_ground_distill(
        frozen,
        store=store,
        provider_factory=lambda: provider,
    )

    assert frozen.source_kind == "GROUND_WORKSPACE_INPUTS"
    assert frozen.request.goal is None
    assert frozen.request.goal_focus is not None
    assert frozen.request.goal_focus.kind == "GROUND"
    assert frozen.request.goal_focus.text == (
        "Learn how real US ticker symbols are assigned."
    )
    assert [source.content for source in frozen.candidate_frame.sources] == [
        "Apple Inc. is listed under AAPL.",
        "Microsoft Corporation is listed under MSFT.",
    ]
    assert result.distill.analysis.source == frozen.candidate_frame
    assert len(provider.calls) == 1


def test_physical_ground_distill_adopts_complete_proposal_as_one_command(
    isolated_store,
):
    store = MemoryStore()
    _physical_ground_with_distill_examples(store)
    frozen = freeze_ground_distill(store, ground_name="physical-distill")
    proposal = execute_ground_distill(
        frozen,
        store=store,
        provider_factory=DistillProvider,
    )

    receipt = apply_ground_distill_result(proposal, store=store)

    workspace = load_ground_workspace(store, "physical-distill")
    assert receipt.revision == frozen.ground_revision + 1
    assert tuple(item.content for item in workspace.rules.iter_items()) == (
        "When conversation is the purpose, prefer a quiet setting "
        "and confirm the final choice with the user.",
    )
    unit = build_ground_workspace_command_stack(
        store,
        "physical-distill",
    ).undo[-1]
    assert unit.action == "adopt-distill"
    undo_ground_workspace_command(store, "physical-distill")
    assert tuple(
        load_ground_workspace(store, "physical-distill").rules.iter_items()
    ) == ()


def test_physical_ground_distill_adoption_rejects_changed_target_lane(
    isolated_store,
):
    store = MemoryStore()
    _physical_ground_with_distill_examples(store)
    frozen = freeze_ground_distill(store, ground_name="physical-distill")
    proposal = execute_ground_distill(
        frozen,
        store=store,
        provider_factory=DistillProvider,
    )
    execute_ground_workspace_memory_add(
        AddGroundWorkspaceMemoryRequest(
            workspace_name="physical-distill",
            lane="rules",
            content="A separately reviewed Rule.",
        ),
        store=store,
    )

    with pytest.raises(DistillError, match="consumed Ground workspace"):
        apply_ground_distill_result(proposal, store=store)


def test_physical_ground_distill_ignores_unconsumed_rule_revision_change(
    isolated_store,
):
    store = MemoryStore()
    _physical_ground_with_distill_examples(store)
    frozen = freeze_ground_distill(store, ground_name="physical-distill")
    execute_ground_workspace_memory_add(
        AddGroundWorkspaceMemoryRequest(
            workspace_name="physical-distill",
            lane="rules",
            content="An unrelated reviewed Rule.",
        ),
        store=store,
    )
    provider = DistillProvider()

    execute_ground_distill(
        frozen,
        store=store,
        provider_factory=lambda: provider,
    )

    assert len(provider.calls) == 1


def test_physical_ground_distill_rejects_consumed_example_drift_before_provider(
    isolated_store,
):
    store = MemoryStore()
    _physical_ground_with_distill_examples(store)
    frozen = freeze_ground_distill(store, ground_name="physical-distill")
    examples = store.load_for_update("physical-distill/examples")
    examples.add("A new consumed Example.")
    store.save(examples)
    provider = DistillProvider()

    with pytest.raises(DistillError, match="consumed Ground workspace Memories"):
        execute_ground_distill(
            frozen,
            store=store,
            provider_factory=lambda: provider,
        )

    assert provider.calls == []


def test_physical_ground_distill_rejects_unresolved_typed_context_input(
    isolated_store,
):
    store = MemoryStore()
    _physical_ground_with_distill_examples(store)
    source = ops.init("physical-distill/external-source")
    memory = ops.add(source, "An externally owned ticker observation.")
    store.create_context(source)
    contexts = store.load_for_update("physical-distill/contexts")
    ops.embed_memory(memory, source, contexts)
    store.save(contexts)

    with pytest.raises(DistillError, match="authority-aware Ground projection"):
        freeze_ground_distill(store, ground_name="physical-distill")


def test_mem_distill_applies_the_exact_rendered_proposal(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = ops.init("distill/cli-cases")
    ops.add(source, "A quiet family meal made conversation easy.")
    ops.add(source, "At a loud restaurant, the user left early.")
    store.save(source)
    provider = DistillProvider()
    monkeypatch.setattr(
        distill_command,
        "connect_semantic_provider",
        lambda: provider,
    )

    result = runner.invoke(
        app,
        [
            "distill",
            source.name,
            "--goal",
            "Recommend a setting for a family conversation.",
            "--save-as",
            "distill/cli-rules",
            "--apply",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "STATUS · EVIDENCE-BOUND PROPOSAL" not in result.output
    assert "DISTILL APPLIED · RESULT distill/cli-rules" in result.output
    assert "EFFECTS · ADD 1 RULES" in result.output
    assert "REVIEW · mem review distill --receipt" in result.output
    assert store.context_exists("distill/cli-rules")
    output = store.load_direct("distill/cli-rules")
    added = next(iter(output.iter_items()))
    assert f"  [memory {added.uid[:8]}] {added.content}" in result.output
    assert "UNDO · mem undo" in result.output
    assert not any(
        line.startswith(("RECEIPT ·", "CHECKPOINT ·", "RECOVERY ·"))
        for line in result.output.splitlines()
    )
    assert len(store.load_direct(source.name).order) == 2


def test_mem_distill_save_as_without_apply_never_prompts_and_remains_read_only(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = ops.init("distill/preview")
    ops.add(source, "One supported source case.")
    store.save(source)
    provider = DistillProvider(
        {
            "overview": "One Rule is supported.",
            "rules": [
                {
                    "content": "Retain the supported source condition.",
                    "rationale": "The Source Memory supports it.",
                    "support_memory_ids": ["m000001"],
                    "boundary_memory_ids": [],
                }
            ],
            "outside_memory_ids": [],
        }
    )
    monkeypatch.setattr(
        distill_command,
        "connect_semantic_provider",
        lambda: provider,
    )

    def forbidden_confirm(*args, **kwargs):
        raise AssertionError("Distill must not open a y/N prompt")

    monkeypatch.setattr(
        distill_command.typer,
        "confirm",
        forbidden_confirm,
    )

    result = runner.invoke(
        app,
        ["distill", source.name, "--save-as", "distill/preview-rules"],
    )

    assert result.exit_code == 0, result.output
    assert "[y/N]" not in result.output
    assert "READY TO CREATE" in result.output
    assert len(provider.calls) == 1
    assert provider.goal_fit_calls == []
    assert not store.context_exists("distill/preview-rules")


def test_mem_distill_help_inventory_exposes_goal_review_and_apply_forms():
    assert COMMAND_FORMS["distill"] == (
        "mem distill (distill current and add Rules back to current)",
        "mem distill --to [target] (distill current into an existing target)",
        "mem distill --from [source] (distill a source into current)",
        "mem distill --from [source] --to [target] (explicit existing endpoints)",
        "mem distill --from [source] --goal [context|memory|text] "
        "(guide Rule relevance without adding evidence)",
        "mem distill --from [source] -r (include descendants and embeds)",
        "mem distill --ground [name] "
        "(inspect read-only Rules from its exact Goal and working-candidate frame)",
        "mem distill --ground [name] --adopt "
        "(atomically add the complete proposal to the physical /rules lane)",
    )
