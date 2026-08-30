"""Exact Dedup and semantic Dedun planning/application tests."""

from __future__ import annotations

import hashlib
import json
import uuid

import click
import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from typer.testing import CliRunner

import memcommit.application.capabilities.ops as ops
from memcommit.adapters.python_api import DedunPlanResult, MemCommitClient
from memcommit.adapters.console.entrypoint import app
from memcommit.adapters.console.terminal.components.quality_find.workbench import (
    run_quality_find_resolution_workbench,
)
from memcommit.core.context import Context, MemoryRef, QueryContextRef
from memcommit.application.capabilities.retained_history.context_snapshot import (
    CONTEXT_SNAPSHOT_SCHEMA_VERSION,
    ContextSnapshotRef,
    context_snapshot_digest,
)
from memcommit.application.operations.dedun.application import (
    DedunAuthorityError,
    DedunConflictError,
    DedunError,
    DedunRequest,
    DedunSelection,
    apply_dedun,
    prepare_dedun,
    recommended_dedun_selections,
)
from memcommit.application.operations.dedun.runtime import MemoryStoreDedunPort
from memcommit.application.capabilities.reviewing.direct_item_duplicates import (
    find_exact_duplicate_groups,
)
from memcommit.application.capabilities.memory_issue_analysis.model import (
    DuplicateFinding,
    DuplicateReport,
)
from memcommit.adapters.agent.dedup import DEDUP_AGENT_TOOL_NAME
from memcommit.adapters.agent.registry import build_default_agent_tool_registry
from memcommit.adapters.console.terminal.core.theme import (
    SemanticColorRole,
    semantic_color_rgb,
)
from memcommit.adapters.console.commands.dedun.workbench import (
    dedun_exact_review,
    dedun_resolution_spec,
    run_dedun_workbench,
)
from memcommit.adapters.console.terminal.components.resolution import ResolutionOutcome
from memcommit.application.capabilities.memory_issue_analysis.workbench import (
    create_quality_find_workbench,
)
from memcommit.application.capabilities.memory_issue_analysis.handoff import (
    QualityFindingHandoff,
    QualityFindingHandoffError,
    QualityFindingReviewDraft,
    QualityFindingSource,
    quality_finding_handoffs,
)
from memcommit.application.capabilities.semantic.redundancy_evidence import (
    redundancy_evidence_dict,
    redundancy_evidence_from_dict,
    redundancy_evidence_json,
)
from memcommit.application.operations.profile.config import (
    AUTHORING_PROFILE_NAME,
    AUTHORING_PROFILE_UID,
    ProfileEntry,
    ProfileRegistry,
    profile_registry_file,
    profile_store_dir,
)
from memcommit.application.operations.profile.model import (
    create_authority_grant,
    update_authority_grant,
)
from memcommit.application.operations.review.model import direct_context_digest
from memcommit.persistence.store import MemoryStore


runner = CliRunner(mix_stderr=False)


def _handoff(
    context,
    left_uid: str,
    right_uid: str,
    *,
    relation: str = "SEMANTIC_EQUIVALENT",
    index: int = 1,
) -> QualityFindingHandoff:
    return QualityFindingHandoff(
        uid=f"finding-handoff-{index}",
        finding_uid=f"duplicate:{left_uid}:{right_uid}",
        kind="DUPLICATE",
        route="DEDUP",
        source_frame_digest="a" * 64,
        sources=(
            QualityFindingSource(
                context_uid=context.uid,
                display_name=context.name,
                direct_memory_digest=direct_context_digest(context),
            ),
        ),
        memory_uids=(left_uid, right_uid),
        memory_context_names=(context.name, context.name),
        classification=relation,
        qualifiers=(),
        reason="The finder classified this pair as equivalent.",
        question="",
        proposed_readings=(),
        review_draft=QualityFindingReviewDraft(
            selected_option_uid="ignored-review-draft"
        ),
    )


def _context(store: MemoryStore):
    context = ops.init("dedup/source")
    first = ops.add(context, "The office opens at eight.")
    second = ops.add(context, "The office opens at 8.")
    third = ops.add(context, "Office opening time is 08:00.")
    unrelated = ops.add(context, "The office closes at five.")
    store.save(context)
    return context, first, second, third, unrelated


def _strict_handoffs(context, *findings: DuplicateFinding):
    session = create_quality_find_workbench(
        "duplicates",
        context,
        DuplicateReport(
            memory_count=sum(
                1 for item in context.iter_items() if hasattr(item, "content")
            ),
            findings=tuple(findings),
        ),
    )
    return quality_finding_handoffs(session)


def _role_aware_exact_fixture(store: MemoryStore):
    """Persist one frame with same-role duplicates and cross-role overlap."""

    source = ops.init("dedup/role-source")
    source_memory = ops.add(source, "same visible content")
    other_source = ops.init("dedup/other-source")
    other_memory = ops.add(other_source, "same visible content")
    target = ops.init("dedup/role-target")
    owned = ops.add(target, "same visible content")

    live_refs = tuple(
        MemoryRef(
            uid=str(uuid.uuid4()),
            target_context_uid=source.uid,
            target_context_name=source.name,
            target_memory_uid=source_memory.uid,
            target=source_memory,
        )
        for _ in range(2)
    )
    digest = hashlib.sha256(source_memory.content.encode("utf-8")).hexdigest()
    snapshot_refs = tuple(
        MemoryRef(
            uid=str(uuid.uuid4()),
            target_context_uid=source.uid,
            target_context_name=source.name,
            target_memory_uid=source_memory.uid,
            target=source_memory,
            snapshot_content_sha256=digest,
        )
        for _ in range(2)
    )
    other_digest = hashlib.sha256(other_memory.content.encode("utf-8")).hexdigest()
    other_snapshot = MemoryRef(
        uid=str(uuid.uuid4()),
        target_context_uid=other_source.uid,
        target_context_name=other_source.name,
        target_memory_uid=other_memory.uid,
        target=other_memory,
        snapshot_content_sha256=other_digest,
    )

    package = {
        "schema_version": CONTEXT_SNAPSHOT_SCHEMA_VERSION,
        "root": {"uid": source.uid, "name": source.name},
        "recursive": False,
        "lexical_context_names": [source.name],
        "contexts": [source.to_dict()],
    }
    package_digest = context_snapshot_digest(package)
    context_snapshots = tuple(
        ContextSnapshotRef(
            uid=str(uuid.uuid4()),
            target_context_uid=source.uid,
            target_context_name=source.name,
            snapshot_package=package,
            snapshot_content_sha256=package_digest,
        )
        for _ in range(2)
    )

    for item in (
        *live_refs,
        *snapshot_refs,
        other_snapshot,
        Context(uid=source.uid, name=source.name),
        *context_snapshots,
    ):
        target.add(item)
    for context in (source, other_source, target):
        store.save(context)
    store.set_current(target.name)
    return (
        target,
        owned,
        live_refs,
        snapshot_refs,
        other_snapshot,
        context_snapshots,
    )


def test_dedup_builds_transitive_components_and_keeps_context_order(isolated_store):
    store = MemoryStore()
    context, first, second, third, _unrelated = _context(store)
    request = DedunRequest(
        (
            _handoff(context, second.uid, third.uid, index=1),
            _handoff(context, first.uid, second.uid, index=2),
        )
    )

    plan = prepare_dedun(
        request,
        port=MemoryStoreDedunPort(store, current_name=context.name),
    )

    assert len(plan.components) == 1
    component = plan.components[0]
    assert tuple(member.uid for member in component.members) == (
        first.uid,
        second.uid,
        third.uid,
    )
    assert component.recommended_survivor_uid == first.uid
    # A finder draft is never an executable survivor selection.
    assert recommended_dedun_selections(plan) == (
        DedunSelection(component.uid, first.uid),
    )


def test_dedun_combines_exact_dup_and_semantic_dun_evidence(isolated_store):
    store = MemoryStore()
    context, first, second, third, _unrelated = _context(store)
    request = DedunRequest(
        (
            _handoff(context, first.uid, second.uid, relation="EXACT", index=1),
            _handoff(
                context,
                second.uid,
                third.uid,
                relation="SEMANTIC_EQUIVALENT",
                index=2,
            ),
        )
    )

    plan = prepare_dedun(
        request,
        port=MemoryStoreDedunPort(store, current_name=context.name),
    )

    assert len(plan.components) == 1
    assert tuple(evidence.relation for evidence in plan.components[0].evidence) == (
        "EXACT",
        "SEMANTIC_EQUIVALENT",
    )


def test_dedup_applies_one_checkpoint_without_rewriting_survivor(isolated_store):
    store = MemoryStore()
    context, first, second, third, unrelated = _context(store)
    request = DedunRequest(
        (
            _handoff(context, first.uid, second.uid, index=1),
            _handoff(context, second.uid, third.uid, index=2),
        )
    )
    port = MemoryStoreDedunPort(store, current_name=context.name)
    plan = prepare_dedun(request, port=port)
    selection = (DedunSelection(plan.components[0].uid, second.uid),)

    receipt = apply_dedun(plan, selection, port=port)

    current = store.load_direct(context.name)
    assert current.memories[second.uid].content == "The office opens at 8."
    assert tuple(current.memories) == (second.uid, unrelated.uid)
    assert receipt.survivor_uids == (second.uid,)
    assert receipt.absorbed_uids == (first.uid, third.uid)
    checkpoints = store.list_checkpoints(context.name)
    assert len(checkpoints) == 1
    assert checkpoints[0]["command"] == "dedun"


def test_dedun_rejects_partial_overlap_until_memories_are_atomized(
    isolated_store,
):
    store = MemoryStore()
    context = ops.init("dedun/partial-overlap")
    first = ops.add(context, "abc")
    second = ops.add(context, "bcd")
    store.save(context)

    with pytest.raises(DedunError, match="OVERLAP"):
        DedunRequest((_handoff(context, first.uid, second.uid, relation="OVERLAP"),))


def test_dedup_fails_closed_when_source_changes(isolated_store):
    store = MemoryStore()
    context, first, second, _third, _unrelated = _context(store)
    request = DedunRequest((_handoff(context, first.uid, second.uid),))
    port = MemoryStoreDedunPort(store, current_name=context.name)
    plan = prepare_dedun(request, port=port)
    current = store.load_direct(context.name)
    ops.add(current, "A later write.")
    store.save(current)

    with pytest.raises(DedunConflictError, match="changed before Apply"):
        apply_dedun(
            plan,
            recommended_dedun_selections(plan),
            port=port,
        )

    assert first.uid in store.load_direct(context.name).memories
    assert second.uid in store.load_direct(context.name).memories


def test_dedup_blocks_absorbing_an_inbound_reference(isolated_store):
    store = MemoryStore()
    context, first, second, _third, _unrelated = _context(store)
    observer = ops.init("dedup/observer")
    observer.add(
        MemoryRef(
            uid=str(uuid.uuid4()),
            target_context_uid=context.uid,
            target_context_name=context.name,
            target_memory_uid=second.uid,
        )
    )
    store.save(observer)
    request = DedunRequest((_handoff(context, first.uid, second.uid),))
    port = MemoryStoreDedunPort(store, current_name=context.name)
    plan = prepare_dedun(request, port=port)

    with pytest.raises(DedunConflictError, match="inbound references"):
        apply_dedun(
            plan,
            recommended_dedun_selections(plan),
            port=port,
        )

    assert second.uid in store.load_direct(context.name).memories


def test_dedup_requires_one_survivor_for_every_component(isolated_store):
    store = MemoryStore()
    context, first, second, _third, _unrelated = _context(store)
    plan = prepare_dedun(
        DedunRequest((_handoff(context, first.uid, second.uid),)),
        port=MemoryStoreDedunPort(store, current_name=context.name),
    )

    with pytest.raises(DedunError, match="unresolved redundancy groups"):
        apply_dedun(
            plan,
            (),
            port=MemoryStoreDedunPort(store, current_name=context.name),
        )


def test_dedup_tui_uses_common_required_resolution_order(isolated_store):
    store = MemoryStore()
    context, first, second, _third, _unrelated = _context(store)
    handoff = _strict_handoffs(
        context,
        DuplicateFinding(
            first,
            second,
            "SEMANTIC_EQUIVALENT",
            "The claims are substitutable.",
        ),
    )[0]
    port = MemoryStoreDedunPort(store, current_name=context.name)
    plan = prepare_dedun(DedunRequest((handoff,)), port=port)
    spec = dedun_resolution_spec(plan)

    assert spec.detail_title.startswith("VIEWER")
    assert spec.responses_title.startswith("RESPONSES")
    assert spec.items_title.startswith("ITEMS")
    report_styles = {
        style
        for section in spec.report.sections
        for style, _text in section.block.fragments
    }
    assert "class:impact.add" in report_styles
    assert "class:impact.keep" not in report_styles
    review = dedun_exact_review(
        plan,
        ResolutionOutcome(
            ((plan.components[0].uid, plan.components[0].recommended_survivor_uid),)
        ),
    )
    assert review.argv[:2] == ("mem", "dedun")
    assert "--evidence" in review.argv
    assert "redundancy-evidence-v2" in review.argv[3]
    assert "--finding-handoff" not in review.argv
    assert review.argv[-1] == "--apply"

    with create_pipe_input() as pipe_input:
        # Viewer -> Items/open -> Viewer detail -> Responses/select -> Items ->
        # To Do/final review -> exact Apply -> close receipt.
        pipe_input.send_text("\t\r\t\r\t\t\r\r\r")
        receipt = run_dedun_workbench(
            plan,
            apply_selections=lambda selections: apply_dedun(
                plan,
                selections,
                port=port,
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt is not None
    assert receipt.survivor_uids == (first.uid,)
    assert second.uid not in store.load_direct(context.name).memories


def test_reported_finder_links_enter_dedup_as_one_typed_batch(isolated_store):
    store = MemoryStore()
    context, first, second, _third, _unrelated = _context(store)
    session = create_quality_find_workbench(
        "duplicates",
        context,
        DuplicateReport(
            memory_count=4,
            findings=(
                DuplicateFinding(
                    first,
                    second,
                    "SEMANTIC_EQUIVALENT",
                    "The claims are substitutable.",
                ),
            ),
        ),
    )
    item_uid = f"duplicate:{first.uid}:{second.uid}"
    received = []

    with create_pipe_input() as pipe_input:
        # Find reports evidence without asking for confirmation. Dedun owns
        # the later survivor and Apply decisions.
        pipe_input.send_text("\r")
        run_quality_find_resolution_workbench(
            session,
            context,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
            duplicate_handoff_handler=received.append,
        )

    assert len(received) == 1
    assert tuple(handoff.finding_uid for handoff in received[0]) == (item_uid,)
    assert session.responses == {}


def test_cli_and_public_api_share_semantic_dedun_application(isolated_store):
    store = MemoryStore()
    context, first, second, _third, _unrelated = _context(store)
    handoff = _strict_handoffs(
        context,
        DuplicateFinding(
            first,
            second,
            "SEMANTIC_EQUIVALENT",
            "The claims are substitutable.",
        ),
    )[0]
    client = MemCommitClient(root=isolated_store, create=False)
    public_plan = client.plan_dedun((handoff,))
    assert isinstance(public_plan, DedunPlanResult)
    assert public_plan.components[0].recommended_survivor_uid == first.uid

    result = runner.invoke(
        app,
        [
            "dedun",
            "--evidence",
            redundancy_evidence_json(handoff),
        ],
        color=True,
    )
    assert result.exit_code == 0
    assert public_plan.revision in click.unstyle(result.stdout)
    assert "RECOMMENDED SURVIVOR" in click.unstyle(result.stdout)
    assert (
        click.style(
            "RECOMMENDED SURVIVOR",
            fg=semantic_color_rgb(SemanticColorRole.ADD),
            bold=True,
        )
        in result.stdout
    )

    receipt = client.apply_dedun(
        public_plan,
        survivors={public_plan.components[0].uid: second.uid},
    )
    assert receipt.survivor_uids == (second.uid,)
    assert first.uid in receipt.absorbed_uids


def test_public_dedun_plan_exposes_and_applies_exact_embed_groups(
    isolated_store,
):
    store = MemoryStore()
    context, first, second, _third, _unrelated = _context(store)
    source = ops.init("dedun/public-embed-source")
    source_memory = ops.add(source, "live content")
    refs = tuple(
        MemoryRef(
            uid=str(uuid.uuid4()),
            target_context_uid=source.uid,
            target_context_name=source.name,
            target_memory_uid=source_memory.uid,
            target=source_memory,
        )
        for _ in range(2)
    )
    for reference in refs:
        context.add(reference)
    store.save(source)
    store.save(context)
    handoff = _strict_handoffs(
        context,
        DuplicateFinding(
            first,
            second,
            "SEMANTIC_EQUIVALENT",
            "The claims are substitutable.",
        ),
    )[0]
    client = MemCommitClient(root=isolated_store, create=False)

    plan = client.plan_dedun((handoff,))

    assert len(plan.components) == 1
    assert len(plan.exact_item_groups) == 1
    assert plan.exact_item_groups[0].item_kind == "MEMORY_EMBED"
    assert plan.exact_item_groups[0].survivor_uid == refs[0].uid
    receipt = client.apply_dedun(
        plan,
        survivors={plan.components[0].uid: first.uid},
    )
    assert second.uid in receipt.absorbed_uids
    assert refs[1].uid in receipt.absorbed_uids
    current = store.load_direct(context.name)
    assert first.uid in current.memories
    assert second.uid not in current.memories
    assert refs[0].uid in current.memories
    assert refs[1].uid not in current.memories
    assert len(store.list_checkpoints(context.name)) == 1


def test_agent_dedup_replays_revision_and_survivors(isolated_store):
    store = MemoryStore()
    context, first, second, _third, _unrelated = _context(store)
    handoff = _strict_handoffs(
        context,
        DuplicateFinding(
            first,
            second,
            "SEMANTIC_EQUIVALENT",
            "The claims are substitutable.",
        ),
    )[0]
    registry = build_default_agent_tool_registry(
        MemCommitClient(root=isolated_store, create=False)
    )
    public_evidence = redundancy_evidence_dict(handoff)
    assert public_evidence["kind"] == "REDUNDANCY"
    assert public_evidence["route"] == "DEDUN"
    analysis = registry.invoke(
        DEDUP_AGENT_TOOL_NAME,
        {
            "version": 1,
            "kind": "analyze",
            "evidence": [public_evidence],
        },
    )
    assert analysis["ok"] is True
    component = analysis["result"]["components"][0]

    applied = registry.invoke(
        DEDUP_AGENT_TOOL_NAME,
        {
            "version": 1,
            "kind": "apply",
            "evidence": [public_evidence],
            "expected_revision": analysis["result"]["revision"],
            "survivors": [
                {
                    "component_uid": component["uid"],
                    "survivor_uid": second.uid,
                }
            ],
        },
    )
    assert applied["ok"] is True
    assert applied["result"]["survivor_uids"] == [second.uid]


def test_legacy_semantic_evidence_decodes_but_cannot_claim_exact_dup(
    isolated_store,
):
    store = MemoryStore()
    context, first, second, _third, _unrelated = _context(store)
    semantic = _strict_handoffs(
        context,
        DuplicateFinding(
            first,
            second,
            "SEMANTIC_EQUIVALENT",
            "The claims are substitutable.",
        ),
    )[0]
    legacy = redundancy_evidence_dict(semantic)
    legacy["contract"] = "semantic-redundancy-evidence-v1"

    assert redundancy_evidence_from_dict(legacy) == semantic

    legacy["classification"] = "EXACT"
    with pytest.raises(QualityFindingHandoffError, match="classification"):
        redundancy_evidence_from_dict(legacy)


def test_cli_dedun_replay_applies_the_reviewed_survivor(isolated_store):
    store = MemoryStore()
    context, first, second, _third, _unrelated = _context(store)
    handoff = _strict_handoffs(
        context,
        DuplicateFinding(
            first,
            second,
            "SEMANTIC_EQUIVALENT",
            "The claims are substitutable.",
        ),
    )[0]
    plan = prepare_dedun(
        DedunRequest((handoff,)),
        port=MemoryStoreDedunPort(store, current_name=context.name),
    )

    result = runner.invoke(
        app,
        [
            "dedun",
            "--evidence",
            redundancy_evidence_json(handoff),
            "--survivor",
            f"{plan.components[0].uid}={second.uid}",
            "--expected-revision",
            plan.revision,
            "--apply",
        ],
    )

    assert result.exit_code == 0
    assert "DEDUN APPLIED" in result.stdout
    current = store.load_direct(context.name)
    assert first.uid not in current.memories
    assert second.uid in current.memories


def test_exact_discovery_groups_only_same_role_and_exact_provenance(isolated_store):
    store = MemoryStore()
    (
        target,
        owned,
        live_refs,
        snapshot_refs,
        other_snapshot,
        context_snapshots,
    ) = _role_aware_exact_fixture(store)

    current = store.load_for_update(target.name)
    query_refs = tuple(
        QueryContextRef(
            uid=str(uuid.uuid4()),
            name="query-only",
            target_source_uid="opaque-source",
            provider="codex_chatgpt",
        )
        for _ in range(2)
    )
    for reference in query_refs:
        current.add(reference)
    store.save(current)

    groups = find_exact_duplicate_groups(store.load_direct(target.name))

    assert [group.item_kind for group in groups] == [
        "MEMORY_EMBED",
        "MEMORY_REFERENCE",
        "CONTEXT_REFERENCE",
    ]
    assert groups[0].survivor_uid == live_refs[0].uid
    assert groups[0].absorbed_uids == (live_refs[1].uid,)
    assert groups[1].survivor_uid == snapshot_refs[0].uid
    assert groups[1].absorbed_uids == (snapshot_refs[1].uid,)
    assert groups[2].survivor_uid == context_snapshots[0].uid
    assert groups[2].absorbed_uids == (context_snapshots[1].uid,)
    grouped_uids = {
        uid for group in groups for uid in (group.survivor_uid, *group.absorbed_uids)
    }
    assert owned.uid not in grouped_uids
    assert other_snapshot.uid not in grouped_uids
    assert all(reference.uid not in grouped_uids for reference in query_refs)


def test_cli_dedup_removes_same_role_exact_links_in_one_checkpoint(isolated_store):
    store = MemoryStore()
    (
        target,
        owned,
        live_refs,
        snapshot_refs,
        other_snapshot,
        context_snapshots,
    ) = _role_aware_exact_fixture(store)

    result = runner.invoke(app, ["dedup"])

    assert result.exit_code == 0, result.output
    assert "removed 3 exact duplicate direct item(s)" in result.stdout
    current = store.load_direct(target.name)
    assert owned.uid in current.memories
    assert live_refs[0].uid in current.memories
    assert live_refs[1].uid not in current.memories
    assert snapshot_refs[0].uid in current.memories
    assert snapshot_refs[1].uid not in current.memories
    assert other_snapshot.uid in current.memories
    assert context_snapshots[0].uid in current.memories
    assert context_snapshots[1].uid not in current.memories
    checkpoints = store.list_checkpoints(target.name)
    assert len(checkpoints) == 1
    assert checkpoints[0]["args"]["contract"] == "exact-dedup-v2"
    assert [group["item_kind"] for group in checkpoints[0]["args"]["groups"]] == [
        "MEMORY_EMBED",
        "MEMORY_REFERENCE",
        "CONTEXT_REFERENCE",
    ]


def test_cli_dedun_includes_role_aware_dedup_without_cross_role_edges(
    isolated_store,
):
    store = MemoryStore()
    (
        target,
        owned,
        live_refs,
        snapshot_refs,
        other_snapshot,
        context_snapshots,
    ) = _role_aware_exact_fixture(store)

    result = runner.invoke(app, ["dedun"])

    assert result.exit_code == 0, result.output
    assert "absorbed 3 redundant direct item(s)" in result.output
    assert "3 DUP / EXACT links" in result.output
    current = store.load_direct(target.name)
    assert owned.uid in current.memories
    assert live_refs[0].uid in current.memories
    assert snapshot_refs[0].uid in current.memories
    assert other_snapshot.uid in current.memories
    assert context_snapshots[0].uid in current.memories
    assert live_refs[1].uid not in current.memories
    assert snapshot_refs[1].uid not in current.memories
    assert context_snapshots[1].uid not in current.memories
    checkpoints = store.list_checkpoints(target.name)
    assert len(checkpoints) == 1
    assert checkpoints[0]["command"] == "dedun"
    assert checkpoints[0]["args"]["contract"] == "dedun-v3"
    assert checkpoints[0]["args"]["components"] == []
    assert [
        group["item_kind"] for group in checkpoints[0]["args"]["exact_item_groups"]
    ] == ["MEMORY_EMBED", "MEMORY_REFERENCE", "CONTEXT_REFERENCE"]

    review = runner.invoke(
        app,
        [
            "review",
            "dedun",
            "--receipt",
            checkpoints[0]["uid"][:8],
            "--snapshot",
        ],
    )
    assert review.exit_code == 0, review.output
    assert "RESOLVED GROUPS · 3" in review.output
    assert "MEMORY_EMBED" in review.output
    assert "MEMORY_REFERENCE" in review.output
    assert "CONTEXT_REFERENCE" in review.output


def test_cli_dedup_removes_only_exact_content_without_review(isolated_store):
    store = MemoryStore()
    context = ops.init("dedup/exact")
    first = ops.add(context, "1123131")
    surface = ops.add(context, " 1123131 ")
    second = ops.add(context, "1123131")
    store.save(context)
    store.set_current(context.name)

    result = runner.invoke(app, ["dedup"])

    assert result.exit_code == 0
    assert "removed 1 exact duplicate direct item(s)" in result.stdout
    current = store.load_direct(context.name)
    assert first.uid in current.memories
    assert surface.uid in current.memories
    assert second.uid not in current.memories
    assert store.list_checkpoints(context.name)[0]["command"] == "dedup"


def test_cli_dedup_recursive_reports_and_applies_independent_context_frames(
    isolated_store,
):
    store = MemoryStore()
    root = ops.init("dedup/cli-tree")
    root_first = ops.add(root, "root exact")
    root_later = ops.add(root, "root exact")
    child = ops.init("dedup/cli-tree/child")
    child_first = ops.add(child, "child exact")
    child_later = ops.add(child, "child exact")
    store.save(root)
    store.save(child)
    store.set_current(root.name)

    result = runner.invoke(app, ["dedup", root.name, "--recursive"])

    assert result.exit_code == 0, result.output
    assert (
        "removed 2 exact duplicate direct item(s) from 2 of 2 Context(s)"
        in result.output
    )
    assert "recovery: mem undo (one command unit)" in result.output
    assert tuple(store.load_direct(root.name).memories) == (root_first.uid,)
    assert root_later.uid not in store.load_direct(root.name).memories
    assert tuple(store.load_direct(child.name).memories) == (child_first.uid,)
    assert child_later.uid not in store.load_direct(child.name).memories


def test_cli_dedup_rejects_conflicting_common_scope_flags(isolated_store):
    store = MemoryStore()
    context = ops.init("dedup/cli-scope-error")
    store.save(context)
    store.set_current(context.name)

    result = runner.invoke(app, ["dedup", "--direct", "--recursive"])

    assert result.exit_code == 2
    assert "Choose either --direct/-d or --recursive/-r" in result.stderr


def test_help_teaches_exact_dedup_read_only_redundancy_and_applying_dedun():
    root_help = runner.invoke(app, ["--help"])
    dedun_help = runner.invoke(app, ["dedun", "--help"])

    assert root_help.exit_code == 0
    assert "same-role exact duplicates (dup)" in root_help.stdout
    assert "role-aware exact plus direct-Memory" in root_help.stdout
    assert "semantic redundancies (dun)" in root_help.stdout
    assert "find-redundancies" in root_help.stdout
    assert "Report same-role exact direct items" in root_help.stdout
    assert "redundant direct Memories" in root_help.stdout
    assert "changing any Source Context" not in root_help.stdout
    assert "consolidate" not in root_help.stdout
    assert dedun_help.exit_code == 0
    assert "--context" in dedun_help.stdout
    assert "--evidence" not in dedun_help.stdout
    assert "--survivor" not in dedun_help.stdout


def test_public_dedup_uses_the_same_exact_application(isolated_store):
    store = MemoryStore()
    context = ops.init("dedup/public-exact")
    first = ops.add(context, "same bytes")
    second = ops.add(context, "same bytes")
    store.save(context)
    store.set_current(context.name)

    result = MemCommitClient(root=isolated_store, create=False).dedup()

    assert result.removed_count == 1
    assert result.groups[0].survivor_uid == first.uid
    assert result.groups[0].absorbed_uids == (second.uid,)
    assert tuple(store.load_direct(context.name).memories) == (first.uid,)


def test_public_find_duplicates_is_provider_free_and_read_only(isolated_store):
    store = MemoryStore()
    context = ops.init("dedup/public-find-exact")
    first = ops.add(context, "same bytes")
    surface = ops.add(context, " same bytes ")
    second = ops.add(context, "same bytes")
    store.save(context)
    store.set_current(context.name)
    before = store._context_file(context.name).read_bytes()

    result = MemCommitClient(root=isolated_store, create=False).find_duplicates()

    assert result.context_name == context.name
    assert result.memory_count == 3
    assert result.duplicate_count == 1
    assert result.groups[0].survivor_uid == first.uid
    assert result.groups[0].absorbed_uids == (second.uid,)
    assert surface.uid not in result.groups[0].absorbed_uids
    assert store._context_file(context.name).read_bytes() == before
    assert store.list_checkpoints(context.name) == []


def test_public_find_duplicates_projects_role_aware_exact_groups(isolated_store):
    store = MemoryStore()
    target, *_rest = _role_aware_exact_fixture(store)
    before = store._context_file(target.name).read_bytes()

    result = MemCommitClient(root=isolated_store, create=False).find_duplicates()

    assert result.item_count == len(target.ordered_uids())
    assert [group.item_kind for group in result.groups] == [
        "MEMORY_EMBED",
        "MEMORY_REFERENCE",
        "CONTEXT_REFERENCE",
    ]
    assert result.duplicate_count == 3
    assert store._context_file(target.name).read_bytes() == before
    assert store.list_checkpoints(target.name) == []


def test_exact_dedup_blocks_inbound_reference_without_checkpoint(isolated_store):
    store = MemoryStore()
    context = ops.init("dedup/exact-referenced")
    first = ops.add(context, "same bytes")
    second = ops.add(context, "same bytes")
    observer = ops.init("dedup/exact-observer")
    observer.add(
        MemoryRef(
            uid=str(uuid.uuid4()),
            target_context_uid=context.uid,
            target_context_name=context.name,
            target_memory_uid=second.uid,
        )
    )
    store.save(context)
    store.save(observer)
    store.set_current(context.name)

    result = runner.invoke(app, ["dedup"])

    assert result.exit_code == 1
    assert "inbound reference" in result.stderr
    assert tuple(store.load_direct(context.name).memories) == (
        first.uid,
        second.uid,
    )
    assert store.list_checkpoints(context.name) == []


def _granted_dedup_fixture(tmp_path, monkeypatch, permissions):
    monkeypatch.setenv("HOME", str(tmp_path))
    local = MemoryStore()
    attachment = ops.init("workspace")
    local.save(attachment)
    local.set_current(attachment.name)
    grantee = ProfileEntry(
        uid=AUTHORING_PROFILE_UID,
        name=AUTHORING_PROFILE_NAME,
        kind="AUTHORING",
    )
    authority = ProfileEntry(
        uid=str(uuid.uuid4()),
        name="dedup-authority",
        kind="MANAGED",
    )
    authority_store = MemoryStore(root=profile_store_dir(authority))
    target = ops.init("notes")
    first = ops.add(target, "The office opens at eight.")
    second = ops.add(target, "The office opens at 8.")
    authority_store.save(target)
    registry = ProfileRegistry(
        generation=1,
        active_uid=grantee.uid,
        profiles=(grantee, authority),
    )
    path = profile_registry_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry.to_dict()) + "\n", encoding="utf-8")
    _registry, grant = create_authority_grant(
        authority_name=authority.name,
        grantee_name=grantee.name,
        resource_name=target.name,
        attachment_name=attachment.name,
        public_name="shared/notes",
        permissions=permissions,
    )
    handoff = QualityFindingHandoff(
        uid="granted-dedup-handoff",
        finding_uid=f"duplicate:{first.uid}:{second.uid}",
        kind="DUPLICATE",
        route="DEDUP",
        source_frame_digest="b" * 64,
        sources=(
            QualityFindingSource(
                context_uid=target.uid,
                display_name="shared/notes",
                direct_memory_digest=direct_context_digest(target),
            ),
        ),
        memory_uids=(first.uid, second.uid),
        memory_context_names=("shared/notes", "shared/notes"),
        classification="SEMANTIC_EQUIVALENT",
        qualifiers=(),
        reason="The claims are substitutable.",
        question="",
        proposed_readings=(),
        review_draft=QualityFindingReviewDraft(),
    )
    return local, authority_store, target, first, second, grant, handoff


def test_granted_dedup_requires_derive_and_delete_before_review(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    local, _authority_store, target, _first, _second, _grant, handoff = (
        _granted_dedup_fixture(tmp_path, monkeypatch, ("READ", "DERIVE"))
    )

    with pytest.raises(DedunAuthorityError, match="DELETE"):
        prepare_dedun(
            DedunRequest((handoff,)),
            port=MemoryStoreDedunPort(local, current_name="workspace"),
        )

    assert len(target.memories) == 2


def test_granted_dedup_revalidates_delete_through_apply(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    local, authority_store, target, first, second, grant, handoff = (
        _granted_dedup_fixture(
            tmp_path,
            monkeypatch,
            ("READ", "DERIVE", "DELETE"),
        )
    )
    port = MemoryStoreDedunPort(local, current_name="workspace")
    plan = prepare_dedun(DedunRequest((handoff,)), port=port)
    update_authority_grant(grant.uid, permissions=("READ", "DERIVE"))

    with pytest.raises(DedunAuthorityError):
        apply_dedun(plan, recommended_dedun_selections(plan), port=port)

    current = authority_store.load_direct(target.name)
    assert first.uid in current.memories
    assert second.uid in current.memories
