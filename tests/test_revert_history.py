"""Picker and natural-language selection contracts for ``mem revert``."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from memcommit.cli import app
from memcommit.commands.history_picker import HistorySelectionReceipt
from memcommit.store import MemoryStore


runner = CliRunner()


def invoke(*args: str):
    return runner.invoke(app, list(args))


class EarliestCheckpointProvider:
    def __init__(self):
        self.called = False

    def complete(self, prompt, *, operation, output_schema=None):
        self.called = True
        payload = json.loads(prompt.split("HISTORY SEARCH PAYLOAD:\n", 1)[1])
        assert payload["allowed_result_kinds"] == ["checkpoint"]
        return json.dumps(
            {
                "understanding": "Choose the earliest saved version.",
                "result_kind": "checkpoint",
                "subject_mode": "ALL",
                "subject_ids": [],
                "event_kinds": [],
                "anchor_kind": "NONE",
                "anchor_ids": [],
                "anchor_occurrence": "ANY",
                "relation": "NONE",
                "reduce": "EARLIEST",
            }
        )


def test_bare_revert_uses_picker_and_exact_returned_uid(
    isolated_store,
    monkeypatch,
):
    invoke("init", "notes")
    invoke("add", "remove me")
    store = MemoryStore()
    init_uid = store.list_checkpoints("notes")[-1]["uid"]
    monkeypatch.setattr(
        "memcommit.commands.revert._interactive_terminal",
        lambda: True,
    )

    monkeypatch.setattr(
        "memcommit.commands.diff_browser.choose_history_location",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("bare Revert must not open the Profile Context tree")
        ),
    )

    def choose(entries, *, context_name, mode, **kwargs):
        assert context_name == "notes"
        assert mode == "revert"
        assert kwargs["keep_history"] is False
        return HistorySelectionReceipt(
            context_name=context_name,
            checkpoint_uid=init_uid,
        )

    monkeypatch.setattr(
        "memcommit.commands.diff_browser.choose_history",
        choose,
    )

    result = invoke("revert")

    assert result.exit_code == 0
    assert "Reverted" in result.output
    assert not store.load_current().memories


def test_bare_revert_opens_the_current_context_history_directly(
    isolated_store,
    monkeypatch,
):
    invoke("init", "notes")
    invoke("add", "remove me")
    monkeypatch.setattr(
        "memcommit.commands.revert._interactive_terminal",
        lambda: True,
    )
    observed = {}

    def browse(*_args, **kwargs):
        observed.update(kwargs)
        return None

    monkeypatch.setattr(
        "memcommit.commands.revert.browse_checkpoint_locations",
        browse,
    )

    result = invoke("revert")

    assert result.exit_code == 0, result.output
    assert observed == {
        "session": None,
        "context_locator": "notes",
        "title": "REVERT",
        "mode": "revert",
        "keep_history": False,
    }
    assert "Revert cancelled" in result.output


def test_bare_revert_keeps_an_empty_current_context_as_its_scope(
    isolated_store,
    monkeypatch,
):
    invoke("init", "task-1/participant")
    invoke("init", "task-1/result")
    invoke("add", "remove me")
    store = MemoryStore()
    store.set_current("task-1/participant")

    monkeypatch.setattr(
        "memcommit.commands.revert._interactive_terminal",
        lambda: True,
    )
    monkeypatch.setattr(
        "memcommit.commands.diff_browser.choose_history_location",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("an empty current Context must not broaden Revert")
        ),
    )

    def choose(entries, *, context_name, **kwargs):
        assert context_name == "task-1/participant"
        assert kwargs["back_navigation"] is False
        return None

    monkeypatch.setattr(
        "memcommit.commands.diff_browser.choose_history",
        choose,
    )

    result = invoke("revert")

    assert result.exit_code == 0, result.output
    assert store.current_context_name() == "task-1/participant"
    assert len(store.load_direct("task-1/result").memories) == 1


def test_revert_tui_keep_choice_preserves_newer_checkpoint_files(
    isolated_store,
    monkeypatch,
):
    invoke("init", "notes")
    invoke("add", "first")
    invoke("add", "second")
    store = MemoryStore()
    before = store.list_checkpoints("notes")
    target_uid = before[-1]["uid"]

    monkeypatch.setattr(
        "memcommit.commands.revert._interactive_terminal",
        lambda: True,
    )
    monkeypatch.setattr(
        "memcommit.commands.diff_browser.choose_history",
        lambda *args, **kwargs: HistorySelectionReceipt(
            context_name="notes",
            checkpoint_uid=target_uid,
            keep_history=True,
        ),
    )

    result = invoke("revert")

    assert result.exit_code == 0, result.output
    after_uids = {entry["uid"] for entry in store.list_checkpoints("notes")}
    assert {entry["uid"] for entry in before} <= after_uids


def test_natural_language_revert_searches_then_requires_picker_enter(
    isolated_store,
    monkeypatch,
):
    invoke("init", "notes")
    invoke("add", "remove me")
    store = MemoryStore()
    init_uid = store.list_checkpoints("notes")[-1]["uid"]
    provider = EarliestCheckpointProvider()
    monkeypatch.setattr(
        "memcommit.commands.revert._interactive_terminal",
        lambda: True,
    )
    monkeypatch.setattr(
        "memcommit.commands.revert.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    def choose(entries, *, context_name, mode, **kwargs):
        assert [entry.uid for entry in entries] == [init_uid]
        assert kwargs["keep_history"] is False
        return HistorySelectionReceipt(
            context_name=context_name,
            checkpoint_uid=entries[0].uid,
        )

    monkeypatch.setattr(
        "memcommit.commands.revert.choose_history",
        choose,
    )

    result = invoke("revert", "the first saved version")

    assert result.exit_code == 0
    assert provider.called is True
    assert not store.load_current().memories


def test_explicit_uid_bypasses_provider_and_picker(
    isolated_store,
    monkeypatch,
):
    invoke("init", "notes")
    store = MemoryStore()
    uid = store.list_checkpoints("notes")[0]["uid"]
    monkeypatch.setattr(
        "memcommit.commands.revert.connect_codex_chatgpt_provider",
        lambda: (_ for _ in ()).throw(
            AssertionError("exact UID must not connect a provider")
        ),
    )
    monkeypatch.setattr(
        "memcommit.commands.revert.choose_history",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("exact UID must not open a picker")
        ),
    )

    result = invoke("revert", uid[:8])

    assert result.exit_code == 0


def test_exact_revert_resolves_an_explicit_relative_context_once(
    isolated_store,
):
    invoke("init", "task/source")
    invoke("init", "task/target")
    invoke("add", "remove me")
    store = MemoryStore()
    target_uid = store.list_checkpoints("task/target")[-1]["uid"]
    store.set_current("task/source")

    result = invoke(
        "revert",
        target_uid[:8],
        "--context",
        "../target",
    )

    assert result.exit_code == 0, result.output
    assert store.current_context_name() == "task/source"
    assert not store.load_direct("task/target").memories


def test_missing_hex_uid_never_falls_back_to_semantic_search(
    isolated_store,
    monkeypatch,
):
    invoke("init", "notes")
    monkeypatch.setattr(
        "memcommit.commands.revert.connect_codex_chatgpt_provider",
        lambda: (_ for _ in ()).throw(
            AssertionError("UID typo must not become a semantic query")
        ),
    )

    result = invoke("revert", "deadbeef")

    assert result.exit_code == 1
    assert "no checkpoint with uid prefix" in result.output


def test_natural_language_revert_outside_tty_does_not_call_provider_or_write(
    isolated_store,
    monkeypatch,
):
    invoke("init", "notes")
    invoke("add", "keep current")
    before = MemoryStore().load_current().to_dict()
    monkeypatch.setattr(
        "memcommit.commands.revert.connect_codex_chatgpt_provider",
        lambda: (_ for _ in ()).throw(
            AssertionError("non-TTY selection must stay read-only")
        ),
    )

    result = invoke("revert", "before the note was added")

    assert result.exit_code == 1
    assert "requires an interactive terminal" in result.output
    assert MemoryStore().load_current().to_dict() == before


def test_picker_frame_change_aborts_before_revert(
    isolated_store,
    monkeypatch,
):
    invoke("init", "notes")
    invoke("add", "reviewed")
    store = MemoryStore()
    init_uid = store.list_checkpoints("notes")[-1]["uid"]
    monkeypatch.setattr(
        "memcommit.commands.revert._interactive_terminal",
        lambda: True,
    )

    def choose(entries, *, context_name, mode, **kwargs):
        changed = store.load(context_name)
        changed.add("concurrent")
        store.save(changed)
        return HistorySelectionReceipt(
            context_name=context_name,
            checkpoint_uid=init_uid,
        )

    monkeypatch.setattr(
        "memcommit.commands.diff_browser.choose_history",
        choose,
    )

    result = invoke("revert")

    assert result.exit_code == 1
    assert "changed before the reviewed revert" in result.output
    assert len(store.load_current().memories) == 2


def test_semantic_revert_race_at_locked_apply_preserves_concurrent_state(
    isolated_store,
    monkeypatch,
):
    invoke("init", "notes")
    invoke("add", "reviewed")
    store = MemoryStore()
    init_uid = store.list_checkpoints("notes")[-1]["uid"]
    provider = EarliestCheckpointProvider()
    monkeypatch.setattr(
        "memcommit.commands.revert._interactive_terminal",
        lambda: True,
    )
    monkeypatch.setattr(
        "memcommit.commands.revert.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    monkeypatch.setattr(
        "memcommit.commands.revert.choose_history",
        lambda entries, **kwargs: HistorySelectionReceipt(
            context_name="notes",
            checkpoint_uid=init_uid,
        ),
    )
    original_revert = MemoryStore.revert
    state_after_race = {}

    def race_before_locked_revert(
        self,
        context_name,
        uid_prefix,
        keep_history=False,
        **expectations,
    ):
        concurrent = self.load_direct(context_name)
        concurrent.add("concurrent")
        self.save(concurrent)
        state_after_race["context"] = self.load_direct(context_name).to_dict()
        state_after_race["history"] = self.list_checkpoints(context_name)
        return original_revert(
            self,
            context_name,
            uid_prefix,
            keep_history=keep_history,
            **expectations,
        )

    monkeypatch.setattr(MemoryStore, "revert", race_before_locked_revert)

    result = invoke("revert", "the first saved version")

    assert result.exit_code == 1
    assert provider.called is True
    assert "changed before the reviewed revert" in result.output
    assert store.load_direct("notes").to_dict() == state_after_race["context"]
    assert store.list_checkpoints("notes") == state_after_race["history"]


def test_cancelled_picker_does_not_resolve_memory_ref_targets(
    isolated_store,
    monkeypatch,
):
    invoke("init", "source")
    invoke("add", "SECRET TARGET")
    store = MemoryStore()
    target_uid = next(iter(store.load_current().memories))
    invoke("init", "notes")
    reference = invoke("reference", target_uid, "--from", "source")
    assert reference.exit_code == 0

    def forbidden(*args, **kwargs):
        raise AssertionError("picker review resolved a MemoryRef target")

    monkeypatch.setattr(MemoryStore, "_load_direct_memory", forbidden)
    monkeypatch.setattr(
        "memcommit.commands.revert._interactive_terminal",
        lambda: True,
    )
    monkeypatch.setattr(
        "memcommit.commands.diff_browser.choose_history",
        lambda *args, **kwargs: None,
    )

    result = invoke("revert")

    assert result.exit_code == 0
    assert "cancelled" in result.output
