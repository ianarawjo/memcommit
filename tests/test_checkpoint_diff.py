"""Checkpoint action and exact transition rendering for Context Diff."""

from __future__ import annotations

from memcommit.adapters.console.terminal.components.history.checkpoint_diff import (
    checkpoint_diff_detail_renderer,
    checkpoint_revision_document_fragments,
    checkpoint_restore_detail_renderer,
    format_checkpoint_revision_report,
    open_checkpoint_revision_viewer,
)
import memcommit.adapters.console.terminal.components.history.checkpoint_diff as checkpoint_diff
from memcommit.adapters.console.terminal.components.history.picker import HistoryDetailView
from memcommit.adapters.console.terminal.components.history.presentation import checkpoint_picker_entries


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
    assert "REVISION DIFF · RESULT 1 DIRECT ITEM" in rendered
    assert "SUMMARY · 0 kept · 0 added · 1 edited · 0 removed" in rendered
    assert "- [EDIT]   [memory] Use the blue entrance." in rendered
    assert "+ [EDIT]   [memory] Use the green entrance." in rendered
    assert ("class:semantic.edit", "EDIT") in fragments
    assert ("class:memory-diff.before-marker", " - ") in fragments
    assert ("class:memory-diff.after-marker", " + ") in fragments
    assert rendered.index("- [EDIT]") < rendered.index("+ [EDIT]")
    assert any(
        style.startswith("class:memory-diff.remove") and "blue" in text
        for style, text in fragments
    )
    assert any(
        style.startswith("class:memory-diff.add") and "green" in text
        for style, text in fragments
    )
    assert detail.unit_start_lines == (7,)
    assert detail.unit_label == "ITEM"


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

    assert "REVISION DIFF · RESULT 1 DIRECT ITEM" in rendered
    assert "+ [ADD]    [memory] First Memory." in rendered
    assert " - " not in rendered
    assert fragments.count(("class:semantic.add", "ADD")) == 1
    assert ("class:memory-diff.after-marker", " + ") in fragments
    assert detail.unit_start_lines == (7,)


def test_reorder_only_checkpoint_keeps_result_items_navigable():
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
    assert detail.unit_start_lines == (7, 8)
    assert "ORDER · retained direct items changed position" in "".join(
        text for _style, text in detail.content
    )


def test_revision_diff_shows_complete_result_and_removed_items():
    before = _checkpoint(
        "11111111-1111-4111-8111-111111111111",
        "2026-08-06T10:00:00-04:00",
        "add",
        "unused",
    )
    before["snapshot"] = {
        "uid": "context",
        "name": "wiki/access",
        "memories": {
            "kept": {"type": "memory", "uid": "kept", "content": "Keep me"},
            "edited": {
                "type": "memory",
                "uid": "edited",
                "content": "Old wording",
            },
            "removed": {
                "type": "memory",
                "uid": "removed",
                "content": "Remove me",
            },
        },
        "order": ["kept", "edited", "removed"],
    }
    after = _checkpoint(
        "22222222-2222-4222-8222-222222222222",
        "2026-08-06T11:00:00-04:00",
        "update",
        "unused",
    )
    after["snapshot"] = {
        "uid": "context",
        "name": "wiki/access",
        "memories": {
            "kept": {"type": "memory", "uid": "kept", "content": "Keep me"},
            "edited": {
                "type": "memory",
                "uid": "edited",
                "content": "New wording",
            },
            "added": {"type": "memory", "uid": "added", "content": "Add me"},
        },
        "order": ["kept", "edited", "added"],
    }
    entry = checkpoint_picker_entries([after, before])[0]

    detail = checkpoint_diff_detail_renderer([after, before])(entry)

    assert isinstance(detail, HistoryDetailView)
    rendered = "".join(text for _style, text in detail.content)
    assert "SUMMARY · 1 kept · 1 added · 1 edited · 1 removed" in rendered
    assert "  [KEEP]   [kept] Keep me" in rendered
    assert "- [EDIT]   [edited] Old wording" in rendered
    assert "+ [EDIT]   [edited] New wording" in rendered
    assert "- [REMOVE] [removed] Remove me" in rendered
    assert "+ [ADD]    [added] Add me" in rendered
    assert rendered.index("[KEEP]") < rendered.index("- [EDIT]")
    assert rendered.index("+ [EDIT]") < rendered.index("- [REMOVE]")
    assert rendered.index("- [REMOVE]") < rendered.index("+ [ADD]")
    assert "REMOVED BY REVISION" not in rendered
    assert detail.unit_start_lines == (7, 8, 10, 11)


def test_revert_uses_revision_result_instead_of_current_to_target_impact():
    first = _checkpoint(
        "11111111-1111-4111-8111-111111111111",
        "2026-08-06T10:00:00-04:00",
        "add",
        "First Memory.",
    )
    entry = checkpoint_picker_entries([first])[0]
    unrelated_current = _snapshot("A much later Memory.")

    restored = checkpoint_restore_detail_renderer(
        unrelated_current,
        [first],
    )(entry)
    diffed = checkpoint_diff_detail_renderer([first])(entry)

    assert isinstance(restored, HistoryDetailView)
    assert isinstance(diffed, HistoryDetailView)
    assert restored == diffed
    rendered = "".join(text for _style, text in restored.content)
    assert "REVISION DIFF" in rendered
    assert "RESTORE IMPACT" not in rendered
    assert "A much later Memory." not in rendered


def test_diff_document_hides_kept_rows_but_preserves_summary_and_color():
    before = _checkpoint(
        "11111111-1111-4111-8111-111111111111",
        "2026-08-06T10:00:00-04:00",
        "add",
        "unused",
    )
    before["snapshot"] = {
        "uid": "context",
        "name": "wiki/access",
        "memories": {
            "kept-memory": {
                "type": "memory",
                "uid": "kept-memory",
                "content": "Keep me",
            },
            "edited-memory": {
                "type": "memory",
                "uid": "edited-memory",
                "content": "Old wording",
            },
        },
        "order": ["kept-memory", "edited-memory"],
    }
    after = _checkpoint(
        "22222222-2222-4222-8222-222222222222",
        "2026-08-06T11:00:00-04:00",
        "update",
        "unused",
    )
    after["snapshot"] = {
        **before["snapshot"],
        "memories": {
            **before["snapshot"]["memories"],
            "edited-memory": {
                "type": "memory",
                "uid": "edited-memory",
                "content": "New wording",
            },
        },
    }
    checkpoints = [after, before]
    entry = checkpoint_picker_entries(checkpoints)[0]

    fragments = checkpoint_revision_document_fragments(
        checkpoints,
        entry,
        context_name="wiki/access",
    )
    rendered = "".join(text for _style, text in fragments)
    plain = format_checkpoint_revision_report(
        checkpoints,
        entry,
        context_name="wiki/access",
    )

    assert "DIFF · wiki/access" in rendered
    assert "1 edited · 0 added · 0 removed · 1 unchanged hidden" in rendered
    assert "Keep me" not in rendered
    assert "Old wording" in rendered
    assert "New wording" in rendered
    assert ("class:semantic.edit", "EDIT") in fragments
    assert ("class:memory-diff.before-marker", " - ") in fragments
    assert ("class:memory-diff.after-marker", " + ") in fragments
    assert plain == rendered.rstrip()


def test_checkpoint_revision_viewer_is_one_read_only_document(monkeypatch):
    checkpoint = _checkpoint(
        "11111111-1111-4111-8111-111111111111",
        "2026-08-06T10:00:00-04:00",
        "add",
        "First Memory.",
    )
    entry = checkpoint_picker_entries([checkpoint])[0]
    viewed = {}
    monkeypatch.setattr(
        checkpoint_diff,
        "run_read_only_viewer",
        lambda text, **kwargs: viewed.update(text=text, kwargs=kwargs),
    )

    open_checkpoint_revision_viewer(
        [checkpoint],
        entry,
        context_name="wiki/access",
    )

    assert "DIFF · wiki/access" in "".join(
        text for _style, text in viewed["text"]
    )
    assert viewed["kwargs"] == {
        "title": "DIFF REPORT",
        "frame_title": "CHECKPOINT REVISION",
        "app_input": None,
        "app_output": None,
        "require_tty": True,
    }
