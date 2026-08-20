"""Contracts for standalone and Ground-composed Elaborate."""

from __future__ import annotations

import ast
from dataclasses import replace
import json
from pathlib import Path

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from typer.testing import CliRunner

import memcommit.commands.elaborate as elaborate_command
import memcommit.elaborate_application as elaborate_application
import memcommit.ops as ops
from memcommit.cli import app
from memcommit.context import Context, Memory
from memcommit.elaborate import (
    ELABORATE_OPERATION,
    ELABORATE_PAYLOAD_MARKER,
    ElaborateError,
    ElaborateMode,
)
from memcommit.elaborate_application import ElaborateRequest
from memcommit.elaborate_config import ElaborateSemanticConfig
from memcommit.elaborate_runtime import execute_elaborate
from memcommit.ground import (
    GroundTargetSpec,
    bind_ground_workbench,
    create_ground_session,
    propose_ground_rule,
)
from memcommit.ground_elaborate import (
    execute_ground_elaborate,
    freeze_ground_elaborate,
)
from memcommit.ground_workspace_application import (
    AddGroundWorkspaceMemoryRequest,
    CreateGroundWorkspaceRequest,
)
from memcommit.ground_workspace_runtime import (
    execute_ground_workspace_creation,
    execute_ground_workspace_memory_add,
)
from memcommit.interfaces.tui.operations.elaborate import (
    project_elaborate_clipboard,
    project_elaborate_result,
    run_elaborate_tui,
)
from memcommit.store import MemoryStore, ground_session_record_digest


runner = CliRunner()


class ElaborateProvider:
    def __init__(self, *, empty: bool = False):
        self.empty = empty
        self.calls: list[tuple[str, dict[str, object]]] = []

    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == ELABORATE_OPERATION
        assert output_schema is not None
        self.calls.append((prompt, output_schema))
        payload = json.loads(prompt.split(ELABORATE_PAYLOAD_MARKER, 1)[1])
        if payload["mode"] == "GOAL_TO_RULES":
            return json.dumps(
                {
                    "overview": "The Goal can be made reviewable through one Rule hypothesis.",
                    "rules": []
                    if self.empty
                    else [
                        {
                            "content": "Confirm the selected option before acting.",
                            "rationale": "This operationalizes the requested confirmation.",
                        }
                    ],
                }
            )
        return json.dumps(
            {
                "overview": "The Rule benefits from a fit and a boundary Case.",
                "cases": []
                if self.empty
                else [
                    {
                        "proposition": "A person explicitly confirms option A.",
                        "expected": "Proceed with option A.",
                        "rationale": "This is an ordinary fitting Case.",
                        "case_role": "FIT",
                        "source_rule_index": 1,
                    },
                    {
                        "proposition": "A person mentions option A without confirming it.",
                        "expected": "Do not proceed yet.",
                        "rationale": "This distinguishes mention from confirmation.",
                        "case_role": "BOUNDARY",
                        "source_rule_index": 1,
                    },
                ],
            }
        )


def test_goal_elaborates_to_bounded_unverified_rule_proposals() -> None:
    provider = ElaborateProvider()

    result = execute_elaborate(
        ElaborateRequest(goal="Confirm a chosen option before acting."),
        provider_factory=lambda: provider,
    )

    assert result.analysis.mode is ElaborateMode.GOAL_TO_RULES
    assert len(result.analysis.rules) == 1
    assert result.analysis.cases == ()
    assert provider.calls[0][1]["properties"]["rules"]["minItems"] == 1
    assert provider.calls[0][1]["properties"]["rules"]["maxItems"] == 4
    assert "Propose at least one and at most 4" in provider.calls[0][0]
    assert "not a reason to return an empty set" in provider.calls[0][0]


def test_rules_elaborate_to_diverse_unverified_case_propositions() -> None:
    provider = ElaborateProvider()
    result = execute_elaborate(
        ElaborateRequest(rules=("Act only after explicit confirmation.",)),
        provider_factory=lambda: provider,
    )

    assert result.analysis.mode is ElaborateMode.RULES_TO_CASES
    assert [case.case_role for case in result.analysis.cases] == ["FIT", "BOUNDARY"]
    assert all(case.source_rule_index == 1 for case in result.analysis.cases)
    assert provider.calls[0][1]["properties"]["cases"]["minItems"] == 1
    assert "Propose at least one and at most 3" in provider.calls[0][0]
    assert "not a reason to return an empty set" in provider.calls[0][0]


@pytest.mark.parametrize(
    "elaborate_request, message",
    (
        (ElaborateRequest(goal="Explore a sparse Goal."), "invalid Rules"),
        (
            ElaborateRequest(rules=("An underspecified Rule.",)),
            "invalid Cases",
        ),
    ),
)
def test_elaborate_rejects_an_empty_proposal_set(
    elaborate_request,
    message,
) -> None:
    provider = ElaborateProvider(empty=True)

    with pytest.raises(ElaborateError, match=message):
        execute_elaborate(
            elaborate_request,
            provider_factory=lambda: provider,
        )

    assert len(provider.calls) == 1


def test_elaborate_request_requires_exactly_one_direction() -> None:
    with pytest.raises(ElaborateError):
        ElaborateRequest()
    with pytest.raises(ElaborateError):
        ElaborateRequest(goal="One Goal", rules=("One Rule",))


def test_elaborate_exact_prepared_lookup_avoids_provider() -> None:
    request = ElaborateRequest(goal="Confirm before acting.")
    live = execute_elaborate(request, provider_factory=ElaborateProvider)

    prepared = execute_elaborate(
        request,
        provider_factory=lambda: (_ for _ in ()).throw(
            AssertionError("exact prepared Elaborate must avoid provider")
        ),
        prepared_lookup=lambda _request, _config: live.analysis,
    )

    assert prepared.analysis is live.analysis
    assert prepared.origin == "PREPARED_EXACT"


def test_elaborate_rejects_an_analysis_from_the_prior_provider_contract() -> None:
    live = execute_elaborate(
        ElaborateRequest(goal="Confirm before acting."),
        provider_factory=ElaborateProvider,
    )

    with pytest.raises(
        ElaborateError,
        match="Unsupported Elaborate provider contract version",
    ):
        replace(live.analysis, provider_contract_version=1)


def test_elaborate_rejects_nonexact_prepared_result() -> None:
    live = execute_elaborate(
        ElaborateRequest(goal="Confirm before acting."),
        provider_factory=ElaborateProvider,
    )

    with pytest.raises(ElaborateError, match="does not exactly match"):
        execute_elaborate(
            ElaborateRequest(goal="Confirm a different action."),
            provider_factory=lambda: (_ for _ in ()).throw(
                AssertionError("a nonexact prepared result must fail closed")
            ),
            prepared_lookup=lambda _request, _config: live.analysis,
        )


def test_elaborate_live_plan_rejects_oversized_input_before_provider() -> None:
    provider_constructions = 0

    def provider_factory():
        nonlocal provider_constructions
        provider_constructions += 1
        return ElaborateProvider()

    config = ElaborateSemanticConfig(text_limit=600_100)
    with pytest.raises(ElaborateError, match="bounded one-turn plan"):
        execute_elaborate(
            ElaborateRequest(
                rules=("A" * 600_000, "B" * 600_000),
            ),
            provider_factory=provider_factory,
            config=config,
        )

    assert provider_constructions == 0


def test_elaborate_application_imports_no_terminal_or_command_adapter() -> None:
    source = Path(elaborate_application.__file__).read_text(encoding="utf-8")
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


def test_elaborate_result_limits_follow_the_injected_config() -> None:
    request = ElaborateRequest(goal="G" * 2_100)
    result = execute_elaborate(
        request,
        provider_factory=ElaborateProvider,
        config=ElaborateSemanticConfig(text_limit=2_200),
    )

    assert result.analysis.inputs == (request.goal,)


def test_elaborate_prepared_result_is_revalidated_against_current_config() -> None:
    request = ElaborateRequest(goal="Confirm.")
    live = execute_elaborate(request, provider_factory=ElaborateProvider)

    with pytest.raises(ElaborateError, match="semantic config does not match"):
        execute_elaborate(
            request,
            provider_factory=lambda: (_ for _ in ()).throw(
                AssertionError("prepared validation must happen before provider")
            ),
            prepared_lookup=lambda _request, _config: live.analysis,
            config=ElaborateSemanticConfig(text_limit=20),
        )


def test_elaborate_shared_viewer_copies_one_proposal_or_all() -> None:
    result = execute_elaborate(
        ElaborateRequest(goal="Confirm before acting."),
        provider_factory=ElaborateProvider,
    )
    document = project_elaborate_result(result)
    rendered = "".join(
        text for _style, text in document.render(focused_uid="ELABORATE:TITLE")
    )
    focused = project_elaborate_clipboard(
        result,
        focused_uid="ELABORATE:RULE:0",
        whole_document=False,
    )

    assert "SUGGESTED · UNVERIFIED" in rendered
    assert focused.text.startswith("[Suggested] [Unverified]")
    assert "WHAT MEM UNDERSTOOD" not in focused.text

    copied: list[str] = []
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[B\x1b[B\x1b[ByYq")
        returned = run_elaborate_tui(
            result,
            clipboard_writer=copied.append,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )
    assert returned == result
    assert copied[0].startswith("[Suggested] [Unverified]")
    assert "WHAT MEM UNDERSTOOD" in copied[1]


def _bound_ground(store: MemoryStore):
    raw = Context(uid="00000000-0000-4000-8000-000000000101", name="ground/raw")
    candidates = Context(
        uid="00000000-0000-4000-8000-000000000102",
        name="ground/candidates",
    )
    candidates.add(
        Memory(
            uid="00000000-0000-4000-8000-000000000104",
            content="A person explicitly confirmed option A before it was used.",
        )
    )
    target = Context(
        uid="00000000-0000-4000-8000-000000000103",
        name="ground/target",
    )
    for context in (raw, candidates, target):
        store.create_context(context)
    session = bind_ground_workbench(
        create_ground_session(
            "elaborate-ground",
            goal="Confirm a chosen option before acting.",
        ),
        description="Build a reviewed confirmation behavior contract.",
        raw_context=raw,
        derived_context=candidates,
        target_contexts=(target,),
        target_requirements=(
            GroundTargetSpec(
                context_name=target.name,
                description="Add one reviewed confirmation Case.",
                role="PUBLICATION_TARGET",
            ),
        ),
    )
    store.save_ground_session(session)
    return session, (raw, candidates, target)


def test_ground_and_standalone_use_the_same_elaborate_application(isolated_store):
    store = MemoryStore()
    session, contexts = _bound_ground(store)
    provider = ElaborateProvider()
    frozen = freeze_ground_elaborate(
        store,
        ground_name=session.contract_name,
        direction="GOAL_TO_RULES",
    )

    ground_result = execute_ground_elaborate(
        frozen,
        store=store,
        provider_factory=lambda: provider,
    )

    assert ground_result.frozen.request == ElaborateRequest(goal=session.goal)
    assert ground_result.elaborate.analysis.rules[0].content == (
        "Confirm the selected option before acting."
    )
    assert store.load_ground_session(session.contract_name) == session
    assert all(store.list_checkpoints(context.name) == [] for context in contexts)


def test_ground_rules_use_the_same_rules_to_cases_application(isolated_store):
    store = MemoryStore()
    session, contexts = _bound_ground(store)
    before = session
    session = propose_ground_rule(
        session,
        rule="Act only after explicit confirmation.",
        rationale="This is the Rule under review.",
        current_contexts=contexts,
    )
    store.save_ground_session(
        session,
        expected_uid=session.uid,
        expected_revision=0,
        expected_digest=ground_session_record_digest(before),
    )
    frozen = freeze_ground_elaborate(
        store,
        ground_name=session.contract_name,
        direction="RULES_TO_CASES",
    )

    result = execute_ground_elaborate(
        frozen,
        store=store,
        provider_factory=ElaborateProvider,
    )

    assert result.elaborate.analysis.mode is ElaborateMode.RULES_TO_CASES
    assert len(result.elaborate.analysis.cases) == 2
    assert store.load_ground_session(session.contract_name) == session


def test_ground_elaborate_rejects_stale_revision_before_provider(isolated_store):
    store = MemoryStore()
    session, contexts = _bound_ground(store)
    frozen = freeze_ground_elaborate(
        store,
        ground_name=session.contract_name,
        direction="GOAL_TO_RULES",
    )
    changed = propose_ground_rule(
        session,
        rule="A concurrent Rule.",
        rationale="Simulate another reviewed Ground turn.",
        current_contexts=contexts,
    )
    store.save_ground_session(
        changed,
        expected_uid=session.uid,
        expected_revision=session.revision,
        expected_digest=ground_session_record_digest(session),
    )
    provider = ElaborateProvider()

    with pytest.raises(ElaborateError, match="changed before Elaborate began"):
        execute_ground_elaborate(
            frozen,
            store=store,
            provider_factory=lambda: provider,
        )

    assert provider.calls == []


def test_ground_elaborate_rejects_revision_change_during_provider(isolated_store):
    store = MemoryStore()
    session, contexts = _bound_ground(store)
    frozen = freeze_ground_elaborate(
        store,
        ground_name=session.contract_name,
        direction="GOAL_TO_RULES",
    )

    class ConcurrentProvider(ElaborateProvider):
        def complete(self, prompt, *, operation, output_schema=None):
            current = store.load_ground_session(session.contract_name)
            assert current is not None
            changed = propose_ground_rule(
                current,
                rule="A concurrent Rule.",
                rationale="Simulate another reviewed Ground turn.",
                current_contexts=contexts,
            )
            store.save_ground_session(
                changed,
                expected_uid=current.uid,
                expected_revision=current.revision,
                expected_digest=ground_session_record_digest(current),
            )
            return super().complete(
                prompt,
                operation=operation,
                output_schema=output_schema,
            )

    provider = ConcurrentProvider()
    with pytest.raises(ElaborateError, match="changed while Elaborate was running"):
        execute_ground_elaborate(
            frozen,
            store=store,
            provider_factory=lambda: provider,
        )

    assert len(provider.calls) == 1
    assert all(store.list_checkpoints(context.name) == [] for context in contexts)


def test_mem_elaborate_plain_uses_the_typed_application(
    isolated_store,
    monkeypatch,
) -> None:
    store = MemoryStore()
    target = ops.init("elaborate/inline-target")
    store.create_context(target)
    store.set_current(target.name)
    monkeypatch.setattr(
        elaborate_command,
        "connect_semantic_provider",
        ElaborateProvider,
    )

    result = runner.invoke(
        app,
        ["elaborate", "--goal", "Confirm before acting.", "--plain"],
    )

    assert result.exit_code == 0, result.output
    assert "ELABORATE · GOAL → RULES" in result.output
    assert (
        "[1] Confirm the selected option before acting. "
        "— SUGGESTED · UNVERIFIED"
    ) in result.output
    assert "Added 1 Elaborate Memories" in result.output
    assert len(store.load_direct(target.name).order) == 1


def test_physical_ground_goal_elaborate_freezes_only_the_goal_memory(
    isolated_store,
):
    store = MemoryStore()
    execute_ground_workspace_creation(
        CreateGroundWorkspaceRequest(
            name="physical-elaborate",
            goal="Confirm a chosen option before acting.",
        ),
        store=store,
    )
    frozen = freeze_ground_elaborate(
        store,
        ground_name="physical-elaborate",
        direction="GOAL_TO_RULES",
    )
    # An Example is outside this direction's consumed frame and must not make
    # a safe cached/provider request stale.
    execute_ground_workspace_memory_add(
        AddGroundWorkspaceMemoryRequest(
            workspace_name="physical-elaborate",
            lane="examples",
            content="A person explicitly confirms option A.",
        ),
        store=store,
    )
    provider = ElaborateProvider()

    result = execute_ground_elaborate(
        frozen,
        store=store,
        provider_factory=lambda: provider,
    )

    assert result.frozen.request == ElaborateRequest(
        goal="Confirm a chosen option before acting."
    )
    assert len(provider.calls) == 1


def test_physical_ground_rules_elaborate_and_fail_on_consumed_rule_drift(
    isolated_store,
):
    store = MemoryStore()
    execute_ground_workspace_creation(
        CreateGroundWorkspaceRequest(name="physical-elaborate"),
        store=store,
    )
    execute_ground_workspace_memory_add(
        AddGroundWorkspaceMemoryRequest(
            workspace_name="physical-elaborate",
            lane="rules",
            content="Act only after explicit confirmation.",
        ),
        store=store,
    )
    frozen = freeze_ground_elaborate(
        store,
        ground_name="physical-elaborate",
        direction="RULES_TO_CASES",
    )
    rules = store.load_for_update("physical-elaborate/rules")
    rules.add("A concurrent consumed Rule.")
    store.save(rules)
    provider = ElaborateProvider()

    with pytest.raises(ElaborateError, match="consumed Ground workspace"):
        execute_ground_elaborate(
            frozen,
            store=store,
            provider_factory=lambda: provider,
        )

    assert provider.calls == []


def test_physical_ground_elaborate_rejects_typed_rule_before_provider(
    isolated_store,
):
    store = MemoryStore()
    execute_ground_workspace_creation(
        CreateGroundWorkspaceRequest(name="physical-elaborate"),
        store=store,
    )
    source = ops.init("physical-elaborate/external-rules")
    memory = ops.add(source, "Act only after explicit confirmation.")
    store.create_context(source)
    rules = store.load_for_update("physical-elaborate/rules")
    ops.embed_memory(memory, source, rules)
    store.save(rules)

    with pytest.raises(ElaborateError, match="authority-aware Ground projection"):
        freeze_ground_elaborate(
            store,
            ground_name="physical-elaborate",
            direction="RULES_TO_CASES",
        )
