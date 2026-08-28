"""Location and subtree dispatch for the interactive Diff browser."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import memcommit.adapters.console.terminal.components.history.browser as diff_browser
from memcommit.core.context_targeting.tui.picker import ContextSubtreeSelection
from memcommit.adapters.console.terminal.components.history.picker import HISTORY_BACK


class Store:
    def list_context_names(self):
        return ["task-1"]

    def list_checkpoints(self, _name):
        return []

    def current_context_name(self):
        return "task-1"

    def load_direct(self, name):
        return SimpleNamespace(name=name, uid=f"uid:{name}")


def test_shared_location_browser_dispatches_one_changed_subtree_history(monkeypatch):
    parent = "task-1/campus-wiki"
    child = f"{parent}/building-access"
    session = SimpleNamespace(
        target_contexts=(SimpleNamespace(name=parent),),
        operations=(SimpleNamespace(owner_context_name=child),),
        application=None,
    )
    observed = {}

    def choose(*_args, **kwargs):
        observed.update(kwargs)
        return ContextSubtreeSelection(parent)

    opened = []
    monkeypatch.setattr(diff_browser, "choose_history_location", choose)
    monkeypatch.setattr(
        diff_browser,
        "choose_update_checkpoint_subtree",
        lambda selected_session, root, **_kwargs: opened.append(
            (selected_session, root)
        ),
    )

    diff_browser.browse_checkpoint_locations(
        Store(),
        session=session,
        context_locator=None,
        title="REVERT",
    )

    assert parent in observed["descendant_scope_names"]
    assert observed["select_nested_checkpoints"] is False
    assert opened == [(session, parent)]


def test_shared_location_browser_backspace_reopens_context_selector(monkeypatch):
    child = "task-1/campus-wiki/building-access"
    session = SimpleNamespace(
        target_contexts=(SimpleNamespace(name=child),),
        operations=(SimpleNamespace(owner_context_name=child),),
        application=None,
    )
    selections = iter((child, None))
    selector_currents = []

    def choose(*_args, **kwargs):
        selector_currents.append(kwargs["current"])
        return next(selections)

    opened = []
    monkeypatch.setattr(diff_browser, "choose_history_location", choose)
    monkeypatch.setattr(
        diff_browser,
        "choose_update_checkpoint_at_location",
        lambda selected_session, name, **kwargs: (
            opened.append((selected_session, name, kwargs)),
            HISTORY_BACK,
        )[1],
    )

    diff_browser.browse_checkpoint_locations(
        Store(),
        session=session,
        context_locator=None,
        title="REVERT",
    )

    assert len(selector_currents) == 2
    assert selector_currents[1] == child
    assert opened == [
        (
            session,
            child,
            {
                "back_navigation": True,
                "title": "REVERT",
            },
        )
    ]


def test_diff_bypasses_profile_location_selection_and_opens_current_fullscreen(
    monkeypatch,
):
    observed = {}

    def browse(*_args, **kwargs):
        observed.update(kwargs)

    monkeypatch.setattr(diff_browser, "browse_checkpoint_locations", browse)

    diff_browser.browse_diff(Store(), session=None, context_locator=None)

    assert observed == {
        "session": None,
        "context_locator": "task-1",
        "title": "DIFF",
    }


def test_diff_explicit_context_bypasses_current_without_switching(monkeypatch):
    observed = {}

    def browse(*_args, **kwargs):
        observed.update(kwargs)

    monkeypatch.setattr(diff_browser, "browse_checkpoint_locations", browse)

    diff_browser.browse_diff(Store(), session=None, context_locator="archive")

    assert observed["context_locator"] == "archive"


def test_diff_resolves_relative_context_from_one_current_snapshot(monkeypatch):
    observed = {}
    store = Store()
    store.current_context_name = lambda: "task-1/current"

    def browse(*_args, **kwargs):
        observed.update(kwargs)

    monkeypatch.setattr(diff_browser, "browse_checkpoint_locations", browse)

    diff_browser.browse_diff(store, session=None, context_locator="../archive")

    assert observed["context_locator"] == "task-1/archive"


def test_diff_without_current_or_explicit_context_fails_before_browser(monkeypatch):
    store = Store()
    store.current_context_name = lambda: None
    monkeypatch.setattr(
        diff_browser,
        "browse_checkpoint_locations",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("profile location browser must not open")
        ),
    )

    with pytest.raises(ValueError, match="No current Context"):
        diff_browser.browse_diff(store, session=None, context_locator=None)


def test_exact_history_scope_does_not_scan_unrelated_context_history(monkeypatch):
    opened = []
    monkeypatch.setattr(
        diff_browser,
        "_local_operation_ids",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("exact history must not scan the Profile catalog")
        ),
    )
    monkeypatch.setattr(
        diff_browser,
        "_browse_local_checkpoints",
        lambda _store, name, **kwargs: opened.append((name, kwargs)),
    )

    diff_browser.browse_checkpoint_locations(
        Store(),
        session=None,
        context_locator="task-1",
        title="DIFF",
    )

    assert opened == [
        (
            "task-1",
            {
                "back_navigation": False,
                "manual": False,
                "show_diffs": True,
                "mode": "log",
                "keep_history": False,
                "staged_checkpoint_uid": None,
                "title": "DIFF",
            },
        )
    ]


def test_subtree_counts_multi_context_update_and_undo_as_two_operations():
    parent = "task-1"
    locations = (
        "task-1/campus-wiki/building-access",
        "task-1/campus-wiki/temporary-parking",
    )
    session = SimpleNamespace(
        uid="session-1",
        status="undone",
        application=SimpleNamespace(operation_digest="digest-1"),
        operations=tuple(
            SimpleNamespace(owner_context_name=name) for name in locations
        ),
    )

    operations = diff_browser._update_operation_ids(session)
    annotations = diff_browser._operation_annotations(
        (parent, *locations),
        operations,
    )

    assert annotations[parent] == ("0 direct · 0 inherited · 2 descendant commands")
    assert annotations[locations[0]] == (
        "2 direct · 0 inherited · 0 descendant commands"
    )


def test_checkpoint_operation_identity_deduplicates_shared_receipts():
    update_args = {
        "update_session_uid": "session-1",
        "operation_digest": "digest-1",
    }
    undo_args = {
        "command_restore": {"receipt_uid": "restore-1"},
    }

    assert diff_browser._checkpoint_operation_identity(
        {"uid": "checkpoint-a", "command": "update", "args": update_args}
    ) == diff_browser._checkpoint_operation_identity(
        {"uid": "checkpoint-b", "command": "update", "args": update_args}
    )
    assert diff_browser._checkpoint_operation_identity(
        {"uid": "checkpoint-c", "command": "undo", "args": undo_args}
    ) == diff_browser._checkpoint_operation_identity(
        {"uid": "checkpoint-d", "command": "undo", "args": undo_args}
    )
    assert (
        diff_browser._checkpoint_operation_identity(
            {"uid": "baseline", "command": "init", "args": {}}
        )
        is None
    )


def test_checkpoint_rows_mark_proven_creation_without_counting_it_as_operation():
    checkpoints = (
        {
            "uid": "atomize-checkpoint",
            "timestamp": "2026-08-13T11:39:00",
            "command": "atomize",
            "description": "Applied atomize",
            "args": {"analysis_uid": "analysis-1"},
        },
        {
            "uid": "creation-checkpoint",
            "timestamp": "2026-08-13T11:38:00",
            "command": "init",
            "description": "Initialized output before applying atomize",
            "args": {"source_analysis_uid": "analysis-1"},
        },
    )

    rows = diff_browser._checkpoint_operation_rows(
        checkpoints,
        context_name="output",
        context_uid="output-uid",
    )

    assert [row.label for row in rows] == ["created"]
    assert rows[0].content.startswith("2026-08-13 11:38 · baseline for CONTEXT")
    assert [badge.text for badge in rows[0].badges] == [
        "CHECKPOINT creation",
        "ATOMIZE",
    ]
    assert diff_browser._checkpoint_operation_identity(checkpoints[1]) is None


def test_checkpoint_rows_keep_unrelated_atomize_after_creation():
    rows = diff_browser._checkpoint_operation_rows(
        (
            {
                "uid": "later-atomize",
                "timestamp": "2026-08-13T12:00:00",
                "command": "atomize",
                "description": "Applied another atomize",
                "args": {"analysis_uid": "analysis-2"},
            },
            {
                "uid": "creation-checkpoint",
                "timestamp": "2026-08-13T11:38:00",
                "command": "init",
                "description": "Initialized output before applying atomize",
                "args": {"source_analysis_uid": "analysis-1"},
            },
        ),
        context_name="output",
        context_uid="output-uid",
    )

    assert [row.label for row in rows] == ["atomize", "created"]


def test_checkpoint_rows_do_not_infer_creation_origin_from_oldest_entry():
    rows = diff_browser._checkpoint_operation_rows(
        (
            {
                "uid": "plain-creation",
                "timestamp": "2026-08-13T10:00:00",
                "command": "init",
                "description": "Initialized context",
                "args": {"name": "output"},
            },
        ),
        context_name="output",
        context_uid="output-uid",
    )

    assert rows[0].label == "created"
    assert [badge.text for badge in rows[0].badges] == ["CHECKPOINT plain-cr"]


def test_revert_version_rows_keep_every_exact_checkpoint_selectable():
    shared_update = {
        "update_session_uid": "session-1",
        "operation_digest": "digest-1",
    }
    checkpoints = (
        {
            "uid": "checkpoint-a",
            "timestamp": "2026-08-13T12:00:00",
            "command": "update",
            "description": "First retained state",
            "args": shared_update,
        },
        {
            "uid": "checkpoint-b",
            "timestamp": "2026-08-13T11:00:00",
            "command": "update",
            "description": "Second retained state",
            "args": shared_update,
        },
        {
            "uid": "checkpoint-init",
            "timestamp": "2026-08-13T10:00:00",
            "command": "init",
            "description": "Creation state",
            "args": {},
        },
    )

    rows = diff_browser._checkpoint_version_rows(
        checkpoints,
        context_name="journal",
        context_uid="journal-uid",
    )

    assert [row.selector for row in rows] == [
        "checkpoint-a",
        "checkpoint-b",
        "checkpoint-init",
    ]
    assert [row.label for row in rows] == ["update", "update", "created"]


def test_checkpoint_rows_separate_direct_commands_from_inherited_lineage():
    rows = diff_browser._checkpoint_operation_rows(
        (
            {
                "uid": "direct-checkpoint-uid",
                "timestamp": "2026-08-19T14:19:00",
                "command": "remove",
                "description": 'Removed memory [memory-uid]: "direct"',
                "args": {"uid": "memory-uid"},
                "snapshot": {"name": "practice/2", "uid": "branch-uid"},
            },
            {
                "uid": "source-add-checkpoint",
                "timestamp": "2026-08-19T14:02:00",
                "command": "add",
                "description": 'Added: "inherited"',
                "args": {
                    "content": "inherited",
                    "memory_uids": ["inherited-memory-uid"],
                },
                "snapshot": {"name": "practice/1", "uid": "source-uid"},
            },
            {
                "uid": "source-init-checkpoint",
                "timestamp": "2026-08-19T14:01:00",
                "command": "init",
                "args": {},
                "snapshot": {"name": "practice/1", "uid": "source-uid"},
            },
        ),
        context_name="practice/2",
        context_uid="branch-uid",
    )

    assert [row.section_label for row in rows] == [
        "DIRECT COMMANDS · practice/2",
        "INHERITED HISTORY · source practice/1",
        None,
    ]
    assert [row.label for row in rows] == ["remove", "add", "created"]
    assert [badge.text for badge in rows[1].badges] == [
        "CHECKPOINT source-a",
        "MEMORY inherite",
    ]


def test_restore_row_labels_checkpoint_receipt_and_source_without_uid_aliases():
    rows = diff_browser._checkpoint_operation_rows(
        (
            {
                "uid": "undo-checkpoint-full",
                "timestamp": "2026-08-19T14:22:00",
                "command": "undo",
                "args": {
                    "command_restore": {
                        "receipt_uid": "receipt-full-uid",
                        "source_command": "remove",
                        "source_unit_uid": "checkpoint:remove-checkpoint-full",
                    }
                },
                "snapshot": {"name": "practice/2", "uid": "branch-uid"},
            },
        ),
        context_name="practice/2",
        context_uid="branch-uid",
    )

    assert [badge.text for badge in rows[0].badges] == [
        "CHECKPOINT undo-che",
        "RECEIPT receipt-",
        "SOURCE remove remove-c",
    ]
    assert [detail.value for detail in rows[0].details] == [
        "undo-checkpoint-full",
        "direct · practice/2",
        "receipt-full-uid",
        "remove",
        "checkpoint:remove-checkpoint-full",
    ]


def test_checkpoint_identity_reuses_merge_command_unit_contract():
    merge_args = {"merge_tree": {"version": 2, "operation_uid": "merge-operation-uid"}}

    assert diff_browser._checkpoint_operation_identity(
        {"uid": "checkpoint-a", "command": "merge", "args": merge_args}
    ) == diff_browser._checkpoint_operation_identity(
        {"uid": "checkpoint-b", "command": "merge", "args": merge_args}
    )
