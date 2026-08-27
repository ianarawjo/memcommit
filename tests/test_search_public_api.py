"""Public Python projection of provider-backed semantic Search."""

from __future__ import annotations

import json

import pytest

import memcommit.application.ops as ops
from memcommit.adapters.python_api import MemCommitClient, SearchResult, SemanticInputError
from memcommit.store import MemoryStore


class _Provider:
    def __init__(self):
        self.operations: list[str] = []

    def complete(self, prompt, *, operation, output_schema=None):
        self.operations.append(operation)
        assert output_schema is not None
        payload = json.loads(prompt.split("FIND PAYLOAD:\n", 1)[1])
        match = next(
            item
            for item in payload["candidates"]
            if "healthcare" in item.get("content", "").casefold()
        )
        return json.dumps(
            {
                "matches": [{"candidate_id": match["candidate_id"]}],
                "related_query": "",
                "related_matches": [],
            }
        )


def _store(root):
    store = MemoryStore(root=root)
    context = ops.init("public/search")
    memory = ops.add(context, "Healthcare enrollment opens in September.")
    ops.add(context, "Parking closes overnight.")
    store.save(context)
    store.set_current(context.name)
    return store, memory


def test_client_searches_through_one_typed_provider_boundary(tmp_path):
    root = tmp_path / "store"
    store, memory = _store(root)
    provider = _Provider()
    checkpoints = store.list_checkpoints("public/search")
    client = MemCommitClient(
        root=root,
        semantic_provider_factory=lambda: provider,
    )

    result = client.search("health coverage")

    assert isinstance(result, SearchResult)
    assert result.context_names == ("public/search",)
    assert result.mode == "CURRENT"
    assert [(item.uid, item.content) for item in result.items] == [
        (memory.uid, memory.content)
    ]
    assert provider.operations == ["search"]
    assert store.list_checkpoints("public/search") == checkpoints


def test_client_search_rejects_invalid_input_before_provider(tmp_path):
    root = tmp_path / "store"
    _store(root)

    def provider():
        raise AssertionError("Invalid Search must not connect a provider.")

    client = MemCommitClient(root=root, semantic_provider_factory=provider)

    with pytest.raises(SemanticInputError, match="nonblank"):
        client.search("  ")


def test_explicit_root_search_does_not_inherit_profile_grants(tmp_path, monkeypatch):
    root = tmp_path / "store"
    _store(root)
    provider = _Provider()

    def forbidden():
        raise AssertionError("Explicit-root Search consulted global Profiles")

    monkeypatch.setattr(
        "memcommit.adapters.python_api._support.readable.load_profile_registry",
        forbidden,
    )

    result = MemCommitClient(
        root=root,
        semantic_provider_factory=lambda: provider,
    ).search("health coverage")

    assert result.items
