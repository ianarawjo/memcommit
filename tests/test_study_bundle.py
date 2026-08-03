"""End-to-end contracts for swappable Task 1--3 fixture stores."""

from __future__ import annotations

import hashlib
import json

import pytest

import memcommit.eval.study_bundle as bundle_module
import memcommit.store as store_module
from memcommit.context import Memory, QueryContextRef
from memcommit.eval.study_bundle import (
    TASK_SPECS,
    StudyBundleError,
    _isolated_store_root,
    build_all_study_bundles,
    build_study_bundle,
)
from memcommit.store import MemoryStore
from memcommit.translation_view_store import load_translation_catalog


EXPECTED_COUNTS = {
    1: (375, 78),
    2: (300, 75),
    3: (375, 75),
}


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_builds_three_isolated_english_stores_with_same_uid_korean_views(
    tmp_path,
):
    output = tmp_path / "study-fixtures"
    manifests = build_all_study_bundles(output)

    assert [path.parent.name for path in manifests] == [
        "task-1",
        "task-2",
        "task-3",
    ]
    readme = (output / "README.md").read_text(encoding="utf-8")
    assert "Do not merge these `.mem/` directories" in readme
    assert "audience annotations are not ACL enforcement" in readme
    for task, manifest_path in enumerate(manifests, start=1):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        ordinary_count, query_count = EXPECTED_COUNTS[task]
        assert manifest["ordinary_count"] == ordinary_count
        assert manifest["query_only_count"] == query_count
        assert manifest["canonical_language"] == "en"
        assert manifest["translation_languages"] == ["ko"]
        entries = manifest["entries"]
        assert len(entries) == ordinary_count + query_count
        assert len({entry["memory_uid"] for entry in entries}) == len(entries)

        with _isolated_store_root(manifest_path.parent / ".mem"):
            store = MemoryStore(create=False)
            assert store.current_context_name() == TASK_SPECS[task].current_context
            if task == 1:
                context_names = set(store.list_context_names())
                assert "campus-wiki" in context_names
                assert "campus-wiki/building-access" in context_names
                assert not any("campus-wiki-fork" in name for name in context_names)
                wiki = store.load_direct("campus-wiki")
                query_refs = [
                    item
                    for item in wiki.iter_items()
                    if isinstance(item, QueryContextRef)
                ]
                assert [item.name for item in query_refs] == [
                    "construction-details"
                ]
            ordinary = [entry for entry in entries if not entry["query_only"]]
            by_owner: dict[str, list[dict[str, object]]] = {}
            for entry in ordinary:
                owner_name = entry["runtime_context"]
                assert isinstance(owner_name, str)
                by_owner.setdefault(owner_name, []).append(entry)
            for owner_name, owner_entries in by_owner.items():
                owner = store.load_direct(owner_name)
                catalog = load_translation_catalog(owner.uid, "ko")
                assert catalog is not None
                for entry in owner_entries:
                    memory = owner.memories[entry["memory_uid"]]
                    assert isinstance(memory, Memory)
                    assert _digest(memory.content) == entry["english_sha256"]
                    translation = catalog.entry_for(memory.uid)
                    assert translation is not None
                    assert translation.curated is not None
                    assert translation.curated.source_sha256 == (
                        entry["english_sha256"]
                    )
                    assert _digest(translation.curated.translated_content) == (
                        entry["korean_sha256"]
                    )
                    assert translation.curated.review_status == "UNREVIEWED"

            query_entries = [entry for entry in entries if entry["query_only"]]
            query_refs = []
            for dataset in TASK_SPECS[task].datasets:
                for parent_name in dataset.query_parents:
                    parent = store.load_direct(parent_name)
                    query_refs.extend(
                        item
                        for item in parent.iter_items()
                        if isinstance(item, QueryContextRef)
                        and item.name == dataset.runtime_root
                    )
            assert query_refs
            source_uid = query_refs[0].target_source_uid
            assert all(ref.target_source_uid == source_uid for ref in query_refs)
            source_name = query_refs[0].name
            english = store.load_query_source(
                source_uid,
                expected_name=source_name,
                language="en",
            )
            korean = store.load_query_source(
                source_uid,
                expected_name=source_name,
                language="ko",
            )
            assert len(english.entries) == query_count
            assert [entry.uid for entry in english.entries] == [
                entry.uid for entry in korean.entries
            ]
            manifest_by_uid = {
                entry["memory_uid"]: entry for entry in query_entries
            }
            assert set(manifest_by_uid) == {
                entry.uid for entry in english.entries
            }
            for source_entry, english_text, korean_text in zip(
                english.entries,
                english.contents,
                korean.contents,
                strict=True,
            ):
                entry = manifest_by_uid[source_entry.uid]
                assert _digest(english_text) == entry["english_sha256"]
                assert _digest(korean_text) == entry["korean_sha256"]
        assert not tuple((manifest_path.parent / ".mem").rglob("*.lock"))


def test_bundle_builder_refuses_to_reuse_a_nonempty_destination(tmp_path):
    output = tmp_path / "study-fixtures"
    output.mkdir()
    (output / "keep.txt").write_text("owned", encoding="utf-8")

    try:
        build_all_study_bundles(output)
    except RuntimeError as error:
        assert "not empty" in str(error)
    else:
        raise AssertionError("builder overwrote a nonempty destination")

    assert (output / "keep.txt").read_text(encoding="utf-8") == "owned"


def test_bundle_builder_publishes_only_after_all_tasks_succeed_and_retries(
    tmp_path,
    monkeypatch,
):
    output = tmp_path / "study-fixtures"
    original = bundle_module._build_study_bundle_contents

    def fail_on_second_task(task, destination, *, fixture_root=None):
        if task == 2:
            raise StudyBundleError("injected Task 2 failure")
        return original(task, destination, fixture_root=fixture_root)

    monkeypatch.setattr(
        bundle_module,
        "_build_study_bundle_contents",
        fail_on_second_task,
    )
    with pytest.raises(StudyBundleError, match="injected Task 2 failure"):
        build_all_study_bundles(output)

    assert not output.exists()
    assert not tuple(tmp_path.glob(".study-fixtures.staging-*"))

    monkeypatch.setattr(
        bundle_module,
        "_build_study_bundle_contents",
        original,
    )
    manifests = build_all_study_bundles(output)
    assert len(manifests) == 3
    assert all(path.is_file() for path in manifests)
    assert not tuple(tmp_path.glob(".study-fixtures.staging-*"))


def test_bundle_builder_rejects_live_store_and_descendants(
    tmp_path,
    monkeypatch,
):
    live_store = tmp_path / "configured-live-store"
    live_store.mkdir()
    monkeypatch.setattr(store_module, "STORE_DIR", live_store)

    with pytest.raises(StudyBundleError, match="overlaps the active store"):
        build_study_bundle(1, live_store)
    with pytest.raises(StudyBundleError, match="overlaps the active store"):
        build_all_study_bundles(live_store / "exports")

    assert not (live_store / "exports").exists()
    assert not tuple(tmp_path.glob(".*.staging-*"))


def test_bundle_builder_rejects_symlink_destination_without_touching_target(
    tmp_path,
):
    target = tmp_path / "owned-target"
    target.mkdir()
    destination = tmp_path / "study-fixtures"
    destination.symlink_to(target, target_is_directory=True)

    with pytest.raises(StudyBundleError, match="must not be a symlink"):
        build_all_study_bundles(destination)

    assert destination.is_symlink()
    assert not tuple(target.iterdir())
    assert not tuple(tmp_path.glob(".study-fixtures.staging-*"))


def test_bundle_builder_accepts_an_existing_empty_destination(tmp_path):
    destination = tmp_path / "task-1"
    destination.mkdir()

    manifest = build_study_bundle(1, destination)

    assert manifest == destination / "manifest.json"
    assert manifest.is_file()
    assert not tuple(tmp_path.glob(".task-1.staging-*"))
