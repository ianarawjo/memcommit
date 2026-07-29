"""Named common-grounding session and CLI scaffold contracts."""
from __future__ import annotations

import json
import uuid
from dataclasses import replace
from pathlib import Path

import pytest
from typer.testing import CliRunner

import memcommit.ops as ops
import memcommit.store as store_module
from memcommit.cli import app
from memcommit.commands.ground import render_ground_snapshot
from memcommit.ground import (
    GroundError,
    GroundItem,
    GroundSession,
    GroundSourceRef,
    GroundTargetSpec,
    accepted_ground_case_count,
    bind_ground_workbench,
    context_frame_digest,
    create_ground_session,
    ground_matches_workbench,
    propose_ground_case,
    propose_ground_round,
    propose_ground_rule,
    review_ground_item,
    revise_ground_goal,
    revise_ground_requirement,
    target_requirement_status,
)
from memcommit.store import MemoryStore


runner = CliRunner()

TASK_1_DESCRIPTION = (
    "Use verified Main Building construction changes from local work memory "
    "to update every affected part of the organizational campus wiki."
)
TASK_1_TARGET_NAMES = (
    "campus-wiki",
    "construction-updates/building-access",
    "construction-updates/event-relocations",
    "construction-updates/temporary-parking",
    "construction-updates/shop-updates",
    "construction-updates/facility-updates",
    "construction-updates/route-changes",
)
TASK_1_TARGET_REQUIREMENTS = tuple(
    GroundTargetSpec(
        context_name=name,
        description=(
            "Establish at least one user-approved, traceable seed case "
            "for this target."
        ),
        role=(
            "PUBLICATION_TARGET"
            if name == "campus-wiki"
            else "PLACEMENT_TARGET"
        ),
        blocked_reason=(
            "The pre-existing campus-wiki baseline fixture is absent."
            if name == "campus-wiki"
            else (
                "Concrete event-relocation destinations are absent."
                if name.endswith("/event-relocations")
                else (
                    "A replacement-parking location is absent."
                    if name.endswith("/temporary-parking")
                    else ""
                )
            )
        ),
    )
    for name in TASK_1_TARGET_NAMES
)


def _task_1_workbench(store: MemoryStore):
    # This helper writes several canonical Task 1 names. Fail loudly if a
    # future test forgets the isolated_store fixture rather than touching the
    # developer's real ~/.mem data again.
    assert store_module.STORE_DIR != Path.home() / ".mem"
    raw = ops.init("temp/task-1")
    ops.add_many(
        raw,
        [
            "The Main Building library-side rear entrance is closed.",
            *[
                f"Raw Task 1 evidence {index:02d}."
                for index in range(2, 52)
            ],
        ],
    )
    derived = ops.init("temp/task-1-atomized")
    derived_memories = ops.add_many(
        derived,
        [
            (
                "The Main Building library-side rear entrance is closed "
                "during construction."
            ),
            *[
                f"Derived Task 1 candidate {index:02d}."
                for index in range(2, 55)
            ],
        ],
    )
    targets = tuple(ops.init(name) for name in TASK_1_TARGET_NAMES)

    for context in (raw, derived, *targets):
        store.save(context)
    store.set_current(raw.name)
    return raw, derived, targets, derived_memories[0]


def _non_ground_store_bytes(root):
    """Capture every persisted artifact except the ground session itself."""
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and "ground-sessions" not in path.parts
    }


def test_empty_ground_session_round_trip_and_method_provenance():
    session = create_ground_session(
        "task-1-fixture",
        goal="Agree on Task 1 wiki and local Memory contents.",
        scope=("campus/wiki", "construction-updates"),
    )

    restored = GroundSession.from_dict(session.to_dict())

    assert restored == session
    assert restored.status == "OPEN"
    assert restored.revision == 0
    assert restored.items == ()
    assert {
        reference.uid for reference in restored.references
    } == {
        "interactive-machine-teaching-ramos-2020",
        "ripple-down-rules-richards-2009",
    }
    assert all(
        reference.provenance
        == "AGENT_SUGGESTED_EXTERNAL_PRECEDENT"
        and reference.reading_status == "UNREAD"
        for reference in restored.references
    )


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("", "must match"),
        ("Task-1", "must match"),
        ("../task-1", "must match"),
        ("task/one", "must match"),
        (".hidden", "must match"),
        ("task one", "must match"),
        ("task.", "must match"),
        ("task\x1b", "must match"),
        ("con", "reserved Windows device name"),
        ("con.txt", "reserved Windows device name"),
        ("a" * 129, "must match"),
    ],
)
def test_ground_contract_name_is_a_portable_non_path_id(name, message):
    with pytest.raises(GroundError, match=message):
        create_ground_session(name)


def test_ground_session_strictly_validates_schema_and_item_links():
    session = create_ground_session("strict-contract")
    data = session.to_dict()
    data["unknown"] = True
    with pytest.raises(GroundError, match="Invalid grounding session"):
        GroundSession.from_dict(data)

    boolean_version = session.to_dict()
    boolean_version["schema_version"] = True
    with pytest.raises(GroundError, match="schema version"):
        GroundSession.from_dict(boolean_version)

    float_version = session.to_dict()
    float_version["schema_version"] = 1.0
    with pytest.raises(GroundError, match="schema version"):
        GroundSession.from_dict(float_version)

    false_approval = session.to_dict()
    false_approval["status"] = "GROUNDED"
    with pytest.raises(GroundError, match="only an empty OPEN"):
        GroundSession.from_dict(false_approval)

    changed_reference = session.to_dict()
    changed_reference["references"][0]["url"] = "https://example.com/"
    with pytest.raises(GroundError, match="invalid method references"):
        GroundSession.from_dict(changed_reference)

    item = GroundItem(
        uid=str(uuid.uuid4()),
        kind="RULE",
        content="A proposed rule.",
        expected="",
        rationale="",
        status="PROPOSED",
        origin="JOINT",
        iteration=1,
        related_uids=("missing",),
    )
    invalid = replace(session, revision=1, items=(item,))
    with pytest.raises(GroundError, match="unknown item"):
        GroundSession.from_dict(invalid.to_dict())

    resolved_rule = replace(item, status="RESOLVED", related_uids=())
    with pytest.raises(GroundError, match="kind/status"):
        GroundItem.from_dict(resolved_rule.to_dict())


def test_store_round_trip_rejects_duplicate_json_and_symlinks(
    isolated_store,
):
    store = MemoryStore()
    session = create_ground_session("stored-contract")
    store.save_ground_session(session)

    assert store.load_ground_session("stored-contract") == session

    path = isolated_store / "ground-sessions" / "stored-contract.json"
    path.write_text('{"uid": "one", "uid": "two"}')
    with pytest.raises(ValueError, match="invalid"):
        store.load_ground_session("stored-contract")

    path.unlink()
    target = isolated_store / "outside.json"
    target.write_text(json.dumps(session.to_dict()))
    path.symlink_to(target)
    with pytest.raises(ValueError, match="invalid"):
        store.load_ground_session("stored-contract")


def test_store_refuses_a_different_uid_without_explicit_replacement(
    isolated_store,
):
    store = MemoryStore(create=False)
    original = create_ground_session("stable-name")
    replacement = create_ground_session("stable-name")
    store.save_ground_session(original)

    with pytest.raises(ValueError, match="different grounding session"):
        store.save_ground_session(replacement)

    assert store.load_ground_session("stable-name").uid == original.uid


def test_store_rejects_a_symbolic_link_grounding_directory(
    isolated_store,
):
    outside = isolated_store.parent / "outside-ground"
    outside.mkdir()
    isolated_store.mkdir()
    (isolated_store / "ground-sessions").symlink_to(
        outside,
        target_is_directory=True,
    )

    with pytest.raises(ValueError, match="cannot be a symbolic link"):
        MemoryStore(create=False).save_ground_session(
            create_ground_session("linked")
        )


def test_cli_creates_resumes_and_snapshots_without_touching_context(
    isolated_store,
):
    store = MemoryStore()
    ctx = ops.init("construction-updates")
    ops.add(ctx, "Existing task Memory.")
    store.save(ctx)
    store.set_current(ctx.name)
    context_path = store._context_file(ctx.name)
    context_before = context_path.read_bytes()
    state_before = (isolated_store / "state.json").read_bytes()
    checkpoints_before = store.list_checkpoints(ctx.name)

    created = runner.invoke(
        app,
        [
            "ground",
            "task-1-fixture",
            "--goal",
            "Agree on wiki and local Task 1 Memories.",
            "--scope",
            "campus/wiki",
            "--scope",
            "construction-updates",
            "--snapshot",
        ],
    )

    assert created.exit_code == 0, created.output
    assert "GROUND · task-1-fixture · OPEN" in created.output
    assert "RULES 0 · CASES 0 · UNRESOLVED 0 · DECISIONS 0" in created.output
    assert "Interactive machine teaching" in created.output
    assert "agent-suggested" in created.output
    path = (
        isolated_store
        / "ground-sessions"
        / "task-1-fixture.json"
    )
    before_resume = path.read_bytes()
    uid = store.load_ground_session("task-1-fixture").uid

    resumed = runner.invoke(
        app,
        ["ground", "task-1-fixture", "--snapshot"],
    )

    assert resumed.exit_code == 0, resumed.output
    assert store.load_ground_session("task-1-fixture").uid == uid
    assert path.read_bytes() == before_resume
    assert context_path.read_bytes() == context_before
    assert (isolated_store / "state.json").read_bytes() == state_before
    assert store.list_checkpoints(ctx.name) == checkpoints_before


def test_cli_ground_does_not_create_context_state_in_a_fresh_store(
    isolated_store,
):
    assert not isolated_store.exists()

    result = runner.invoke(
        app,
        ["ground", "standalone-contract", "--snapshot"],
    )

    assert result.exit_code == 0, result.output
    assert (
        isolated_store
        / "ground-sessions"
        / "standalone-contract.json"
    ).is_file()
    assert not (isolated_store / "state.json").exists()
    assert not (isolated_store / "contexts").exists()


def test_cli_keeps_named_sessions_independent_and_refuses_silent_redefinition(
    isolated_store,
):
    first = runner.invoke(app, ["ground", "task-1-fixture"])
    second = runner.invoke(app, ["ground", "task-2-fixture"])

    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    assert (
        isolated_store / "ground-sessions" / "task-1-fixture.json"
    ).exists()
    assert (
        isolated_store / "ground-sessions" / "task-2-fixture.json"
    ).exists()

    refused = runner.invoke(
        app,
        [
            "ground",
            "task-1-fixture",
            "--goal",
            "Silently redefine the goal.",
        ],
    )
    assert refused.exit_code == 1
    assert "--replace-ground" in refused.output


def test_explicit_replace_recovers_a_malformed_named_session(
    isolated_store,
):
    store = MemoryStore()
    original = create_ground_session("recoverable")
    store.save_ground_session(original)
    path = isolated_store / "ground-sessions" / "recoverable.json"
    path.write_text("{invalid")

    recovered = runner.invoke(
        app,
        [
            "ground",
            "recoverable",
            "--replace-ground",
            "--goal",
            "A recovered empty contract.",
            "--snapshot",
        ],
    )

    assert recovered.exit_code == 0, recovered.output
    restored = store.load_ground_session("recoverable")
    assert restored.uid != original.uid
    assert restored.goal == "A recovered empty contract."


def test_malformed_session_is_preserved_without_explicit_replace(
    isolated_store,
):
    path = isolated_store / "ground-sessions" / "malformed.json"
    path.parent.mkdir(parents=True)
    path.write_text("{invalid")
    before = path.read_bytes()

    refused = runner.invoke(
        app,
        ["ground", "malformed", "--snapshot"],
    )

    assert refused.exit_code == 1
    assert "invalid" in refused.output
    assert path.read_bytes() == before


def test_ground_snapshot_sanitizes_terminal_control_characters():
    session = create_ground_session(
        "safe-output",
        goal="Visible\x1b[31m text",
    )

    rendered = render_ground_snapshot(session)

    assert "\x1b" not in rendered
    assert "Visible�[31m text" in rendered


def test_task_1_workbench_binds_empty_target_contract_above_51_to_54_frame(
    isolated_store,
):
    store = MemoryStore()
    raw, derived, targets, _ = _task_1_workbench(store)
    storage_before = _non_ground_store_bytes(isolated_store)
    session = create_ground_session(
        "task-1-fixture",
        goal="Agree on Task 1 wiki and local fixture contents.",
        scope=TASK_1_TARGET_NAMES,
    )

    bound = bind_ground_workbench(
        session,
        description=TASK_1_DESCRIPTION,
        raw_context=raw,
        derived_context=derived,
        target_contexts=targets,
        target_requirements=TASK_1_TARGET_REQUIREMENTS,
    )

    assert session.revision == 0
    assert session.items == ()
    assert bound.revision == 0
    assert bound.items == ()
    assert ground_matches_workbench(
        bound,
        (raw, derived, *targets),
    )

    payload = bound.to_dict()
    assert payload["schema_version"] == 2
    assert payload["brief"]["content"] == TASK_1_DESCRIPTION
    raw_frame, derived_frame, *target_frames = payload["frames"]
    assert raw_frame == {
        "role": "RAW_EVIDENCE",
        "context_uid": raw.uid,
        "context_name": raw.name,
        "context_digest": context_frame_digest(raw),
        "direct_memory_count": 51,
        "direct_item_count": 51,
    }
    assert derived_frame == {
        "role": "WORKING_CANDIDATES",
        "context_uid": derived.uid,
        "context_name": derived.name,
        "context_digest": context_frame_digest(derived),
        "direct_memory_count": 54,
        "direct_item_count": 54,
    }
    assert [
        frame["context_name"] for frame in target_frames
    ] == list(TASK_1_TARGET_NAMES)
    assert all(
        frame["direct_memory_count"] == 0
        for frame in target_frames
    )

    snapshot = render_ground_snapshot(bound, (raw, derived, *targets))
    assert "GOAL SUCCESS CRITERIA" in snapshot
    assert "WORKBENCH" in snapshot
    assert "RAW" in snapshot
    assert "temp/task-1" in snapshot
    assert "51" in snapshot
    assert "DERIVED" in snapshot
    assert "temp/task-1-atomized" in snapshot
    assert "54" in snapshot
    assert "TARGETS 7" in snapshot
    assert "EMPTY" in snapshot
    assert "event-relocation destinations" in snapshot
    for name in TASK_1_TARGET_NAMES:
        assert name in snapshot

    store.save_ground_session(bound)
    restored = store.load_ground_session("task-1-fixture")
    assert restored is not None
    assert restored.to_dict() == bound.to_dict()
    assert _non_ground_store_bytes(isolated_store) == storage_before


def test_one_proposed_ground_round_persists_revision_without_applying_contexts(
    isolated_store,
):
    store = MemoryStore()
    raw, derived, targets, candidate = _task_1_workbench(store)
    target_before = {
        context.name: context.to_dict()
        for context in targets
    }
    storage_before = _non_ground_store_bytes(isolated_store)
    session = bind_ground_workbench(
        create_ground_session("task-1-fixture"),
        description=TASK_1_DESCRIPTION,
        raw_context=raw,
        derived_context=derived,
        target_contexts=targets,
        target_requirements=TASK_1_TARGET_REQUIREMENTS,
    )
    store.save_ground_session(session)

    revised = propose_ground_round(
        session,
        rule=(
            "Publish operational access guidance in campus-wiki and retain "
            "its verified local fact in the matching construction child."
        ),
        case=candidate.content,
        source_context_uid=derived.uid,
        source_memory_uid=candidate.uid,
        target_context_names=(
            "campus-wiki",
            "construction-updates/building-access",
        ),
        expected=(
            "Keep one atomic building-access Memory and publish the "
            "corresponding visitor guidance."
        ),
        rationale=(
            "The candidate is a verified access change with both a local "
            "source role and an organizational publication role."
        ),
        current_contexts=(raw, derived, *targets),
    )

    assert session.revision == 0
    assert session.items == ()
    assert revised.revision == 1
    assert revised.status == "OPEN"
    assert [item.kind for item in revised.items] == ["RULE", "CASE"]
    assert all(item.status == "PROPOSED" for item in revised.items)
    rule, case = revised.items
    assert rule.related_uids == (case.uid,)
    assert case.related_uids == (rule.uid,)
    assert case.source_refs[0].context_uid == derived.uid
    assert case.source_refs[0].memory_uid == candidate.uid
    target_name_by_uid = {
        frame.context_uid: frame.context_name
        for frame in revised.frames
    }
    assert tuple(
        target_name_by_uid[uid] for uid in case.target_context_uids
    ) == (
        "campus-wiki",
        "construction-updates/building-access",
    )
    assert case.expected.startswith("Keep one atomic")
    assert case.rationale.startswith("The candidate is a verified")
    round_snapshot = render_ground_snapshot(
        revised,
        (raw, derived, *targets),
    )
    assert "2 · WORKING RULES" in round_snapshot
    assert "[PROPOSED · INDUCED_FROM_CASES]" in round_snapshot
    assert "3 · CASES · FIT / BOUNDARY / CONTRAST" in round_snapshot
    assert "[PROPOSED · FIT · INCLUDE]" in round_snapshot
    assert candidate.content in round_snapshot
    assert "campus-wiki" in round_snapshot
    assert "construction-updates/building-access" in round_snapshot

    store.save_ground_session(revised)
    restored = store.load_ground_session("task-1-fixture")
    assert restored is not None
    assert restored.to_dict() == revised.to_dict()
    assert restored.revision == 1
    assert [
        item.kind for item in restored.items
    ] == ["RULE", "CASE"]

    assert {
        context.name: context.to_dict()
        for context in targets
    } == target_before
    assert _non_ground_store_bytes(isolated_store) == storage_before
    assert all(
        store.list_checkpoints(context.name) == []
        for context in targets
    )


def test_ground_round_refuses_a_stale_bound_frame_and_preserves_saved_revision(
    isolated_store,
):
    store = MemoryStore()
    raw, derived, targets, candidate = _task_1_workbench(store)
    session = bind_ground_workbench(
        create_ground_session("task-1-fixture"),
        description=TASK_1_DESCRIPTION,
        raw_context=raw,
        derived_context=derived,
        target_contexts=targets,
        target_requirements=TASK_1_TARGET_REQUIREMENTS,
    )
    store.save_ground_session(session)
    session_path = (
        isolated_store
        / "ground-sessions"
        / "task-1-fixture.json"
    )
    session_before = session_path.read_bytes()
    targets_before = {
        context.name: context.to_dict()
        for context in targets
    }

    derived.replace(
        type(candidate)(
            uid=candidate.uid,
            content="The candidate changed after the grounding frame.",
        )
    )

    assert not ground_matches_workbench(
        session,
        (raw, derived, *targets),
    )
    with pytest.raises(GroundError, match="[Ss]tale"):
        propose_ground_round(
            session,
            rule="A rule that must not be recorded against a stale frame.",
            case=candidate.content,
            source_context_uid=derived.uid,
            source_memory_uid=candidate.uid,
            target_context_names=("campus-wiki",),
            expected="No result is saved.",
            rationale="The complete bound frame changed.",
            current_contexts=(raw, derived, *targets),
        )

    assert session_path.read_bytes() == session_before
    restored = store.load_ground_session("task-1-fixture")
    assert restored is not None
    assert restored.revision == 0
    assert restored.items == ()
    assert {
        context.name: context.to_dict()
        for context in targets
    } == targets_before


def test_context_frame_digest_covers_identity_order_and_direct_memory_content():
    first = ops.init("frame")
    memories = ops.add_many(first, ["Alpha.", "Beta."])
    original = context_frame_digest(first)

    reordered = ops.init(first.name)
    reordered.uid = first.uid
    reordered.add(memories[1])
    reordered.add(memories[0])
    renamed = ops.init("renamed")
    renamed.uid = first.uid
    renamed.add(memories[0])
    renamed.add(memories[1])
    recreated = ops.init(first.name)
    recreated.add(memories[0])
    recreated.add(memories[1])

    assert len(original) == 64
    assert set(original) <= set("0123456789abcdef")
    assert context_frame_digest(reordered) != original
    assert context_frame_digest(renamed) != original
    assert context_frame_digest(recreated) != original


def test_target_contract_can_be_revised_from_an_awkward_lower_case(
    isolated_store,
):
    store = MemoryStore()
    raw, derived, targets, _ = _task_1_workbench(store)
    session = bind_ground_workbench(
        create_ground_session("task-1-fixture"),
        description=TASK_1_DESCRIPTION,
        raw_context=raw,
        derived_context=derived,
        target_contexts=targets,
        target_requirements=TASK_1_TARGET_REQUIREMENTS,
    )

    revised = revise_ground_requirement(
        session,
        "construction-updates/event-relocations",
        description=(
            "Retain verified event closure or relocation effects; a concrete "
            "destination is required only when the source asserts relocation."
        ),
        blocked_reason="",
        reason=(
            "The lower evidence includes event closures but does not support "
            "requiring a relocated destination for every event case."
        ),
        current_contexts=(raw, derived, *targets),
    )

    assert revised.revision == 1
    requirement = next(
        requirement
        for requirement in revised.requirements
        if next(
            frame.context_name
            for frame in revised.frames
            if frame.context_uid == requirement.target_context_uid
        )
        == "construction-updates/event-relocations"
    )
    assert requirement.blocked_reason == ""
    assert "only when the source asserts relocation" in requirement.description
    assert revised.items[-1].kind == "DECISION"
    assert revised.items[-1].related_uids == (requirement.uid,)


def test_goal_rules_and_cases_converge_bidirectionally_without_applying_targets(
    isolated_store,
):
    store = MemoryStore()
    raw, derived, targets, candidate = _task_1_workbench(store)
    contexts = (raw, derived, *targets)
    target_before = {
        context.name: context.to_dict()
        for context in targets
    }
    session = bind_ground_workbench(
        create_ground_session(
            "task-1-fixture",
            goal="Place verified changes in seven fixed target slots.",
        ),
        description=TASK_1_DESCRIPTION,
        raw_context=raw,
        derived_context=derived,
        target_contexts=targets,
        target_requirements=TASK_1_TARGET_REQUIREMENTS,
    )
    proposed = propose_ground_round(
        session,
        rule="Publish every verified access change.",
        case=candidate.content,
        source_context_uid=derived.uid,
        source_memory_uid=candidate.uid,
        target_context_names=(
            "construction-updates/building-access",
        ),
        expected="Retain the rear-entrance closure as building access.",
        rationale="The source describes a direct access effect.",
        current_contexts=contexts,
        rule_provenance="DISTILLED_FROM_GOAL",
    )
    rule, case = proposed.items

    refined_rule = review_ground_item(
        proposed,
        rule.uid,
        action="REFINE",
        response=(
            "Publish supported campus-facing effects; preserve unresolved "
            "timing instead of inventing it."
        ),
        current_contexts=contexts,
    )
    current_rule = next(
        item for item in refined_rule.items if item.uid == rule.uid
    )
    assert current_rule.status == "PROPOSED"
    assert current_rule.rule_provenance == "JOINTLY_REVISED"

    accepted_rule = review_ground_item(
        refined_rule,
        rule.uid,
        action="ACCEPT",
        current_contexts=contexts,
    )
    accepted_case = review_ground_item(
        accepted_rule,
        case.uid,
        action="ACCEPT",
        current_contexts=contexts,
    )
    revised_goal = revise_ground_goal(
        accepted_case,
        (
            "Build traceable local update fixtures and a supported public "
            "wiki update without filling evidence gaps by invention."
        ),
        reason=(
            "The lower case showed that preserving unresolved scope is part "
            "of the Goal, not merely a wording detail."
        ),
        current_contexts=contexts,
    )

    assert revised_goal.revision == 5
    assert revised_goal.items[-1].content == "REFINE GOAL"
    assert revised_goal.items[-1].related_uids == ()
    building_frame = next(
        frame
        for frame in revised_goal.frames
        if frame.context_name
        == "construction-updates/building-access"
    )
    building_requirement = next(
        requirement
        for requirement in revised_goal.requirements
        if requirement.target_context_uid == building_frame.context_uid
    )
    assert (
        target_requirement_status(revised_goal, building_requirement)
        == "COVERED"
    )
    assert {
        context.name: context.to_dict()
        for context in targets
    } == target_before
    assert all(
        store.list_checkpoints(context.name) == []
        for context in targets
    )


def test_cli_binds_proposes_accepts_and_revises_goal_in_named_workbench(
    isolated_store,
):
    store = MemoryStore()
    raw, derived, targets, candidate = _task_1_workbench(store)
    target_by_name = {target.name: target for target in targets}
    selected_targets = (
        target_by_name["campus-wiki"],
        target_by_name["construction-updates/building-access"],
    )
    context_bytes_before = {
        context.name: store._context_file(context.name).read_bytes()
        for context in (raw, derived, *selected_targets)
    }
    checkpoints_before = {
        context.name: store.list_checkpoints(context.name)
        for context in (raw, derived, *selected_targets)
    }

    bound = runner.invoke(
        app,
        [
            "ground",
            "task-1-cli",
            "--goal",
            "Build the Task 1 source and publication fixtures.",
            "--description",
            TASK_1_DESCRIPTION,
            "--raw-context",
            raw.name,
            "--derived-context",
            derived.name,
            "--publication-target",
            "campus-wiki",
            "--placement-target",
            "construction-updates/building-access",
            "--blocked-target",
            "campus-wiki=The baseline wiki fixture is absent.",
            "--snapshot",
        ],
    )
    assert bound.exit_code == 0, bound.output
    assert "1 · GOAL · EDITABLE CONTRACT" in bound.output
    assert "2 · WORKING RULES" in bound.output
    assert "3 · CASES · FIT / BOUNDARY / CONTRAST" in bound.output

    proposed = runner.invoke(
        app,
        [
            "ground",
            "task-1-cli",
            "--propose-source",
            candidate.uid[:8],
            "--propose-rule",
            "Publish supported access effects without inventing timing.",
            "--rule-provenance",
            "DISTILLED_FROM_GOAL",
            "--propose-target",
            "construction-updates/building-access",
            "--expected",
            "Retain the rear-entrance closure as building access.",
            "--rationale",
            "The source describes a direct access effect.",
        ],
    )
    assert proposed.exit_code == 0, proposed.output
    session = store.load_ground_session("task-1-cli")
    assert session is not None and session.revision == 1
    rule = next(item for item in session.items if item.kind == "RULE")
    case = next(item for item in session.items if item.kind == "CASE")

    accepted_rule = runner.invoke(
        app,
        [
            "ground",
            "task-1-cli",
            "--decide",
            rule.uid[:8],
            "--action",
            "ACCEPT",
        ],
    )
    assert accepted_rule.exit_code == 0, accepted_rule.output

    accepted_case = runner.invoke(
        app,
        [
            "ground",
            "task-1-cli",
            "--decide",
            case.uid[:8],
            "--action",
            "ACCEPT",
        ],
    )
    assert accepted_case.exit_code == 0, accepted_case.output

    goal_changed = runner.invoke(
        app,
        [
            "ground",
            "task-1-cli",
            "--revise-goal",
            (
                "Build traceable source and publication fixtures without "
                "filling evidence gaps by invention."
            ),
            "--change-reason",
            "The reviewed case exposed preservation of gaps as a Goal.",
            "--snapshot",
        ],
    )
    assert goal_changed.exit_code == 0, goal_changed.output
    assert "Revision: 4" in goal_changed.output
    assert "without filling evidence gaps by invention" in goal_changed.output
    assert "[COVERED]" in goal_changed.output

    assert {
        context.name: store._context_file(context.name).read_bytes()
        for context in (raw, derived, *selected_targets)
    } == context_bytes_before
    assert {
        context.name: store.list_checkpoints(context.name)
        for context in (raw, derived, *selected_targets)
    } == checkpoints_before


def test_one_working_rule_can_hold_multiple_fit_and_boundary_cases(
    isolated_store,
):
    store = MemoryStore()
    raw, derived, targets, first_candidate = _task_1_workbench(store)
    contexts = (raw, derived, *targets)
    session = bind_ground_workbench(
        create_ground_session("reusable-rule"),
        description=TASK_1_DESCRIPTION,
        raw_context=raw,
        derived_context=derived,
        target_contexts=targets,
        target_requirements=TASK_1_TARGET_REQUIREMENTS,
    )
    with_rule = propose_ground_rule(
        session,
        rule="Preserve supported access changes without inventing scope.",
        rationale="This rule is distilled from the top-level Goal.",
        current_contexts=contexts,
        rule_provenance="DISTILLED_FROM_GOAL",
    )
    rule = next(item for item in with_rule.items if item.kind == "RULE")
    second_candidate = tuple(
        item for item in derived.iter_items() if hasattr(item, "content")
    )[1]
    with_fit = propose_ground_case(
        with_rule,
        rule_selector=rule.uid[:8],
        case=first_candidate.content,
        source_context_uid=derived.uid,
        source_memory_uid=first_candidate.uid,
        target_context_names=(
            "construction-updates/building-access",
        ),
        expected="Retain the supported entrance closure.",
        rationale="This is an ordinary case that fits the rule.",
        current_contexts=contexts,
        case_role="FIT",
    )
    with_boundary = propose_ground_case(
        with_fit,
        rule_selector=rule.uid[:8],
        case=second_candidate.content,
        source_context_uid=derived.uid,
        source_memory_uid=second_candidate.uid,
        target_context_names=(
            "construction-updates/building-access",
        ),
        expected="Keep this candidate unresolved at the boundary.",
        rationale="This case tests where the current rule stops.",
        current_contexts=contexts,
        case_role="BOUNDARY",
        disposition="UNRESOLVED",
    )

    rules = with_boundary.items_of_kind("RULE")
    cases = with_boundary.items_of_kind("CASE")
    assert len(rules) == 1
    assert len(cases) == 2
    assert rules[0].related_uids == tuple(case.uid for case in cases)
    assert all(case.related_uids == (rule.uid,) for case in cases)
    assert [case.case_role for case in cases] == ["FIT", "BOUNDARY"]


@pytest.mark.parametrize("disposition", ["EXCLUDE", "UNRESOLVED"])
def test_accepted_non_include_case_never_covers_a_target(
    isolated_store,
    disposition,
):
    store = MemoryStore()
    raw, derived, targets, candidate = _task_1_workbench(store)
    contexts = (raw, derived, *targets)
    session = bind_ground_workbench(
        create_ground_session(f"no-coverage-{disposition.casefold()}"),
        description=TASK_1_DESCRIPTION,
        raw_context=raw,
        derived_context=derived,
        target_contexts=targets,
        target_requirements=TASK_1_TARGET_REQUIREMENTS,
    )
    proposed = propose_ground_round(
        session,
        rule="Only supported items may be included.",
        case=candidate.content,
        source_context_uid=derived.uid,
        source_memory_uid=candidate.uid,
        target_context_names=(
            "construction-updates/building-access",
        ),
        expected="",
        rationale="The candidate does not establish an includable placement.",
        current_contexts=contexts,
        disposition=disposition,
    )
    rule, case = proposed.items
    accepted_rule = review_ground_item(
        proposed,
        rule.uid,
        action="ACCEPT",
        current_contexts=contexts,
    )
    accepted_case = review_ground_item(
        accepted_rule,
        case.uid,
        action="ACCEPT",
        current_contexts=contexts,
    )
    requirement = next(
        requirement
        for requirement in accepted_case.requirements
        if next(
            frame.context_name
            for frame in accepted_case.frames
            if frame.context_uid == requirement.target_context_uid
        )
        == "construction-updates/building-access"
    )

    assert accepted_ground_case_count(
        accepted_case,
        requirement.target_context_uid,
    ) == 0
    assert target_requirement_status(accepted_case, requirement) == "EMPTY"


def test_accepted_case_requires_an_accepted_rule_for_coverage(
    isolated_store,
):
    store = MemoryStore()
    raw, derived, targets, candidate = _task_1_workbench(store)
    contexts = (raw, derived, *targets)
    proposed = propose_ground_round(
        bind_ground_workbench(
            create_ground_session("rule-gated-coverage"),
            description=TASK_1_DESCRIPTION,
            raw_context=raw,
            derived_context=derived,
            target_contexts=targets,
            target_requirements=TASK_1_TARGET_REQUIREMENTS,
        ),
        rule="Publish supported access effects.",
        case=candidate.content,
        source_context_uid=derived.uid,
        source_memory_uid=candidate.uid,
        target_context_names=(
            "construction-updates/building-access",
        ),
        expected="Retain the entrance closure.",
        rationale="This candidate is an access effect.",
        current_contexts=contexts,
    )
    rule, case = proposed.items
    case_only = review_ground_item(
        proposed,
        case.uid,
        action="ACCEPT",
        current_contexts=contexts,
    )
    requirement = next(
        requirement
        for requirement in case_only.requirements
        if next(
            frame.context_name
            for frame in case_only.frames
            if frame.context_uid == requirement.target_context_uid
        )
        == "construction-updates/building-access"
    )
    assert target_requirement_status(case_only, requirement) == "EMPTY"

    rule_and_case = review_ground_item(
        case_only,
        rule.uid,
        action="ACCEPT",
        current_contexts=contexts,
    )
    assert target_requirement_status(rule_and_case, requirement) == "COVERED"


def test_refining_an_accepted_rule_reopens_it_and_drops_derived_coverage(
    isolated_store,
):
    store = MemoryStore()
    raw, derived, targets, candidate = _task_1_workbench(store)
    contexts = (raw, derived, *targets)
    proposed = propose_ground_round(
        bind_ground_workbench(
            create_ground_session("reopen-rule"),
            description=TASK_1_DESCRIPTION,
            raw_context=raw,
            derived_context=derived,
            target_contexts=targets,
            target_requirements=TASK_1_TARGET_REQUIREMENTS,
        ),
        rule="Publish all access changes.",
        case=candidate.content,
        source_context_uid=derived.uid,
        source_memory_uid=candidate.uid,
        target_context_names=(
            "construction-updates/building-access",
        ),
        expected="Retain the entrance closure.",
        rationale="The candidate is an access effect.",
        current_contexts=contexts,
    )
    rule, case = proposed.items
    accepted = review_ground_item(
        review_ground_item(
            proposed,
            rule.uid,
            action="ACCEPT",
            current_contexts=contexts,
        ),
        case.uid,
        action="ACCEPT",
        current_contexts=contexts,
    )
    requirement = next(
        requirement
        for requirement in accepted.requirements
        if next(
            frame.context_name
            for frame in accepted.frames
            if frame.context_uid == requirement.target_context_uid
        )
        == "construction-updates/building-access"
    )
    assert target_requirement_status(accepted, requirement) == "COVERED"

    reopened = review_ground_item(
        accepted,
        rule.uid,
        action="REFINE",
        response="Publish only supported campus-facing access changes.",
        current_contexts=contexts,
    )
    reopened_rule = next(
        item for item in reopened.items if item.uid == rule.uid
    )
    assert reopened_rule.status == "PROPOSED"
    assert reopened_rule.rule_provenance == "JOINTLY_REVISED"
    assert target_requirement_status(reopened, requirement) == "EMPTY"


def test_duplicate_accepted_cases_from_one_source_count_as_one_evidence(
    isolated_store,
):
    store = MemoryStore()
    raw, derived, targets, candidate = _task_1_workbench(store)
    contexts = (raw, derived, *targets)
    with_rule = propose_ground_rule(
        bind_ground_workbench(
            create_ground_session("deduplicated-coverage"),
            description=TASK_1_DESCRIPTION,
            raw_context=raw,
            derived_context=derived,
            target_contexts=targets,
            target_requirements=TASK_1_TARGET_REQUIREMENTS,
        ),
        rule="Preserve each supported access fact once.",
        rationale="Coverage should represent unique source evidence.",
        current_contexts=contexts,
    )
    rule = with_rule.items_of_kind("RULE")[0]
    with_first_case = propose_ground_case(
        with_rule,
        rule_selector=rule.uid,
        case=candidate.content,
        source_context_uid=derived.uid,
        source_memory_uid=candidate.uid,
        target_context_names=(
            "construction-updates/building-access",
        ),
        expected="Publish the supported entrance closure.",
        rationale="This is the first review of the candidate.",
        current_contexts=contexts,
    )
    with_duplicate_case = propose_ground_case(
        with_first_case,
        rule_selector=rule.uid,
        case=candidate.content,
        source_context_uid=derived.uid,
        source_memory_uid=candidate.uid,
        target_context_names=(
            "construction-updates/building-access",
        ),
        expected="Publish the same supported entrance closure.",
        rationale="This deliberately repeats the same source evidence.",
        current_contexts=contexts,
    )
    cases = with_duplicate_case.items_of_kind("CASE")
    accepted = review_ground_item(
        with_duplicate_case,
        rule.uid,
        action="ACCEPT",
        current_contexts=contexts,
    )
    for case in cases:
        accepted = review_ground_item(
            accepted,
            case.uid,
            action="ACCEPT",
            current_contexts=contexts,
        )
    requirement = next(
        requirement
        for requirement in accepted.requirements
        if next(
            frame.context_name
            for frame in accepted.frames
            if frame.context_uid == requirement.target_context_uid
        )
        == "construction-updates/building-access"
    )

    assert len(
        [
            case
            for case in accepted.items_of_kind("CASE")
            if case.status == "ACCEPTED"
        ]
    ) == 2
    assert accepted_ground_case_count(
        accepted,
        requirement.target_context_uid,
    ) == 1
    assert target_requirement_status(accepted, requirement) == "COVERED"


def test_legacy_representative_case_loads_as_fit(
    isolated_store,
):
    store = MemoryStore()
    raw, derived, targets, candidate = _task_1_workbench(store)
    proposed = propose_ground_round(
        bind_ground_workbench(
            create_ground_session("legacy-case-role"),
            description=TASK_1_DESCRIPTION,
            raw_context=raw,
            derived_context=derived,
            target_contexts=targets,
            target_requirements=TASK_1_TARGET_REQUIREMENTS,
        ),
        rule="Preserve supported access changes.",
        case=candidate.content,
        source_context_uid=derived.uid,
        source_memory_uid=candidate.uid,
        target_context_names=("campus-wiki",),
        expected="Publish the supported closure.",
        rationale="The case predates the FIT label.",
        current_contexts=(raw, derived, *targets),
    )
    payload = proposed.to_dict()
    case_payload = next(
        item for item in payload["items"] if item["kind"] == "CASE"
    )
    case_payload["case_role"] = "REPRESENTATIVE"

    restored = GroundSession.from_dict(payload)

    assert restored.items_of_kind("CASE")[0].case_role == "FIT"


def test_snapshot_marks_an_explicitly_loaded_empty_frame_set_stale(
    isolated_store,
):
    store = MemoryStore()
    raw, derived, targets, _ = _task_1_workbench(store)
    bound = bind_ground_workbench(
        create_ground_session("missing-frames"),
        description=TASK_1_DESCRIPTION,
        raw_context=raw,
        derived_context=derived,
        target_contexts=targets,
        target_requirements=TASK_1_TARGET_REQUIREMENTS,
    )

    snapshot = render_ground_snapshot(bound, ())

    assert "OPEN · STALE" in snapshot
    assert "STALE FRAMES" in snapshot
    assert raw.name in snapshot
    assert derived.name in snapshot


def test_forged_case_text_or_source_reference_marks_workbench_stale(
    isolated_store,
):
    store = MemoryStore()
    raw, derived, targets, candidate = _task_1_workbench(store)
    contexts = (raw, derived, *targets)
    proposed = propose_ground_round(
        bind_ground_workbench(
            create_ground_session("forged-source"),
            description=TASK_1_DESCRIPTION,
            raw_context=raw,
            derived_context=derived,
            target_contexts=targets,
            target_requirements=TASK_1_TARGET_REQUIREMENTS,
        ),
        rule="Preserve supported access changes.",
        case=candidate.content,
        source_context_uid=derived.uid,
        source_memory_uid=candidate.uid,
        target_context_names=("campus-wiki",),
        expected="Publish the supported closure.",
        rationale="The case must remain content-addressed.",
        current_contexts=contexts,
    )
    rule, case = proposed.items
    forged_case = replace(case, content="A substituted, unsupported case.")
    forged = replace(proposed, items=(rule, forged_case))
    forged = GroundSession.from_dict(forged.to_dict())

    assert not ground_matches_workbench(forged, contexts)

    random_source = replace(
        case,
        source_refs=(
            GroundSourceRef(
                context_uid=derived.uid,
                memory_uid=str(uuid.uuid4()),
                content_digest=case.source_refs[0].content_digest,
            ),
        ),
    )
    forged_ref = GroundSession.from_dict(
        replace(proposed, items=(rule, random_source)).to_dict()
    )
    assert not ground_matches_workbench(forged_ref, contexts)


def test_forged_frame_counts_and_nonexistent_cursor_mark_workbench_stale(
    isolated_store,
):
    store = MemoryStore()
    raw, derived, targets, _ = _task_1_workbench(store)
    contexts = (raw, derived, *targets)
    bound = bind_ground_workbench(
        create_ground_session("forged-frame-counts"),
        description=TASK_1_DESCRIPTION,
        raw_context=raw,
        derived_context=derived,
        target_contexts=targets,
        target_requirements=TASK_1_TARGET_REQUIREMENTS,
    )
    payload = bound.to_dict()
    working_frame = next(
        frame
        for frame in payload["frames"]
        if frame["role"] == "WORKING_CANDIDATES"
    )
    real_candidate_count = working_frame["direct_memory_count"]
    working_frame["direct_memory_count"] += 1
    working_frame["direct_item_count"] += 1
    # This cursor exists only according to the forged count, not in the
    # current working-candidate Context.
    payload["cursor_position"] = real_candidate_count

    forged = GroundSession.from_dict(payload)

    assert forged.cursor_position == real_candidate_count
    assert not ground_matches_workbench(forged, contexts)
    assert "OPEN · STALE" in render_ground_snapshot(forged, contexts)


def test_revision_zero_cannot_contain_grounding_items(
    isolated_store,
):
    store = MemoryStore()
    raw, derived, targets, _ = _task_1_workbench(store)
    contexts = (raw, derived, *targets)
    proposed = propose_ground_rule(
        bind_ground_workbench(
            create_ground_session("zero-revision-items"),
            description=TASK_1_DESCRIPTION,
            raw_context=raw,
            derived_context=derived,
            target_contexts=targets,
            target_requirements=TASK_1_TARGET_REQUIREMENTS,
        ),
        rule="Preserve only supported access changes.",
        rationale="The nonempty session must carry its semantic revision.",
        current_contexts=contexts,
    )
    payload = proposed.to_dict()
    payload["revision"] = 0

    with pytest.raises(GroundError, match="iterations.*revision"):
        GroundSession.from_dict(payload)


def test_grounding_case_cannot_reference_raw_evidence(
    isolated_store,
):
    store = MemoryStore()
    raw, derived, targets, candidate = _task_1_workbench(store)
    contexts = (raw, derived, *targets)
    proposed = propose_ground_round(
        bind_ground_workbench(
            create_ground_session("raw-source-ref"),
            description=TASK_1_DESCRIPTION,
            raw_context=raw,
            derived_context=derived,
            target_contexts=targets,
            target_requirements=TASK_1_TARGET_REQUIREMENTS,
        ),
        rule="Fit cases only from the working-candidate frame.",
        case=candidate.content,
        source_context_uid=derived.uid,
        source_memory_uid=candidate.uid,
        target_context_names=(
            "construction-updates/building-access",
        ),
        expected="Publish the supported entrance closure.",
        rationale="The initial proposal has valid working-candidate evidence.",
        current_contexts=contexts,
    )
    payload = proposed.to_dict()
    case_payload = next(
        item for item in payload["items"] if item["kind"] == "CASE"
    )
    case_payload["source_refs"][0]["context_uid"] = raw.uid

    with pytest.raises(
        GroundError,
        match="working-candidate Context",
    ):
        GroundSession.from_dict(payload)


def test_invalid_in_memory_schema_version_cannot_be_silently_normalized():
    session = create_ground_session("invalid-version")

    for version in (True, 0, 3):
        with pytest.raises(GroundError, match="schema version"):
            replace(session, schema_version=version).to_dict()


def test_load_requires_a_user_accept_decision_for_each_accepted_item(
    isolated_store,
):
    store = MemoryStore()
    raw, derived, targets, candidate = _task_1_workbench(store)
    contexts = (raw, derived, *targets)
    proposed = propose_ground_round(
        bind_ground_workbench(
            create_ground_session("approval-boundary"),
            description=TASK_1_DESCRIPTION,
            raw_context=raw,
            derived_context=derived,
            target_contexts=targets,
            target_requirements=TASK_1_TARGET_REQUIREMENTS,
        ),
        rule="Preserve supported access changes.",
        case=candidate.content,
        source_context_uid=derived.uid,
        source_memory_uid=candidate.uid,
        target_context_names=("campus-wiki",),
        expected="Publish the supported closure.",
        rationale="This needs explicit approval.",
        current_contexts=contexts,
    )
    rule = proposed.items_of_kind("RULE")[0]
    accepted = review_ground_item(
        proposed,
        rule.uid,
        action="ACCEPT",
        current_contexts=contexts,
    )
    payload = accepted.to_dict()
    decision = next(
        item for item in payload["items"] if item["kind"] == "DECISION"
    )
    decision["origin"] = "AGENT"
    with pytest.raises(GroundError, match="approval decision"):
        GroundSession.from_dict(payload)

    unresolved = accepted.to_dict()
    next(
        item for item in unresolved["items"] if item["kind"] == "DECISION"
    )["status"] = "PROPOSED"
    with pytest.raises(GroundError, match="kind/status"):
        GroundSession.from_dict(unresolved)


@pytest.mark.parametrize(
    "args",
    [
        ["--case-role", "CONTRAST"],
        ["--disposition", "EXCLUDE"],
        ["--rule-provenance", "USER_STATED"],
        ["--response", "A response without a decision."],
    ],
)
def test_cli_never_silently_ignores_grounding_action_modifiers(
    isolated_store,
    args,
):
    store = MemoryStore()
    raw, derived, targets, _ = _task_1_workbench(store)
    session = bind_ground_workbench(
        create_ground_session("modifier-errors"),
        description=TASK_1_DESCRIPTION,
        raw_context=raw,
        derived_context=derived,
        target_contexts=targets,
        target_requirements=TASK_1_TARGET_REQUIREMENTS,
    )
    store.save_ground_session(session)
    path = isolated_store / "ground-sessions" / "modifier-errors.json"
    before = path.read_bytes()

    result = runner.invoke(
        app,
        ["ground", "modifier-errors", *args],
    )

    assert result.exit_code == 1
    assert path.read_bytes() == before


def test_cli_rejects_a_proposal_before_the_session_is_bound(
    isolated_store,
):
    store = MemoryStore()
    session = create_ground_session("unbound-proposal")
    store.save_ground_session(session)
    path = isolated_store / "ground-sessions" / "unbound-proposal.json"
    before = path.read_bytes()

    result = runner.invoke(
        app,
        [
            "ground",
            "unbound-proposal",
            "--propose-rule",
            "A rule cannot precede the bound evidence frame.",
            "--rationale",
            "A proposal without its Task and Context bindings is ungrounded.",
        ],
    )

    assert result.exit_code == 1
    assert "Bind the grounding session before proposing" in result.output
    assert path.read_bytes() == before
