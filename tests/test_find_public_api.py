"""Public Python projection of deterministic Find."""

from __future__ import annotations

import pytest

import memcommit.application.capabilities.ops as ops
from memcommit.adapters.python_api import FindInputError, FindResult, MemCommitClient
from memcommit.persistence.store import MemoryStore


def _store(root):
    store = MemoryStore(root=root)
    context = ops.init("public/find")
    memory = ops.add(context, "Cafe closes at five; cafe opens at eight.")
    store.save(context)
    store.set_current(context.name)
    return store, memory


def test_client_find_is_provider_free_and_returns_exact_spans(tmp_path):
    root = tmp_path / "store"
    store, memory = _store(root)
    checkpoints = store.list_checkpoints("public/find")

    def provider():
        raise AssertionError("Deterministic Find must not connect a provider.")

    result = MemCommitClient(
        root=root,
        semantic_provider_factory=provider,
    ).find("cafe", ignore_case=True)

    assert isinstance(result, FindResult)
    assert result.mode == "LITERAL"
    assert result.occurrence_count == 2
    assert result.matches[0].item_uid == memory.uid
    assert [span.text for span in result.matches[0].spans] == ["Cafe", "cafe"]
    assert store.list_checkpoints("public/find") == checkpoints


def test_client_find_supports_explicit_consuming_regex(tmp_path):
    root = tmp_path / "store"
    _store(root)

    result = MemCommitClient(root=root).find(r"cafe\b", regex=True)

    assert result.mode == "REGEX"
    assert [span.text for span in result.matches[0].spans] == ["cafe"]


def test_client_find_rejects_zero_width_regex(tmp_path):
    root = tmp_path / "store"
    _store(root)

    with pytest.raises(FindInputError, match="consume"):
        MemCommitClient(root=root).find(r"^", regex=True)
