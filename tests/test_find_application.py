"""Application-boundary contracts for terminal-independent Find search."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import uuid

import pytest

from memcommit.context import Context, Memory, QueryContextRef
import memcommit.operations.search.application as find_application
from memcommit.operations.search.application import (
    FindSearchRequest,
    FrozenFindCurrentSource,
    FrozenFindHistorySource,
    run_find_search,
)
from memcommit.operations.search.runtime import execute_find_search
from memcommit.history_search import HistorySearchResult
from memcommit.search import SearchCandidate
from memcommit.store import MemoryStore


class _CurrentSource:
    def __init__(self, candidates=()):
        self.candidates = tuple(candidates)
        self.calls: list[tuple[str, FindSearchRequest]] = []

    def freeze_current(self, request):
        self.calls.append(("CURRENT", request))
        return FrozenFindCurrentSource(self.candidates)

    def freeze_history(self, request):
        self.calls.append(("HISTORY", request))
        raise AssertionError("A current query must not enumerate retained history.")


class _SelectingProvider:
    def __init__(self):
        self.calls = 0

    def complete(self, prompt, *, operation, output_schema=None):
        self.calls += 1
        payload = json.loads(prompt.split("FIND PAYLOAD:\n", 1)[1])
        return json.dumps(
            {
                "matches": [{"candidate_id": payload["candidates"][0]["candidate_id"]}],
                "related_query": "",
                "related_matches": [],
            }
        )


def _candidate(content="One authorized search result."):
    memory = Memory(uid="memory-1", content=content)
    return SearchCandidate(
        candidate_id="c000001",
        kind="memory",
        context_uid="context-1",
        context_names=("notes",),
        item=memory,
        search_text=memory.content,
    )


def test_run_find_search_returns_typed_current_result_without_terminal():
    request = FindSearchRequest(
        "authorized result",
        ("notes",),
        include_descendants=False,
        follow_embeds=False,
    )
    source = _CurrentSource((_candidate(),))
    provider = _SelectingProvider()
    stages = []

    response = run_find_search(
        request,
        source_port=source,
        provider_factory=lambda: provider,
        observer=stages.append,
    )

    assert source.calls == [("CURRENT", request)]
    assert provider.calls == 1
    assert stages == ["INPUTS_FROZEN", "CONNECTING_PROVIDER", "SEARCHING"]
    assert response.request == request
    assert response.mode == "CURRENT"
    assert response.results[0].content == "One authorized search result."
    assert response.results[0].source_memory_uid == "memory-1"
    assert response.results[0].current_match is not None


def test_run_find_search_freezes_empty_current_frame_before_provider_factory():
    events = []

    class Source(_CurrentSource):
        def freeze_current(self, request):
            events.append("freeze")
            return super().freeze_current(request)

    def provider_factory():
        events.append("provider")
        return object()

    response = run_find_search(
        FindSearchRequest("anything", ("empty",)),
        source_port=Source(),
        provider_factory=provider_factory,
    )

    assert events == ["freeze", "provider"]
    assert response.results == ()


def test_run_find_search_uses_history_source_and_preserves_local_result(monkeypatch):
    request = FindSearchRequest("the last updated Memory", ("notes",))
    history_result = HistorySearchResult(
        candidate_id="t000001",
        kind="memory_transition",
        context_uid="context-1",
        context_name="notes",
        checkpoint_uid="checkpoint-1",
        timestamp="2026-08-14T12:00:00Z",
        description="The note changed.",
        selectable=False,
    )
    calls = []

    class Source:
        def freeze_current(self, _request):
            raise AssertionError("A temporal query must not open current artifacts.")

        def freeze_history(self, frozen_request):
            calls.append(("freeze", frozen_request))
            return FrozenFindHistorySource(())

    provider = object()

    def search(timelines, query, selected_provider, **kwargs):
        calls.append(("search", timelines, query, selected_provider, kwargs))
        return [history_result]

    monkeypatch.setattr(find_application, "search_history", search)

    response = run_find_search(
        request,
        source_port=Source(),
        provider_factory=lambda: provider,
    )

    assert calls[0] == ("freeze", request)
    assert calls[1][0:4] == ("search", (), request.query, provider)
    assert response.mode == "HISTORY"
    assert response.results[0].history_result is history_result
    assert "The note changed." in response.results[0].content


def test_execute_find_search_freezes_direct_scope_and_query_route(
    isolated_store,
    monkeypatch,
    capsys,
):
    store = MemoryStore()
    root = Context(uid=str(uuid.uuid4()), name="root")
    root.add(Memory(uid="root-memory", content="Root content"))
    root.add(
        QueryContextRef(
            uid="query-route",
            name="private-policy",
            target_source_uid="hidden-source",
            provider="authority-grant",
        )
    )
    child = Context(uid=str(uuid.uuid4()), name="root/child")
    child.add(Memory(uid="child-memory", content="Child content"))
    store.save(root)
    store.save(child)

    class Access:
        is_granted = False

    class Catalog:
        def list_context_names(self):
            return ["root", "root/child"]

        def context_exists(self, name):
            return store.context_exists(name)

        def load_direct(self, name):
            return store.load_direct(name)

        def load(self, name):
            return store.load(name)

        def access_for(self, _name):
            return Access()

    observed = []

    def rank(query, candidates, provider, *, limit):
        observed.append((query, tuple(item.kind for item in candidates), limit))
        return []

    monkeypatch.setattr(find_application, "rank_candidates", rank)

    response = execute_find_search(
        FindSearchRequest(
            "policy",
            ("root",),
            include_descendants=False,
            follow_embeds=False,
        ),
        store=store,
        catalog=Catalog(),
        provider_factory=object,
    )

    assert observed == [("policy", ("memory", "query_context"), 5)]
    assert response.results == ()
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_execute_temporal_find_rejects_granted_history_before_provider(
    isolated_store,
):
    store = MemoryStore()
    granted = Context(uid="granted-uid", name="granted")
    provider_calls = 0

    class Access:
        is_granted = True

    class Catalog:
        def list_context_names(self):
            return ["granted"]

        def context_exists(self, name):
            return name == "granted"

        def load_direct(self, _name):
            return granted

        def load(self, _name):
            return granted

        def load_without_attached_reads(self, _name):
            return granted

        def access_for(self, _name):
            return Access()

    def provider_factory():
        nonlocal provider_calls
        provider_calls += 1
        return object()

    with pytest.raises(RuntimeError, match="does not expose authority checkpoint"):
        execute_find_search(
            FindSearchRequest("the last updated Memory", ("granted",)),
            store=store,
            catalog=Catalog(),
            provider_factory=provider_factory,
        )

    assert provider_calls == 0


def test_find_application_has_no_command_typer_or_tui_imports():
    source = Path(find_application.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.append(node.module)

    forbidden = tuple(
        name
        for name in imported
        if name == "typer"
        or name.startswith("prompt_toolkit")
        or name.startswith("memcommit.commands")
    )
    assert forbidden == ()
    assert FindSearchRequest.__module__ == "memcommit.operations.search.application"
