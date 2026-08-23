from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest

import memcommit.comparison as comparison_module
import memcommit.ops as ops
import memcommit.study_prewarm.compare as compare_prewarm_module
import memcommit.study_prewarm.update as update_prewarm_module
import memcommit.update as update_module
from memcommit.comparison import (
    ComparisonAnalysis,
    ComparisonInput,
    ComparisonMember,
    ComparisonRelation,
    ComparisonReports,
)
from memcommit.study_prewarm.prepare import inspect_study_prewarm_compatibility
from memcommit.study_prewarm.registry import (
    StudyPrewarmRegistryError,
    load_registry,
    payload_digest,
    publish_artifact,
    replace_operation_artifacts,
)
from memcommit.update import AddOperation, UpdateSession, collect_update_inputs


def _analysis(reference, compared) -> ComparisonAnalysis:
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
                "summary": "One exact test claim is present on this side.",
                "reason": "No counterpart is assigned in the test fixture.",
            }
        )
        for frame in comparison_input.frames
        for memory in frame.memories
    )
    return ComparisonAnalysis.create(
        comparison_input,
        overview="The exact test frames remain distinct.",
        reports=ComparisonReports(
            both="",
            differences="",
            reference_only="The reference claim is independently assigned.",
            compared_only="The compared claim is independently assigned.",
        ),
        relations=relations,
        issues=(),
    )


def _update_session(source, target) -> UpdateSession:
    inputs = collect_update_inputs(source, target)
    return UpdateSession(
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
                new_content="The north entrance opens Monday.",
                source_refs=(inputs.source_candidates[0].reference,),
                reason="The construction notice adds a current access change.",
            ),
        ),
        source_include_descendants=True,
        target_include_descendants=True,
    )


def _legacy_artifacts(monkeypatch):
    compare_description = ops.init("task-2/description")
    reference = ops.init("task-2/advisor1")
    compared = ops.init("task-2/advisor2")
    ops.add(compare_description, "Compare the two advisor documents.")
    ops.add(reference, "Reference-only guidance.")
    ops.add(compared, "Compared-only guidance.")

    with monkeypatch.context() as patch:
        patch.setattr(
            comparison_module,
            "COMPARISON_RULESET_VERSION",
            "peer-relations-v3",
        )
        patch.setattr(
            compare_prewarm_module,
            "COMPARISON_RULESET_VERSION",
            "peer-relations-v3",
        )
        legacy_analysis = _analysis(reference, compared)
        compare_key, compare_artifact = (
            compare_prewarm_module.build_compare_prewarm_artifact(
                task="task-2",
                task_description=compare_description,
                analysis=legacy_analysis,
                provider="codex_chatgpt",
                model="gpt-5.6-sol",
                reasoning="none",
                offline_provider_seconds=1.0,
            )
        )
        legacy_compare_material = compare_prewarm_module._compare_key_material(
            task="task-2",
            description=compare_artifact["task_description"],
            analysis=legacy_analysis,
            provider="codex_chatgpt",
            model="gpt-5.6-sol",
            reasoning="none",
            ruleset_version="peer-relations-v3",
            provider_contract_version="one-shot-exhaustive-v1",
        )
        compare_key = payload_digest(legacy_compare_material)
        compare_artifact["key"] = compare_key
        compare_artifact["provider_contract_version"] = "one-shot-exhaustive-v1"

    update_description = ops.init("task-1/description")
    source = ops.init("task-1/participant/construction-updates")
    target = ops.init("task-1/campus-wiki")
    ops.add(update_description, "Update the campus wiki.")
    ops.add(source, "The north entrance opens Monday.")
    ops.add(target, "The south entrance is currently open.")
    session = _update_session(source, target)
    with monkeypatch.context() as patch:
        patch.setattr(update_module, "UPDATE_SCHEMA_VERSION", 6)
        patch.setattr(update_prewarm_module, "UPDATE_SCHEMA_VERSION", 6)
        update_key, update_artifact = (
            update_prewarm_module.build_update_prewarm_artifact(
                task_description=update_description,
                session=session,
                provider="codex_chatgpt",
                model="gpt-5.6-sol",
                reasoning="none",
                offline_provider_seconds=2.0,
            )
        )
        legacy_update_material = update_prewarm_module._key_material(
            description=update_artifact["task_description"],
            session=session,
            provider="codex_chatgpt",
            model="gpt-5.6-sol",
            reasoning="none",
            update_schema_version=6,
        )
        update_key = payload_digest(legacy_update_material)
        update_artifact["key"] = update_key
        update_artifact["update_schema_version"] = 6
    return (
        compare_description,
        reference,
        compared,
        compare_key,
        compare_artifact,
        update_key,
        update_artifact,
    )


def test_compatibility_audit_classifies_supported_generations_and_replaces_them(
    tmp_path,
    monkeypatch,
):
    baseline_uid = str(uuid.uuid4())
    (
        compare_description,
        reference,
        compared,
        compare_key,
        compare_artifact,
        update_key,
        update_artifact,
    ) = _legacy_artifacts(monkeypatch)
    publish_artifact(
        tmp_path,
        baseline_profile_uid=baseline_uid,
        operation="COMPARE",
        task="task-2",
        key=compare_key,
        artifact=compare_artifact,
    )
    publish_artifact(
        tmp_path,
        baseline_profile_uid=baseline_uid,
        operation="UPDATE",
        task="task-1",
        key=update_key,
        artifact=update_artifact,
    )

    compatibility = inspect_study_prewarm_compatibility(tmp_path)

    assert compatibility.verified_enabled == 2
    assert len(compatibility.legacy_compare_parents) == 1
    assert len(compatibility.migrated_update_records) == 1
    migrated_update = compatibility.migrated_update_records[0]
    update_prewarm_module._validate_artifact(
        migrated_update[2],
        entry_key=migrated_update[1],
    )

    current_analysis = _analysis(reference, compared)
    current_compare_key, current_compare = (
        compare_prewarm_module.build_compare_prewarm_artifact(
            task="task-2",
            task_description=compare_description,
            analysis=current_analysis,
            provider="codex_chatgpt",
            model="gpt-5.6-sol",
            reasoning="none",
            offline_provider_seconds=3.0,
        )
    )
    replaced = replace_operation_artifacts(
        tmp_path,
        baseline_profile_uid=baseline_uid,
        replacements={
            "COMPARE": (("task-2", current_compare_key, current_compare),),
            "UPDATE": (migrated_update,),
        },
    )

    enabled = [entry for entry in replaced.entries if entry.enabled]
    disabled = [entry for entry in replaced.entries if not entry.enabled]
    assert {entry.key for entry in enabled} == {
        current_compare_key,
        migrated_update[1],
    }
    assert {entry.key for entry in disabled} == {compare_key, update_key}
    refreshed = inspect_study_prewarm_compatibility(tmp_path)
    assert refreshed.verified_enabled == 2
    assert refreshed.migrated_update_records == ()
    assert len(refreshed.legacy_compare_parents) == 1


def test_compatibility_audit_keeps_tampered_artifacts_fail_closed(
    tmp_path,
    monkeypatch,
):
    baseline_uid = str(uuid.uuid4())
    *_, compare_key, compare_artifact, _update_key, _update_artifact = (
        _legacy_artifacts(monkeypatch)
    )
    entry = publish_artifact(
        tmp_path,
        baseline_profile_uid=baseline_uid,
        operation="COMPARE",
        task="task-2",
        key=compare_key,
        artifact=compare_artifact,
    )
    artifact_path = tmp_path / "study-semantic-prewarm" / entry.artifact
    artifact_path.write_text("{}\n", encoding="utf-8")

    with pytest.raises(
        StudyPrewarmRegistryError,
        match="changed after lookup",
    ):
        inspect_study_prewarm_compatibility(tmp_path)


def test_compatibility_audit_rejects_unknown_semantic_generation(
    tmp_path,
    monkeypatch,
):
    baseline_uid = str(uuid.uuid4())
    *_, compare_key, compare_artifact, _update_key, _update_artifact = (
        _legacy_artifacts(monkeypatch)
    )
    compare_artifact["ruleset_version"] = "peer-relations-v999"
    publish_artifact(
        tmp_path,
        baseline_profile_uid=baseline_uid,
        operation="COMPARE",
        task="task-2",
        key=compare_key,
        artifact=compare_artifact,
    )

    with pytest.raises(
        StudyPrewarmRegistryError,
        match="Declared Compare prewarm is invalid",
    ):
        inspect_study_prewarm_compatibility(tmp_path)


def test_compatibility_audit_rejects_unknown_compare_provider_contract(
    tmp_path,
    monkeypatch,
):
    baseline_uid = str(uuid.uuid4())
    *_, compare_key, compare_artifact, _update_key, _update_artifact = (
        _legacy_artifacts(monkeypatch)
    )
    compare_artifact["provider_contract_version"] = "unknown-compare-v999"
    publish_artifact(
        tmp_path,
        baseline_profile_uid=baseline_uid,
        operation="COMPARE",
        task="task-2",
        key=compare_key,
        artifact=compare_artifact,
    )

    with pytest.raises(
        StudyPrewarmRegistryError,
        match="Declared Compare prewarm is invalid",
    ):
        inspect_study_prewarm_compatibility(tmp_path)


def test_batch_replacement_does_not_switch_registry_after_prepublication_failure(
    tmp_path,
    monkeypatch,
):
    baseline_uid = str(uuid.uuid4())
    (
        compare_description,
        reference,
        compared,
        compare_key,
        compare_artifact,
        _update_key,
        _update_artifact,
    ) = _legacy_artifacts(monkeypatch)
    publish_artifact(
        tmp_path,
        baseline_profile_uid=baseline_uid,
        operation="COMPARE",
        task="task-2",
        key=compare_key,
        artifact=compare_artifact,
    )
    before = load_registry(tmp_path)
    assert before is not None
    current_analysis = _analysis(reference, compared)
    current_key, current_artifact = (
        compare_prewarm_module.build_compare_prewarm_artifact(
            task="task-2",
            task_description=compare_description,
            analysis=current_analysis,
            provider="codex_chatgpt",
            model="gpt-5.6-sol",
            reasoning="none",
            offline_provider_seconds=3.0,
        )
    )

    with pytest.raises(
        StudyPrewarmRegistryError,
        match="keys must be unique",
    ):
        replace_operation_artifacts(
            tmp_path,
            baseline_profile_uid=baseline_uid,
            replacements={
                "COMPARE": (
                    ("task-2", current_key, current_artifact),
                    ("task-2", current_key, current_artifact),
                )
            },
        )

    assert load_registry(tmp_path) == before
