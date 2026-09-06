"""The Revert adapter freezes exact versions without command-unit deduplication."""

from types import SimpleNamespace

import pytest

import memcommit.adapters.console.commands.revert.selection as selection


def test_revert_keeps_every_retained_version_in_the_frozen_review(monkeypatch):
    shared_update = {"update_session_uid": "session-1", "operation_digest": "digest-1"}
    checkpoints = [
        {
            "uid": uid,
            "timestamp": "2026-08-13T12:00:00",
            "command": command,
            "description": "Retained state",
            "args": args,
        }
        for uid, command, args in (
            ("checkpoint-a", "update", shared_update),
            ("checkpoint-b", "update", shared_update),
            ("checkpoint-atomize", "atomize", {"analysis_uid": "analysis-1"}),
            ("checkpoint-init", "init", {"source_analysis_uid": "analysis-1"}),
        )
    ]

    class Store:
        def list_context_names(self):
            return ["journal"]

        def load_direct(self, name):
            assert name == "journal"
            return SimpleNamespace(name=name, uid="journal-uid")

        def list_checkpoints(self, name):
            assert name == "journal"
            return checkpoints

    observed = []

    def choose(entries, **kwargs):
        observed.extend(entry.uid for entry in entries)
        assert kwargs["context_name"] == "journal"
        assert kwargs["back_navigation"] is False
        assert kwargs["keep_history"] is True
        return None

    monkeypatch.setattr(selection, "freeze_checkpoint_catalog", lambda _store: object())
    monkeypatch.setattr(
        selection, "checkpoint_revision_detail_renderer", lambda _entries: None
    )
    monkeypatch.setattr(selection, "choose_revert_history", choose)

    assert selection.review_context_checkpoints(Store(), context_name="journal") is None
    assert observed == [checkpoint["uid"] for checkpoint in checkpoints]


def test_revert_rejects_a_current_public_name_outside_the_local_catalog():
    class Store:
        def list_context_names(self):
            return ["journal"]

        def load_direct(self, _name):
            raise AssertionError("An unavailable target must fail before loading")

    with pytest.raises(ValueError, match="not available for REVERT"):
        selection.review_context_checkpoints(Store(), context_name="granted/source")
