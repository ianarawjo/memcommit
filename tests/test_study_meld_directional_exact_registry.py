from __future__ import annotations

from datetime import datetime, timezone
import json
import uuid

from typer.testing import CliRunner

import memcommit.configuration.config as config_module
import memcommit.application.capabilities.ops as ops
from memcommit.adapters.console.commands.meld import command as meld_command
from memcommit.adapters.console.entrypoint import app
from memcommit.application.capabilities.memory_issue_analysis.peer_relations.model import ComparisonInput
from memcommit.application.capabilities.memory_issue_analysis.peer_relations.provider_contract import (
    COMPARISON_PAYLOAD_MARKER,
    analyze_comparison,
)
from memcommit.application.capabilities.memory_issue_analysis.peer_relations.repository import save_comparison_analysis
from memcommit.configuration.config import Config
from memcommit.core.context import Context, Memory
from memcommit.core.context_targeting.loading import load_context_scope
from memcommit.application.capabilities.memory_issue_analysis.peer_relations.granted_repository import recursive_comparison_projection
from memcommit.application.operations.meld.model import (
    MeldAssessment,
    MeldProposal,
    MeldSession,
    directional_comparison_basis_assessment,
)
from memcommit.application.operations.profile.config import (
    ProfileEntry,
    ProfileRegistry,
    STUDY_RUN_PARTICIPANT_SOURCE_KIND,
)
from memcommit.persistence.store import MemoryStore
from memcommit.study_scenarios.legacy.prewarm.meld_directional import (
    BASELINE_NAME,
    DESCRIPTION_NAME,
    INCOMING_NAME,
    build_directional_meld_prewarm_artifact,
    find_installed_equivalent_directional_comparison,
    find_installed_exact_directional_meld_prewarm,
    find_installed_directional_meld_prewarm,
    install_declared_directional_meld_prewarms,
)
from memcommit.study_scenarios.legacy.prewarm.registry import publish_artifact


runner = CliRunner()


class _DistinctCompareProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "compare_contexts"
        payload = json.loads(prompt.split(COMPARISON_PAYLOAD_MARKER, 1)[1])
        incoming = [item["memory_id"] for item in payload["frames"][0]["memories"]]
        baseline = [item["memory_id"] for item in payload["frames"][1]["memories"]]
        relations = []
        for index, memory_id in enumerate(incoming, start=1):
            relations.append(
                {
                    "relation_key": f"incoming-{index}",
                    "reference_memory_ids": [memory_id],
                    "compared_memory_ids": [],
                    "kind": "DISTINCT",
                    "status": "RESOLVED",
                    "summary": "The construction notice is incoming-only.",
                    "reason": "No baseline Memory contains the notice.",
                }
            )
        for index, memory_id in enumerate(baseline, start=1):
            relations.append(
                {
                    "relation_key": f"baseline-{index}",
                    "reference_memory_ids": [],
                    "compared_memory_ids": [memory_id],
                    "kind": "DISTINCT",
                    "status": "RESOLVED",
                    "summary": "The baseline policy is baseline-only.",
                    "reason": "The incoming notice does not replace it.",
                }
            )
        return json.dumps(
            {
                "overview": "The incoming notice and baseline policy are distinct.",
                "reports": {
                    "both": "",
                    "differences": "",
                    "reference_only": "The notice is new.",
                    "compared_only": "The existing policy remains unchanged.",
                },
                "relations": relations,
                "issues": [],
            }
        )


def _profile(baseline_uid: str) -> ProfileEntry:
    return ProfileEntry(
        uid=str(uuid.uuid4()),
        name="study-meld-directional-test",
        kind="MANAGED",
        source={
            "kind": STUDY_RUN_PARTICIPANT_SOURCE_KIND,
            "study_uid": str(uuid.uuid4()),
            "study_name": "study-meld-directional-test",
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
    incoming = ops.init(INCOMING_NAME)
    east = ops.init(INCOMING_NAME + "/east-entrance")
    west = ops.init(INCOMING_NAME + "/west-stairwell")
    baseline = ops.init(BASELINE_NAME)
    ops.add(description, "Integrate construction updates into the campus wiki.")
    ops.add(east, "The east entrance closes on Monday.")
    ops.add(west, "The west stairwell reopens on Tuesday.")
    incoming.add(east)
    incoming.add(west)
    ops.add(baseline, "The campus wiki retains verified access guidance.")
    for context in (description, incoming, east, west, baseline):
        store.create_context(context)
    comparison = analyze_comparison(
        ComparisonInput.from_contexts(
            recursive_comparison_projection(incoming),
            recursive_comparison_projection(baseline),
            reference_descendants=True,
            compared_descendants=True,
        ),
        _DistinctCompareProvider(),
    )
    save_comparison_analysis(store, comparison, expected_analysis_uid=None)
    session = MeldSession.create_directional_from_comparison(
        comparison, incoming, baseline
    )
    turn = session.start_initial_analysis()
    basis = directional_comparison_basis_assessment(
        comparison, (session.frames[0], session.frames[1])
    )
    incoming_by_uid = {item.uid: item for item in session.frames[0].memories}
    proposals = []
    for relation in basis.relations:
        member = next(
            (item for item in relation.members if item.memory_uid in incoming_by_uid),
            None,
        )
        if member is None:
            continue
        proposals.append(
            MeldProposal.from_dict(
                {
                    "uid": str(uuid.uuid4()),
                    "operation": "ADD",
                    "disposition": "PRESERVE",
                    "memory_uid": str(uuid.uuid4()),
                    "content": incoming_by_uid[member.memory_uid].content,
                    "reason": "Preserve the distinct incoming notice.",
                    "relation_uids": [relation.uid],
                    "source_members": [member.to_dict()],
                    "grounded_by_turn_uids": [],
                    "owner_context": {"uid": baseline.uid, "name": baseline.name},
                }
            )
        )
    assessment = MeldAssessment.from_dict(
        {
            "overview": "The incoming notice can be added without changing the baseline policy.",
            "relations": [item.to_dict() for item in basis.relations],
            "issues": [],
            "proposals": [proposal.to_dict() for proposal in proposals],
            "ready_to_apply": True,
        }
    )
    session.record_assessment(turn.uid, assessment)
    baseline_uid = str(uuid.uuid4())
    profile = _profile(baseline_uid)
    registry = ProfileRegistry(
        generation=1, active_uid=profile.uid, profiles=(profile,)
    )
    key, artifact = build_directional_meld_prewarm_artifact(
        task_description=description,
        session=session,
        provider="codex_chatgpt",
        model="gpt-5.6-sol",
        reasoning="medium",
        offline_provider_seconds=205.3266,
    )
    publish_artifact(
        root,
        baseline_profile_uid=baseline_uid,
        operation="MELD_DIRECTIONAL",
        task="task-1",
        key=key,
        artifact=artifact,
    )
    return store, profile, registry, session, comparison


def test_directional_meld_registry_installs_hidden_and_rebinds_exact_request(
    isolated_store, tmp_path, monkeypatch
):
    store, profile, registry, prepared, comparison = _fixture(
        tmp_path, monkeypatch, isolated_store
    )

    result = install_declared_directional_meld_prewarms(
        store=store,
        profile=profile,
        registry_snapshot=registry,
    )
    current = MeldSession.create_directional_from_comparison(
        comparison,
        load_context_scope(store, INCOMING_NAME, include_descendants=True),
        load_context_scope(store, BASELINE_NAME, include_descendants=True),
    )
    current.start_initial_analysis()
    restored = find_installed_exact_directional_meld_prewarm(
        store=store, current=current
    )

    assert result.declared == result.installed == 1
    assert store.load_meld_session(current.target.context_uid) is None
    assert restored is not None
    assert restored.state == "READY_TO_APPLY"
    assert [item.content for item in restored.current_assessment.proposals] == [
        item.content for item in prepared.current_assessment.proposals
    ]
    assert {
        member.frame_uid
        for item in restored.current_assessment.relations
        for member in item.members
    } == {frame.uid for frame in current.frames}


def test_directional_meld_exact_cli_never_connects_provider(
    isolated_store, tmp_path, monkeypatch
):
    store, profile, registry, _prepared, _comparison = _fixture(
        tmp_path, monkeypatch, isolated_store
    )
    install_declared_directional_meld_prewarms(
        store=store,
        profile=profile,
        registry_snapshot=registry,
    )
    monkeypatch.setattr(
        meld_command,
        "connect_codex_chatgpt_provider",
        lambda: (_ for _ in ()).throw(AssertionError("provider called")),
    )

    result = runner.invoke(
        app,
        [
            "meld",
            INCOMING_NAME,
            "--into",
            BASELINE_NAME,
            "--left-descendants",
            "--right-descendants",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "ANALYSIS · EXACT PREWARM · PROVIDER NOT CALLED" in result.output
    saved = store.load_meld_session(store.load_direct(BASELINE_NAME).uid)
    assert saved is not None
    assert saved.state == "READY_TO_APPLY"


def test_directional_meld_description_edit_is_a_clean_exact_miss(
    isolated_store, tmp_path, monkeypatch
):
    store, profile, registry, _prepared, comparison = _fixture(
        tmp_path, monkeypatch, isolated_store
    )
    install_declared_directional_meld_prewarms(
        store=store,
        profile=profile,
        registry_snapshot=registry,
    )
    description = store.load_direct(DESCRIPTION_NAME)
    ops.add(description, "The study task changed after setup.")
    store.save(description)
    current = MeldSession.create_directional_from_comparison(
        comparison,
        load_context_scope(store, INCOMING_NAME, include_descendants=True),
        load_context_scope(store, BASELINE_NAME, include_descendants=True),
    )
    current.start_initial_analysis()

    assert (
        find_installed_exact_directional_meld_prewarm(store=store, current=current)
        is None
    )


def test_directional_meld_higher_quality_cache_installs_for_lower_request(
    isolated_store, tmp_path, monkeypatch
):
    store, profile, registry, _prepared, _comparison = _fixture(
        tmp_path, monkeypatch, isolated_store
    )
    Config().update({"codex_chatgpt_reasoning_effort": "low"})

    result = install_declared_directional_meld_prewarms(
        store=store,
        profile=profile,
        registry_snapshot=registry,
    )

    assert result.declared == 1
    assert result.installed == 1
    assert result.skipped_configuration == 0


def test_directional_meld_empty_parent_scope_is_provider_free(
    isolated_store, tmp_path, monkeypatch
):
    store, profile, registry, _prepared, _comparison = _fixture(
        tmp_path, monkeypatch, isolated_store
    )
    install_declared_directional_meld_prewarms(
        store=store,
        profile=profile,
        registry_snapshot=registry,
    )
    parent = ops.init("task-1/participant")
    store.create_context(parent)
    monkeypatch.setattr(
        meld_command,
        "connect_codex_chatgpt_provider",
        lambda: (_ for _ in ()).throw(AssertionError("provider called")),
    )

    result = runner.invoke(
        app,
        [
            "meld",
            parent.name,
            "--into",
            BASELINE_NAME,
            "--left-descendants",
            "--right-descendants",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "ANALYSIS · EQUIVALENT SCOPE PREWARM · PROVIDER NOT CALLED" in result.output
    saved = store.load_meld_session(store.load_direct(BASELINE_NAME).uid)
    assert saved is not None
    assert saved.frames[0].context_name == parent.name
    assert saved.state == "READY_TO_APPLY"


def test_directional_meld_unchanged_incoming_subset_projects_without_provider(
    isolated_store, tmp_path, monkeypatch
):
    store, profile, registry, _prepared, _comparison = _fixture(
        tmp_path, monkeypatch, isolated_store
    )
    install_declared_directional_meld_prewarms(
        store=store,
        profile=profile,
        registry_snapshot=registry,
    )
    subset = store.load_direct(INCOMING_NAME + "/east-entrance")
    kept = next(item for item in subset.iter_items() if isinstance(item, Memory))
    baseline = load_context_scope(store, BASELINE_NAME, include_descendants=True)
    comparison_match = find_installed_equivalent_directional_comparison(
        store=store,
        comparison_input=ComparisonInput.from_contexts(
            subset,
            recursive_comparison_projection(baseline),
            reference_descendants=False,
            compared_descendants=True,
        ),
        registry_snapshot=registry,
    )
    assert comparison_match is not None
    assert comparison_match.origin == "PROJECTED_PREWARM"
    current = MeldSession.create_directional_from_comparison(
        comparison_match.analysis,
        subset,
        baseline,
    )
    current.start_initial_analysis()
    meld_match = find_installed_directional_meld_prewarm(
        store=store,
        current=current,
        registry_snapshot=registry,
    )
    assert meld_match is not None
    assert meld_match.origin == "PROJECTED_PREWARM"
    monkeypatch.setattr(
        meld_command,
        "connect_codex_chatgpt_provider",
        lambda: (_ for _ in ()).throw(AssertionError("provider called")),
    )

    result = runner.invoke(
        app,
        [
            "meld",
            subset.name,
            "--into",
            BASELINE_NAME,
            "--right-descendants",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "ANALYSIS · PROJECTED PREWARM · PROVIDER NOT CALLED" in result.output
    saved = store.load_meld_session(store.load_direct(BASELINE_NAME).uid)
    assert saved is not None and saved.state == "READY_TO_APPLY"
    assessment = saved.current_assessment
    assert assessment is not None
    assert [proposal.content for proposal in assessment.proposals] == [kept.content]
    assert {
        member.memory_uid
        for relation in assessment.relations
        for member in relation.members
        if member.frame_uid == saved.frames[0].uid
    } == {kept.uid}


def test_directional_equivalence_rejects_added_wrapper_memory_and_target_change(
    isolated_store, tmp_path, monkeypatch
):
    store, profile, registry, _prepared, _comparison = _fixture(
        tmp_path, monkeypatch, isolated_store
    )
    install_declared_directional_meld_prewarms(
        store=store,
        profile=profile,
        registry_snapshot=registry,
    )
    parent = ops.init("task-1/participant")
    ops.add(parent, "A parent-local claim changes the selected Source frame.")
    store.create_context(parent)
    incoming = recursive_comparison_projection(
        load_context_scope(store, parent.name, include_descendants=True)
    )
    baseline = recursive_comparison_projection(
        load_context_scope(store, BASELINE_NAME, include_descendants=True)
    )
    comparison_input = ComparisonInput.from_contexts(
        incoming,
        baseline,
        reference_descendants=True,
        compared_descendants=True,
    )

    assert (
        find_installed_equivalent_directional_comparison(
            store=store,
            comparison_input=comparison_input,
            registry_snapshot=registry,
        )
        is None
    )

    # Changing BASELINE/target is never a Source-root alias, even when its
    # visible Memory happens to have the same durable identity and content.
    parent_memory = next(
        item for item in parent.iter_items() if isinstance(item, Memory)
    )
    parent.remove(parent_memory.uid)
    store.save(parent)
    clean_incoming = recursive_comparison_projection(
        load_context_scope(store, parent.name, include_descendants=True)
    )
    comparison_match = find_installed_equivalent_directional_comparison(
        store=store,
        comparison_input=ComparisonInput.from_contexts(
            clean_incoming,
            baseline,
            reference_descendants=True,
            compared_descendants=True,
        ),
        registry_snapshot=registry,
    )
    assert comparison_match is not None
    baseline_memory = next(
        item
        for item in store.load_direct(BASELINE_NAME).iter_items()
        if isinstance(item, Memory)
    )
    changed_target = Context(uid=str(uuid.uuid4()), name="task-1/other-target")
    changed_target.add(Memory(uid=baseline_memory.uid, content=baseline_memory.content))
    changed_target_input = ComparisonInput.from_contexts(
        clean_incoming,
        changed_target,
        reference_descendants=True,
        compared_descendants=True,
    )
    assert (
        find_installed_equivalent_directional_comparison(
            store=store,
            comparison_input=changed_target_input,
            registry_snapshot=registry,
        )
        is None
    )
