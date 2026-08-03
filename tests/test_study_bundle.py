"""End-to-end contracts for swappable Task 1--3 fixture stores."""

from __future__ import annotations

import hashlib
import json

import pytest

import memcommit.eval.study_bundle as bundle_module
import memcommit.store as store_module
from memcommit.context import Memory
from memcommit.eval.study_bundle import (
    StudyBundleError,
    _isolated_store_root,
    build_all_study_bundles,
    build_study_bundle,
)
from memcommit.store import MemoryStore
from memcommit.translation_view_store import load_translation_catalog


EXPECTED_PROFILES = {
    1: {
        "task-1": (
            "TASK",
            75,
            7,
            "participant/construction-updates",
        ),
        "task-1-campus-authority": (
            "AUTHORITY",
            378,
            14,
            "campus-wiki",
        ),
    },
    2: {
        "task-2": (
            "TASK",
            0,
            1,
            "participant/proposal-workspace",
        ),
        "task-2-proposal-authority": (
            "AUTHORITY",
            375,
            45,
            "advisor1",
        ),
    },
    3: {
        "task-3": ("TASK", 300, 31, "personal-memory"),
        "task-3-healthcare-authority": (
            "AUTHORITY",
            150,
            18,
            "guardrails",
        ),
    },
}

EXPECTED_QUERY_VIEW_COUNTS = {1: 78, 2: 75, 3: 75}


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _stored_context_names(manifest_path, profile: dict[str, object]) -> set[str]:
    store_path = profile["store_path"]
    assert isinstance(store_path, str)
    with _isolated_store_root(manifest_path.parent / store_path):
        return set(MemoryStore(create=False).list_context_names())


def _assert_profile_ownership(task, profile_records, manifest_path):
    entries_by_dataset = {
        dataset: {
            entry["owner_profile"]
            for profile in profile_records.values()
            for entry in profile["entries"]
            if entry["dataset"] == dataset
        }
        for dataset in {
            entry["dataset"]
            for profile in profile_records.values()
            for entry in profile["entries"]
        }
    }
    if task == 1:
        assert entries_by_dataset == {
            "task1-construction-updates": {"task-1"},
            "task1-campus-wiki": {"task-1-campus-authority"},
            "task1-campus-wiki-details": {"task-1-campus-authority"},
        }
        task_contexts = _stored_context_names(
            manifest_path,
            profile_records["task-1"],
        )
        authority_contexts = _stored_context_names(
            manifest_path,
            profile_records["task-1-campus-authority"],
        )
        assert "campus-wiki" not in task_contexts
        assert "campus-wiki" in authority_contexts
        assert "campus-wiki/construction-details" in authority_contexts
    elif task == 2:
        assert entries_by_dataset == {
            "task2-advisor1": {"task-2-proposal-authority"},
            "task2-advisor2": {"task-2-proposal-authority"},
            "task2-proposal-guidelines": {"task-2-proposal-authority"},
        }
        assert _stored_context_names(
            manifest_path,
            profile_records["task-2"],
        ) == {"participant/proposal-workspace"}
    else:
        assert entries_by_dataset == {
            "task3-personal-memory": {"task-3"},
            "task3-guardrails": {"task-3-healthcare-authority"},
            "task3-healthcare-info-request": {"task-3-healthcare-authority"},
        }
        task_contexts = _stored_context_names(
            manifest_path,
            profile_records["task-3"],
        )
        authority_contexts = _stored_context_names(
            manifest_path,
            profile_records["task-3-healthcare-authority"],
        )
        assert "guardrails" not in task_contexts
        assert "guardrails" in authority_contexts
        assert "government/healthcare-agent/information-request" in authority_contexts


def _assert_grant_templates(task, manifest, context_uids):
    grants = {grant["key"]: grant for grant in manifest["grant_templates"]}
    expected_keys = {
        1: {
            "task-1-campus-wiki-view",
            "task-1-construction-details-query",
        },
        2: {
            "task-2-advisor1-view",
            "task-2-advisor2-view",
            "task-2-proposal-guidelines-query",
        },
        3: {
            "task-3-guardrails-view",
            "task-3-healthcare-information-query",
        },
    }[task]
    assert set(grants) == expected_keys
    for grant in grants.values():
        authority_key = (
            grant["authority_profile"],
            grant["authority_context"]["name"],
        )
        assert grant["authority_context"]["uid"] == context_uids[authority_key]
        assert grant["recursive"] is True
        attachment = grant["attachment"]
        if attachment["kind"] == "GRANTEE_CONTEXT":
            grantee_key = (
                grant["grantee_profile"],
                attachment["context"]["name"],
            )
            assert attachment["context"]["uid"] == context_uids[grantee_key]
        else:
            assert attachment["kind"] == "GRANT_VIEW"
            parent = grants[attachment["grant_key"]]
            assert attachment["grant_uid"] == parent["grant_uid"]

    if task == 1:
        campus = grants["task-1-campus-wiki-view"]
        details = grants["task-1-construction-details-query"]
        assert campus["permissions"] == ["READ", "CREATE", "UPDATE"]
        assert campus["public_name"] == "campus-wiki"
        assert campus["attachment"]["context"]["name"] == (
            "participant/construction-updates"
        )
        assert campus["excluded_contexts"] == [
            {
                "uid": context_uids[
                    (
                        "task-1-campus-authority",
                        "campus-wiki/construction-details",
                    )
                ],
                "name": "campus-wiki/construction-details",
            }
        ]
        assert details["permissions"] == ["QUERY", "SESSION_LOG"]
        assert details["provider"] == "codex_chatgpt"
        assert details["attachment"]["grant_key"] == campus["key"]
    elif task == 2:
        assert grants["task-2-advisor1-view"]["permissions"] == ["READ"]
        assert grants["task-2-advisor2-view"]["permissions"] == ["READ"]
        guidelines = grants["task-2-proposal-guidelines-query"]
        assert guidelines["permissions"] == ["QUERY", "SESSION_LOG"]
        assert guidelines["provider"] == "codex_chatgpt"
        assert {
            grant["attachment"]["context"]["name"] for grant in grants.values()
        } == {"participant/proposal-workspace"}
    else:
        assert grants["task-3-guardrails-view"]["permissions"] == ["READ"]
        healthcare = grants["task-3-healthcare-information-query"]
        assert healthcare["permissions"] == ["QUERY", "SESSION_LOG"]
        assert healthcare["provider"] == "codex_chatgpt"
        assert {
            grant["attachment"]["context"]["name"] for grant in grants.values()
        } == {"personal-memory"}


def test_builds_task_and_authority_profiles_with_grant_templates(
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
    assert "participant task profile and its switchable" in readme
    assert "Do not merge or copy" in readme
    assert "Audience annotations remain review" in readme
    for task, manifest_path in enumerate(manifests, start=1):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected_profiles = EXPECTED_PROFILES[task]
        expected_total = sum(values[1] for values in expected_profiles.values())
        assert manifest["schema_version"] == 2
        assert manifest["ordinary_count"] == expected_total
        assert manifest["query_only_count"] == 0
        assert manifest["query_view_count"] == EXPECTED_QUERY_VIEW_COUNTS[task]
        assert manifest["canonical_language"] == "en"
        assert manifest["translation_languages"] == ["ko"]
        entries = manifest["entries"]
        assert len(entries) == expected_total
        assert len({entry["memory_uid"] for entry in entries}) == len(entries)
        assert all(entry["query_only"] is False for entry in entries)
        assert all(isinstance(entry["runtime_context"], str) for entry in entries)

        profile_records = {
            profile["profile_name"]: profile for profile in manifest["profiles"]
        }
        assert set(profile_records) == set(expected_profiles)
        context_uids: dict[tuple[str, str], str] = {}
        for profile_name, expected in expected_profiles.items():
            role, memory_count, context_count, current_context = expected
            profile = profile_records[profile_name]
            assert profile["role"] == role
            assert profile["ordinary_count"] == memory_count
            assert profile["context_count"] == context_count
            assert profile["current_context"] == current_context
            assert profile["store_path"] == (f"profiles/{profile_name}/.mem")
            profile_entries = profile["entries"]
            assert len(profile_entries) == memory_count
            assert all(
                entry["owner_profile"] == profile_name for entry in profile_entries
            )
            assert profile_entries == [
                entry for entry in entries if entry["owner_profile"] == profile_name
            ]

            store_root = manifest_path.parent / profile["store_path"]
            with _isolated_store_root(store_root):
                store = MemoryStore(create=False)
                assert store.current_context_name() == current_context
                context_names = set(store.list_context_names())
                assert len(context_names) == context_count
                for context_name in context_names:
                    context_uids[(profile_name, context_name)] = store.load_direct(
                        context_name
                    ).uid
                assert not (store_root / "query-sources").exists()

            by_owner: dict[str, list[dict[str, object]]] = {}
            for entry in profile_entries:
                owner_name = entry["runtime_context"]
                assert isinstance(owner_name, str)
                by_owner.setdefault(owner_name, []).append(entry)
            for owner_name, owner_entries in by_owner.items():
                with _isolated_store_root(store_root):
                    store = MemoryStore(create=False)
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
                        assert (
                            _digest(translation.curated.translated_content)
                            == entry["korean_sha256"]
                        )
                        assert translation.curated.review_status == "UNREVIEWED"
            assert not tuple(store_root.rglob("*.lock"))

        _assert_profile_ownership(task, profile_records, manifest_path)
        _assert_grant_templates(task, manifest, context_uids)


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
