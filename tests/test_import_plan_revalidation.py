"""Import previews must still identify the bytes and target approved."""

from __future__ import annotations

import pytest

from memcommit.core.context import Memory
from memcommit.application.operations.profile.config import load_profile_registry, profile_store_dir
from memcommit.application.operations.profile.model import ProfileError
from memcommit.application.operations.resource_import.model import (
    import_context_from_profile,
    import_memory_from_profile,
    import_profile_from_profile,
    plan_context_import,
    plan_memory_import,
)
from memcommit.persistence.store import MemoryStore
from tests.test_resource_import import _prepare_profiles


def test_context_import_revalidates_source_snapshot_after_review(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, _identities = _prepare_profiles(isolated_store, tmp_path, monkeypatch)
    plan = plan_context_import(
        "source-profile",
        "source/root",
        target_name="reviewed/root",
        recursive=True,
    )
    source_profile = load_profile_registry().by_name("source-profile")
    assert source_profile is not None
    source_store = MemoryStore(root=profile_store_dir(source_profile), create=False)
    child = source_store.load_direct("source/root/child")
    memory = next(item for item in child.iter_items() if isinstance(item, Memory))
    memory.content = "Changed after the import preview."
    source_store.save(child)

    with pytest.raises(ProfileError, match="changed after review"):
        import_context_from_profile(
            "source-profile",
            "source/root",
            target_name="reviewed/root",
            recursive=True,
            expected_plan=plan,
        )

    assert not active.context_exists("reviewed/root")


def test_memory_import_revalidates_destination_snapshot_after_review(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, identities = _prepare_profiles(isolated_store, tmp_path, monkeypatch)
    plan = plan_memory_import(
        "source-profile",
        "source/root/child",
        identities["child_memory_uid"],
        target_context_locator="destination",
    )
    destination = active.load_for_update("destination")
    destination.add(
        Memory(
            uid="50000000-0000-4000-8000-000000000001",
            content="Concurrent destination change.",
        )
    )
    active.save(destination)

    with pytest.raises(ProfileError, match="changed after review"):
        import_memory_from_profile(
            "source-profile",
            "source/root/child",
            identities["child_memory_uid"],
            target_context_locator="destination",
            expected_plan=plan,
        )

    actual = active.load_direct("destination")
    assert identities["child_memory_uid"] not in actual.memories


def test_profile_import_revalidates_selected_source_identity(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _prepare_profiles(isolated_store, tmp_path, monkeypatch)

    with pytest.raises(ProfileError, match="identity changed after import review"):
        import_profile_from_profile(
            "copy",
            "source-profile",
            expected_source_profile_uid="not-the-reviewed-uid",
        )
