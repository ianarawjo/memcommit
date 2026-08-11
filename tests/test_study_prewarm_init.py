from __future__ import annotations

import json
import uuid

from typer.testing import CliRunner

import memcommit.config as config_module
import memcommit.ops as ops
from memcommit.cli import app
from memcommit.atomize import create_atomize_analysis, impact_atomize
from memcommit.commands.comparison_execution import load_comparison_context
from memcommit.commands.granted_context import resolve_context_access
from memcommit.comparison import (
    ComparisonAnalysis,
    ComparisonInput,
    ComparisonMember,
    ComparisonRelation,
    ComparisonReports,
)
from memcommit.config import Config
from memcommit.eval.study_bundle import build_all_study_bundles
from memcommit.granted_comparison_store import load_granted_comparison_artifact
from memcommit.profile_config import load_profile_registry, profile_store_dir
from memcommit.store import MemoryStore
from memcommit.study_prewarm.atomize import build_atomize_prewarm_artifact
from memcommit.study_prewarm.compare import build_compare_prewarm_artifact
from memcommit.study_prewarm.registry import publish_artifact


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
    seeded_run = runner.invoke(app, ["init-study", "seed-source"])
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
        load_comparison_context(access, include_descendants=True)
        for access in accesses
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

    initialized = runner.invoke(app, ["init-study", "seed-target"])

    assert initialized.exit_code == 0, initialized.stderr or initialized.output
    assert "Declared Compare prewarms 1 installed." in initialized.output
    assert "Declared Tutorial Atomize prewarms 1 installed." in initialized.output
    second_registry = load_profile_registry()
    second = second_registry.active
    second_store = MemoryStore(root=profile_store_dir(second), create=False)
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
    atomize_workbench = second_store.load_atomize_workbench(saved_atomize)
    assert atomize_workbench is not None
    assert atomize_workbench.output_context_name == "practice/source-atomized"
    assert all(
        binding.grantee_profile_uid != first.uid
        for binding in saved.bindings
        if binding is not None
    )
