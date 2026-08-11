from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from typer.testing import CliRunner

import memcommit.config as config_module
import memcommit.ops as ops
from memcommit.commands.granted_context import resolve_context_access
from memcommit.commands.sever import _capture_binding, _start
from memcommit.cli import app
from memcommit.config import Config
from memcommit.context import Memory
from memcommit.profile_config import (
    ProfileEntry,
    ProfileRegistry,
    STUDY_RUN_PARTICIPANT_SOURCE_KIND,
)
from memcommit.sever import SeverCandidate, SeverSession
from memcommit.sever_store import SeverSessionStore
from memcommit.store import MemoryStore
from memcommit.study_prewarm.registry import (
    StudyPrewarmRegistryError,
    publish_artifact,
)
from memcommit.study_prewarm.sever import (
    CRITERIA_NAME,
    DESCRIPTION_NAME,
    OUTPUT_NAME,
    SOURCE_NAME,
    build_sever_prewarm_artifact,
    find_installed_exact_sever_prewarm,
    install_declared_sever_prewarms,
)


def _profile(baseline_uid: str) -> ProfileEntry:
    return ProfileEntry(
        uid=str(uuid.uuid4()),
        name="study-sever-test",
        kind="MANAGED",
        source={
            "kind": STUDY_RUN_PARTICIPANT_SOURCE_KIND,
            "study_uid": str(uuid.uuid4()),
            "study_name": "study-sever-test",
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
    description = ops.init(DESCRIPTION_NAME)
    source = ops.init(SOURCE_NAME)
    criteria = ops.init(CRITERIA_NAME)
    ops.add(description, "Remove personal information under the supplied guardrails.")
    first = ops.add(source, "My home alarm code is 1234.")
    second = ops.add(source, "I prefer morning appointments.")
    criterion = ops.add(criteria, "Do not retain sensitive or identifying information.")
    for context in (description, source, criteria):
        store.create_context(context)
    source_binding = _capture_binding(
        resolve_context_access(
            store,
            SOURCE_NAME,
            current_name=None,
            required_permission="READ",
        ),
        include_descendants=True,
    )
    criteria_binding = _capture_binding(
        resolve_context_access(
            store,
            CRITERIA_NAME,
            current_name=None,
            required_permission="READ",
        ),
        include_descendants=True,
    )
    session_uid = str(uuid.uuid4())
    session = SeverSession(
        uid=session_uid,
        revision=1,
        state="REVIEWING",
        source=source_binding,
        criteria=criteria_binding,
        output_name=OUTPUT_NAME,
        overview="The Source contains a secret and a scheduling preference.",
        candidates=(
            SeverCandidate(
                uid=str(uuid.uuid5(uuid.UUID(session_uid), first.uid)),
                source_memory_uid=first.uid,
                recommendation="FORGET",
                proposed_content="",
                rationale="The criterion excludes this secret.",
                criterion_memory_uids=(criterion.uid,),
            ),
            SeverCandidate(
                uid=str(uuid.uuid5(uuid.UUID(session_uid), second.uid)),
                source_memory_uid=second.uid,
                recommendation="KEEP_AS_WRITTEN",
                proposed_content=second.content,
                rationale="The preference is not identifying.",
                criterion_memory_uids=(),
            ),
        ),
    )
    baseline_uid = str(uuid.uuid4())
    profile = _profile(baseline_uid)
    registry = ProfileRegistry(generation=1, active_uid=profile.uid, profiles=(profile,))
    key, artifact = build_sever_prewarm_artifact(
        task_description=description,
        session=session,
        provider="codex_chatgpt",
        model="gpt-5.6-sol",
        reasoning="medium",
        offline_provider_seconds=192.178,
    )
    publish_artifact(
        root,
        baseline_profile_uid=baseline_uid,
        operation="SEVER",
        task="task-3",
        key=key,
        artifact=artifact,
    )
    return store, profile, registry, session, source_binding, criteria_binding


def test_exact_sever_registry_installs_hidden_and_clones_fresh_review(
    isolated_store, tmp_path, monkeypatch
):
    store, profile, registry, prepared, source, criteria = _fixture(
        tmp_path, monkeypatch, isolated_store
    )

    result = install_declared_sever_prewarms(
        store=store,
        profile=profile,
        registry_snapshot=registry,
    )
    review = find_installed_exact_sever_prewarm(
        store=store,
        source=source,
        criteria=criteria,
        output_name=OUTPUT_NAME,
    )

    assert result.declared == result.installed == 1
    assert result.skipped_configuration == 0
    assert SeverSessionStore(store).list() == ()
    assert review is not None
    assert review.uid != prepared.uid
    assert review.state == "REVIEWING"
    assert [item.recommendation for item in review.candidates] == [
        "FORGET",
        "KEEP_AS_WRITTEN",
    ]
    assert all(item.selection == "RECOMMENDED" for item in review.candidates)
    assert not store.context_exists(OUTPUT_NAME)


def test_exact_sever_start_does_not_connect_provider(
    isolated_store, tmp_path, monkeypatch
):
    store, profile, registry, _prepared, _source, _criteria = _fixture(
        tmp_path, monkeypatch, isolated_store
    )
    install_declared_sever_prewarms(
        store=store,
        profile=profile,
        registry_snapshot=registry,
    )
    calls = 0

    def forbidden_provider():
        nonlocal calls
        calls += 1
        raise AssertionError("provider must not be connected on an exact hit")

    review = _start(
        store=store,
        source_name=SOURCE_NAME,
        criteria_name=CRITERIA_NAME,
        output_name=OUTPUT_NAME,
        provider_factory=forbidden_provider,
    )

    assert calls == 0
    assert len(review.candidates) == 2


def test_exact_sever_cli_discloses_prewarm_origin(
    isolated_store, tmp_path, monkeypatch
):
    store, profile, registry, _prepared, _source, _criteria = _fixture(
        tmp_path, monkeypatch, isolated_store
    )
    install_declared_sever_prewarms(
        store=store,
        profile=profile,
        registry_snapshot=registry,
    )
    monkeypatch.setattr(
        "memcommit.commands.sever.connect_codex_chatgpt_provider",
        lambda: (_ for _ in ()).throw(AssertionError("provider must not connect")),
    )

    result = CliRunner(mix_stderr=False).invoke(
        app,
        [
            "sever",
            "--source",
            SOURCE_NAME,
            "--criteria",
            CRITERIA_NAME,
            "--save-as",
            OUTPUT_NAME,
        ],
    )

    assert result.exit_code == 0
    assert "ANALYSIS · EXACT PREWARM · PROVIDER NOT CALLED" in result.stdout
    assert len(SeverSessionStore(store).list()) == 1


def test_sever_registry_rejects_changed_source_before_receipt(
    isolated_store, tmp_path, monkeypatch
):
    store, profile, registry, _prepared, _source, _criteria = _fixture(
        tmp_path, monkeypatch, isolated_store
    )
    source = store.load_direct(SOURCE_NAME)
    memory = next(item for item in source.iter_items() if isinstance(item, Memory))
    source.replace(Memory(uid=memory.uid, content=memory.content + " Changed."))
    store.save(source)

    with pytest.raises(StudyPrewarmRegistryError, match="does not match"):
        install_declared_sever_prewarms(
            store=store,
            profile=profile,
            registry_snapshot=registry,
        )

    assert not any(
        (store.store_dir / "study-prewarm-installations").glob("sever-*.json")
    )


def test_sever_registry_configuration_mismatch_is_a_clean_skip(
    isolated_store, tmp_path, monkeypatch
):
    store, profile, registry, _prepared, source, criteria = _fixture(
        tmp_path, monkeypatch, isolated_store
    )
    Config().update({"codex_chatgpt_reasoning_effort": "low"})

    result = install_declared_sever_prewarms(
        store=store,
        profile=profile,
        registry_snapshot=registry,
    )

    assert result.declared == 1
    assert result.installed == 0
    assert result.skipped_configuration == 1
    assert (
        find_installed_exact_sever_prewarm(
            store=store,
            source=source,
            criteria=criteria,
            output_name=OUTPUT_NAME,
        )
        is None
    )


def test_sever_runtime_addition_and_output_change_are_cache_misses(
    isolated_store, tmp_path, monkeypatch
):
    store, profile, registry, _prepared, _source, criteria = _fixture(
        tmp_path, monkeypatch, isolated_store
    )
    install_declared_sever_prewarms(
        store=store,
        profile=profile,
        registry_snapshot=registry,
    )
    source_context = store.load_direct(SOURCE_NAME)
    source_context.add(Memory(uid=str(uuid.uuid4()), content="A newly added fact."))
    store.save(source_context)
    changed_source = _capture_binding(
        resolve_context_access(
            store,
            SOURCE_NAME,
            current_name=None,
            required_permission="READ",
        ),
        include_descendants=True,
    )

    assert (
        find_installed_exact_sever_prewarm(
            store=store,
            source=changed_source,
            criteria=criteria,
            output_name=OUTPUT_NAME,
        )
        is None
    )
    assert (
        find_installed_exact_sever_prewarm(
            store=store,
            source=_source,
            criteria=criteria,
            output_name="task-3/participant/different-output",
        )
        is None
    )
