"""Safety contracts for ordinary Context catalog completeness."""

from __future__ import annotations

import json

import pytest

import memcommit.ops as ops
from memcommit.store import MemoryStore


def test_context_storage_root_symlink_fails_closed_for_all_record_paths(
    isolated_store,
):
    store = MemoryStore()
    contexts_root = isolated_store / "contexts"
    contexts_root.rmdir()
    outside_root = isolated_store.parent / "outside-contexts"
    outside_context = outside_root / "external"
    outside_context.mkdir(parents=True)
    outside_file = outside_context / "context.json"
    outside_file.write_text(
        json.dumps(ops.init("external").to_dict()),
        encoding="utf-8",
    )
    contexts_root.symlink_to(outside_root, target_is_directory=True)

    with pytest.raises(ValueError, match="storage root.*symbolic link"):
        store.context_exists("external")
    with pytest.raises(ValueError, match="storage root.*symbolic link"):
        store.list_context_names()
    with pytest.raises(ValueError, match="storage root.*symbolic link"):
        store.load("external")
    with pytest.raises(ValueError, match="storage root.*symbolic link"):
        store.save(ops.init("new"))
    with pytest.raises(ValueError, match="storage root.*symbolic link"):
        store.delete("external")

    assert outside_file.is_file()


def test_tolerant_context_catalog_preserves_typed_omission_diagnostics(
    isolated_store,
):
    store = MemoryStore()
    store.save(ops.init("valid"))
    malformed = isolated_store / "contexts" / "malformed" / "context.json"
    malformed.parent.mkdir()
    malformed.write_text("{not-json", encoding="utf-8")
    outside = isolated_store.parent / "linked-contexts"
    outside.mkdir()
    (isolated_store / "contexts" / "linked").symlink_to(
        outside,
        target_is_directory=True,
    )

    catalog = store.scan_context_catalog()

    assert catalog.names == ("valid",)
    assert not catalog.complete
    assert {
        (diagnostic.code, diagnostic.relative_path)
        for diagnostic in catalog.diagnostics
    } == {
        ("INVALID_JSON", "malformed/context.json"),
        ("UNSAFE_ENTRY", "linked"),
    }
    assert store.list_context_names() == ["valid"]


def test_strict_direct_context_graph_rejects_any_catalog_omission(
    isolated_store,
):
    store = MemoryStore()
    store.save(ops.init("valid"))
    malformed = isolated_store / "contexts" / "malformed" / "context.json"
    malformed.parent.mkdir()
    malformed.write_text("{not-json", encoding="utf-8")

    with pytest.raises(ValueError, match="malformed.*invalid JSON"):
        store.load_direct_context_graph_strict()
