"""Location and subtree dispatch for the interactive Diff browser."""
from __future__ import annotations

from types import SimpleNamespace

import memcommit.commands.diff_browser as diff_browser
from memcommit.commands.context_picker import ContextSubtreeSelection
from memcommit.commands.history_picker import HISTORY_BACK


class Store:
    def list_context_names(self):
        return ["task-1"]

    def list_checkpoints(self, _name):
        return []

    def current_context_name(self):
        return "task-1"


def test_namespace_enter_dispatches_one_changed_subtree_history(monkeypatch):
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

    diff_browser.browse_diff(
        Store(),
        session=session,
        context_locator=None,
    )

    assert parent in observed["descendant_scope_names"]
    assert opened == [(session, parent)]


def test_checkpoint_backspace_reopens_context_selector(monkeypatch):
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

    diff_browser.browse_diff(
        Store(),
        session=session,
        context_locator=None,
    )

    assert len(selector_currents) == 2
    assert selector_currents[1] == child
    assert opened == [
        (session, child, {"back_navigation": True})
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
            SimpleNamespace(owner_context_name=name)
            for name in locations
        ),
    )

    operations = diff_browser._update_operation_ids(session)
    annotations = diff_browser._operation_annotations(
        (parent, *locations),
        operations,
    )

    assert annotations[parent] == "0 direct · 2 descendant operations"
    assert annotations[locations[0]] == (
        "2 direct · 0 descendant operations"
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
    assert diff_browser._checkpoint_operation_identity(
        {"uid": "baseline", "command": "init", "args": {}}
    ) is None
