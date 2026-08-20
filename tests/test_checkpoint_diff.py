"""Checkpoint action and exact transition rendering for Context Diff."""
from __future__ import annotations

from memcommit.commands.checkpoint_diff import checkpoint_diff_detail_renderer
from memcommit.commands.history_picker import HistoryDetailView
from memcommit.commands.history_present import checkpoint_picker_entries


def _snapshot(content: str | None) -> dict:
    memories = (
        {}
        if content is None
        else {"memory": {"type": "memory", "uid": "memory", "content": content}}
    )
    return {
        "uid": "context",
        "name": "wiki/access",
        "memories": memories,
        "order": list(memories),
    }


def _checkpoint(uid: str, timestamp: str, command: str, content: str) -> dict:
    return {
        "uid": uid,
        "timestamp": timestamp,
        "command": command,
        "description": f"Ran {command}",
        "snapshot": _snapshot(content),
    }


def test_selected_checkpoint_shows_action_and_red_then_green_memory_change():
    first = _checkpoint(
        "11111111-1111-4111-8111-111111111111",
        "2026-08-06T10:00:00-04:00",
        "add",
        "Use the blue entrance.",
    )
    second = _checkpoint(
        "22222222-2222-4222-8222-222222222222",
        "2026-08-06T11:00:00-04:00",
        "update",
        "Use the green entrance.",
    )
    checkpoints = [second, first]
    entry = checkpoint_picker_entries(checkpoints)[0]
    detail = checkpoint_diff_detail_renderer(checkpoints)(entry)
    assert isinstance(detail, HistoryDetailView)
    fragments = detail.content
    rendered = "".join(text for _style, text in fragments)

    assert "ACTION      update" in rendered
    assert "UPDATE · EDIT [memory]" in rendered
    assert rendered.index(" - Use the blue entrance.") < rendered.index(
        " + Use the green entrance."
    )
    assert any(
        style.startswith("class:memory-diff.remove") and "blue" in text
        for style, text in fragments
    )
    assert any(
        style.startswith("class:memory-diff.add") and "green" in text
        for style, text in fragments
    )
    assert detail.unit_start_lines == (4,)


def test_first_checkpoint_is_an_addition_from_the_empty_baseline():
    first = _checkpoint(
        "11111111-1111-4111-8111-111111111111",
        "2026-08-06T10:00:00-04:00",
        "add",
        "First Memory.",
    )
    entry = checkpoint_picker_entries([first])[0]
    detail = checkpoint_diff_detail_renderer([first])(entry)
    assert isinstance(detail, HistoryDetailView)
    fragments = detail.content
    rendered = "".join(text for _style, text in fragments)

    assert "ADD · ADD [memory]" in rendered
    assert " + First Memory." in rendered
    assert " - " not in rendered
    assert detail.unit_start_lines == (4,)


def test_reorder_only_checkpoint_is_one_navigable_change():
    first = _checkpoint(
        "11111111-1111-4111-8111-111111111111",
        "2026-08-06T10:00:00-04:00",
        "add",
        "First Memory.",
    )
    first["snapshot"] = {
        "uid": "context",
        "name": "wiki/access",
        "memories": {
            "one": {"type": "memory", "uid": "one", "content": "One"},
            "two": {"type": "memory", "uid": "two", "content": "Two"},
        },
        "order": ["one", "two"],
    }
    second = _checkpoint(
        "22222222-2222-4222-8222-222222222222",
        "2026-08-06T11:00:00-04:00",
        "edit",
        "unused",
    )
    second["snapshot"] = {**first["snapshot"], "order": ["two", "one"]}
    checkpoints = [second, first]
    entry = checkpoint_picker_entries(checkpoints)[0]

    detail = checkpoint_diff_detail_renderer(checkpoints)(entry)

    assert isinstance(detail, HistoryDetailView)
    assert detail.unit_start_lines == (4,)
    assert "Direct-item order changed" in "".join(
        text for _style, text in detail.content
    )
