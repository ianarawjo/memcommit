"""Built-in Coffee Study scenario and legacy-selection contracts."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

import memcommit.application.ops as ops
import memcommit.profiles as profiles_module
from memcommit.adapters.console.entrypoint import app
from memcommit.context import Memory
from memcommit.profile_config import (
    load_profile_registry,
    profile_store_dir,
    study_run_identity,
)
from memcommit.profiles import resolve_share_endpoint
from memcommit.store import MemoryStore
from memcommit.study_scenarios.coffee_v1 import (
    COFFEE_V1_BASELINE_UID,
    COFFEE_V1_DIGEST,
    build_coffee_v1_scenario,
)


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


def test_coffee_v1_spec_is_stable_bilingual_and_has_24_24_8_inputs():
    scenario = build_coffee_v1_scenario()
    rebuilt = build_coffee_v1_scenario()

    assert scenario.scenario_id == "coffee-v1"
    assert scenario.baseline_uid == COFFEE_V1_BASELINE_UID
    assert scenario.digest == rebuilt.digest == COFFEE_V1_DIGEST
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


def test_plain_init_study_builds_coffee_v1_without_a_baseline_or_prewarm(
    isolated_store: Path,
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring()

    def reject_legacy_prewarm(*_args, **_kwargs):
        raise AssertionError("coffee-v1 must not inspect or prepare legacy prewarms")

    monkeypatch.setattr(
        "memcommit.study_prewarm.prepare.prepare_study_prewarms",
        reject_legacy_prewarm,
    )

    result = runner.invoke(app, ["init-study", "coffee-default"])

    assert result.exit_code == 0, result.stderr or result.output
    assert "Scenario: coffee-v1" in result.output
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
    assert identity.baseline_profile_uid == COFFEE_V1_BASELINE_UID
    assert identity.baseline_profile_name == "coffee-v1"
    assert identity.baseline_sha256 == COFFEE_V1_DIGEST

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
    assert "COMBINE" in grants["task-2/operational-perspectives"].permissions
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
    assert "must be 'coffee-v1' or 'legacy-v1'" in result.stderr
    assert [profile.name for profile in load_profile_registry().profiles] == [
        "authoring"
    ]
