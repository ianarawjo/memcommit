"""Content-free Context locator discovery for Ground startup."""
from __future__ import annotations

import builtins

import pytest

from memcommit.application import ops
from memcommit.application.operations.ground.context_catalog import (
    GroundContextLocator,
    discover_ground_context_locators,
    select_ground_context_locators,
)
from memcommit.persistence.store import MemoryStore


def test_locator_discovery_never_opens_context_records(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = ops.init("temp/task-1")
    ops.add(source, "SECRET MEMORY CONTENT THAT MUST NOT BE READ")
    store.save(source)
    store.save(ops.init("campus-wiki"))

    def forbidden_open(*_args, **_kwargs):
        raise AssertionError("Ground discovery opened a Context record")

    monkeypatch.setattr(builtins, "open", forbidden_open)

    assert discover_ground_context_locators(store) == (
        GroundContextLocator(name="campus-wiki"),
        GroundContextLocator(name="temp/task-1"),
    )


def test_locator_is_unverified_and_later_load_rejects_malformed_record(
    isolated_store,
):
    context_file = (
        isolated_store / "contexts" / "broken" / "context.json"
    )
    context_file.parent.mkdir(parents=True)
    context_file.write_text("{not-json", encoding="utf-8")
    store = MemoryStore(create=False)

    assert discover_ground_context_locators(store) == (
        GroundContextLocator(name="broken"),
    )
    with pytest.raises(ValueError):
        store.load("broken")


def test_locator_discovery_skips_symlinks_checkpoints_and_query_sources(
    isolated_store,
):
    store = MemoryStore()
    store.save(ops.init("ordinary"))
    context_root = isolated_store / "contexts"

    checkpoint_fake = context_root / "ordinary" / "checkpoints" / "context.json"
    checkpoint_fake.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_fake.write_text("{}", encoding="utf-8")

    external = isolated_store / "external-context.json"
    external.write_text("{}", encoding="utf-8")
    symlinked = context_root / "linked" / "context.json"
    symlinked.parent.mkdir(parents=True)
    symlinked.symlink_to(external)

    query_source = (
        isolated_store / "query-sources" / "private" / "context.json"
    )
    query_source.parent.mkdir(parents=True)
    query_source.write_text("{}", encoding="utf-8")

    assert discover_ground_context_locators(store) == (
        GroundContextLocator(name="ordinary"),
    )


def test_large_catalog_is_bounded_by_name_only_request_ranking():
    locators = tuple(
        GroundContextLocator(name=f"archive/context-{index:03d}")
        for index in range(70)
    ) + (
        GroundContextLocator(name="temp/task-1"),
        GroundContextLocator(name="campus-wiki"),
    )

    selected = select_ground_context_locators(
        "Review Task 1.",
        locators,
        limit=8,
    )

    assert len(selected) == 8
    assert selected[0].name == "temp/task-1"
