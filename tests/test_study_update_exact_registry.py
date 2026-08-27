from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from typer.testing import CliRunner

import memcommit.config as config_module
import memcommit.application.ops as ops
from memcommit.commands.update import command as update_command
from memcommit.adapters.console.entrypoint import app
from memcommit.config import Config
from memcommit.context import Context, Memory
from memcommit.core.context_targeting.loading import load_context_scope
from memcommit.profile_config import (
    ProfileEntry,
    ProfileRegistry,
    STUDY_RUN_PARTICIPANT_SOURCE_KIND,
)
from memcommit.store import MemoryStore
from memcommit.study_prewarm.registry import (
    StudyPrewarmRegistryError,
    publish_artifact,
)
from memcommit.study_prewarm.update import (
    build_update_prewarm_artifact,
    find_installed_equivalent_update_prewarm,
    find_installed_projectable_update_prewarm,
    install_declared_update_prewarms,
    installed_update_prewarm_origin,
    is_installed_update_prewarm,
    record_equivalent_update_prewarm,
)
from memcommit.update import AddOperation, UpdateSession, collect_update_inputs


runner = CliRunner()


def _profile(baseline_uid: str) -> ProfileEntry:
    return ProfileEntry(
        uid=str(uuid.uuid4()),
        name="study-update-test",
        kind="MANAGED",
        source={
            "kind": STUDY_RUN_PARTICIPANT_SOURCE_KIND,
            "study_uid": str(uuid.uuid4()),
            "study_name": "study-update-test",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "baseline_sha256": "a" * 64,
            "baseline_profile_uid": baseline_uid,
            "baseline_profile_name": "study-baseline",
        },
    )


def _fixture(tmp_path, monkeypatch, root):
    monkeypatch.setattr(config_module, "CONFIG_FILE", tmp_path / "config.json")
    Config().update(
        {
            "semantic_provider": "codex_chatgpt",
            "codex_chatgpt_model": "gpt-5.6-sol",
            "codex_chatgpt_reasoning_effort": "medium",
        }
    )
    store = MemoryStore(root=root)
    description = ops.init("task-1/description")
    source = ops.init("task-1/participant/construction-updates")
    target = ops.init("task-1/campus-wiki")
    ops.add(description, "Update the campus wiki from the construction notices.")
    source_memory = ops.add(source, "The library entrance moves north on Monday.")
    ops.add(target, "The library entrance is on the south side.")
    for context in (description, source, target):
        store.create_context(context)
    inputs = collect_update_inputs(source, target)
    session = UpdateSession(
        uid=str(uuid.uuid4()),
        status="impact",
        created_at=datetime.now(timezone.utc).isoformat(),
        source_uid=source.uid,
        source_name=source.name,
        source_digest=inputs.source_digest,
        source_contexts=inputs.source_contexts,
        target_uid=target.uid,
        target_name=target.name,
        target_digest=inputs.target_digest,
        target_contexts=inputs.target_context_fingerprints,
        operations=(
            AddOperation(
                owner_context_uid=target.uid,
                owner_context_name=target.name,
                memory_uid=str(uuid.uuid4()),
                new_content="The library entrance moves north on Monday.",
                source_refs=(inputs.source_candidates[0].reference,),
                reason="The construction notice adds a current access change.",
            ),
        ),
        source_include_descendants=True,
        target_include_descendants=True,
    )
    assert source_memory.uid == inputs.source_candidates[0].memory_uid
    baseline_uid = str(uuid.uuid4())
    profile = _profile(baseline_uid)
    registry = ProfileRegistry(generation=1, active_uid=profile.uid, profiles=(profile,))
    key, artifact = build_update_prewarm_artifact(
        task_description=description,
        session=session,
        provider="codex_chatgpt",
        model="gpt-5.6-sol",
        reasoning="medium",
        offline_provider_seconds=118.1,
    )
    publish_artifact(
        root,
        baseline_profile_uid=baseline_uid,
        operation="UPDATE",
        task="task-1",
        key=key,
        artifact=artifact,
    )
    return store, profile, registry, session


def test_exact_update_registry_installs_hidden_receipt_then_materializes(
    isolated_store, tmp_path, monkeypatch
):
    store, profile, registry, prepared = _fixture(
        tmp_path, monkeypatch, isolated_store
    )

    result = install_declared_update_prewarms(
        store=store,
        profile=profile,
        registry_snapshot=registry,
    )
    cached = store.load_impact_plan()

    assert result.declared == 1
    assert result.installed == 1
    assert result.skipped_configuration == 0
    assert cached is None
    match = find_installed_projectable_update_prewarm(
        store=store,
        source=store.load_direct("task-1/participant/construction-updates"),
        target=store.load_direct("task-1/campus-wiki"),
        source_include_descendants=True,
        target_include_descendants=True,
        granted_source=None,
        granted_target=None,
        registry_snapshot=registry,
    )
    assert match is not None
    assert match.origin == "EXACT_PREWARM"
    assert match.session.to_dict() == prepared.to_dict()
    assert store.load_staged_update() is None
    assert store.load("task-1/campus-wiki").to_dict() == store.load_direct(
        "task-1/campus-wiki"
    ).to_dict()


def test_exact_update_impact_materializes_hidden_receipt_without_provider(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    store, profile, registry, prepared = _fixture(
        tmp_path, monkeypatch, isolated_store
    )
    install_declared_update_prewarms(
        store=store,
        profile=profile,
        registry_snapshot=registry,
    )
    assert store.load_impact_plan() is None
    monkeypatch.setattr(
        "memcommit.commands.impact.command.connect_codex_chatgpt_provider",
        lambda: (_ for _ in ()).throw(
            AssertionError("hidden exact Update receipt opened a provider")
        ),
    )

    result = runner.invoke(
        app,
        [
            "impact",
            "--from",
            "task-1/participant/construction-updates",
                "--to",
                "task-1/campus-wiki",
                "--recursive",
            ],
    )

    assert result.exit_code == 0, result.output
    assert "EXACT PREWARM · UPDATE IMPACT MATERIALIZED" in result.output
    cached = store.load_impact_plan()
    assert cached is not None
    assert cached.to_dict() == prepared.to_dict()
    assert is_installed_update_prewarm(store, cached)


def test_exact_update_registry_rejects_changed_source_before_publication(
    isolated_store, tmp_path, monkeypatch
):
    store, profile, registry, _prepared = _fixture(
        tmp_path, monkeypatch, isolated_store
    )
    source = store.load_direct("task-1/participant/construction-updates")
    memory = next(item for item in source.iter_items() if isinstance(item, Memory))
    source.replace(Memory(uid=memory.uid, content=memory.content + " Changed."))
    store.save(source)

    with pytest.raises(StudyPrewarmRegistryError, match="does not match"):
        install_declared_update_prewarms(
            store=store,
            profile=profile,
            registry_snapshot=registry,
        )

    assert store.load_impact_plan() is None


def test_update_registry_higher_quality_cache_installs_for_lower_request(
    isolated_store, tmp_path, monkeypatch
):
    store, profile, registry, _prepared = _fixture(
        tmp_path, monkeypatch, isolated_store
    )
    Config().update({"codex_chatgpt_reasoning_effort": "low"})

    result = install_declared_update_prewarms(
        store=store,
        profile=profile,
        registry_snapshot=registry,
    )

    assert result.declared == 1
    assert result.installed == 1
    assert result.skipped_configuration == 0
    assert store.load_impact_plan() is None


def test_update_empty_source_parent_reuses_exact_plan(
    isolated_store, tmp_path, monkeypatch
):
    store, profile, registry, _prepared = _fixture(
        tmp_path, monkeypatch, isolated_store
    )
    install_declared_update_prewarms(
        store=store,
        profile=profile,
        registry_snapshot=registry,
    )
    parent = ops.init("task-1/participant")
    store.create_context(parent)
    source = load_context_scope(store, parent.name, include_descendants=True)
    target = load_context_scope(
        store,
        "task-1/campus-wiki",
        include_descendants=True,
    )

    match = find_installed_equivalent_update_prewarm(
        store=store,
        source=source,
        target=target,
        granted_source=None,
        granted_target=None,
        registry_snapshot=registry,
    )

    assert match is not None
    assert match.session.source_name == parent.name
    assert match.session.operations == _prepared.operations
    record_equivalent_update_prewarm(
        store,
        entry_key=match.entry_key,
        session=match.session,
        prepared_source_name=match.prepared_source_name,
    )
    assert (
        installed_update_prewarm_origin(store, match.session)
        == "EQUIVALENT_SCOPE_PREWARM"
    )


def test_update_empty_source_parent_cli_never_plans_live(
    isolated_store, tmp_path, monkeypatch
):
    store, profile, registry, _prepared = _fixture(
        tmp_path, monkeypatch, isolated_store
    )
    install_declared_update_prewarms(
        store=store,
        profile=profile,
        registry_snapshot=registry,
    )
    parent = ops.init("task-1/participant")
    store.create_context(parent)
    monkeypatch.setattr(
        update_command,
        "_plan_update_with_wait",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("transparent Update scope planned live")
        ),
    )

    result = runner.invoke(
        app,
        [
            "update",
            "--from",
            parent.name,
            "--to",
            "task-1/campus-wiki",
            "--source-descendants",
            "--target-descendants",
        ],
    )

    assert result.exit_code == 0, result.output
    assert (
        "EQUIVALENT SCOPE PREWARM · UPDATE PLAN REUSED · provider was not called."
        in result.output
    )
    target = store.load_direct("task-1/campus-wiki")
    assert "The library entrance moves north on Monday." in {
        item.content for item in target.iter_items() if isinstance(item, Memory)
    }


@pytest.mark.parametrize(
    ("source_descendants", "target_descendants"),
    [(False, False), (False, True), (True, False), (True, True)],
)
def test_update_equal_evidence_ignores_locator_scope_flags(
    isolated_store,
    tmp_path,
    monkeypatch,
    source_descendants,
    target_descendants,
):
    store, profile, registry, prepared = _fixture(
        tmp_path, monkeypatch, isolated_store
    )
    install_declared_update_prewarms(
        store=store,
        profile=profile,
        registry_snapshot=registry,
    )

    match = find_installed_projectable_update_prewarm(
        store=store,
        source=store.load_direct("task-1/participant/construction-updates"),
        target=store.load_direct("task-1/campus-wiki"),
        source_include_descendants=source_descendants,
        target_include_descendants=target_descendants,
        granted_source=None,
        granted_target=None,
        registry_snapshot=registry,
    )

    assert match is not None
    assert match.origin == (
        "EXACT_PREWARM"
        if source_descendants and target_descendants
        else "EQUIVALENT_SCOPE_PREWARM"
    )
    assert match.session.operations == prepared.operations
    assert match.session.source_include_descendants is source_descendants
    assert match.session.target_include_descendants is target_descendants


def test_update_empty_source_subset_projects_to_empty_plan(
    isolated_store, tmp_path, monkeypatch
):
    store, profile, registry, _prepared = _fixture(
        tmp_path, monkeypatch, isolated_store
    )
    install_declared_update_prewarms(
        store=store,
        profile=profile,
        registry_snapshot=registry,
    )
    empty = ops.init("task-1/participant/empty-selection")
    store.create_context(empty)

    match = find_installed_projectable_update_prewarm(
        store=store,
        source=empty,
        target=store.load_direct("task-1/campus-wiki"),
        source_include_descendants=False,
        target_include_descendants=False,
        granted_source=None,
        granted_target=None,
        registry_snapshot=registry,
    )

    assert match is not None
    assert match.origin == "PROJECTED_PREWARM"
    assert match.session.operations == ()


@pytest.mark.parametrize("violation", ["memory", "unrelated", "target"])
def test_update_scope_equivalence_rejects_nontransparent_requests(
    isolated_store, tmp_path, monkeypatch, violation
):
    store, profile, registry, _prepared = _fixture(
        tmp_path, monkeypatch, isolated_store
    )
    install_declared_update_prewarms(
        store=store,
        profile=profile,
        registry_snapshot=registry,
    )
    source_name = (
        "task-1/unrelated-source"
        if violation == "unrelated"
        else "task-1/participant"
    )
    parent = ops.init(source_name)
    if violation == "memory":
        ops.add(parent, "A wrapper-local source claim.")
    elif violation == "unrelated":
        exact_source = store.load_direct(
            "task-1/participant/construction-updates"
        )
        source_memory = next(
            item for item in exact_source.iter_items() if isinstance(item, Memory)
        )
        parent.add(Memory(uid=source_memory.uid, content=source_memory.content))
    store.create_context(parent)
    source = load_context_scope(store, parent.name, include_descendants=True)
    target = load_context_scope(
        store,
        "task-1/campus-wiki",
        include_descendants=True,
    )
    if violation == "target":
        target = Context(uid=target.uid, name="task-1/other-target")

    match = find_installed_equivalent_update_prewarm(
        store=store,
        source=source,
        target=target,
        granted_source=None,
        granted_target=None,
        registry_snapshot=registry,
    )

    assert match is None
