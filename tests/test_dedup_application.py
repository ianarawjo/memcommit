"""Exact Dedup and semantic Dedun planning/application tests."""

from __future__ import annotations

import json
import uuid

import click
import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.api import DedunPlanResult, MemCommitClient
from memcommit.cli import app
from memcommit.commands.quality_find_workbench import (
    run_quality_find_resolution_workbench,
)
from memcommit.context import MemoryRef
from memcommit.dedup_application import (
    DedupAuthorityError,
    DedupConflictError,
    DedupError,
    DedupRequest,
    DedupSelection,
    apply_dedup,
    prepare_dedup,
    recommended_dedup_selections,
)
from memcommit.dedup_runtime import MemoryStoreDedupPort
from memcommit.findings import DuplicateFinding, DuplicateReport
from memcommit.interfaces.agent import (
    DEDUP_AGENT_TOOL_NAME,
    build_default_agent_tool_registry,
)
from memcommit.interfaces.console.theme import (
    SemanticColorRole,
    semantic_color_rgb,
)
from memcommit.interfaces.tui.operations.dedup import (
    dedup_exact_review,
    dedup_resolution_spec,
    run_dedup_tui,
)
from memcommit.interfaces.tui.workbenches.resolution import ResolutionOutcome
from memcommit.quality_find_workbench import create_quality_find_workbench
from memcommit.quality_finding_handoff import (
    QualityFindingHandoff,
    QualityFindingHandoffError,
    QualityFindingReviewDraft,
    QualityFindingSource,
    quality_finding_handoffs,
)
from memcommit.semantic_redundancy_evidence import (
    redundancy_evidence_dict,
    redundancy_evidence_from_dict,
    redundancy_evidence_json,
)
from memcommit.profile_config import (
    AUTHORING_PROFILE_NAME,
    AUTHORING_PROFILE_UID,
    ProfileEntry,
    ProfileRegistry,
    profile_registry_file,
    profile_store_dir,
)
from memcommit.profiles import create_authority_grant, update_authority_grant
from memcommit.review import direct_context_digest
from memcommit.store import MemoryStore


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


def test_dedup_builds_transitive_components_and_keeps_context_order(isolated_store):
    store = MemoryStore()
    context, first, second, third, _unrelated = _context(store)
    request = DedupRequest(
        (
            _handoff(context, second.uid, third.uid, index=1),
            _handoff(context, first.uid, second.uid, index=2),
        )
    )

    plan = prepare_dedup(
        request,
        port=MemoryStoreDedupPort(store, current_name=context.name),
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
    assert recommended_dedup_selections(plan) == (
        DedupSelection(component.uid, first.uid),
    )


def test_dedun_combines_exact_dup_and_semantic_dun_evidence(isolated_store):
    store = MemoryStore()
    context, first, second, third, _unrelated = _context(store)
    request = DedupRequest(
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

    plan = prepare_dedup(
        request,
        port=MemoryStoreDedupPort(store, current_name=context.name),
    )

    assert len(plan.components) == 1
    assert tuple(evidence.relation for evidence in plan.components[0].evidence) == (
        "EXACT",
        "SEMANTIC_EQUIVALENT",
    )


def test_dedup_applies_one_checkpoint_without_rewriting_survivor(isolated_store):
    store = MemoryStore()
    context, first, second, third, unrelated = _context(store)
    request = DedupRequest(
        (
            _handoff(context, first.uid, second.uid, index=1),
            _handoff(context, second.uid, third.uid, index=2),
        )
    )
    port = MemoryStoreDedupPort(store, current_name=context.name)
    plan = prepare_dedup(request, port=port)
    selection = (DedupSelection(plan.components[0].uid, second.uid),)

    receipt = apply_dedup(plan, selection, port=port)

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

    with pytest.raises(DedupError, match="OVERLAP"):
        DedupRequest((_handoff(context, first.uid, second.uid, relation="OVERLAP"),))


def test_dedup_fails_closed_when_source_changes(isolated_store):
    store = MemoryStore()
    context, first, second, _third, _unrelated = _context(store)
    request = DedupRequest((_handoff(context, first.uid, second.uid),))
    port = MemoryStoreDedupPort(store, current_name=context.name)
    plan = prepare_dedup(request, port=port)
    current = store.load_direct(context.name)
    ops.add(current, "A later write.")
    store.save(current)

    with pytest.raises(DedupConflictError, match="changed before Apply"):
        apply_dedup(
            plan,
            recommended_dedup_selections(plan),
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
    request = DedupRequest((_handoff(context, first.uid, second.uid),))
    port = MemoryStoreDedupPort(store, current_name=context.name)
    plan = prepare_dedup(request, port=port)

    with pytest.raises(DedupConflictError, match="inbound references"):
        apply_dedup(
            plan,
            recommended_dedup_selections(plan),
            port=port,
        )

    assert second.uid in store.load_direct(context.name).memories


def test_dedup_requires_one_survivor_for_every_component(isolated_store):
    store = MemoryStore()
    context, first, second, _third, _unrelated = _context(store)
    plan = prepare_dedup(
        DedupRequest((_handoff(context, first.uid, second.uid),)),
        port=MemoryStoreDedupPort(store, current_name=context.name),
    )

    with pytest.raises(DedupError, match="unresolved redundancy groups"):
        apply_dedup(
            plan,
            (),
            port=MemoryStoreDedupPort(store, current_name=context.name),
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
    port = MemoryStoreDedupPort(store, current_name=context.name)
    plan = prepare_dedup(DedupRequest((handoff,)), port=port)
    spec = dedup_resolution_spec(plan)

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
    review = dedup_exact_review(
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
        receipt = run_dedup_tui(
            plan,
            apply_selections=lambda selections: apply_dedup(
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
        pipe_input.send_text("d")
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
            "--plain",
        ],
        color=True,
    )
    assert result.exit_code == 0
    assert public_plan.revision in click.unstyle(result.stdout)
    assert "RECOMMENDED SURVIVOR" in click.unstyle(result.stdout)
    assert click.style(
        "RECOMMENDED SURVIVOR",
        fg=semantic_color_rgb(SemanticColorRole.ADD),
        bold=True,
    ) in result.stdout

    receipt = client.apply_dedun(
        public_plan,
        survivors={public_plan.components[0].uid: second.uid},
    )
    assert receipt.survivor_uids == (second.uid,)
    assert first.uid in receipt.absorbed_uids


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
    plan = prepare_dedup(
        DedupRequest((handoff,)),
        port=MemoryStoreDedupPort(store, current_name=context.name),
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
    assert "removed 1 exact duplicate Memory item(s)" in result.stdout
    current = store.load_direct(context.name)
    assert first.uid in current.memories
    assert surface.uid in current.memories
    assert second.uid not in current.memories
    assert store.list_checkpoints(context.name)[0]["command"] == "dedup"


def test_help_teaches_exact_dedup_read_only_redundancy_and_applying_dedun():
    root_help = runner.invoke(app, ["--help"])
    dedun_help = runner.invoke(app, ["dedun", "--help"])

    assert root_help.exit_code == 0
    assert "byte-identical duplicates (dup)" in root_help.stdout
    assert "exact plus semantic redundancies" in root_help.stdout
    assert "find-redundancies" in root_help.stdout
    assert "Report exact and semantically redundant direct Memories" in root_help.stdout
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

    with pytest.raises(DedupAuthorityError, match="DELETE"):
        prepare_dedup(
            DedupRequest((handoff,)),
            port=MemoryStoreDedupPort(local, current_name="workspace"),
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
    port = MemoryStoreDedupPort(local, current_name="workspace")
    plan = prepare_dedup(DedupRequest((handoff,)), port=port)
    update_authority_grant(grant.uid, permissions=("READ", "DERIVE"))

    with pytest.raises(DedupAuthorityError):
        apply_dedup(plan, recommended_dedup_selections(plan), port=port)

    current = authority_store.load_direct(target.name)
    assert first.uid in current.memories
    assert second.uid in current.memories
