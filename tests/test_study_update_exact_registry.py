from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest

import memcommit.config as config_module
import memcommit.ops as ops
from memcommit.config import Config
from memcommit.context import Memory
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
    install_declared_update_prewarms,
    is_installed_update_prewarm,
)
from memcommit.update import AddOperation, UpdateSession, collect_update_inputs


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


def test_exact_update_registry_installs_into_ordinary_impact_slot(
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
    assert cached is not None
    assert cached.to_dict() == prepared.to_dict()
    assert is_installed_update_prewarm(store, cached)
    assert store.load_staged_update() is None
    assert store.load("task-1/campus-wiki").to_dict() == store.load_direct(
        "task-1/campus-wiki"
    ).to_dict()


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


def test_update_registry_configuration_mismatch_is_a_clean_skip(
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
    assert result.installed == 0
    assert result.skipped_configuration == 1
    assert store.load_impact_plan() is None
