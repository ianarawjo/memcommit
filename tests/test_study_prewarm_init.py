from __future__ import annotations

import json
import uuid

from typer.testing import CliRunner

import memcommit.config as config_module
import memcommit.application.ops as ops
import memcommit.profiles as profiles_module
import memcommit.semantic_prompt_policy as semantic_prompt_policy_module
import memcommit.study_prewarm.atomize as atomize_prewarm_module
import memcommit.study_prewarm.prepare as prewarm_prepare_module
from memcommit.adapters.console.entrypoint import app
from memcommit.atomize import create_atomize_analysis, impact_atomize
from memcommit.commands.compare.execution import load_comparison_context
from memcommit.commands.compare.execution import ensure_comparison_analysis
from memcommit.commands.atomize.sessions import atomize_session_entries
from memcommit.commands.compare.sessions import comparison_session_entries
from memcommit.atomize_workflow import open_or_create_atomize_workbench
from memcommit.application.authority.access import resolve_context_access
from memcommit.comparison import (
    ComparisonAnalysis,
    ComparisonInput,
    ComparisonMember,
    ComparisonRelation,
    ComparisonReports,
)
from memcommit.config import Config
from memcommit.context import Memory
from memcommit.application.evaluation.study_bundle import build_all_study_bundles
from memcommit.granted_comparison_store import load_granted_comparison_artifact
from memcommit.profile_config import load_profile_registry, profile_store_dir
from memcommit.store import MemoryStore
from memcommit.study_prewarm.atomize import (
    build_atomize_prewarm_artifact,
    find_declared_atomize_prewarm,
)
from memcommit.study_prewarm.compare import (
    build_compare_prewarm_artifact,
    find_declared_equivalent_compare_analysis,
)
from memcommit.study_prewarm.registry import publish_artifact
from memcommit.study_prewarm.registry import (
    bundle_reference_path,
    registry_root,
    shared_bundle_root,
)


runner = CliRunner(mix_stderr=False)


class _TutorialAtomizeProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "impact_atomize"
        payload = json.loads(prompt.split("ATOMIZE IMPACT PAYLOAD:\n", 1)[1])
        memories = payload["memories"]
        source_ids = [item["candidate_id"] for item in memories]
        return json.dumps(
            {
                "overview": {
                    "understood": {
                        "text": "The frozen tutorial request is preserved.",
                        "source_ids": source_ids,
                    },
                    "changed": {
                        "text": "No split is proposed by this setup fixture.",
                        "source_ids": source_ids,
                    },
                    "unresolved": {"text": "", "source_ids": []},
                },
                "items": [
                    {
                        "candidate_id": item["candidate_id"],
                        "classification": "ATOMIC",
                        "reason_codes": ["A01_ONE_FOCUS"],
                        "children": [],
                        "reason": "The source is retained as one test focus.",
                    }
                    for item in memories
                ],
                "quality_issues": [],
            }
        )


def _distinct_analysis(reference, compared) -> ComparisonAnalysis:
    comparison_input = ComparisonInput.from_contexts(
        reference,
        compared,
        reference_descendants=True,
        compared_descendants=True,
    )
    relations = tuple(
        ComparisonRelation.from_dict(
            {
                "uid": str(uuid.uuid4()),
                "kind": "DISTINCT",
                "status": "RESOLVED",
                "members": [
                    ComparisonMember(
                        frame_uid=frame.uid,
                        memory_uid=memory.uid,
                    ).to_dict()
                ],
                "summary": "The frozen test claim is present on only one peer side.",
                "reason": "No counterpart is assigned in this portable test seed.",
            }
        )
        for frame in comparison_input.frames
        for memory in frame.memories
    )
    return ComparisonAnalysis.create(
        comparison_input,
        overview="The exact frozen peer frames are preserved for setup testing.",
        reports=ComparisonReports(
            both="",
            differences="",
            reference_only="The reference contains independently assigned claims.",
            compared_only="The compared peer contains independently assigned claims.",
        ),
        relations=relations,
        issues=(),
    )


def test_init_study_copies_and_rebinds_declared_compare_and_atomize(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    # The shared test harness pins ordinary commands to virtual authoring.
    # This regression explicitly exercises Study-only prompt-policy prewarms,
    # so policy selection must observe the real run Profile created below.
    monkeypatch.setattr(
        semantic_prompt_policy_module,
        "load_profile_registry",
        load_profile_registry,
    )
    monkeypatch.setattr(config_module, "CONFIG_FILE", tmp_path / "config.json")
    Config().update(
        {
            "semantic_provider": "codex_chatgpt",
            "codex_chatgpt_model": "gpt-5.6-sol",
            "codex_chatgpt_reasoning_effort": "medium",
        }
    )
    authoring = MemoryStore()
    authoring.save(ops.init("authoring-notes"))
    authoring.set_current("authoring-notes")
    bundles = tmp_path / "bundles"
    build_all_study_bundles(bundles)
    imported = runner.invoke(
        app,
        ["profile", "import-study", "--from", str(bundles)],
    )
    assert imported.exit_code == 0, imported.stderr or imported.output
    seeded_run = runner.invoke(
        app,
        ["init-study", "seed-source", "--scenario", "legacy-v1"],
    )
    assert seeded_run.exit_code == 0, seeded_run.stderr or seeded_run.output

    first_registry = load_profile_registry()
    first = first_registry.active
    first_store = MemoryStore(root=profile_store_dir(first), create=False)
    current_name = first_store.current_context_name()
    accesses = tuple(
        resolve_context_access(
            first_store,
            name,
            current_name=current_name,
            required_permission="READ",
            registry=first_registry,
        )
        for name in ("task-2/advisor1", "task-2/advisor2")
    )
    contexts = tuple(
        load_comparison_context(access, include_descendants=True) for access in accesses
    )
    description_access = resolve_context_access(
        first_store,
        "task-2/description",
        current_name=current_name,
        required_permission="READ",
        registry=first_registry,
    )
    description = load_comparison_context(description_access)
    analysis = _distinct_analysis(contexts[0], contexts[1])
    baseline = first_registry.by_name("study-baseline")
    assert baseline is not None
    key, artifact = build_compare_prewarm_artifact(
        task="task-2",
        task_description=description,
        analysis=analysis,
        provider="codex_chatgpt",
        model="gpt-5.6-sol",
        reasoning="medium",
        offline_provider_seconds=10.0,
    )
    publish_artifact(
        profile_store_dir(baseline),
        baseline_profile_uid=baseline.uid,
        operation="COMPARE",
        task="task-2",
        key=key,
        artifact=artifact,
    )
    practice_source = first_store.load_direct("practice/source")
    practice_description = first_store.load_direct("practice/description")

    def make_legacy_pre_split(value):
        overview = value.memories[
            profiles_module._STUDY_PRACTICE_DESCRIPTION_OVERVIEW_UID
        ]
        task = value.memories[profiles_module._STUDY_PRACTICE_DESCRIPTION_TASK_UID]
        assert isinstance(overview, Memory)
        assert isinstance(task, Memory)
        overview.content = (
            profiles_module._LEGACY_STUDY_PRACTICE_DESCRIPTION_OVERVIEW_CONTENT
        )
        value.remove(profiles_module._STUDY_PRACTICE_DESCRIPTION_SITUATION_UID)
        task.content = (
            profiles_module._LEGACY_PRE_SPLIT_STUDY_PRACTICE_DESCRIPTION_CONTENT
        )

    make_legacy_pre_split(practice_description)
    legacy_provenance = Memory(
        uid=profiles_module._LEGACY_STUDY_PRACTICE_PROVENANCE_UID,
        content=atomize_prewarm_module._LEGACY_PRACTICE_PROVENANCE_CONTENT,
    )
    practice_description.add(legacy_provenance)
    baseline_store = MemoryStore(root=profile_store_dir(baseline), create=False)
    baseline_description = baseline_store.load_direct("practice/description")
    make_legacy_pre_split(baseline_description)
    baseline_description.add(legacy_provenance)
    baseline_store.save(baseline_description)
    atomize_analysis = create_atomize_analysis(
        practice_source,
        impact_atomize(practice_source, _TutorialAtomizeProvider),
    )
    atomize_key, atomize_artifact = build_atomize_prewarm_artifact(
        task_description=practice_description,
        analysis=atomize_analysis,
        provider="codex_chatgpt",
        model="gpt-5.6-sol",
        reasoning="medium",
        offline_provider_seconds=2.0,
    )
    publish_artifact(
        profile_store_dir(baseline),
        baseline_profile_uid=baseline.uid,
        operation="ATOMIZE",
        task="tutorial",
        key=atomize_key,
        artifact=atomize_artifact,
    )

    preparation_calls = []
    real_prepare = prewarm_prepare_module.prepare_study_prewarms

    def observed_prepare(**kwargs):
        preparation_calls.append(kwargs)
        return real_prepare(**kwargs)

    monkeypatch.setattr(
        prewarm_prepare_module,
        "prepare_study_prewarms",
        observed_prepare,
    )
    initialized = runner.invoke(
        app,
        ["init-study", "seed-target", "--scenario", "legacy-v1"],
    )

    assert initialized.exit_code == 0, initialized.stderr or initialized.output
    assert len(preparation_calls) == 1
    assert preparation_calls[0]["workers"] == 96
    assert preparation_calls[0]["reasoning"] == "xhigh"
    assert initialized.output.count("Shared Study prewarm bundle attached.") == 1
    assert "Compare prewarms" not in initialized.output
    assert "Atomize prewarms" not in initialized.output
    second_registry = load_profile_registry()
    second = second_registry.active
    second_store = MemoryStore(root=profile_store_dir(second), create=False)
    reference = json.loads(
        bundle_reference_path(second_store.store_dir).read_text(encoding="utf-8")
    )
    assert not registry_root(second_store.store_dir).exists()
    assert not (second_store.store_dir / "study-prewarm-installations").exists()
    assert shared_bundle_root(reference["bundle_digest"]).is_dir()
    saved = load_granted_comparison_artifact(
        second_store,
        analysis.frames[0].context_uid,
        analysis.frames[1].context_uid,
    )
    assert saved is None
    assert comparison_session_entries(second_store) == ()
    assert atomize_session_entries(second_store) == ()
    assert second_store.load_impact_plan() is None
    assert second_store.load_staged_update() is None
    assert second_store.load_atomize_analysis(practice_source.uid) is None

    current_source = second_store.load_direct("practice/source")
    atomize_match = find_declared_atomize_prewarm(
        store=second_store,
        context=current_source,
    )
    assert atomize_match is not None
    opened_atomize = open_or_create_atomize_workbench(
        store=second_store,
        ctx=current_source,
        provider_factory=lambda: (_ for _ in ()).throw(
            AssertionError("lazy Atomize materialization opened a provider")
        ),
        prepared_analysis=atomize_match.analysis,
        output_context_name=atomize_match.output_context_name,
    )
    assert opened_atomize.materialized_prepared is True
    assert comparison_session_entries(second_store) == ()
    assert (
        load_granted_comparison_artifact(
            second_store,
            analysis.frames[0].context_uid,
            analysis.frames[1].context_uid,
        )
        is None
    )

    current_name = second_store.current_context_name()
    compare_accesses = tuple(
        resolve_context_access(
            second_store,
            name,
            current_name=current_name,
            required_permission="READ",
            registry=second_registry,
        )
        for name in ("task-2/advisor1", "task-2/advisor2")
    )
    compare_contexts = tuple(
        load_comparison_context(access, include_descendants=True)
        for access in compare_accesses
    )

    def exact_compare(comparison_input):
        match = find_declared_equivalent_compare_analysis(
            store=second_store,
            comparison_input=comparison_input,
            current_name=current_name,
            registry_snapshot=second_registry,
        )
        assert match is not None
        return match.analysis

    execution = ensure_comparison_analysis(
        store=second_store,
        reference_access=compare_accesses[0],
        compared_access=compare_accesses[1],
        reference=compare_contexts[0],
        compared=compare_contexts[1],
        current_name=current_name,
        include_descendants=(True, True),
        analyze=lambda _input: (_ for _ in ()).throw(
            AssertionError("lazy Compare materialization opened a provider")
        ),
        equivalent=exact_compare,
    )
    assert execution.analysis.to_dict() == analysis.to_dict()
    saved = load_granted_comparison_artifact(
        second_store,
        analysis.frames[0].context_uid,
        analysis.frames[1].context_uid,
    )
    assert saved is not None
    assert saved.analysis.to_dict() == analysis.to_dict()
    assert all(binding is not None for binding in saved.bindings)
    assert all(
        binding.grantee_profile_uid == second.uid
        for binding in saved.bindings
        if binding is not None
    )
    saved_atomize = second_store.load_atomize_analysis(practice_source.uid)
    assert saved_atomize is not None
    assert saved_atomize.to_dict() == atomize_analysis.to_dict()
    copied_description = second_store.load_direct("practice/description")
    assert (
        profiles_module._LEGACY_STUDY_PRACTICE_PROVENANCE_UID
        not in copied_description.memories
    )
    copied_memories = [
        item for item in copied_description.iter_items() if isinstance(item, Memory)
    ]
    assert [item.content for item in copied_memories] == [
        profiles_module._STUDY_PRACTICE_DESCRIPTION_OVERVIEW_CONTENT,
        profiles_module._STUDY_PRACTICE_DESCRIPTION_SITUATION_CONTENT,
        profiles_module._STUDY_PRACTICE_DESCRIPTION_TASK_CONTENT,
    ]
    atomize_workbench = second_store.load_atomize_workbench(saved_atomize)
    assert atomize_workbench is not None
    assert atomize_workbench.output_context_name == "practice/source-atomized"
    assert all(
        binding.grantee_profile_uid != first.uid
        for binding in saved.bindings
        if binding is not None
    )
