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
                "best_supported_reading": "The advice follows the readable subtree.",
                "contextual_flow": "An earlier observation supports the advice.",
                "support_ids": [candidate["candidate_id"] for candidate in candidates],
                "unresolved": [],
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
    assert "Rationale scope: advisor and readable descendants · 2 Context(s)" in (
        result.output
    )


def test_study_run_trace_is_local_to_task_three_and_visible_in_ls_and_switch(
    isolated_store,
    monkeypatch,
):
    assert runner.invoke(app, ["init", "task-1/participant"]).exit_code == 0
    assert runner.invoke(app, ["add", "Task 1 note."]).exit_code == 0
    assert runner.invoke(app, ["init", "task-3/personal-memory"]).exit_code == 0
    assert runner.invoke(app, ["add", "Task 3 note."]).exit_code == 0
    store = MemoryStore()
    task1 = _memory(store, "task-1/participant", "Task 1 note.")
    task3 = _memory(store, "task-3/personal-memory", "Task 3 note.")
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
    monkeypatch.setattr(
        "memcommit.study_operation_policy.load_profile_registry",
        lambda: registry,
    )
    monkeypatch.setattr(
        "memcommit.study_operation_policy.profile_store_dir",
        lambda _profile: isolated_store,
    )
    monkeypatch.setattr(
        "memcommit.commands.switch.load_profile_registry",
        lambda: registry,
    )

    blocked = runner.invoke(
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

    assert blocked.exit_code == 1
    assert "only in the Task 3 subtree" in blocked.output
    assert allowed.exit_code == 0, allowed.output
    assert "RATIONALE SUBTREE + TRACE BLOCKED" in task1_ls.output
    assert "RATIONALE SUBTREE + TRACE ALLOWED" in task3_ls.output
    assert annotations["task-1/participant"] == (
        "[RATIONALE SUBTREE + TRACE BLOCKED]"
    )
    assert annotations["task-3/personal-memory"] == (
        "[RATIONALE SUBTREE + TRACE ALLOWED]"
    )
