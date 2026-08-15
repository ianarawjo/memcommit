"""Durable Ground Example USE mutations and their CLI boundary."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from memcommit.cli import app
from memcommit.context import Context, Memory
from memcommit.ground import (
    GroundError,
    GroundTargetSpec,
    bind_ground_workbench,
    create_ground_session,
    propose_ground_case,
    propose_ground_rule,
    set_ground_example_use,
)
from memcommit.store import MemoryStore


runner = CliRunner()


def _ground_with_example(store: MemoryStore):
    raw = Context(uid="10000000-0000-4000-8000-000000000001", name="use/raw")
    candidates = Context(
        uid="10000000-0000-4000-8000-000000000002",
        name="use/candidates",
    )
    source = Memory(
        uid="10000000-0000-4000-8000-000000000011",
        content="Apple Inc.",
    )
    candidates.add(source)
    target = Context(
        uid="10000000-0000-4000-8000-000000000003",
        name="use/rules",
    )
    for context in (raw, candidates, target):
        store.create_context(context)
    contexts = (raw, candidates, target)
    session = bind_ground_workbench(
        create_ground_session("use-ground", goal="Derive ticker Rules."),
        description="Review ticker Examples before distillation.",
        raw_context=raw,
        derived_context=candidates,
        target_contexts=(target,),
        target_requirements=(
            GroundTargetSpec(
                context_name=target.name,
                description="Publish reviewed ticker Rules.",
                role="PUBLICATION_TARGET",
            ),
        ),
    )
    session = propose_ground_rule(
        session,
        rule="Use a company's reviewed short ticker.",
        rationale="The Example needs one candidate Rule.",
        current_contexts=contexts,
    )
    session = propose_ground_case(
        session,
        rule_selector=session.items_of_kind("RULE")[0].uid,
        case=source.content,
        source_context_uid=candidates.uid,
        source_memory_uid=source.uid,
        target_context_names=(target.name,),
        expected="AAPL",
        rationale="One concrete ticker Example.",
        current_contexts=contexts,
        disposition="INCLUDE",
    )
    return session, contexts


def test_set_ground_example_use_is_revisioned_and_traceable(isolated_store):
    store = MemoryStore()
    session, contexts = _ground_with_example(store)
    example = session.items_of_kind("CASE")[0]

    updated = set_ground_example_use(
        session,
        example.uid,
        use="EXCLUDE",
        current_contexts=contexts,
    )

    changed = updated.items_of_kind("CASE")[0]
    decision = updated.items_of_kind("DECISION")[-1]
    assert updated.revision == session.revision + 1
    assert changed.uid == example.uid
    assert changed.disposition == "EXCLUDE"
    assert changed.iteration == updated.revision
    assert decision.content == "SET EXAMPLE USE EXCLUDE"
    assert decision.related_uids == (example.uid,)


def test_set_ground_example_use_rejects_noop_and_stale_binding(isolated_store):
    store = MemoryStore()
    session, contexts = _ground_with_example(store)
    example = session.items_of_kind("CASE")[0]

    with pytest.raises(GroundError, match="already set"):
        set_ground_example_use(
            session,
            example.uid,
            use="INCLUDE",
            current_contexts=contexts,
        )

    changed_candidates = store.load_direct("use/candidates")
    changed_candidates.add(
        Memory(
            uid="10000000-0000-4000-8000-000000000012",
            content="A concurrent Example.",
        )
    )
    store.save(changed_candidates)
    with pytest.raises(GroundError, match="stale"):
        set_ground_example_use(
            session,
            example.uid,
            use="EXCLUDE",
            current_contexts=(
                contexts[0],
                changed_candidates,
                contexts[2],
            ),
        )


def test_mem_ground_set_example_use_changes_only_reviewed_ground(isolated_store):
    store = MemoryStore()
    session, contexts = _ground_with_example(store)
    store.save_ground_session(session)
    example = session.items_of_kind("CASE")[0]

    result = runner.invoke(
        app,
        [
            "ground",
            session.contract_name,
            "--set-example-use",
            example.uid,
            "--use",
            "EXCLUDE",
        ],
    )

    assert result.exit_code == 0, result.output
    saved = store.load_ground_session(session.contract_name)
    assert saved is not None
    assert saved.revision == session.revision + 1
    assert saved.items_of_kind("CASE")[0].disposition == "EXCLUDE"
    assert all(store.list_checkpoints(context.name) == [] for context in contexts)
    assert "No Context or Context Memory changes applied" in result.output


def test_mem_ground_set_example_use_requires_complete_pair(isolated_store):
    store = MemoryStore()
    session, _contexts = _ground_with_example(store)
    store.save_ground_session(session)
    example = session.items_of_kind("CASE")[0]

    result = runner.invoke(
        app,
        ["ground", session.contract_name, "--set-example-use", example.uid],
    )

    assert result.exit_code == 1
    assert "requires both --set-example-use and --use" in result.output
