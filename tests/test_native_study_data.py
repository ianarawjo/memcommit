"""Migration parity and real shared-import coverage for Study JSON data."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import shutil

import pytest

from memcommit.application.operations.resource_import.documents import publication
from memcommit.study_scenarios.legacy.fixtures import (
    default_fixture_root,
    load_study_fixture_corpus,
)
from memcommit.study_scenarios.legacy.bundle import build_all_study_bundles
from memcommit.study_scenarios.coffee.scenario import build_coffee_scenario

ROOT = Path(__file__).parents[1]
BASELINE = json.loads(
    (
        ROOT
        / "agent-records/outputs/native-json-import-20260906/baseline-equivalence.json"
    ).read_text()
)
FIELDS = (
    "dataset",
    "language",
    "fixture_id",
    "locator",
    "canonical_locator",
    "content",
    "purpose",
    "audiences",
    "verified",
)


def _digest(value):
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


@pytest.mark.parametrize("language", ["en", "ko"])
def test_native_corpus_keeps_every_original_body_identity_and_review_annotation(
    language,
):
    corpus = load_study_fixture_corpus(language=language)
    for dataset in corpus.datasets:
        rows = []
        for memory in dataset.records:
            row = asdict(memory)
            row["audiences"] = [role.value for role in memory.audiences]
            rows.append({key: row[key] for key in FIELDS})
            assert memory.source_path.suffix == ".json"
            assert memory.memory_uid
            assert (default_fixture_root() / memory.source_location).is_file()
        expected = BASELINE["legacy_corpus"][language][dataset.spec.name]
        assert len(rows) == expected["count"]
        assert _digest(rows) == expected["sha256"]


def test_legacy_native_install_keeps_all_context_records_and_uses_import(
    tmp_path, monkeypatch
):
    calls = []
    original = publication.import_context_records

    def tracked(destination, entries, **kwargs):
        calls.append(destination.store_dir)
        return original(destination, entries, **kwargs)

    monkeypatch.setattr(publication, "import_context_records", tracked)
    manifests = build_all_study_bundles(tmp_path / "bundles")
    assert len(calls) == 6
    for manifest in manifests:
        for profile in json.loads(manifest.read_text())["profiles"]:
            source = manifest.parent / profile["store_path"] / "contexts"
            records = {
                p.relative_to(source).as_posix(): json.loads(p.read_bytes())
                for p in sorted(source.rglob("context.json"))
            }
            expected = BASELINE["legacy_profiles"][profile["profile_name"]]
            assert len(records) == expected["count"]
            assert _digest(records) == expected["sha256"]


def test_coffee_keeps_all_contexts_catalogs_and_fingerprint():
    scenario = build_coffee_scenario()
    tasks = [
        {
            "task": task.task,
            "participant": [c.to_dict() for c in task.participant_contexts],
            "authority": [c.to_dict() for c in task.authority_contexts],
            "participant_catalogs": [asdict(c) for c in task.participant_catalogs],
            "authority_catalogs": [asdict(c) for c in task.authority_catalogs],
        }
        for task in scenario.tasks
    ]
    assert scenario.digest == BASELINE["coffee"]["digest"]
    assert _digest(tasks) == BASELINE["coffee"]["sha256"]


def test_legacy_practice_keeps_original_contexts_and_memory_order():
    from memcommit.study_scenarios.legacy.practice import load_practice_contexts

    assert (
        _digest([c.to_dict() for c in load_practice_contexts()])
        == BASELINE["legacy_practice_sha256"]
    )


@pytest.mark.parametrize("scenario_name", ["coffee", "legacy"])
def test_init_study_prepares_native_sources_through_common_import(
    tmp_path, monkeypatch, scenario_name
):
    from memcommit.application.operations.init_study.profile.composition import (
        _coffee_study_packages,
        _legacy_study_packages,
    )

    calls = []
    original = publication.import_context_records

    def tracked(destination, entries, **kwargs):
        calls.append(destination.store_dir)
        return original(destination, entries, **kwargs)

    monkeypatch.setattr(publication, "import_context_records", tracked)
    result = (
        _coffee_study_packages if scenario_name == "coffee" else _legacy_study_packages
    )(tmp_path / scenario_name)
    packages = result[0] if isinstance(result, tuple) else result
    assert len(packages) == 3
    assert len(calls) >= 6
    for package in packages.values():
        for profile in package.profiles:
            assert not tuple(profile.store.rglob("checkpoints/*.json"))


def test_native_authoring_accepts_json_whitespace_and_rejects_translation_uid_drift(
    tmp_path,
):
    from memcommit.study_scenarios.legacy.fixtures import (
        load_study_fixture,
        StudyFixtureError,
    )

    root = tmp_path / "data"
    shutil.copytree(default_fixture_root(), root)
    expected = load_study_fixture("task1-campus-wiki", language="ko", root=root)
    path = expected.records[0].source_path
    record = json.loads(path.read_text())
    path.write_text(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
    actual = load_study_fixture("task1-campus-wiki", language="ko", root=root)
    assert [m.content for m in actual.records] == [m.content for m in expected.records]
    record["uid"] = "changed-context-identity"
    path.write_text(json.dumps(record))
    with pytest.raises(StudyFixtureError, match="identity or item order drifted"):
        load_study_fixture("task1-campus-wiki", language="ko", root=root)


def test_packaged_native_context_order_is_covered_by_manifest_digest(tmp_path):
    from memcommit.application.operations.init_study.profile.package import (
        _study_packages,
    )
    from memcommit.application.operations.profile.model._storage import ProfileError

    root = tmp_path / "bundles"
    build_all_study_bundles(root)
    path = (
        root
        / "task-1/profiles/task-1-campus-authority/.mem/contexts/campus-wiki/building-access/context.json"
    )
    record = json.loads(path.read_text())
    record["order"].reverse()
    path.write_text(json.dumps(record))
    with pytest.raises(ProfileError, match="native Context records changed"):
        _study_packages(root)
