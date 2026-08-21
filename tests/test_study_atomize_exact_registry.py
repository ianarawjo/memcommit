from __future__ import annotations

from datetime import datetime, timezone
import json
import uuid

import pytest
from typer.testing import CliRunner

import memcommit.config as config_module
import memcommit.ops as ops
import memcommit.study_prewarm.atomize as atomize_prewarm_module
from memcommit.atomize import create_atomize_analysis, impact_atomize
from memcommit.atomize_workflow import open_or_create_atomize_workbench
from memcommit.cli import app
from memcommit.config import Config
from memcommit.context import Memory
from memcommit.profile_config import (
    ProfileEntry,
    ProfileRegistry,
    STUDY_RUN_PARTICIPANT_SOURCE_KIND,
)
from memcommit.store import MemoryStore
from memcommit.study_prewarm.atomize import (
    build_atomize_prewarm_artifact,
    find_declared_atomize_prewarm,
    install_declared_atomize_prewarms,
    is_installed_atomize_prewarm,
)
from memcommit.study_prewarm.registry import (
    StudyPrewarmRegistryError,
    publish_artifact,
)


runner = CliRunner(mix_stderr=False)
PAYLOAD_MARKER = "ATOMIZE IMPACT PAYLOAD:\n"


class CompositeProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "impact_atomize"
        payload = json.loads(prompt.split(PAYLOAD_MARKER, 1)[1])
        source = payload["memories"][0]
        return json.dumps(
            {
                "overview": {
                    "understood": {
                        "text": "The request contains two editing constraints.",
                        "source_ids": [source["candidate_id"]],
                    },
                    "changed": {
                        "text": "The two constraints are separated without additions.",
                        "source_ids": [source["candidate_id"]],
                    },
                    "unresolved": {"text": "", "source_ids": []},
                },
                "items": [
                    {
                        "candidate_id": source["candidate_id"],
                        "classification": "COMPOSITE",
                        "reason_codes": ["A01_ONE_FOCUS"],
                        "children": [
                            {
                                "content": "Keep the wording concise.",
                                "source_spans": ["Keep the wording concise."],
                            },
                            {
                                "content": "Preserve the original meaning.",
                                "source_spans": ["Preserve the original meaning."],
                            },
                        ],
                        "reason": "Each sentence is independently revisable.",
                    }
                ],
                "quality_issues": [],
            }
        )


def _profile(baseline_uid: str) -> ProfileEntry:
    uid = str(uuid.uuid4())
    return ProfileEntry(
        uid=uid,
        name="study-atomize-test",
        kind="MANAGED",
        source={
            "kind": STUDY_RUN_PARTICIPANT_SOURCE_KIND,
            "study_uid": str(uuid.uuid4()),
            "study_name": "study-atomize-test",
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
    description = ops.init("practice/description")
    source = ops.init("practice/source")
    ops.add(description, "Atomize the fixed tutorial editing request.")
    ops.add(source, "Keep the wording concise. Preserve the original meaning.")
    store.create_context(description)
    store.create_context(source)
    store.set_current(source.name)
    report = impact_atomize(source, CompositeProvider)
    analysis = create_atomize_analysis(source, report)
    baseline_uid = str(uuid.uuid4())
    profile = _profile(baseline_uid)
    registry = ProfileRegistry(
        generation=1,
        active_uid=profile.uid,
        profiles=(profile,),
    )
    key, artifact = build_atomize_prewarm_artifact(
        task_description=description,
        analysis=analysis,
        provider="codex_chatgpt",
        model="gpt-5.6-sol",
        reasoning="medium",
        offline_provider_seconds=22.81,
    )
    publish_artifact(
        root,
        baseline_profile_uid=baseline_uid,
        operation="ATOMIZE",
        task="tutorial",
        key=key,
        artifact=artifact,
    )
    return store, profile, registry, source, analysis


def test_exact_atomize_registry_installs_and_reopens_without_provider(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    store, profile, registry, source, prepared = _fixture(
        tmp_path, monkeypatch, isolated_store
    )

    installed = install_declared_atomize_prewarms(
        store=store,
        profile=profile,
        registry_snapshot=registry,
    )
    provider_calls = 0

    def forbidden():
        nonlocal provider_calls
        provider_calls += 1
        raise AssertionError("exact Atomize prewarm opened a provider")

    assert store.load_atomize_analysis(source.uid) is None
    match = find_declared_atomize_prewarm(
        store=store,
        context=store.load_direct(source.name),
    )
    assert match is not None
    opened = open_or_create_atomize_workbench(
        store=store,
        ctx=store.load_direct(source.name),
        provider_factory=forbidden,
        prepared_analysis=match.analysis,
        output_context_name=match.output_context_name,
    )

    assert installed.declared == 1
    assert installed.installed == 1
    assert installed.skipped_configuration == 0
    assert provider_calls == 0
    assert opened.analysis.to_dict() == prepared.to_dict()
    assert opened.created_analysis is False
    assert opened.materialized_prepared is True
    assert opened.workbench.output_context_name == "practice/source-atomized"
    assert is_installed_atomize_prewarm(store, opened.analysis)


def test_exact_atomize_cli_auto_applies_and_discloses_zero_provider(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    store, profile, registry, _source, _prepared = _fixture(
        tmp_path, monkeypatch, isolated_store
    )
    install_declared_atomize_prewarms(
        store=store,
        profile=profile,
        registry_snapshot=registry,
    )
    monkeypatch.setattr(
        "memcommit.commands.atomize.connect_codex_chatgpt_provider",
        lambda: (_ for _ in ()).throw(
            AssertionError("prewarmed CLI opened a provider")
        ),
    )

    result = runner.invoke(app, ["atomize", "--context", "practice/source"])

    assert result.exit_code == 0, result.stderr or result.output
    assert "ATOMIZE APPLIED · practice/source" in result.output
    assert "ANALYSIS · EXACT PREWARM · PROVIDER NOT CALLED" in result.output


def test_exact_single_memory_focus_reuses_equivalent_atomize_prewarm(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    store, profile, registry, source, _prepared = _fixture(
        tmp_path, monkeypatch, isolated_store
    )
    install_declared_atomize_prewarms(
        store=store,
        profile=profile,
        registry_snapshot=registry,
    )
    memory = next(item for item in source.iter_items() if isinstance(item, Memory))
    monkeypatch.setattr(
        "memcommit.commands.atomize.connect_codex_chatgpt_provider",
        lambda: (_ for _ in ()).throw(
            AssertionError("equivalent focused prewarm opened a provider")
        ),
    )

    result = runner.invoke(
        app,
        [
            "atomize",
            "--context",
            source.name,
            "--memory",
            memory.uid,
        ],
    )

    assert result.exit_code == 0, result.stderr or result.output
    assert "EXACT PREWARM · CURRENT" in result.output
    assert "provider was not called" in result.output


def test_exact_atomize_source_change_fails_before_publication(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    store, profile, registry, source, _prepared = _fixture(
        tmp_path, monkeypatch, isolated_store
    )
    changed = store.load_direct(source.name)
    memory = next(item for item in changed.iter_items() if isinstance(item, Memory))
    changed.replace(Memory(uid=memory.uid, content=memory.content + " Changed."))
    store.save(changed)

    with pytest.raises(
        StudyPrewarmRegistryError,
        match="does not match the current Source",
    ):
        install_declared_atomize_prewarms(
            store=store,
            profile=profile,
            registry_snapshot=registry,
        )

    assert store.load_atomize_analysis(source.uid) is None


def test_exact_atomize_instruction_change_fails_before_publication(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    store, profile, registry, source, _prepared = _fixture(
        tmp_path, monkeypatch, isolated_store
    )
    description = store.load_direct("practice/description")
    memory = next(
        item for item in description.iter_items() if isinstance(item, Memory)
    )
    description.replace(
        Memory(uid=memory.uid, content=memory.content + " Changed instruction.")
    )
    store.save(description)

    with pytest.raises(
        StudyPrewarmRegistryError,
        match="Tutorial instruction changed",
    ):
        install_declared_atomize_prewarms(
            store=store,
            profile=profile,
            registry_snapshot=registry,
        )

    assert store.load_atomize_analysis(source.uid) is None


def test_exact_atomize_installation_rolls_back_partial_workbench_save(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    store, profile, registry, source, _prepared = _fixture(
        tmp_path, monkeypatch, isolated_store
    )
    install_declared_atomize_prewarms(
        store=store,
        profile=profile,
        registry_snapshot=registry,
    )
    match = find_declared_atomize_prewarm(store=store, context=source)
    assert match is not None
    monkeypatch.setattr(
        store,
        "save_atomize_workbench",
        lambda _workbench: (_ for _ in ()).throw(OSError("injected save failure")),
    )

    with pytest.raises(OSError, match="injected save failure"):
        open_or_create_atomize_workbench(
            store=store,
            ctx=source,
            provider_factory=lambda: (_ for _ in ()).throw(
                AssertionError("materialization opened a provider")
            ),
            prepared_analysis=match.analysis,
            output_context_name=match.output_context_name,
        )

    assert store.load_atomize_analysis(source.uid) is None
    assert not store._atomize_workbench_path(source.uid).exists()


def test_higher_quality_atomize_cache_installs_for_lower_request(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    store, profile, registry, source, _prepared = _fixture(
        tmp_path, monkeypatch, isolated_store
    )
    Config().update({"codex_chatgpt_reasoning_effort": "low"})

    installed = install_declared_atomize_prewarms(
        store=store,
        profile=profile,
        registry_snapshot=registry,
    )

    assert installed.declared == 1
    assert installed.installed == 1
    assert installed.skipped_configuration == 0
    assert store.load_atomize_analysis(source.uid) is None
    match = find_declared_atomize_prewarm(store=store, context=source)
    assert match is not None
    assert match.analysis.uid == _prepared.uid


def test_exact_description_wins_over_legacy_compatible_duplicate(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    store, profile, registry, source, prepared = _fixture(
        tmp_path, monkeypatch, isolated_store
    )
    install_declared_atomize_prewarms(
        store=store,
        profile=profile,
        registry_snapshot=registry,
    )
    exact_match = find_declared_atomize_prewarm(store=store, context=source)
    assert exact_match is not None

    description = store.load_direct("practice/description")
    memory = next(
        item for item in description.iter_items() if isinstance(item, Memory)
    )
    exact_content = memory.content
    description.replace(
        Memory(uid=memory.uid, content="A retained compatible legacy instruction.")
    )
    legacy_key, legacy_artifact = build_atomize_prewarm_artifact(
        task_description=description,
        analysis=prepared,
        provider="codex_chatgpt",
        model="gpt-5.6-sol",
        reasoning="medium",
        offline_provider_seconds=1.0,
    )
    publish_artifact(
        isolated_store,
        baseline_profile_uid=profile.source["baseline_profile_uid"],
        operation="ATOMIZE",
        task="tutorial",
        key=legacy_key,
        artifact=legacy_artifact,
    )
    description.replace(Memory(uid=memory.uid, content=exact_content))
    store.save(description)

    monkeypatch.setattr(
        atomize_prewarm_module,
        "_description_matches_prepared_digest",
        lambda _description, _digest: True,
    )
    installed = install_declared_atomize_prewarms(
        store=store,
        profile=profile,
        registry_snapshot=registry,
    )
    match = find_declared_atomize_prewarm(store=store, context=source)

    assert installed.installed == 2
    assert match is not None
    assert match.entry_key == exact_match.entry_key
    assert match.entry_key != legacy_key


def test_lower_quality_atomize_cache_is_an_explicit_skip(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    store, profile, registry, source, _prepared = _fixture(
        tmp_path, monkeypatch, isolated_store
    )
    Config().update({"codex_chatgpt_reasoning_effort": "high"})

    installed = install_declared_atomize_prewarms(
        store=store,
        profile=profile,
        registry_snapshot=registry,
    )

    assert installed.declared == 1
    assert installed.installed == 0
    assert installed.skipped_configuration == 1
    assert find_declared_atomize_prewarm(store=store, context=source) is None
