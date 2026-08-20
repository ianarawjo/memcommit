"""Recursive Rationale scope and Study Trace policy contracts."""

from __future__ import annotations

import json
import uuid

from typer.testing import CliRunner

from memcommit.cli import app
from memcommit.commands.switch import _local_picker_annotations
from memcommit.context import Memory
from memcommit.profile_config import ProfileEntry, ProfileRegistry
from memcommit.store import MemoryStore
from memcommit.study_operation_policy import operation_policy


runner = CliRunner()
RATIONALE_MARKER = "RATIONALE PAYLOAD:\n"


class _Provider:
    def __init__(self):
        self.payload: dict[str, object] | None = None

    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "rationale inference"
        assert output_schema is not None
        self.payload = json.loads(prompt.split(RATIONALE_MARKER, 1)[1])
        candidates = self.payload["candidates"]
        assert isinstance(candidates, list)
        return json.dumps(
            {
                "explanation": (
                    "Earlier notes support using diagrams; details remain open."
                ),
                "support_ids": [candidate["candidate_id"] for candidate in candidates],
            }
        )


def _memory(store: MemoryStore, context_name: str, content: str) -> Memory:
    return next(
        item
        for item in store.load_direct(context_name).iter_items()
        if isinstance(item, Memory) and item.content == content
    )


def test_rationale_from_parent_uses_owned_descendant_memories(
    isolated_store,
    monkeypatch,
):
    assert runner.invoke(app, ["init", "advisor"]).exit_code == 0
    assert runner.invoke(app, ["add", "Reviewers scan diagrams first."]).exit_code == 0
    assert runner.invoke(app, ["init", "advisor/style"]).exit_code == 0
    assert runner.invoke(app, ["add", "Drawing a diagram takes longer."]).exit_code == 0
    assert runner.invoke(app, ["add", "Use a diagram when branches matter."]).exit_code == 0
    store = MemoryStore()
    target = _memory(store, "advisor/style", "Use a diagram when branches matter.")
    provider = _Provider()
    monkeypatch.setattr(
        "memcommit.commands.rationale.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    result = runner.invoke(
        app,
        ["rationale", target.uid[:8], "--context", "advisor"],
    )

    assert result.exit_code == 0, result.output
    assert provider.payload is not None
    candidates = provider.payload["candidates"]
    assert {
        (candidate["context_name"], candidate["content"])
        for candidate in candidates
    } == {
        ("advisor", "Reviewers scan diagrams first."),
        ("advisor/style", "Drawing a diagram takes longer."),
    }
    assert "advisor and readable descendants · 2 Context(s)" in result.output


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
