"""Regression coverage for current-only ``mem search`` routing."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from memcommit.adapters.console.entrypoint import app
from memcommit.adapters.console.commands.search.command import _run_search_request
from memcommit.adapters.console.commands.search.search_workbench import SearchRequest
from memcommit.application.capabilities.authority.access import resolve_context_access
from memcommit.core.context_targeting.readable_catalog import (
    freeze_readable_context_catalog,
)
from memcommit.persistence.store import MemoryStore


runner = CliRunner()


def invoke(*args: str):
    return runner.invoke(app, list(args))


class CurrentNoticeProvider:
    def __init__(self):
        self.queries: list[str] = []
        self.candidate_contents: list[list[str]] = []

    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "search"
        assert output_schema is not None
        payload = json.loads(prompt.split("SEARCH PAYLOAD:\n", 1)[1])
        self.queries.append(payload["query"])
        contents = [candidate.get("content", "") for candidate in payload["candidates"]]
        self.candidate_contents.append(contents)
        matching = next(
            candidate["candidate_id"]
            for candidate in payload["candidates"]
            if "Lot B" in candidate.get("content", "")
        )
        return json.dumps(
            {
                "matches": [{"candidate_id": matching}],
                "related_query": "",
                "related_matches": [],
            }
        )


def _edited_fixture() -> None:
    assert invoke("init", "transport").exit_code == 0
    assert invoke("add", "Parking is in Lot A.").exit_code == 0
    store = MemoryStore()
    uid = next(iter(store.load_current().memories))
    assert invoke("edit", uid[:8], "Parking is in Lot B.").exit_code == 0


@pytest.mark.parametrize(
    "query",
    [
        "changes during construction",
        "the last updated Memory",
        "Memories updated after the shuttle was removed",
        "공사 기간 동안 바뀐 메모리",
    ],
)
def test_time_language_searches_only_current_memories(
    isolated_store,
    monkeypatch,
    query,
):
    _edited_fixture()
    provider = CurrentNoticeProvider()
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.search.command.connect_search_provider",
        lambda: provider,
    )

    result = invoke("search", query)

    assert result.exit_code == 0, result.output
    assert "Parking is in Lot B." in result.output
    assert "memory_transition" not in result.output
    assert "event boundary" not in result.output
    assert provider.queries == [query]


def test_application_request_with_time_language_has_current_mode(
    isolated_store,
    monkeypatch,
):
    _edited_fixture()
    store = MemoryStore()
    current = store.current_context_name()
    assert current == "transport"
    access = resolve_context_access(
        store,
        current,
        current_name=current,
        required_permission="READ",
    )
    catalog = freeze_readable_context_catalog(store, access)
    provider = CurrentNoticeProvider()
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.search.command.connect_search_provider",
        lambda: provider,
    )
    request = SearchRequest(
        "the last updated Memory",
        (current,),
        include_descendants=False,
        follow_embeds=False,
    )

    response = _run_search_request(store, catalog, request)

    assert response.mode == "CURRENT"
    assert len(response.results) == 1
    assert response.results[0].kind == "memory"
    assert response.results[0].content == "Parking is in Lot B."
