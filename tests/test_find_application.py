"""Application-boundary contracts for terminal-independent Search."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import uuid

import pytest

from memcommit.core.context import Context, Memory, QueryContextRef
import memcommit.application.operations.search.application as search_application
from memcommit.application.operations.search.application import (
    SearchRequest,
    FrozenSearchCurrentSource,
    run_search,
)
from memcommit.application.operations.search.runtime import execute_search
from memcommit.application.operations.search.model import SearchCandidate
from memcommit.persistence.store import MemoryStore


class _CurrentSource:
    def __init__(self, candidates=()):
        self.candidates = tuple(candidates)
        self.calls: list[tuple[str, SearchRequest]] = []

    def freeze_current(self, request):
        self.calls.append(("CURRENT", request))
        return FrozenSearchCurrentSource(self.candidates)


class _SelectingProvider:
    def __init__(self):
        self.calls = 0

    def complete(self, prompt, *, operation, output_schema=None):
        self.calls += 1
        payload = json.loads(prompt.split("SEARCH PAYLOAD:\n", 1)[1])
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


def test_run_search_returns_typed_current_result_without_terminal():
    request = SearchRequest(
        "authorized result",
        ("notes",),
        include_descendants=False,
        follow_embeds=False,
    )
    source = _CurrentSource((_candidate(),))
    provider = _SelectingProvider()
    stages = []

    response = run_search(
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


def test_run_search_freezes_empty_current_frame_before_provider_factory():
    events = []

    class Source(_CurrentSource):
        def freeze_current(self, request):
            events.append("freeze")
            return super().freeze_current(request)

    def provider_factory():
        events.append("provider")
        return object()

    response = run_search(
        SearchRequest("anything", ("empty",)),
        source_port=Source(),
        provider_factory=provider_factory,
    )

    assert events == ["freeze", "provider"]
    assert response.results == ()


@pytest.mark.parametrize(
    "query",
    [
        "changes during construction",
        "the last updated Memory",
        "공사 기간 동안 바뀐 메모리",
    ],
)
def test_run_search_treats_time_language_as_current_content(query):
    request = SearchRequest(query, ("notes",))
    source = _CurrentSource((_candidate("Current construction notice."),))
    provider = _SelectingProvider()

    response = run_search(
        request,
        source_port=source,
        provider_factory=lambda: provider,
    )

    assert source.calls == [("CURRENT", request)]
    assert provider.calls == 1
    assert response.mode == "CURRENT"
    assert response.results[0].content == "Current construction notice."


def test_execute_search_freezes_direct_scope_and_query_route(
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

    monkeypatch.setattr(search_application, "rank_candidates", rank)

    response = execute_search(
        SearchRequest(
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


def test_execute_search_with_time_language_reads_granted_current_content(
    isolated_store,
):
    store = MemoryStore()
    granted = Context(uid="granted-uid", name="granted")
    granted.add(Memory(uid="granted-memory", content="Current granted notice."))

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

    provider = _SelectingProvider()
    response = execute_search(
        SearchRequest("changes during construction", ("granted",)),
        store=store,
        catalog=Catalog(),
        provider_factory=lambda: provider,
    )

    assert provider.calls == 1
    assert response.mode == "CURRENT"
    assert response.results[0].content == "Current granted notice."


def test_search_application_has_no_command_typer_or_tui_imports():
    source = Path(search_application.__file__).read_text(encoding="utf-8")
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
        or name.startswith("memcommit.adapters.console.commands")
    )
    assert forbidden == ()
    assert (
        SearchRequest.__module__
        == "memcommit.application.operations.search.application"
    )
