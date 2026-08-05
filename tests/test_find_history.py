"""CLI routing for temporal ``mem find`` queries."""
from __future__ import annotations

import json

from typer.testing import CliRunner

from memcommit.cli import app


runner = CliRunner()


def invoke(*args: str):
    return runner.invoke(app, list(args))


class LatestEditProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        payload = json.loads(
            prompt.split("HISTORY SEARCH PAYLOAD:\n", 1)[1]
        )
        assert operation == "history search"
        assert set(payload["allowed_result_kinds"]) == {
            "memory_version",
            "memory_transition",
            "checkpoint",
        }
        return json.dumps(
            {
                "understanding": "Find the latest edited Memory.",
                "result_kind": "memory_transition",
                "subject_mode": "ALL",
                "subject_ids": [],
                "event_kinds": ["EDITED"],
                "anchor_kind": "NONE",
                "anchor_ids": [],
                "anchor_occurrence": "ANY",
                "relation": "NONE",
                "reduce": "LATEST",
            }
        )


def _history_fixture():
    invoke("init", "transport")
    invoke("add", "Parking is in Lot A.")
    from memcommit.store import MemoryStore

    store = MemoryStore()
    uid = next(iter(store.load_current().memories))
    invoke("edit", uid[:8], "Parking is in Lot B.")


def test_temporal_find_prints_versioned_transition_outside_tty(
    isolated_store,
    monkeypatch,
):
    _history_fixture()
    monkeypatch.setattr(
        "memcommit.commands.find.connect_codex_chatgpt_provider",
        lambda: LatestEditProvider(),
    )

    result = invoke("find", "the last updated Memory")

    assert result.exit_code == 0
    assert "transport" in result.output
    assert "memory_transition" in result.output
    assert "Parking is in Lot B." in result.output
    assert "event boundary" in result.output
    assert "not a direct restore target" in result.output


def test_temporal_find_uses_shared_read_only_picker_in_tty(
    isolated_store,
    monkeypatch,
):
    _history_fixture()
    observed = {}
    monkeypatch.setattr(
        "memcommit.commands.find.connect_codex_chatgpt_provider",
        lambda: LatestEditProvider(),
    )
    monkeypatch.setattr(
        "memcommit.commands.find._interactive_terminal",
        lambda: True,
    )

    def choose(entries, *, context_name, mode):
        observed["entries"] = entries
        observed["context_name"] = context_name
        observed["mode"] = mode
        return None

    monkeypatch.setattr(
        "memcommit.commands.find.choose_history",
        choose,
    )

    result = invoke("find", "the latest changed Memory")

    assert result.exit_code == 0
    assert observed["context_name"] == "transport"
    assert observed["mode"] == "log"
    assert "Before: Parking is in Lot A." in observed["entries"][0].detail
    assert "After: Parking is in Lot B." in observed["entries"][0].detail
    assert "event boundary · not a direct restore target" in (
        observed["entries"][0].detail
    )


def test_non_temporal_find_keeps_the_existing_current_state_path(
    isolated_store,
    monkeypatch,
):
    invoke("init", "notes")
    observed = {}

    def current_find(
        context,
        query,
        provider_factory,
        *,
        recursive,
        limit,
        additional_roots,
    ):
        observed["query"] = query
        observed["recursive"] = recursive
        observed["limit"] = limit
        observed["additional_roots"] = additional_roots
        return []

    monkeypatch.setattr("memcommit.commands.find.ops.find", current_find)
    monkeypatch.setattr(
        "memcommit.commands.find.build_history",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("ordinary find must not enumerate history")
        ),
    )

    result = invoke("find", "parking information")

    assert result.exit_code == 0
    assert observed == {
        "query": "parking information",
        "recursive": True,
        "limit": 5,
        "additional_roots": (),
    }


def test_temporal_find_also_descends_the_visible_embedded_context_graph(
    isolated_store,
    monkeypatch,
):
    invoke("init", "transport")
    invoke("add", "Parking is in Lot A.")
    from memcommit.store import MemoryStore

    store = MemoryStore()
    uid = next(iter(store.load_current().memories))
    invoke("edit", uid[:8], "Parking is in Lot B.")
    invoke("init", "wiki")
    invoke("embed", "transport", "--into", "wiki")
    invoke("switch", "wiki")
    monkeypatch.setattr(
        "memcommit.commands.find.connect_codex_chatgpt_provider",
        lambda: LatestEditProvider(),
    )

    result = invoke("find", "the last updated Memory")

    assert result.exit_code == 0
    assert "transport" in result.output
    assert "Parking is in Lot B." in result.output


def test_temporal_find_searches_materialized_namespace_descendants_by_default(
    isolated_store,
    monkeypatch,
):
    invoke("init", "task-3")
    invoke("init", "task-3/personal-memory")
    invoke("add", "The clinic appointment is at 9 a.m.")
    from memcommit.store import MemoryStore

    store = MemoryStore()
    uid = next(iter(store.load_current().memories))
    invoke("edit", uid[:8], "The clinic appointment is at 10 a.m.")
    invoke("switch", "task-3")
    monkeypatch.setattr(
        "memcommit.commands.find.connect_codex_chatgpt_provider",
        lambda: LatestEditProvider(),
    )

    result = invoke("find", "the last updated Memory")

    assert result.exit_code == 0, result.output
    assert "task-3/personal-memory" in result.output
    assert "The clinic appointment is at 10 a.m." in result.output

    direct = invoke("find", "the last updated Memory", "--direct")

    assert direct.exit_code == 0, direct.output
    assert "task-3/personal-memory" not in direct.output
    assert "no matching historical items" in direct.output


def test_temporal_find_does_not_resolve_memory_refs_or_query_sources(
    isolated_store,
    monkeypatch,
):
    invoke("init", "source")
    invoke("add", "SECRET TARGET")
    from memcommit.store import MemoryStore

    store = MemoryStore()
    source = store.load_current()
    target_uid = next(iter(source.memories))
    invoke("init", "search-root")
    reference = invoke("reference", target_uid, "--from", "source")
    assert reference.exit_code == 0

    def forbidden(*args, **kwargs):
        raise AssertionError("temporal find opened pointer content")

    monkeypatch.setattr(MemoryStore, "_load_direct_memory", forbidden)
    monkeypatch.setattr(MemoryStore, "load_query_source", forbidden)

    class PrivacyProvider(LatestEditProvider):
        def complete(self, prompt, *, operation, output_schema=None):
            assert "SECRET TARGET" not in prompt
            return super().complete(
                prompt,
                operation=operation,
                output_schema=output_schema,
            )

    monkeypatch.setattr(
        "memcommit.commands.find.connect_codex_chatgpt_provider",
        lambda: PrivacyProvider(),
    )

    result = invoke("find", "the last updated Memory")

    assert result.exit_code == 0
    assert "SECRET TARGET" not in result.output
