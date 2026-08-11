from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest

import memcommit.config as config_module
import memcommit.ops as ops
import memcommit.store as store_module
from memcommit.commands.compare import render_comparison
from memcommit.commands.comparison_execution import ensure_comparison_analysis
from memcommit.commands.granted_context import ContextAccess
from memcommit.comparison import (
    ComparisonAnalysis,
    ComparisonInput,
    ComparisonMember,
    ComparisonRelation,
    ComparisonReports,
)
from memcommit.comparison_store import load_comparison_analysis
from memcommit.config import Config
from memcommit.context import Context, Memory
from memcommit.profile_config import (
    ProfileEntry,
    ProfileRegistry,
    STUDY_RUN_PARTICIPANT_SOURCE_KIND,
)
from memcommit.store import MemoryStore
from memcommit.study_prewarm.compare import (
    build_compare_prewarm_artifact,
    install_declared_compare_prewarms,
    is_installed_compare_prewarm,
    project_declared_compare_analysis,
)
from memcommit.study_prewarm.registry import (
    StudyPrewarmRegistryError,
    publish_artifact,
)


def _profile(baseline_uid: str) -> ProfileEntry:
    uid = str(uuid.uuid4())
    return ProfileEntry(
        uid=uid,
        name="study-test",
        kind="MANAGED",
        source={
            "kind": STUDY_RUN_PARTICIPANT_SOURCE_KIND,
            "study_uid": str(uuid.uuid4()),
            "study_name": "study-test",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "baseline_sha256": "a" * 64,
            "baseline_profile_uid": baseline_uid,
            "baseline_profile_name": "study-baseline",
        },
    )


def _analysis(reference, compared) -> ComparisonAnalysis:
    comparison_input = ComparisonInput.from_contexts(
        reference,
        compared,
        reference_descendants=True,
        compared_descendants=True,
    )
    relations = []
    for frame in comparison_input.frames:
        for memory in frame.memories:
            relations.append(
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
                        "summary": "This claim appears on only one peer side.",
                        "reason": "The other frozen peer has no grouped counterpart.",
                    }
                )
            )
    return ComparisonAnalysis.create(
        comparison_input,
        overview="The two frozen peer frames contain independent test claims.",
        reports=ComparisonReports(
            both="",
            differences="",
            reference_only="The reference has one independent claim.",
            compared_only="The compared peer has one independent claim.",
        ),
        relations=relations,
        issues=(),
    )


def _fixture(tmp_path, monkeypatch, *, task: str = "task-2"):
    root = tmp_path / "run"
    monkeypatch.setattr(store_module, "STORE_DIR", root)
    monkeypatch.setattr(config_module, "CONFIG_FILE", tmp_path / "config.json")
    Config().update(
        {
            "semantic_provider": "codex_chatgpt",
            "codex_chatgpt_model": "gpt-5.6-sol",
            "codex_chatgpt_reasoning_effort": "medium",
        }
    )
    store = MemoryStore(root=root)
    if task == "task-1":
        description = ops.init("task-1/description")
        reference = ops.init("task-1/participant/construction-updates")
        compared = ops.init("task-1/campus-wiki")
    else:
        description = ops.init("task-2/description")
        reference = ops.init("task-2/advisor1")
        compared = ops.init("task-2/advisor2")
    ops.add(description, "Compare the two advisor documents.")
    ops.add(reference, "Reference-only guidance.")
    ops.add(compared, "Compared-only guidance.")
    for context in (description, reference, compared):
        store.create_context(context)
    store.set_current(reference.name)
    baseline_uid = str(uuid.uuid4())
    profile = _profile(baseline_uid)
    registry = ProfileRegistry(
        generation=1,
        active_uid=profile.uid,
        profiles=(profile,),
    )
    analysis = _analysis(reference, compared)
    key, artifact = build_compare_prewarm_artifact(
        task=task,
        task_description=description,
        analysis=analysis,
        provider="codex_chatgpt",
        model="gpt-5.6-sol",
        reasoning="medium",
        offline_provider_seconds=123.0,
    )
    publish_artifact(
        root,
        baseline_profile_uid=baseline_uid,
        operation="COMPARE",
        task=task,
        key=key,
        artifact=artifact,
    )
    return store, profile, registry, reference, compared, analysis


def test_task1_exact_basis_and_opposite_descendants_use_generic_registry(
    tmp_path,
    monkeypatch,
):
    store, profile, registry, reference, compared, prepared = _fixture(
        tmp_path,
        monkeypatch,
        task="task-1",
    )
    installed = install_declared_compare_prewarms(
        store=store,
        profile=profile,
        registry_snapshot=registry,
    )
    exact_calls = 0

    def forbidden(_comparison_input):
        nonlocal exact_calls
        exact_calls += 1
        raise AssertionError("Task 1 exact prewarm called the analyzer")

    exact = ensure_comparison_analysis(
        store=store,
        reference_access=_access(store, reference),
        compared_access=_access(store, compared),
        reference=reference,
        compared=compared,
        current_name=reference.name,
        include_descendants=(True, True),
        analyze=forbidden,
    )
    reference_child = _subset_context(
        reference,
        reference.name + "/building-access",
    )
    compared_child = _subset_context(
        compared,
        compared.name + "/building-access",
    )
    projected = project_declared_compare_analysis(
        store=store,
        comparison_input=ComparisonInput.from_contexts(
            reference_child,
            compared_child,
        ),
        current_name=reference.name,
        registry_snapshot=registry,
    )

    assert installed.installed == 1
    assert exact_calls == 0
    assert exact.analysis.uid == prepared.uid
    assert projected is not None
    assert sum(len(relation.members) for relation in projected.relations) == 2
    assert len(projected.relations) <= 2


def _access(store: MemoryStore, context) -> ContextAccess:
    return ContextAccess(
        store=store,
        context_name=context.name,
        display_name=context.name,
        attachment_name=None,
        permission="READ",
    )


def _subset_context(parent, name: str, *, changed: bool = False) -> Context:
    source = next(iter(parent.iter_items()))
    assert isinstance(source, Memory)
    child = Context(uid=str(uuid.uuid4()), name=name)
    child.add(
        Memory(
            uid=source.uid,
            content=(source.content + " changed") if changed else source.content,
        )
    )
    return child


def _live_distinct_analysis(comparison_input: ComparisonInput) -> ComparisonAnalysis:
    relations = []
    for frame in comparison_input.frames:
        for memory in frame.memories:
            relations.append(
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
                        "summary": "A live one-sided relation.",
                        "reason": "The live fallback found no grouped counterpart.",
                    }
                )
            )
    return ComparisonAnalysis.create(
        comparison_input,
        overview="A fresh live fallback comparison.",
        reports=ComparisonReports(
            both="",
            differences="",
            reference_only="The reference has live-only material.",
            compared_only="The compared frame has live-only material.",
        ),
        relations=relations,
        issues=(),
    )


def test_exact_registry_installs_then_production_compare_never_calls_provider(
    tmp_path,
    monkeypatch,
):
    store, profile, registry, reference, compared, prepared = _fixture(
        tmp_path,
        monkeypatch,
    )

    installed = install_declared_compare_prewarms(
        store=store,
        profile=profile,
        registry_snapshot=registry,
    )
    analyzer_calls = 0

    def forbidden(_comparison_input):
        nonlocal analyzer_calls
        analyzer_calls += 1
        raise AssertionError("exact installed prewarm called the analyzer")

    execution = ensure_comparison_analysis(
        store=store,
        reference_access=_access(store, reference),
        compared_access=_access(store, compared),
        reference=reference,
        compared=compared,
        current_name=reference.name,
        include_descendants=(True, True),
        analyze=forbidden,
    )

    assert installed.declared == 1
    assert installed.installed == 1
    assert installed.skipped_configuration == 0
    assert analyzer_calls == 0
    assert execution.reused is True
    assert execution.analysis.uid == prepared.uid
    assert is_installed_compare_prewarm(store, execution.analysis) is True
    saved = load_comparison_analysis(reference.uid, compared.uid)
    assert saved is not None and saved.uid == prepared.uid


def test_configuration_mismatch_skips_seed_without_publishing(
    tmp_path,
    monkeypatch,
):
    store, profile, registry, reference, compared, _prepared = _fixture(
        tmp_path,
        monkeypatch,
    )
    Config().set("codex_chatgpt_reasoning_effort", "low")

    result = install_declared_compare_prewarms(
        store=store,
        profile=profile,
        registry_snapshot=registry,
    )

    assert result.declared == 1
    assert result.installed == 0
    assert result.skipped_configuration == 1
    assert load_comparison_analysis(reference.uid, compared.uid) is None


def test_changed_task_description_rejects_seed_without_partial_publication(
    tmp_path,
    monkeypatch,
):
    store, profile, registry, reference, compared, _prepared = _fixture(
        tmp_path,
        monkeypatch,
    )
    description = store.load_direct("task-2/description")
    ops.add(description, "A changed description invalidates the semantic frame.")
    store.save(description)

    with pytest.raises(
        StudyPrewarmRegistryError,
        match="description changed",
    ):
        install_declared_compare_prewarms(
            store=store,
            profile=profile,
            registry_snapshot=registry,
        )

    assert load_comparison_analysis(reference.uid, compared.uid) is None


def test_declared_parent_projects_opposite_descendant_subsets_without_provider(
    tmp_path,
    monkeypatch,
):
    store, profile, registry, reference, compared, _prepared = _fixture(
        tmp_path,
        monkeypatch,
    )
    install_declared_compare_prewarms(
        store=store,
        profile=profile,
        registry_snapshot=registry,
    )
    reference_child = _subset_context(
        reference,
        "task-2/advisor1/construction",
    )
    compared_child = _subset_context(
        compared,
        "task-2/advisor2/details",
    )
    store.create_context(reference_child)
    store.create_context(compared_child)
    analyzer_calls = 0

    def forbidden(_comparison_input):
        nonlocal analyzer_calls
        analyzer_calls += 1
        raise AssertionError("deletion projection called the provider")

    execution = ensure_comparison_analysis(
        store=store,
        reference_access=_access(store, reference_child),
        compared_access=_access(store, compared_child),
        reference=reference_child,
        compared=compared_child,
        current_name=reference_child.name,
        analyze=forbidden,
        project=lambda comparison_input: project_declared_compare_analysis(
            store=store,
            comparison_input=comparison_input,
            current_name=reference_child.name,
            registry_snapshot=registry,
        ),
    )

    expected_members = {
        (frame.uid, memory.uid)
        for frame in execution.analysis.frames
        for memory in frame.memories
    }
    observed_members = {
        (member.frame_uid, member.memory_uid)
        for relation in execution.analysis.relations
        for member in relation.members
    }
    assert analyzer_calls == 0
    assert execution.origin == "PROJECTED"
    assert execution.reused is True
    assert execution.durable is False
    assert observed_members == expected_members
    assert len(execution.analysis.relations) <= len(expected_members)
    assert load_comparison_analysis(reference_child.uid, compared_child.uid) is None
    rendered = render_comparison(
        execution.analysis,
        reused=execution.reused,
        origin=execution.origin,
        durable=execution.durable,
    )
    assert "PROJECTED · NOT SAVED · PREVIEW" in rendered
    assert "Create a new result Context" not in rendered


def test_declared_parent_projection_supports_reversed_opposite_sides(
    tmp_path,
    monkeypatch,
):
    store, _profile_entry, registry, reference, compared, _prepared = _fixture(
        tmp_path,
        monkeypatch,
    )
    left = _subset_context(reference, "task-2/advisor1/left")
    right = _subset_context(compared, "task-2/advisor2/right")
    comparison_input = ComparisonInput.from_contexts(right, left)

    projected = project_declared_compare_analysis(
        store=store,
        comparison_input=comparison_input,
        current_name=left.name,
        registry_snapshot=registry,
    )

    assert projected is not None
    assert [frame.context_name for frame in projected.frames] == [right.name, left.name]
    assert {
        member.memory_uid
        for relation in projected.relations
        for member in relation.members
    } == {
        memory.uid
        for frame in comparison_input.frames
        for memory in frame.memories
    }


@pytest.mark.parametrize("condition", ["edit", "addition", "same-side", "cross-task"])
def test_projection_misses_non_deletion_or_non_opposite_requests(
    tmp_path,
    monkeypatch,
    condition,
):
    store, _profile_entry, registry, reference, compared, _prepared = _fixture(
        tmp_path,
        monkeypatch,
    )
    left = _subset_context(
        reference,
        "task-2/advisor1/left",
        changed=condition == "edit",
    )
    if condition == "addition":
        left.add(Memory(uid=str(uuid.uuid4()), content="A newly added claim."))
    if condition == "same-side":
        right = _subset_context(reference, "task-2/advisor1/right")
    else:
        right = _subset_context(compared, "task-2/advisor2/right")
    if condition == "cross-task":
        right.name = "task-3/right"
    comparison_input = ComparisonInput.from_contexts(left, right)

    projected = project_declared_compare_analysis(
        store=store,
        comparison_input=comparison_input,
        current_name=left.name,
        registry_snapshot=registry,
    )

    assert projected is None


def test_refresh_bypasses_available_projection_and_runs_live_once(
    tmp_path,
    monkeypatch,
):
    store, _profile_entry, registry, reference, compared, _prepared = _fixture(
        tmp_path,
        monkeypatch,
    )
    left = _subset_context(reference, "task-2/advisor1/left")
    right = _subset_context(compared, "task-2/advisor2/right")
    store.create_context(left)
    store.create_context(right)
    analyzer_calls = 0

    def live(comparison_input):
        nonlocal analyzer_calls
        analyzer_calls += 1
        return _live_distinct_analysis(comparison_input)

    execution = ensure_comparison_analysis(
        store=store,
        reference_access=_access(store, left),
        compared_access=_access(store, right),
        reference=left,
        compared=right,
        current_name=left.name,
        refresh=True,
        analyze=live,
        project=lambda comparison_input: project_declared_compare_analysis(
            store=store,
            comparison_input=comparison_input,
            current_name=left.name,
            registry_snapshot=registry,
        ),
    )

    assert analyzer_calls == 1
    assert execution.origin == "LIVE"
    assert execution.durable is True
    assert load_comparison_analysis(left.uid, right.uid) is not None
