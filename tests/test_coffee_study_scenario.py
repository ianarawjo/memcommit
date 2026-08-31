"""Built-in Coffee Study scenario and legacy-selection contracts."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

import memcommit.application.capabilities.ops as ops
import memcommit.application.operations.profiles.profile.model as profiles_module
from memcommit.adapters.console.entrypoint import app
from memcommit.core.context import Memory
from memcommit.application.operations.profiles.profile.config import (
    load_profile_registry,
    profile_store_dir,
    study_run_identity,
)
from memcommit.application.operations.profiles.profile.model import resolve_share_endpoint
from memcommit.persistence.store import MemoryStore
from memcommit.study_scenarios.coffee import (
    COFFEE_BASELINE_UID,
    COFFEE_DIGEST,
    build_coffee_scenario,
)
from memcommit.study_scenarios.legacy import LEGACY_BASELINE_UID, LEGACY_DIGEST


runner = CliRunner(mix_stderr=False)


def _prepare_authoring() -> None:
    store = MemoryStore()
    store.save(ops.init("authoring-notes"))
    store.set_current("authoring-notes")


def _direct_contents(store: MemoryStore, name: str) -> tuple[str, ...]:
    context = store.load_direct(name)
    return tuple(
        item.content for item in context.iter_items() if isinstance(item, Memory)
    )


def test_coffee_spec_is_stable_bilingual_and_has_24_24_8_inputs():
    scenario = build_coffee_scenario()
    rebuilt = build_coffee_scenario()

    assert scenario.scenario_id == "coffee"
    assert scenario.baseline_uid == COFFEE_BASELINE_UID
    assert scenario.digest == rebuilt.digest == COFFEE_DIGEST
    assert [
        sum(len(context.memories) for context in task.authority_contexts)
        for task in scenario.tasks
    ] == [24, 24, 8]
    assert [len(task.authority_catalogs) for task in scenario.tasks] == [3, 3, 1]

    task_one = scenario.tasks[0]
    overtime = next(
        context
        for context in task_one.authority_contexts
        if context.name.endswith("/woohooovertime")
    )
    first = next(item for item in overtime.iter_items() if isinstance(item, Memory))
    assert "Over the past month" in first.content
    catalog = next(
        item for item in task_one.authority_catalogs if item.context_uid == overtime.uid
    )
    translated = catalog.entry_for(first.uid)
    assert translated is not None and translated.curated is not None
    assert "지난 한 달 동안" in translated.curated.translated_content
    assert "이 카페" not in translated.curated.translated_content


def test_plain_init_study_builds_coffee_without_a_baseline_or_prewarm(
    isolated_store: Path,
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring()

    def reject_legacy_prewarm(*_args, **_kwargs):
        raise AssertionError("coffee must not inspect or prepare legacy prewarms")

    monkeypatch.setattr(
        "memcommit.study_scenarios.legacy.prewarm.prepare.prepare_study_prewarms",
        reject_legacy_prewarm,
    )

    result = runner.invoke(app, ["init-study", "coffee-default"])

    assert result.exit_code == 0, result.stderr or result.output
    assert "Scenario: coffee" in result.output
    assert "Baseline Profile:" not in result.output
    assert "Contexts 10 · Memories 14 · current=practice" in result.output
    assert "Granted Contexts 9 · Granted Memories 56" in result.output
    assert "no shared semantic prewarm was attached" in result.output
    assert "Checking shared Study cache compatibility" not in result.output

    registry = load_profile_registry()
    participant = registry.by_name("coffee-default")
    authority = registry.by_name("coffee-default-granted-memory")
    assert participant is not None and authority is not None
    assert registry.by_name("study-baseline") is None
    identity = study_run_identity(participant)
    authority_identity = study_run_identity(authority)
    assert identity is not None and authority_identity is not None
    assert identity.uid == authority_identity.uid
    assert identity.baseline_profile_uid == COFFEE_BASELINE_UID
    assert identity.baseline_profile_name == "coffee"
    assert identity.baseline_sha256 == COFFEE_DIGEST

    participant_root = profile_store_dir(participant)
    authority_root = profile_store_dir(authority)
    participant_store = MemoryStore(root=participant_root, create=False)
    authority_store = MemoryStore(root=authority_root, create=False)
    assert participant_store.list_context_names() == [
        "practice",
        "practice/coffee",
        "practice/coffee/chunk-atomize-summarize",
        "practice/coffee/compare-merge-meld-update",
        "practice/coffee/compare-merge-meld-update/a",
        "practice/coffee/compare-merge-meld-update/b",
        "practice/coffee/search-find-sever-forget",
        "task-1",
        "task-2",
        "task-3",
    ]
    assert participant_store.current_context_name() == "practice"
    assert _direct_contents(participant_store, "practice") == ()
    assert (
        len(
            _direct_contents(
                participant_store,
                "practice/coffee/chunk-atomize-summarize",
            )
        )
        == 1
    )
    assert (
        len(
            _direct_contents(
                participant_store,
                "practice/coffee/compare-merge-meld-update/a",
            )
        )
        == 4
    )
    assert (
        len(
            _direct_contents(
                participant_store,
                "practice/coffee/compare-merge-meld-update/b",
            )
        )
        == 4
    )
    assert (
        len(
            _direct_contents(
                participant_store,
                "practice/coffee/search-find-sever-forget",
            )
        )
        == 5
    )
    assert len(authority_store.list_context_names()) == 13
    assert (
        sum(
            len(_direct_contents(authority_store, name))
            for name in authority_store.list_context_names()
        )
        == 56
    )
    assert all(
        not any(
            (root / name).exists()
            for name in (
                "study-semantic-prewarm",
                "study-semantic-prewarm-reference.json",
            )
        )
        for root in (participant_root, authority_root)
    )

    grants = {
        grant.public_name: grant
        for grant in registry.grants
        if grant.grantee_profile_uid == participant.uid
    }
    assert set(grants) == {
        "task-1/customer-perspectives",
        "task-2/operational-perspectives",
        "task-3/friend-cafe/conditions",
        "task-3/friend-cafe",
    }
    assert "READ" in grants["task-1/customer-perspectives"].permissions
    assert grants["task-2/operational-perspectives"].permissions == ("READ",)
    assert grants["task-3/friend-cafe"].permissions == ("SHARE",)
    assert len(grants["task-3/friend-cafe"].contexts) == 1
    endpoint = resolve_share_endpoint("task-3/friend-cafe")
    assert endpoint.receiver_context_name == "task-3/friend-cafe"

    catalogs = profiles_module._study_catalogs(authority_root)
    overtime = authority_store.load_direct(
        "task-1/customer-perspectives/woohooovertime"
    )
    first = next(item for item in overtime.iter_items() if isinstance(item, Memory))
    korean = catalogs[(overtime.name, "ko")].entry_for(first.uid)
    assert korean is not None and korean.curated is not None
    assert "지난 한 달 동안" in korean.curated.translated_content

    participant_catalogs = profiles_module._study_catalogs(participant_root)
    practice_source = participant_store.load_direct(
        "practice/coffee/chunk-atomize-summarize"
    )
    practice_memory = next(
        item for item in practice_source.iter_items() if isinstance(item, Memory)
    )
    practice_korean = participant_catalogs[(practice_source.name, "ko")].entry_for(
        practice_memory.uid
    )
    assert practice_korean is not None and practice_korean.curated is not None
    assert "아이스 아메리카노" in practice_korean.curated.translated_content


def test_explicit_legacy_scenario_materializes_without_profile_import(
    isolated_store: Path,
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring()

    result = runner.invoke(
        app,
        ["init-study", "legacy-direct", "--scenario", "legacy"],
    )

    assert result.exit_code == 0, result.stderr or result.output
    assert "Scenario: legacy" in result.output
    assert "Baseline Profile:" not in result.output
    assert "Contexts 65 · Memories 471 · current=practice" in result.output
    assert "Granted Contexts 43 · Granted Memories 625" in result.output
    registry = load_profile_registry()
    assert [profile.name for profile in registry.profiles] == [
        "authoring",
        "legacy-direct",
        "legacy-direct-granted-memory",
    ]
    assert registry.by_name("study-baseline") is None
    participant = registry.by_name("legacy-direct")
    authority = registry.by_name("legacy-direct-granted-memory")
    assert participant is not None and authority is not None
    participant_identity = study_run_identity(participant)
    authority_identity = study_run_identity(authority)
    assert participant_identity is not None and authority_identity is not None
    assert participant_identity.uid == authority_identity.uid
    assert participant_identity.baseline_profile_uid == LEGACY_BASELINE_UID
    assert participant_identity.baseline_profile_name == "legacy"
    assert participant_identity.baseline_sha256 == LEGACY_DIGEST
    assert len(registry.grants) == 8

    participant_store = MemoryStore(
        root=profile_store_dir(participant),
        create=False,
    )
    authority_store = MemoryStore(root=profile_store_dir(authority), create=False)
    assert len(participant_store.list_context_names()) == 65
    assert len(authority_store.list_context_names()) == 75
    assert participant_store.current_context_name() == "practice"
    assert authority_store.current_context_name() == "task-1/campus-wiki"


def test_init_study_rejects_unknown_scenario_before_creating_profiles(
    isolated_store: Path,
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring()

    result = runner.invoke(
        app,
        ["init-study", "bad-scenario", "--scenario", "coffee-latest"],
    )

    assert result.exit_code == 1
    assert "must be 'coffee' or 'legacy'" in result.stderr
    assert [profile.name for profile in load_profile_registry().profiles] == [
        "authoring"
    ]
