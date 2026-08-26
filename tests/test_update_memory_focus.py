"""Focused-Memory identity and safety contracts for directional Update."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

import memcommit.ops as ops
import memcommit.commands.update.command as update_command
from memcommit.cli import app
from memcommit.store import MemoryStore
from memcommit.update import UpdateError, UpdateSession, plan_update, session_matches


class _Provider:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object] | None]] = []

    def complete(self, prompt, *, operation, output_schema=None):
        self.calls.append((prompt, output_schema))
        payload = json.loads(prompt.split("UPDATE PAYLOAD:\n", 1)[1])
        source_id = payload["source"]["memories"][0]["source_id"]
        target_id = payload["target"]["memories"][0]["target_id"]
        return json.dumps(
            {
                "edits": [
                    {
                        "target_id": target_id,
                        "new_content": "The south entrance is open.",
                        "source_ids": [source_id],
                        "reason": "The selected source supersedes the target.",
                    }
                ],
                "additions": [],
                "removals": [],
            }
        )


def _focused_pair():
    source = ops.init("focused/update/source")
    source_neighbor = ops.add(source, "Background construction note.")
    source_focus = ops.add(source, "The south entrance is open.")
    target = ops.init("focused/update/target")
    target_focus = ops.add(target, "The south entrance is closed.")
    target_neighbor = ops.add(target, "The library remains open.")
    return (
        source,
        source_neighbor,
        source_focus,
        target,
        target_focus,
        target_neighbor,
    )


def test_focused_update_keeps_neighbors_context_only_and_binds_exact_identity():
    (
        source,
        source_neighbor,
        source_focus,
        target,
        target_focus,
        target_neighbor,
    ) = _focused_pair()
    provider = _Provider()

    session = plan_update(
        source,
        target,
        lambda: provider,
        source_memory_selector=source_focus.uid[:8],
        target_memory_selector=target_focus.uid[:8],
    )
    prompt, schema = provider.calls[0]
    payload = json.loads(prompt.split("UPDATE PAYLOAD:\n", 1)[1])

    assert session.source_memory_uid == source_focus.uid
    assert session.target_memory_uid == target_focus.uid
    assert payload["source"]["memories"] == [
        {
            "source_id": "s000002",
            "context": source.name,
            "content": source_focus.content,
        }
    ]
    assert payload["source"]["context_evidence"][0]["content"] == (
        source_neighbor.content
    )
    assert payload["target"]["memories"][0]["content"] == target_focus.content
    assert payload["target"]["context_evidence"][0]["content"] == (
        target_neighbor.content
    )
    assert payload["target"]["contexts"] == []
    assert schema is not None
    assert schema["properties"]["additions"]["maxItems"] == 0
    assert session.operations[0].memory_uid == target_focus.uid
    assert UpdateSession.from_dict(session.to_dict()) == session


def test_focused_update_session_tracks_the_complete_observed_graph():
    source, source_neighbor, source_focus, target, target_focus, _ = _focused_pair()
    session = plan_update(
        source,
        target,
        _Provider,
        source_memory_selector=source_focus.uid,
        target_memory_selector=target_focus.uid,
    )

    assert session_matches(session, source, target)
    source_neighbor.content = "Changed contextual construction note."
    assert not session_matches(session, source, target)


def test_focused_update_reuses_only_an_exact_uid_bound_impact_cache(
    isolated_store,
    monkeypatch,
):
    source, _, source_focus, target, target_focus, _ = _focused_pair()
    store = MemoryStore()
    store.create_context(source)
    store.create_context(target)
    store.set_current(source.name)
    cached = plan_update(
        source,
        target,
        _Provider,
        source_memory_selector=source_focus.uid,
        target_memory_selector=target_focus.uid,
    )
    store.save_impact_plan(cached)
    monkeypatch.setattr(
        update_command,
        "connect_codex_chatgpt_provider",
        lambda: pytest.fail("an exact focused cache must avoid provider construction"),
    )

    result = CliRunner(mix_stderr=False).invoke(
        app,
        [
            "update",
            "--from",
            source.name,
            "--to",
            target.name,
            "--source-memory",
            source_focus.uid,
            "--target-memory",
            target_focus.uid,
        ],
    )

    assert result.exit_code == 0, result.output
    applied = store.load_staged_update()
    assert applied is not None and applied.status == "applied"
    assert applied.source_memory_uid == source_focus.uid
    assert applied.target_memory_uid == target_focus.uid
    updated_target = store.load_direct(target.name)
    assert updated_target.memories[target_focus.uid].content == (
        "The south entrance is open."
    )


@pytest.mark.parametrize("side", ("source", "target"))
def test_focused_update_rejects_descendant_reach(side: str):
    source, _, source_focus, target, target_focus, _ = _focused_pair()
    kwargs = {
        "source_memory_selector": source_focus.uid if side == "source" else None,
        "target_memory_selector": target_focus.uid if side == "target" else None,
        "source_include_descendants": side == "source",
        "target_include_descendants": side == "target",
    }

    with pytest.raises(UpdateError, match="cannot be combined"):
        plan_update(source, target, _Provider, **kwargs)
