"""Recursive Rationale scope and Study Trace policy contracts."""

from __future__ import annotations

import uuid

from typer.testing import CliRunner

from memcommit.adapters.console.entrypoint import app
from memcommit.adapters.console.commands.browse_navigate.switch.command import _local_picker_annotations
from memcommit.core.context import Memory
from memcommit.application.operations.profiles.profile.config import ProfileEntry, ProfileRegistry
from memcommit.persistence.store import MemoryStore
from memcommit.application.capabilities.authority.study_operation_policy import operation_policy


runner = CliRunner()
def _memory(store: MemoryStore, context_name: str, content: str) -> Memory:
    return next(
        item
        for item in store.load_direct(context_name).iter_items()
        if isinstance(item, Memory) and item.content == content
    )


def test_rationale_from_parent_selects_descendant_but_does_not_analyze_neighbors(
    isolated_store,
):
    assert runner.invoke(app, ["init", "advisor"]).exit_code == 0
    assert runner.invoke(app, ["add", "Reviewers scan diagrams first."]).exit_code == 0
    assert runner.invoke(app, ["init", "advisor/style"]).exit_code == 0
    assert runner.invoke(app, ["add", "Drawing a diagram takes longer."]).exit_code == 0
    assert runner.invoke(app, ["add", "Use a diagram when branches matter."]).exit_code == 0
    store = MemoryStore()
    target = _memory(store, "advisor/style", "Use a diagram when branches matter.")
    result = runner.invoke(
        app,
        ["rationale", target.uid[:8], "--context", "advisor"],
    )
    structured = runner.invoke(
        app,
        ["rationale", target.uid[:8], "--context", "advisor", "--json"],
    )

    assert result.exit_code == 0, result.output
    assert structured.exit_code == 0, structured.output
    assert "Use a diagram when branches matter." in result.output
    assert "Reviewers scan diagrams first." not in result.output
    assert "Drawing a diagram takes longer." not in result.output
    assert "APPARENT PURPOSE" not in result.output
    assert "Context(s)" not in result.output


def test_locally_owned_trace_is_available_independent_of_study_task(
    isolated_store,
):
    assert runner.invoke(app, ["init", "task-1/participant"]).exit_code == 0
    assert runner.invoke(app, ["add", "Task 1 note."]).exit_code == 0
    assert runner.invoke(app, ["init", "task-3/personal-memory"]).exit_code == 0
    assert runner.invoke(app, ["add", "Task 3 note."]).exit_code == 0
    store = MemoryStore()
    task1 = _memory(store, "task-1/participant", "Task 1 note.")
    task3 = _memory(store, "task-3/personal-memory", "Task 3 note.")
    task1_result = runner.invoke(
        app,
        ["trace", task1.uid[:8], "--context", "task-1/participant"],
    )
    allowed = runner.invoke(
        app,
        ["trace", task3.uid[:8], "--context", "task-3/personal-memory"],
    )
    task1_ls = runner.invoke(app, ["ls", "task-1/participant"])
    task3_ls = runner.invoke(app, ["ls", "task-3/personal-memory"])
    annotations = _local_picker_annotations(store.list_context_names())

    assert task1_result.exit_code == 0, task1_result.output
    assert allowed.exit_code == 0, allowed.output
    assert "Analysis:" not in task1_ls.output
    assert "Analysis:" not in task3_ls.output
    assert annotations == {}


def test_study_profile_metadata_does_not_reduce_local_trace_authority():
    profile = ProfileEntry(
        uid=str(uuid.uuid4()),
        name="study-run",
        kind="MANAGED",
        source={"kind": "STUDY_RUN"},
    )
    registry = ProfileRegistry(
        generation=1,
        active_uid=profile.uid,
        profiles=(profile,),
    )

    assert operation_policy(
        "task-1/participant",
        granted=False,
        registry=registry,
    ).trace_allowed
    assert operation_policy(
        "task-3/personal-memory",
        granted=False,
        registry=registry,
    ).trace_allowed
    assert not operation_policy(
        "task-3/shared-view",
        granted=True,
        registry=registry,
    ).trace_allowed
