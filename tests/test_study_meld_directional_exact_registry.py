from __future__ import annotations

from datetime import datetime, timezone
import json
import uuid

from typer.testing import CliRunner

import memcommit.config as config_module
import memcommit.ops as ops
from memcommit.commands import meld as meld_command
from memcommit.cli import app
from memcommit.comparison import ComparisonInput
from memcommit.comparison_provider import (
    COMPARISON_PAYLOAD_MARKER,
    analyze_comparison,
)
from memcommit.comparison_store import save_comparison_analysis
from memcommit.config import Config
from memcommit.meld import (
    MeldAssessment,
    MeldProposal,
    MeldSession,
    directional_comparison_basis_assessment,
)
from memcommit.profile_config import (
    ProfileEntry,
    ProfileRegistry,
    STUDY_RUN_PARTICIPANT_SOURCE_KIND,
)
from memcommit.store import MemoryStore
from memcommit.study_prewarm.meld_directional import (
    BASELINE_NAME,
    DESCRIPTION_NAME,
    INCOMING_NAME,
    build_directional_meld_prewarm_artifact,
    find_installed_exact_directional_meld_prewarm,
    install_declared_directional_meld_prewarms,
)
from memcommit.study_prewarm.registry import publish_artifact


runner = CliRunner()


class _DistinctCompareProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "compare_contexts"
        payload = json.loads(prompt.split(COMPARISON_PAYLOAD_MARKER, 1)[1])
        incoming = payload["frames"][0]["memories"][0]["memory_id"]
        baseline = payload["frames"][1]["memories"][0]["memory_id"]
        return json.dumps(
            {
                "overview": "The incoming notice and baseline policy are distinct.",
                "reports": {
                    "both": "",
                    "differences": "",
                    "reference_only": "The notice is new.",
                    "compared_only": "The existing policy remains unchanged.",
                },
                "relations": [
                    {
                        "relation_key": "incoming",
                        "reference_memory_ids": [incoming],
                        "compared_memory_ids": [],
                        "kind": "DISTINCT",
                        "status": "RESOLVED",
                        "summary": "The construction notice is incoming-only.",
                        "reason": "No baseline Memory contains the notice.",
                    },
                    {
                        "relation_key": "baseline",
                        "reference_memory_ids": [],
                        "compared_memory_ids": [baseline],
                        "kind": "DISTINCT",
                        "status": "RESOLVED",
                        "summary": "The baseline policy is baseline-only.",
                        "reason": "The incoming notice does not replace it.",
                    },
                ],
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
    baseline = ops.init(BASELINE_NAME)
    ops.add(description, "Integrate construction updates into the campus wiki.")
    incoming_memory = ops.add(incoming, "The east entrance closes on Monday.")
    ops.add(baseline, "The campus wiki retains verified access guidance.")
    for context in (description, incoming, baseline):
        store.create_context(context)
    comparison = analyze_comparison(
        ComparisonInput.from_contexts(
            incoming,
            baseline,
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
    relation = next(
        item
        for item in basis.relations
        if any(member.memory_uid == incoming_memory.uid for member in item.members)
    )
    proposal = MeldProposal.from_dict(
        {
            "uid": str(uuid.uuid4()),
            "operation": "ADD",
            "disposition": "PRESERVE",
            "memory_uid": str(uuid.uuid4()),
            "content": incoming_memory.content,
            "reason": "Preserve the distinct incoming notice.",
            "relation_uids": [relation.uid],
            "source_members": [member.to_dict() for member in relation.members],
            "grounded_by_turn_uids": [],
            "owner_context": {"uid": baseline.uid, "name": baseline.name},
        }
    )
    assessment = MeldAssessment.from_dict(
        {
            "overview": "The incoming notice can be added without changing the baseline policy.",
            "relations": [item.to_dict() for item in basis.relations],
            "issues": [],
            "proposals": [proposal.to_dict()],
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
        store.load_direct(INCOMING_NAME),
        store.load_direct(BASELINE_NAME),
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
        store.load_direct(INCOMING_NAME),
        store.load_direct(BASELINE_NAME),
    )
    current.start_initial_analysis()

    assert (
        find_installed_exact_directional_meld_prewarm(store=store, current=current)
        is None
    )


def test_directional_meld_configuration_mismatch_skips_installation(
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
    assert result.installed == 0
    assert result.skipped_configuration == 1
