"""Named common-grounding session and CLI scaffold contracts."""
from __future__ import annotations

import json
import subprocess
import uuid
from dataclasses import replace
from pathlib import Path

import pytest
from typer.testing import CliRunner

import memcommit.application.ops as ops
import memcommit.persistence.store as store_module
import memcommit.adapters.console.commands.ground.command as ground_command
from memcommit.adapters.console.entrypoint import app
from memcommit.adapters.console.commands.ground.command import (
    render_ground_focus,
    render_ground_snapshot,
    render_ground_start,
)
from memcommit.adapters.console.commands.ground.shell import GroundShellResult
from memcommit.application.operations.ground.model import (
    GROUND_PROPOSITION_SCHEMA_VERSION,
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
    propose_ground_example,
    propose_ground_round,
    propose_ground_rule,
    resolve_ground_requirement,
    review_ground_item,
    revise_ground_goal,
    revise_ground_requirement,
    target_requirement_status,
    upgrade_ground_to_propositions,
)
from memcommit.application.operations.ground.dialogue import (
    GroundDialogueError,
    GroundDialogueProposal,
)
from memcommit.application.operations.ground.turn_dialogue import (
    GroundTurnAction,
    GroundTurnDraft,
    GroundTurnDraftBatch,
)
from memcommit.persistence.store import MemoryStore, ground_session_record_digest


runner = CliRunner()

TASK_1_UPSTREAM_NAME = "construction-details"
TASK_1_WIKI_NAME = "campus-wiki"
TASK_1_CHANGE_ROOT_NAME = "participant/construction-updates"
TASK_1_DESCRIPTION = (
    "Use verified Main Building construction changes from local work memory "
    "to update every affected part of the ordinary campus wiki."
)
TASK_1_TARGET_NAMES = (
    TASK_1_WIKI_NAME,
    f"{TASK_1_CHANGE_ROOT_NAME}/building-access",
    f"{TASK_1_CHANGE_ROOT_NAME}/event-relocations",
    f"{TASK_1_CHANGE_ROOT_NAME}/temporary-parking",
    f"{TASK_1_CHANGE_ROOT_NAME}/shop-updates",
    f"{TASK_1_CHANGE_ROOT_NAME}/facility-updates",
    f"{TASK_1_CHANGE_ROOT_NAME}/route-changes",
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
            if name == TASK_1_WIKI_NAME
            else "PLACEMENT_TARGET"
        ),
        blocked_reason=(
            "The provisioned local-fork baseline is absent from this Ground "
            "fixture."
            if name == TASK_1_WIKI_NAME
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


def test_explicit_proposition_upgrade_preserves_v2_semantics_and_identity(
    isolated_store,
) -> None:
    store = MemoryStore()
    raw, derived, targets, candidate = _task_1_workbench(store)
    contexts = (raw, derived, *targets)
    session = bind_ground_workbench(
        create_ground_session(
            "proposition-upgrade",
            goal="Build source-supported fixture Examples.",
        ),
        description=TASK_1_DESCRIPTION,
        raw_context=raw,
        derived_context=derived,
        target_contexts=targets,
        target_requirements=TASK_1_TARGET_REQUIREMENTS,
    )
    session = propose_ground_rule(
        session,
        rule="Publish only source-supported facts.",
        rationale="This is the active generalized Rule.",
        current_contexts=contexts,
    )
    rule = session.items_of_kind("RULE")[0]
    session = propose_ground_case(
        session,
        rule_selector=rule.uid,
        case=candidate.content,
        source_context_uid=derived.uid,
        source_memory_uid=candidate.uid,
        target_context_names=(targets[0].name,),
        expected="Publish the reviewed entrance closure.",
        rationale="This is one concrete reviewed Example.",
        current_contexts=contexts,
    )
    before_digest = ground_session_record_digest(session)

    upgraded = upgrade_ground_to_propositions(session)
    restored = GroundSession.from_dict(upgraded.to_dict())

    assert upgraded.schema_version == GROUND_PROPOSITION_SCHEMA_VERSION
    assert upgraded.uid == session.uid
    assert upgraded.revision == session.revision
    assert tuple(item.uid for item in upgraded.items) == tuple(
        item.uid for item in session.items
    )
    assert upgraded.frames == session.frames
    assert upgraded.requirements == session.requirements
    example = upgraded.items_of_kind("CASE")[0]
    assert example.content == candidate.content
    assert example.expected == "Publish the reviewed entrance closure."
    assert example.proposition == (
        f"{candidate.content} -> Publish the reviewed entrance closure."
    )
    assert restored == upgraded
    assert ground_session_record_digest(upgraded) != before_digest


def test_proposition_upgrade_is_explicit_and_rejects_empty_example_proposition(
    isolated_store,
) -> None:
    store = MemoryStore()
    raw, derived, targets, candidate = _task_1_workbench(store)
    contexts = (raw, derived, *targets)
    session = bind_ground_workbench(
        create_ground_session("invalid-proposition-upgrade"),
        description=TASK_1_DESCRIPTION,
        raw_context=raw,
        derived_context=derived,
        target_contexts=targets,
        target_requirements=TASK_1_TARGET_REQUIREMENTS,
    )
    session = propose_ground_rule(
        session,
        rule="Publish supported facts.",
        rationale="One Rule.",
        current_contexts=contexts,
    )
    session = propose_ground_case(
        session,
        rule_selector=session.items_of_kind("RULE")[0].uid,
        case=candidate.content,
        source_context_uid=derived.uid,
        source_memory_uid=candidate.uid,
        target_context_names=(targets[0].name,),
        expected="Publish one fact.",
        rationale="One Example.",
        current_contexts=contexts,
    )
    upgraded = upgrade_ground_to_propositions(session)
    forged = upgraded.to_dict()
    forged["items"][1]["proposition"] = ""

    with pytest.raises(GroundError, match="Ground Memory shape"):
        GroundSession.from_dict(forged)
    assert upgrade_ground_to_propositions(upgraded) == upgraded


def test_cli_explicitly_upgrades_one_saved_ground_to_propositions(
    isolated_store,
) -> None:
    store = MemoryStore()
    raw, derived, targets, candidate = _task_1_workbench(store)
    contexts = (raw, derived, *targets)
    session = bind_ground_workbench(
        create_ground_session("cli-proposition-upgrade"),
        description=TASK_1_DESCRIPTION,
        raw_context=raw,
        derived_context=derived,
        target_contexts=targets,
        target_requirements=TASK_1_TARGET_REQUIREMENTS,
    )
    session = propose_ground_rule(
        session,
        rule="Publish supported facts.",
        rationale="One active Rule.",
        current_contexts=contexts,
    )
    session = propose_ground_case(
        session,
        rule_selector=session.items_of_kind("RULE")[0].uid,
        case=candidate.content,
        source_context_uid=derived.uid,
        source_memory_uid=candidate.uid,
        target_context_names=(targets[0].name,),
        expected="Publish one fact.",
        rationale="One concrete Example.",
        current_contexts=contexts,
    )
    store.save_ground_session(session)

    result = runner.invoke(
        app,
        ["ground", session.contract_name, "--upgrade-propositions"],
    )

    assert result.exit_code == 0, result.output
    assert "upgraded to proposition schema" in result.output
    loaded = store.load_ground_session(session.contract_name)
    assert loaded is not None
    assert loaded.schema_version == GROUND_PROPOSITION_SCHEMA_VERSION
    assert loaded.items_of_kind("CASE")[0].proposition.endswith(
        "-> Publish one fact."
    )


def test_native_examples_allow_observations_before_rules_and_multiple_links(
    isolated_store,
) -> None:
    store = MemoryStore()
    raw, derived, targets, _candidate = _task_1_workbench(store)
    contexts = (raw, derived, *targets)
    session = bind_ground_workbench(
        create_ground_session(
            "native-examples",
            goal="Refine general claims against concrete observations.",
        ),
        description=TASK_1_DESCRIPTION,
        raw_context=raw,
        derived_context=derived,
        target_contexts=targets,
        target_requirements=TASK_1_TARGET_REQUIREMENTS,
    )
    session = upgrade_ground_to_propositions(session)
    session = propose_ground_example(
        session,
        proposition="On August 15 the sky over Toronto was yellow.",
        rationale="A concrete observation can precede its general Rule.",
        current_contexts=contexts,
    )
    observation = session.items_of_kind("CASE")[0]

    assert observation.related_uids == ()
    assert observation.source_refs == ()
    assert observation.target_context_uids == ()
    assert observation.expected == ""
    assert GroundSession.from_dict(session.to_dict()) == session

    session = propose_ground_rule(
        session,
        rule="The sky is always blue.",
        rationale="A universal claim to check against observations.",
        current_contexts=contexts,
    )
    session = propose_ground_rule(
        session,
        rule="Observed sky color may vary.",
        rationale="A competing generalization.",
        current_contexts=contexts,
    )
    rules = session.items_of_kind("RULE")
    session = propose_ground_example(
        session,
        proposition="On August 16 the sky over Toronto was blue.",
        rationale="This observation bears on both active generalizations.",
        current_contexts=contexts,
        rule_selectors=(rules[0].uid, rules[1].uid),
    )
    linked = session.items_of_kind("CASE")[1]

    assert linked.related_uids == (rules[0].uid, rules[1].uid)
    assert all(linked.uid in rule.related_uids for rule in session.items_of_kind("RULE"))

    refined = review_ground_item(
        session,
        observation.uid,
        action="REFINE",
        response="On August 15 the observed sky over Toronto was amber.",
        current_contexts=contexts,
    )
    refined_observation = refined.items_of_kind("CASE")[0]
    assert refined_observation.proposition.endswith("was amber.")
    assert refined_observation.expected == ""


def test_cli_adds_native_examples_one_revision_at_a_time(isolated_store) -> None:
    store = MemoryStore()
    raw, derived, targets, _candidate = _task_1_workbench(store)
    session = bind_ground_workbench(
        create_ground_session("native-example-cli"),
        description=TASK_1_DESCRIPTION,
        raw_context=raw,
        derived_context=derived,
        target_contexts=targets,
        target_requirements=TASK_1_TARGET_REQUIREMENTS,
    )
    session = upgrade_ground_to_propositions(session)
    store.save_ground_session(session)

    first = runner.invoke(
        app,
        [
            "ground",
            session.contract_name,
            "--propose-example",
            "Apple Inc. may be represented by AAPL.",
        ],
    )
    after_first = store.load_ground_session(session.contract_name)
    second = runner.invoke(
        app,
        [
            "ground",
            session.contract_name,
            "--propose-example",
            "Axiom AI Technologies may be represented by AAT.",
        ],
    )
    after_second = store.load_ground_session(session.contract_name)

    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    assert after_first is not None and after_second is not None
    assert after_first.revision == session.revision + 1
    assert after_second.revision == session.revision + 2
    assert tuple(
        item.proposition for item in after_second.items_of_kind("CASE")
    ) == (
        "Apple Inc. may be represented by AAPL.",
        "Axiom AI Technologies may be represented by AAT.",
    )

assert TASK_1_UPSTREAM_NAME not in TASK_1_TARGET_NAMES


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
    # Ground's current publication-target adapter binds the writable fork.
    # The query-only organizational origin is intentionally never a frame.
    assert TASK_1_UPSTREAM_NAME not in {
        context.name for context in targets
    }

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


def _store_bytes(root):
    """Capture every persisted file in the isolated store."""
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_empty_ground_session_round_trip_and_method_provenance():
    session = create_ground_session(
        "task-1-fixture",
        goal="Agree on Task 1 wiki and local Memory contents.",
        scope=(TASK_1_WIKI_NAME, TASK_1_CHANGE_ROOT_NAME),
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
    ctx = ops.init(TASK_1_CHANGE_ROOT_NAME)
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
            TASK_1_WIKI_NAME,
            "--scope",
            TASK_1_CHANGE_ROOT_NAME,
            "--snapshot",
        ],
    )

    assert created.exit_code == 0, created.output
    assert "GROUND · task-1-fixture · OPEN" in created.output
    assert (
        "RULES 0 · MEMORIES 0 · UNRESOLVED 0 · DECISIONS 0"
        in created.output
    )
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


def test_cli_ground_creates_a_physical_workspace_without_global_current_state(
    isolated_store,
):
    assert not isolated_store.exists()

    result = runner.invoke(
        app,
        ["ground", "standalone-contract", "--snapshot"],
    )

    assert result.exit_code == 0, result.output
    assert not (isolated_store / "ground-sessions").exists()
    assert MemoryStore(create=False).current_context_name() is None
    assert (isolated_store / "contexts").is_dir()
    assert set(MemoryStore(create=False).list_context_names()) == {
        "standalone-contract",
        "standalone-contract/goals",
        "standalone-contract/rules",
        "standalone-contract/examples",
        "standalone-contract/contexts",
        "standalone-contract/relations",
    }


def test_cli_ground_without_name_opens_unsaved_blank_frame(
    isolated_store,
):
    assert not isolated_store.exists()

    first = runner.invoke(app, ["ground"])
    second = runner.invoke(app, ["ground"])

    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    expected = f"{render_ground_start()}\n"
    assert first.output == expected
    assert second.output == expected
    assert "\x1b" not in first.output
    assert not isolated_store.exists()


@pytest.mark.parametrize(
    "args",
    (
        ("--goal", "A nameless Goal must not be saved."),
        ("--snapshot",),
        ("--focus-target", "example-target"),
        ("--replace-ground",),
        ("--scope", "example-target"),
        ("--description", "A binding requires a name."),
        ("--propose-rule", "A proposal requires a name."),
        ("--decide", "deadbeef"),
        ("--revise-goal", "A revision requires a name."),
    ),
)
def test_cli_ground_without_name_rejects_options_without_state(
    isolated_store,
    args,
):
    assert not isolated_store.exists()

    result = runner.invoke(app, ["ground", *args])

    assert result.exit_code == 1
    assert "GROUND_NAME is required when using options" in result.output
    assert "without options to start from a blank Ground" in result.output
    assert not isolated_store.exists()


def test_cli_ground_without_name_preserves_a_populated_store(
    isolated_store,
):
    store = MemoryStore()
    context = ops.init("existing-context")
    ops.add(context, "Existing Memory.")
    store.save(context)
    store.set_current(context.name)
    store.save_ground_session(
        create_ground_session(
            "existing-ground",
            goal="Keep this Ground byte-identical.",
        )
    )
    before = _store_bytes(isolated_store)

    result = runner.invoke(app, ["ground"])

    assert result.exit_code == 0, result.output
    assert result.output == f"{render_ground_start()}\n"
    assert _store_bytes(isolated_store) == before


def test_cli_ground_tty_picker_reopens_existing_without_creating_state(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore(create=False)
    session = create_ground_session(
        "saved-ground",
        goal="Resume this Ground.",
    )
    store.save_ground_session(session)
    before = _store_bytes(isolated_store)
    opened = []
    monkeypatch.setattr(ground_command, "_interactive_terminal", lambda: True)
    picker_options = []

    def choose_saved_ground(*_args, **kwargs):
        picker_options.append(kwargs)
        return ground_command.SessionOpenReceipt(
            kind="ground",
            key="saved-ground",
            argv=("mem", "ground", "saved-ground"),
        )

    monkeypatch.setattr(ground_command, "choose_session", choose_saved_ground)
    monkeypatch.setattr(
        ground_command,
        "_run_existing_ground_shell",
        lambda value, **_kwargs: opened.append(value),
    )
    monkeypatch.setattr(
        ground_command,
        "_run_new_ground_shell",
        lambda *_args, **_kwargs: pytest.fail("must not start a new Ground"),
    )

    result = runner.invoke(app, ["ground"])

    assert result.exit_code == 0, result.output
    assert opened == [session]
    assert picker_options[0]["initial_sort_mode"] == "recent"
    assert picker_options[0]["initial_group_mode"] == "context"
    assert picker_options[0]["location"].store_path == str(isolated_store)
    assert _store_bytes(isolated_store) == before


def test_ground_back_reopens_a_fresh_picker_catalog(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore(create=False)
    first = create_ground_session("first-ground", goal="Open first.")
    store.save_ground_session(first)
    picker_titles = []
    opened = []

    def choose_saved(entries, **_kwargs):
        titles = tuple(entry.title for entry in entries)
        picker_titles.append(titles)
        key = "first-ground" if len(picker_titles) == 1 else "second-ground"
        return ground_command.SessionOpenReceipt(
            kind="ground",
            key=key,
            argv=("mem", "ground", key),
        )

    def open_ground(session, **_kwargs):
        opened.append(session.contract_name)
        if session.contract_name == "first-ground":
            store.save_ground_session(
                create_ground_session("second-ground", goal="Open second.")
            )
            return "BACK_TO_PICKER"
        return "CLOSED"

    monkeypatch.setattr(ground_command, "choose_session", choose_saved)
    monkeypatch.setattr(
        ground_command,
        "_run_existing_ground_shell",
        open_ground,
    )

    ground_command._run_ground_session_picker(store)

    assert picker_titles == [
        ("first-ground",),
        ("first-ground", "second-ground"),
    ]
    assert opened == ["first-ground", "second-ground"]


@pytest.mark.parametrize(
    ("shell_outcome", "picker_calls"),
    [("BACK_TO_PICKER", 1), ("CLOSED", 0)],
)
def test_direct_named_ground_back_opens_picker_but_quit_does_not(
    isolated_store,
    monkeypatch,
    shell_outcome,
    picker_calls,
):
    store = MemoryStore(create=False)
    store.save_ground_session(
        create_ground_session("saved-ground", goal="Resume this Ground.")
    )
    reopened = []
    monkeypatch.setattr(ground_command, "_interactive_terminal", lambda: True)
    monkeypatch.setattr(
        ground_command,
        "_run_existing_ground_shell",
        lambda *_args, **_kwargs: shell_outcome,
    )
    monkeypatch.setattr(
        ground_command,
        "_run_ground_session_picker",
        lambda selected_store, **_kwargs: reopened.append(selected_store),
    )

    result = runner.invoke(app, ["ground", "saved-ground"])

    assert result.exit_code == 0, result.output
    assert len(reopened) == picker_calls


def test_cli_ground_tty_picker_new_receipt_keeps_new_flow_explicit(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore(create=False)
    store.save_ground_session(create_ground_session("saved-ground"))
    started = []
    monkeypatch.setattr(ground_command, "_interactive_terminal", lambda: True)
    monkeypatch.setattr(
        ground_command,
        "choose_session",
        lambda *_args, **_kwargs: ground_command.SessionNewReceipt(
            kind="ground",
            argv=("mem", "ground"),
        ),
    )
    monkeypatch.setattr(
        ground_command,
        "_run_new_ground_shell",
        lambda *_args, **kwargs: started.append(kwargs.get("ground_name")),
    )

    result = runner.invoke(app, ["ground"])

    assert result.exit_code == 0, result.output
    # New enters a blank Ground session. Its Save Location is chosen from the
    # persistent LOCATION control inside that session, not before it opens.
    assert started == [None]


def test_cli_ground_picker_does_not_recreate_a_disappeared_selection(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore(create=False)
    store.save_ground_session(create_ground_session("vanishing-ground"))
    path = isolated_store / "ground-sessions" / "vanishing-ground.json"

    def remove_then_select(*_args, **_kwargs):
        path.unlink()
        return ground_command.SessionOpenReceipt(
            kind="ground",
            key="vanishing-ground",
            argv=("mem", "ground", "vanishing-ground"),
        )

    monkeypatch.setattr(ground_command, "_interactive_terminal", lambda: True)
    monkeypatch.setattr(ground_command, "choose_session", remove_then_select)

    result = runner.invoke(app, ["ground", "--sessions"])

    assert result.exit_code == 1
    assert "no longer exists" in result.output
    assert not path.exists()


def test_cli_ground_sessions_requires_tty_without_changing_store(
    isolated_store,
):
    store = MemoryStore(create=False)
    store.save_ground_session(create_ground_session("saved-ground"))
    before = _store_bytes(isolated_store)

    result = runner.invoke(app, ["ground", "--sessions"])

    assert result.exit_code == 1
    assert "requires an interactive terminal" in result.output
    assert _store_bytes(isolated_store) == before


def test_cli_ground_without_name_uses_tui_and_applies_one_frozen_command(
    isolated_store,
    monkeypatch,
):
    shell_calls = []
    continued = []

    def fake_shell(
        *,
        interpret,
        apply,
        validate_new_context,
        choose_save_location,
        ground_name=None,
        current_context_name=None,
    ):
        assert current_context_name is None
        assert ground_name is None
        assert callable(validate_new_context)
        assert callable(choose_save_location)
        new_name = "test/ground/ticker-rule-examples"
        assert validate_new_context(new_name) == new_name
        assert not MemoryStore(create=False).context_exists(new_name)
        assert choose_save_location(None) == "task-1-report-coverage"
        shell_calls.append((interpret, apply))
        proposal = ground_command.GroundShellProposal(
            ground_name="task-1-report-coverage",
            goal="Determine which Task 1 claims were represented.",
            understanding="Compare report coverage.",
            question="Approve this Ground?",
        )
        actual_output = apply(proposal)
        return GroundShellResult(
            status="APPLIED",
            proposal=proposal,
            actual_output=actual_output,
                submitted_turns=("Inspect report coverage.",),
                selected_context_names=("temp/task-1", "campus-wiki"),
                new_context_name_hint="test/ground/ticker-rule-examples",
        )

    monkeypatch.setattr(
        ground_command,
        "_interactive_terminal",
        lambda: True,
    )
    monkeypatch.setattr(
        ground_command,
        "choose_session",
        lambda *_args, **_kwargs: ground_command.SessionNewReceipt(
            kind="ground",
            argv=("mem", "ground"),
        ),
    )
    monkeypatch.setattr(
        ground_command,
        "_choose_ground_workspace_save_location",
        lambda _store, **_kwargs: "task-1-report-coverage",
    )
    monkeypatch.setattr(
        ground_command,
        "run_ground_shell",
        fake_shell,
    )
    def run_in_process(argv):
        # The real subprocess has captured (non-TTY) stdout, so it prints a
        # snapshot instead of opening a nested workspace TUI. Typer's in-
        # process runner inherits the mocked interactive predicate; emulate
        # the real presentation boundary without changing the approved argv.
        invoked = runner.invoke(app, [*argv[1:], "--snapshot"])
        return subprocess.CompletedProcess(
            argv,
            invoked.exit_code,
            stdout=invoked.output,
            stderr="",
        )

    monkeypatch.setattr(
        ground_command,
        "_run_approved_ground_command",
        run_in_process,
    )
    monkeypatch.setattr(
        ground_command,
        "run_ground_workspace_tui",
        lambda workspace, **_kwargs: continued.append(workspace),
    )

    result = runner.invoke(app, ["ground"])

    assert result.exit_code == 0, result.output
    assert len(shell_calls) == 1
    assert len(continued) == 1
    assert continued[0].name == "task-1-report-coverage"
    [goal] = tuple(continued[0].goals.iter_items())
    assert goal.content == "Determine which Task 1 claims were represented."
    assert MemoryStore(create=False).load_ground_session(
        "task-1-report-coverage"
    ) is None
    persisted = b"\n".join(_store_bytes(isolated_store).values())
    assert b"temp/task-1" not in persisted
    assert b"campus-wiki" not in persisted
    assert b"test/ground/ticker-rule-examples" not in persisted
    assert (isolated_store / "contexts").exists()
    assert MemoryStore(create=False).current_context_name() is None


def test_approved_ground_command_uses_argv_without_a_shell(monkeypatch):
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(
            args,
            0,
            stdout="created\n",
            stderr="",
        )

    monkeypatch.setattr(ground_command.subprocess, "run", fake_run)
    proposal = ground_command.GroundShellProposal(
        ground_name="safe-ground",
        goal="A goal containing ; $(unsafe) and spaces.",
        understanding="Create one safe Ground.",
        question="Approve?",
    )

    result = ground_command._run_approved_ground_command(
        ground_command.proposal_argv(proposal)
    )

    assert result.stdout == "created\n"
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == [
        ground_command.sys.executable,
        "-m",
        "memcommit.adapters.console.entrypoint",
        "ground",
        "safe-ground",
        "--goal",
        "A goal containing ; $(unsafe) and spaces.",
    ]
    assert kwargs["capture_output"] is True
    assert kwargs["check"] is False
    assert "shell" not in kwargs


def test_cli_ground_tui_cancel_creates_nothing(
    isolated_store,
    monkeypatch,
):
    monkeypatch.setattr(
        ground_command,
        "_interactive_terminal",
        lambda: True,
    )
    monkeypatch.setattr(
        ground_command,
        "choose_session",
        lambda *_args, **_kwargs: ground_command.SessionNewReceipt(
            kind="ground",
            argv=("mem", "ground"),
        ),
    )
    monkeypatch.setattr(
        ground_command,
        "_choose_ground_workspace_save_location",
        lambda _store: "cancelled-ground",
    )
    monkeypatch.setattr(
        ground_command,
        "run_ground_shell",
        lambda **_kwargs: GroundShellResult(
            status="CANCELLED"
        ),
    )

    result = runner.invoke(app, ["ground"])

    assert result.exit_code == 0, result.output
    assert "cancelled. Nothing was created." in result.output
    assert not isolated_store.exists()


def test_plain_named_ground_in_a_tty_resumes_the_named_tui(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore(create=False)
    session = create_ground_session(
        "resume-dialogue",
        goal="Continue this saved Goal.",
    )
    store.save_ground_session(session)
    opened = []
    monkeypatch.setattr(
        ground_command,
        "_interactive_terminal",
        lambda: True,
    )
    monkeypatch.setattr(
        ground_command,
        "_run_existing_ground_shell",
        lambda value, *, initial_receipt="", context_hints=(): opened.append(
            (value, initial_receipt, context_hints)
        ),
    )

    result = runner.invoke(app, ["ground", "resume-dialogue"])

    assert result.exit_code == 0, result.output
    assert opened == [(session, "", ())]
    assert result.output == ""


def test_new_ground_name_collision_is_rejected_before_and_during_apply(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore(create=False)
    existing = create_ground_session(
        "already-there",
        goal="Preserve this Ground.",
    )
    store.save_ground_session(existing)
    path = (
        isolated_store
        / "ground-sessions"
        / "already-there.json"
    )
    before = path.read_bytes()
    dialogue_proposal = GroundDialogueProposal(
        understanding="Create a colliding Ground.",
        question="Approve?",
        ground_name="already-there",
        goal="Overwrite the existing Ground.",
    )
    monkeypatch.setattr(
        ground_command,
        "interpret_ground_dialogue",
        lambda *_args, **_kwargs: dialogue_proposal,
    )

    with pytest.raises(GroundDialogueError, match="already exists"):
        ground_command._interpret_new_ground_turn("Create it.")

    frozen = ground_command.GroundShellProposal(
        ground_name="already-there",
        goal=dialogue_proposal.goal,
        understanding=dialogue_proposal.understanding,
        question=dialogue_proposal.question,
    )
    with pytest.raises(GroundError, match="created before approval"):
        ground_command._apply_new_ground_proposal(frozen)

    assert path.read_bytes() == before


def test_named_ground_dialogue_applies_bind_rule_review_and_case_one_at_a_time(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    raw, derived, targets, candidate = _task_1_workbench(store)
    session = create_ground_session(
        "dialogue-cycle",
        goal="Build reviewed Task 1 fixture content.",
    )
    store.save_ground_session(session)
    non_ground_before = _non_ground_store_bytes(isolated_store)

    def run_in_process(argv):
        invoked = runner.invoke(app, list(argv[1:]))
        return subprocess.CompletedProcess(
            argv,
            invoked.exit_code,
            stdout=invoked.output,
            stderr="",
        )

    monkeypatch.setattr(
        ground_command,
        "_run_approved_ground_command",
        run_in_process,
    )

    bind = GroundTurnAction(
        kind="BIND",
        understanding="Bind the Task 1 evidence and target.",
        question="Approve this explicit binding?",
        description=TASK_1_DESCRIPTION,
        raw_context=raw.name,
        derived_context=derived.name,
        publication_target=targets[0].name,
        placement_targets=(targets[1].name,),
    )
    bind_proposal = ground_command._ground_action_proposal(session, bind)
    assert bind_proposal.review.argv[:3] == (
        "mem",
        "ground",
        "dialogue-cycle",
    )
    assert bind_proposal.review.argv[3:5] == (
        "--if-ground-version",
        ground_command._ground_version_token(session),
    )
    assert [
        bind_proposal.review.argv[index + 1]
        for index, value in enumerate(bind_proposal.review.argv[:-1])
        if value == "--if-context-version"
    ] == [
        ground_command._context_version_token(context)
        for context in (raw, derived, targets[0], targets[1])
    ]
    description_index = bind_proposal.review.argv.index("--description")
    assert bind_proposal.review.argv[description_index:] == (
        "--description",
        TASK_1_DESCRIPTION,
        "--raw-context",
        raw.name,
        "--derived-context",
        derived.name,
        "--publication-target",
        targets[0].name,
        "--placement-target",
        targets[1].name,
    )
    bound, _output = ground_command._apply_named_ground_proposal(
        session,
        bind_proposal,
    )
    assert bound.schema_version == 2
    assert bound.revision == 0

    rule = GroundTurnAction(
        kind="PROPOSE_RULE",
        understanding="Record one source-evidence Rule.",
        question="Approve recording this proposed Rule?",
        content="Publish only facts supported by the bound candidate Context.",
        rationale="This keeps publication traceable to the bound evidence.",
        rule_provenance="DISTILLED_FROM_GOAL",
    )
    rule_proposal = ground_command._ground_action_proposal(bound, rule)
    assert "--propose-rule" in rule_proposal.review.argv
    rule_proposal = ground_command._ground_retarget_proposal(
        bound,
        rule_proposal,
        targets[1].name,
    )
    assert ground_command._argv_option_values(
        rule_proposal.review.argv,
        "--propose-rule-target",
    ) == (targets[1].name,)
    with_rule, _output = ground_command._apply_named_ground_proposal(
        bound,
        rule_proposal,
    )
    assert with_rule.revision == 1
    assert with_rule.items[0].kind == "RULE"
    assert with_rule.items[0].status == "PROPOSED"
    assert with_rule.items[0].target_context_uids == (targets[1].uid,)

    accept = GroundTurnAction(
        kind="REVIEW_ITEM",
        understanding="Accept the proposed Rule.",
        question="Approve this separate acceptance command?",
        selector="r1",
        decision="ACCEPT",
    )
    accept_proposal = ground_command._ground_action_proposal(
        with_rule,
        accept,
    )
    assert accept_proposal.review.argv[-2:] == ("--action", "ACCEPT")
    accepted, _output = ground_command._apply_named_ground_proposal(
        with_rule,
        accept_proposal,
    )
    assert accepted.revision == 2
    assert accepted.items[0].status == "ACCEPTED"

    case = GroundTurnAction(
        kind="PROPOSE_CASE",
        understanding=(
            "Use the selected candidate as one fitting Ground Memory."
        ),
        question="Approve recording this proposed Ground Memory?",
        selector="r1",
        source_selector=candidate.uid[:8],
        targets=(targets[0].name,),
        expected="Publish the supported rear-entrance closure.",
        rationale="The candidate directly supports this target statement.",
        case_role="FIT",
        disposition="INCLUDE",
    )
    case_proposal = ground_command._ground_action_proposal(accepted, case)
    assert candidate.uid in case_proposal.review.argv
    assert "--case-role" in case_proposal.review.argv
    rendered_effects = "\n".join(case_proposal.review.effects)
    assert candidate.content in rendered_effects
    assert (
        "Ground Memories: ADD one traceable PROPOSED Ground Memory"
        in rendered_effects
    )
    assert "Source Context Memory" in rendered_effects
    assert "Contexts and Context Memories: unchanged" in rendered_effects
    with_case, _output = ground_command._apply_named_ground_proposal(
        accepted,
        case_proposal,
    )
    cases = [item for item in with_case.items if item.kind == "CASE"]
    assert with_case.revision == 3
    assert len(cases) == 1
    assert cases[0].content == candidate.content
    assert cases[0].status == "PROPOSED"

    assert _non_ground_store_bytes(isolated_store) == non_ground_before
    assert all(
        store.list_checkpoints(context.name) == []
        for context in (raw, derived, *targets)
    )


def test_named_ground_proposition_action_applies_one_reviewed_example(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    raw, derived, targets, candidate = _task_1_workbench(store)
    contexts = (raw, derived, *targets)
    session = bind_ground_workbench(
        create_ground_session(
            "proposition-dialogue",
            goal="Check concrete ticker propositions against reviewed Rules.",
        ),
        description=TASK_1_DESCRIPTION,
        raw_context=raw,
        derived_context=derived,
        target_contexts=targets,
        target_requirements=TASK_1_TARGET_REQUIREMENTS,
    )
    session = upgrade_ground_to_propositions(session)
    session = propose_ground_rule(
        session,
        rule="Use the reviewed ticker mapping for this company.",
        rationale="This Rule is exercised by an exact concrete Example.",
        current_contexts=contexts,
        target_context_names=(targets[0].name,),
    )
    store.save_ground_session(session)
    proposition = (
        f'Applying the ticker Rules to "{candidate.content}" '
        'produces "RER".'
    )

    def run_in_process(argv):
        invoked = runner.invoke(app, list(argv[1:]))
        return subprocess.CompletedProcess(
            argv,
            invoked.exit_code,
            stdout=invoked.output,
            stderr="",
        )

    monkeypatch.setattr(
        ground_command,
        "_run_approved_ground_command",
        run_in_process,
    )
    action = GroundTurnAction(
        kind="PROPOSE_CASE",
        understanding="Record one concrete ticker proposition.",
        question="Approve this exact proposition and projection?",
        content=proposition,
        selector="r1",
        source_selector=candidate.uid[:8],
        targets=(targets[0].name,),
        expected="RER",
        rationale="The candidate is the reviewed exact input.",
        case_role="FIT",
        disposition="INCLUDE",
    )

    proposal = ground_command._ground_action_proposal(session, action)

    assert "--propose-example" in proposal.review.argv
    assert "--propose-source" not in proposal.review.argv
    assert ground_command._argv_option_values(
        proposal.review.argv,
        "--propose-example",
    ) == (proposition,)
    assert ground_command._argv_option_values(
        proposal.review.argv,
        "--example-input",
    ) == (candidate.content,)
    assert ground_command._argv_option_values(
        proposal.review.argv,
        "--example-expected",
    ) == ("RER",)
    proposal = ground_command._ground_retarget_proposal(
        session,
        proposal,
        targets[1].name,
    )
    assert ground_command._argv_option_values(
        proposal.review.argv,
        "--example-target",
    ) == (targets[1].name,)

    updated, _output = ground_command._apply_named_ground_proposal(
        session,
        proposal,
    )
    example = updated.items_of_kind("CASE")[0]

    assert updated.schema_version == GROUND_PROPOSITION_SCHEMA_VERSION
    assert example.proposition == proposition
    assert example.content == candidate.content
    assert example.expected == "RER"
    assert example.source_refs[0].memory_uid == candidate.uid
    assert example.target_context_uids == (targets[1].uid,)


def test_ready_rule_draft_reuses_the_guarded_rule_proposal_path(
    isolated_store,
):
    store = MemoryStore()
    raw, derived, targets, _candidate = _task_1_workbench(store)
    session = bind_ground_workbench(
        create_ground_session(
            "draft-rule",
            goal="Build reviewed Task 1 fixtures.",
        ),
        description=TASK_1_DESCRIPTION,
        raw_context=raw,
        derived_context=derived,
        target_contexts=targets,
        target_requirements=TASK_1_TARGET_REQUIREMENTS,
    )
    draft = GroundTurnDraft(
        kind="RULE",
        status="READY",
        content="Keep all six update areas separate.",
        classification_reason="This constrains the fixture structure.",
        source_spans=("6개가 다 나눠져있어야함.",),
        proposal_rationale="The user explicitly required six areas.",
        rule_provenance="USER_STATED",
    )

    proposal = ground_command._ground_rule_draft_proposal(session, draft)

    assert proposal.kind == "PROPOSE_RULE"
    assert proposal.expected_revision == session.revision
    assert proposal.review.argv[:3] == ("mem", "ground", "draft-rule")
    assert proposal.review.argv[3:5] == (
        "--if-ground-version",
        ground_command._ground_version_token(session),
    )
    assert "--propose-rule" in proposal.review.argv
    assert draft.content in proposal.review.argv
    assert draft.proposal_rationale in proposal.review.argv
    assert "Rules: ADD one PROPOSED Rule" in proposal.review.effects
    assert any(
        "proposal is not approval" in effect
        for effect in proposal.review.effects
    )

    with pytest.raises(GroundError, match="Bind this Ground"):
        ground_command._ground_rule_draft_proposal(
            create_ground_session("unbound-draft"),
            draft,
        )


def test_direct_ground_edits_use_exact_guarded_goal_and_rule_commands(
    isolated_store,
):
    store = MemoryStore()
    raw, derived, targets, _candidate = _task_1_workbench(store)
    contexts = (raw, derived, *targets)
    session = bind_ground_workbench(
        create_ground_session(
            "direct-edit-ground",
            goal="Build reviewed fixture content.",
        ),
        description=TASK_1_DESCRIPTION,
        raw_context=raw,
        derived_context=derived,
        target_contexts=targets,
        target_requirements=TASK_1_TARGET_REQUIREMENTS,
    )

    goal_text = "Build reviewed fixture and wiki content."
    goal_proposal = ground_command._ground_direct_edit_proposal(
        session,
        "GOAL",
        "",
        goal_text,
        "The wiki is part of the intended output.",
    )

    assert goal_proposal.kind == "REVISE_GOAL"
    assert goal_proposal.review.argv[:5] == (
        "mem",
        "ground",
        "direct-edit-ground",
        "--if-ground-version",
        ground_command._ground_version_token(session),
    )
    goal_index = goal_proposal.review.argv.index("--revise-goal")
    assert goal_proposal.review.argv[goal_index + 1] == goal_text
    reason_index = goal_proposal.review.argv.index("--change-reason")
    assert (
        goal_proposal.review.argv[reason_index + 1]
        == "The wiki is part of the intended output."
    )

    with_rule = propose_ground_rule(
        session,
        rule="Publish only source-supported facts.",
        rationale="Keep the fixture traceable.",
        current_contexts=contexts,
    )
    rule_text = "Publish only facts supported by a bound source Memory."
    rule_proposal = ground_command._ground_direct_edit_proposal(
        with_rule,
        "RULE",
        "r1",
        rule_text,
        "",
    )

    assert rule_proposal.kind == "REVIEW_ITEM"
    assert "--decide" in rule_proposal.review.argv
    assert with_rule.items[0].uid in rule_proposal.review.argv
    assert rule_proposal.review.argv[-4:] == (
        "--action",
        "REFINE",
        "--response",
        rule_text,
    )

    rejected = replace(
        with_rule,
        items=(replace(with_rule.items[0], status="REJECTED"),),
    )
    with pytest.raises(GroundError, match="REJECTED"):
        ground_command._ground_direct_edit_proposal(
            rejected,
            "RULE",
            "r1",
            "This invalid refinement must not reach approval.",
            "",
        )
    with pytest.raises(GroundError, match="too long"):
        ground_command._ground_direct_edit_proposal(
            with_rule,
            "RULE",
            "r1",
            "x" * (ground_command.GROUND_TEXT_LIMIT + 1),
            "",
        )


def test_named_ground_approval_rejects_a_stale_frozen_state(
    isolated_store,
):
    store = MemoryStore(create=False)
    session = create_ground_session(
        "stale-dialogue",
        goal="Original Goal.",
    )
    store.save_ground_session(session)
    action = GroundTurnAction(
        kind="BIND",
        understanding="Bind explicit Contexts.",
        question="Approve?",
        description="A binding description.",
        raw_context="missing-raw",
        derived_context="missing-derived",
        publication_target="missing-target",
    )

    # Build a valid frozen action against real Context names, then change only
    # the Ground bytes without changing its revision.
    for name in ("missing-raw", "missing-derived", "missing-target"):
        store.save(ops.init(name))
    proposal = ground_command._ground_action_proposal(session, action)
    changed = replace(session, goal="Concurrently changed Goal.")
    store.save_ground_session(changed)

    with pytest.raises(GroundError, match="changed after this proposal"):
        ground_command._apply_named_ground_proposal(session, proposal)


def test_named_ground_child_save_rechecks_state_after_parent_preflight(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    session = create_ground_session(
        "save-boundary-dialogue",
        goal="Original Goal.",
    )
    store.save_ground_session(session)
    for name in ("race-raw", "race-derived", "race-target"):
        store.save(ops.init(name))
    proposal = ground_command._ground_action_proposal(
        session,
        GroundTurnAction(
            kind="BIND",
            understanding="Bind the reviewed Contexts.",
            question="Approve?",
            description="A binding description.",
            raw_context="race-raw",
            derived_context="race-derived",
            publication_target="race-target",
        ),
    )
    competing = replace(session, goal="Concurrent Goal.")

    def race_then_run(argv):
        # This occurs after the parent-side freshness check but before the
        # child command reaches its atomic save boundary.
        store.save_ground_session(competing)
        invoked = runner.invoke(app, list(argv[1:]))
        return subprocess.CompletedProcess(
            argv,
            invoked.exit_code,
            stdout=invoked.output,
            stderr="",
        )

    monkeypatch.setattr(
        ground_command,
        "_run_approved_ground_command",
        race_then_run,
    )

    with pytest.raises(GroundError, match="approved Ground command failed"):
        ground_command._apply_named_ground_proposal(session, proposal)

    assert store.load_ground_session(session.contract_name) == competing


def test_named_ground_binding_rechecks_context_versions_in_child(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    session = create_ground_session(
        "binding-context-race",
        goal="Bind exact evidence.",
    )
    store.save_ground_session(session)
    for name in ("bind-raw", "bind-derived", "bind-target"):
        context = ops.init(name)
        context.add(f"Initial content for {name}.")
        store.save(context)
    proposal = ground_command._ground_action_proposal(
        session,
        GroundTurnAction(
            kind="BIND",
            understanding="Bind the reviewed Context versions.",
            question="Approve?",
            description="A binding description.",
            raw_context="bind-raw",
            derived_context="bind-derived",
            publication_target="bind-target",
        ),
    )

    def change_context_then_run(argv):
        changed = store.load_direct("bind-derived")
        changed.add("Concurrent candidate.")
        store.save(changed)
        invoked = runner.invoke(app, list(argv[1:]))
        return subprocess.CompletedProcess(
            argv,
            invoked.exit_code,
            stdout=invoked.output,
            stderr="",
        )

    monkeypatch.setattr(
        ground_command,
        "_run_approved_ground_command",
        change_context_then_run,
    )

    with pytest.raises(GroundError, match="approved Ground command failed"):
        ground_command._apply_named_ground_proposal(session, proposal)

    assert store.load_ground_session(session.contract_name) == session
    assert len(tuple(store.load_direct("bind-derived").iter_items())) == 2


def test_named_ground_provider_receives_local_source_alias_not_memory_uid(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    raw, derived, targets, candidate = _task_1_workbench(store)
    contexts = (raw, derived, *targets)
    session = bind_ground_workbench(
        create_ground_session(
            "private-source-selector",
            goal="Build source-supported fixture cases.",
        ),
        description=TASK_1_DESCRIPTION,
        raw_context=raw,
        derived_context=derived,
        target_contexts=targets,
        target_requirements=TASK_1_TARGET_REQUIREMENTS,
    )
    session = propose_ground_rule(
        session,
        rule="Publish only source-supported facts.",
        rationale="This preserves the evidence boundary.",
        current_contexts=contexts,
        rule_provenance="DISTILLED_FROM_GOAL",
    )
    store.save_ground_session(session)
    seen: list[str] = []

    def fake_interpret(
        current,
        text,
        _provider,
        *,
        draft_source_text=None,
    ):
        assert current == session
        seen.append(text)
        assert draft_source_text is not None
        return GroundTurnAction(
            kind="PROPOSE_CASE",
            understanding="Use the locally aliased candidate.",
            question="Approve this exact Ground Memory proposal?",
            selector="r1",
            source_selector="m1",
            targets=(targets[0].name,),
            expected="Publish the supported entrance closure.",
            rationale="The selected candidate supports the target.",
            case_role="FIT",
            disposition="INCLUDE",
        )

    monkeypatch.setattr(
        ground_command,
        "interpret_ground_turn",
        fake_interpret,
    )

    proposal = ground_command._interpret_named_ground_turn(
        session,
        (
            f"On 2026-07-29, use Memory {candidate.uid[:8]} as the "
            "fitting example."
        ),
        (
            f"On 2026-07-29, use Memory {candidate.uid[:8]} as the "
            "fitting example."
        ),
    )

    assert len(seen) == 1
    assert candidate.uid[:8] not in seen[0]
    assert "Memory m1" in seen[0]
    assert "2026-07-29" in seen[0]
    assert candidate.uid in proposal.review.argv
    assert "m1" not in proposal.review.argv

    with pytest.raises(
        GroundError,
        match="source Context Memory selector supplied in this visible turn",
    ):
        ground_command._interpret_named_ground_turn(
            session,
            "Use the first candidate without an explicit selector.",
            "Use the first candidate without an explicit selector.",
        )
    assert len(seen) == 2

    unknown_uid = "ffffffff-ffff-4fff-8fff-ffffffffffff"
    redacted, aliases = ground_command._redact_ground_source_selectors(
        session,
        f"Do not use {unknown_uid} or deadbeef on 2026-07-29.",
        store,
    )
    assert unknown_uid not in redacted
    assert "deadbeef" not in redacted
    assert redacted.count("<unrecognized-identifier>") == 2
    assert "2026-07-29" in redacted
    assert aliases == {}


def test_ground_drafts_fail_closed_when_source_selector_was_redacted(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    raw, derived, targets, candidate = _task_1_workbench(store)
    session = bind_ground_workbench(
        create_ground_session(
            "redacted-draft-source",
            goal="Build source-supported fixture Rules.",
        ),
        description=TASK_1_DESCRIPTION,
        raw_context=raw,
        derived_context=derived,
        target_contexts=targets,
        target_requirements=TASK_1_TARGET_REQUIREMENTS,
    )
    submitted = (
        f"Treat Memory {candidate.uid[:8]} as the required source example."
    )

    def fake_interpret(
        _session,
        _dialogue,
        _provider,
        *,
        draft_source_text=None,
    ):
        assert draft_source_text is not None
        assert candidate.uid[:8] not in draft_source_text
        assert "m1" in draft_source_text
        return GroundTurnDraftBatch(
            understanding="The source selector was aliased.",
            question="Review the draft.",
            drafts=(
                GroundTurnDraft(
                    kind="RULE",
                    status="READY",
                    content="Treat Memory m1 as the required source example.",
                    classification_reason="A source-selection constraint.",
                    source_spans=(draft_source_text,),
                    proposal_rationale="The user selected a source.",
                    rule_provenance="USER_STATED",
                ),
            ),
            raw_source=draft_source_text,
        )

    monkeypatch.setattr(
        ground_command,
        "interpret_ground_turn",
        fake_interpret,
    )

    with pytest.raises(
        GroundError,
        match="cannot preserve exact source spans",
    ):
        ground_command._interpret_named_ground_turn(
            session,
            submitted,
            submitted,
        )


@pytest.mark.parametrize("tamper", ("ground", "context", "duplicate"))
def test_named_ground_apply_rejects_tampered_frozen_version_guards(
    isolated_store,
    monkeypatch,
    tamper,
):
    store = MemoryStore()
    session = create_ground_session(
        "tampered-review",
        goal="Bind exact evidence.",
    )
    store.save_ground_session(session)
    for name in ("tamper-raw", "tamper-derived", "tamper-target"):
        store.save(ops.init(name))
    proposal = ground_command._ground_action_proposal(
        session,
        GroundTurnAction(
            kind="BIND",
            understanding="Bind the reviewed Contexts.",
            question="Approve?",
            description="An exact binding.",
            raw_context="tamper-raw",
            derived_context="tamper-derived",
            publication_target="tamper-target",
        ),
    )
    argv = list(proposal.review.argv)
    if tamper == "ground":
        del argv[3:5]
    elif tamper == "context":
        index = argv.index("--if-context-version")
        del argv[index : index + 2]
    else:
        argv.extend(
            [
                "--if-ground-version",
                ground_command._ground_version_token(session),
            ]
        )
    tampered = replace(
        proposal,
        review=ground_command.ExactCommandReview(
            argv=tuple(argv),
            effects=proposal.review.effects,
        ),
    )
    monkeypatch.setattr(
        ground_command,
        "_run_approved_ground_command",
        lambda _argv: pytest.fail("tampered command must not run"),
    )

    with pytest.raises(
        GroundError,
        match="version guard|Ground revision check|Context revision checks",
    ):
        ground_command._apply_named_ground_proposal(session, tampered)

    assert store.load_ground_session(session.contract_name) == session


def test_ordinary_ground_writer_cannot_overwrite_a_newer_guarded_state(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    original = create_ground_session(
        "ordinary-writer-race",
        goal="Original Goal.",
    )
    store.save_ground_session(original)
    for name in ("ordinary-raw", "ordinary-derived", "ordinary-target"):
        store.save(ops.init(name))
    competing = replace(original, goal="Newer guarded Goal.")
    original_save = MemoryStore.save_ground_session
    captured: list[dict[str, object]] = []

    def race_before_stale_save(self, value, **kwargs):
        if (
            value.contract_name == original.contract_name
            and value.schema_version == 2
            and not captured
        ):
            captured.append(dict(kwargs))
            original_save(self, competing)
        return original_save(self, value, **kwargs)

    monkeypatch.setattr(
        MemoryStore,
        "save_ground_session",
        race_before_stale_save,
    )

    result = runner.invoke(
        app,
        [
            "ground",
            original.contract_name,
            "--description",
            "Bind the exact evidence.",
            "--raw-context",
            "ordinary-raw",
            "--derived-context",
            "ordinary-derived",
            "--publication-target",
            "ordinary-target",
        ],
    )

    assert result.exit_code == 1
    assert "changed before it could be saved" in result.output
    assert captured == [
        {
            "replace": False,
            "verify_bound_frames": True,
            "expected_uid": original.uid,
            "expected_revision": original.revision,
            "expected_digest": ground_session_record_digest(original),
        }
    ]
    assert store.load_ground_session(original.contract_name) == competing


def test_cli_ground_help_marks_name_as_optional():
    result = runner.invoke(app, ["ground", "--help"])

    assert result.exit_code == 0, result.output
    assert "[GROUND_NAME]" in result.output
    assert "omit to start from a blank" in result.output
    assert "unsaved frame" in result.output


def test_cli_keeps_physical_grounds_independent_and_refuses_silent_redefinition(
    isolated_store,
):
    first = runner.invoke(app, ["ground", "task-1-fixture"])
    second = runner.invoke(app, ["ground", "task-2-fixture"])

    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    names = set(MemoryStore(create=False).list_context_names())
    assert "task-1-fixture" in names
    assert "task-2-fixture" in names
    assert not (isolated_store / "ground-sessions").exists()

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
    assert "already exists" in refused.output
    assert "/goals" in refused.output


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
    assert "TARGET REQUIREMENTS" in snapshot
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


def test_target_focus_renders_one_compact_read_only_ground_screen(
    isolated_store,
):
    store = MemoryStore()
    raw, derived, targets, candidate = _task_1_workbench(store)
    contexts = (raw, derived, *targets)
    bound = bind_ground_workbench(
        create_ground_session(
            "task-1-focus",
            goal=(
                "Determine what the participant's local campus-wiki fork "
                "must contain and how the verified local changes relate to "
                "it."
            ),
        ),
        description=TASK_1_DESCRIPTION,
        raw_context=raw,
        derived_context=derived,
        target_contexts=targets,
        target_requirements=TASK_1_TARGET_REQUIREMENTS,
    )
    proposed = propose_ground_round(
        bound,
        rule=(
            "Use verified construction changes only for supported target "
            "entries."
        ),
        case=candidate.content,
        source_context_uid=derived.uid,
        source_memory_uid=candidate.uid,
        target_context_names=("campus-wiki",),
        expected="Record the supported entrance closure.",
        rationale="The source supports one affected wiki entry.",
        current_contexts=contexts,
    )

    rendered = render_ground_focus(
        proposed,
        "campus-wiki",
        contexts,
    )

    assert (
        "MEM GROUND · task-1-focus · OPEN · FRESH"
        in rendered
    )
    assert "Revision: 1" in rendered
    assert "FOCUS · campus-wiki" in rendered
    assert "GOAL\n" in rendered
    assert "BOUND MATERIAL" in rendered
    assert "RAW         temp/task-1 · 51 Memories" in rendered
    assert (
        "CANDIDATES  temp/task-1-atomized · 54 Memories"
        in rendered
    )
    assert "TARGET      campus-wiki · 0 Memories" in rendered
    assert "MEM UNDERSTANDS" in rendered
    assert "[BLOCKED]" in rendered
    assert "SUPPORTED SLICE" in rendered
    assert "FULL TARGET" in rendered
    assert "> 3  BOTH" in rendered
    assert (
        "RULES 1 (1 proposed) · MEMORIES 1 (1 proposed) · ACCEPTED 0"
        in rendered
    )
    assert "one exact mem command" in rendered
    assert "requires its own approval" in rendered
    assert "METHOD READINGS" not in rendered
    assert "Derived Task 1 candidate 02." not in rendered


def test_cli_focus_target_is_read_only_and_can_render_one_action_result(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    raw, derived, targets, _ = _task_1_workbench(store)
    contexts = (raw, derived, *targets)
    session = bind_ground_workbench(
        create_ground_session(
            "task-1-focus-cli",
            goal="Design the affected local campus-wiki fork material.",
        ),
        description=TASK_1_DESCRIPTION,
        raw_context=raw,
        derived_context=derived,
        target_contexts=targets,
        target_requirements=TASK_1_TARGET_REQUIREMENTS,
    )
    store.save_ground_session(session)
    ground_path = (
        isolated_store
        / "ground-sessions"
        / "task-1-focus-cli.json"
    )
    ground_before = ground_path.read_bytes()
    non_ground_before = _non_ground_store_bytes(isolated_store)

    def refuse_save(*_args, **_kwargs):
        raise AssertionError("focus-only rendering must not save")

    with monkeypatch.context() as patch:
        patch.setattr(
            MemoryStore,
            "save_ground_session",
            refuse_save,
        )
        focused = runner.invoke(
            app,
            [
                "ground",
                "task-1-focus-cli",
                "--focus-target",
                "campus-wiki",
            ],
        )
    assert focused.exit_code == 0, focused.output
    assert "FOCUS · campus-wiki" in focused.output
    assert ground_path.read_bytes() == ground_before
    assert _non_ground_store_bytes(isolated_store) == non_ground_before

    revised = runner.invoke(
        app,
        [
            "ground",
            "task-1-focus-cli",
            "--revise-goal",
            (
                "Ground supported local-fork Memories first, then record missing "
                "baseline requirements separately."
            ),
            "--change-reason",
            "The bound evidence supports a slice, not a complete baseline.",
            "--focus-target",
            "campus-wiki",
        ],
    )

    assert revised.exit_code == 0, revised.output
    assert "Revision: 1" in revised.output
    assert "FOCUS · campus-wiki" in revised.output
    assert "Ground supported local-fork Memories first" in revised.output
    restored = store.load_ground_session("task-1-focus-cli")
    assert restored is not None
    assert restored.revision == 1
    assert len(restored.items) == 1
    assert restored.items[0].content == "REFINE GOAL"
    assert _non_ground_store_bytes(isolated_store) == non_ground_before
    assert all(
        store.list_checkpoints(context.name) == []
        for context in contexts
    )


def test_cli_focus_target_rejects_missing_unbound_and_competing_views(
    isolated_store,
):
    store = MemoryStore()
    raw, derived, targets, _ = _task_1_workbench(store)
    session = bind_ground_workbench(
        create_ground_session("focus-errors"),
        description=TASK_1_DESCRIPTION,
        raw_context=raw,
        derived_context=derived,
        target_contexts=targets,
        target_requirements=TASK_1_TARGET_REQUIREMENTS,
    )
    store.save_ground_session(session)
    path = isolated_store / "ground-sessions" / "focus-errors.json"
    before = path.read_bytes()

    unknown = runner.invoke(
        app,
        [
            "ground",
            "focus-errors",
            "--focus-target",
            "missing-target",
        ],
    )
    unknown_after_action_request = runner.invoke(
        app,
        [
            "ground",
            "focus-errors",
            "--revise-goal",
            "This revision must not be saved.",
            "--change-reason",
            "The focused target is invalid.",
            "--focus-target",
            "missing-target",
        ],
    )
    competing = runner.invoke(
        app,
        [
            "ground",
            "focus-errors",
            "--focus-target",
            "campus-wiki",
            "--snapshot",
        ],
    )
    absent = runner.invoke(
        app,
        [
            "ground",
            "focus-does-not-exist",
            "--focus-target",
            "campus-wiki",
        ],
    )
    bind_and_focus = runner.invoke(
        app,
        [
            "ground",
            "focus-errors",
            "--description",
            "Do not rebind while focusing.",
            "--focus-target",
            "campus-wiki",
        ],
    )
    unsupported_action = runner.invoke(
        app,
        [
            "ground",
            "focus-errors",
            "--select",
            "1",
            "--focus-target",
            "campus-wiki",
        ],
    )
    hidden_target_revision = runner.invoke(
        app,
        [
            "ground",
            "focus-errors",
            "--focus-target",
            "campus-wiki",
            "--revise-target",
            "participant/construction-updates/building-access",
            "--requirement-text",
            "This different target must not be changed.",
            "--change-reason",
            "The focused receipt would hide this effect.",
        ],
    )

    assert unknown.exit_code == 1
    assert "missing or ambiguous" in unknown.output
    assert unknown_after_action_request.exit_code == 1
    assert "missing or ambiguous" in unknown_after_action_request.output
    assert competing.exit_code == 1
    assert "either --snapshot or --focus-target" in competing.output
    assert absent.exit_code == 1
    assert "requires an existing bound Ground" in absent.output
    assert bind_and_focus.exit_code == 1
    assert "requires an already bound Ground" in bind_and_focus.output
    assert unsupported_action.exit_code == 1
    assert "combines only with one Goal" in unsupported_action.output
    assert hidden_target_revision.exit_code == 1
    assert "must identify the same target" in hidden_target_revision.output
    assert not (
        isolated_store
        / "ground-sessions"
        / "focus-does-not-exist.json"
    ).exists()
    assert path.read_bytes() == before


def test_target_focus_reports_stale_frames_and_sanitizes_text(
    isolated_store,
):
    store = MemoryStore()
    raw, derived, targets, _ = _task_1_workbench(store)
    contexts = (raw, derived, *targets)
    session = bind_ground_workbench(
        create_ground_session(
            "focus-stale",
            goal="Visible\x1b[31m Goal",
        ),
        description=TASK_1_DESCRIPTION,
        raw_context=raw,
        derived_context=derived,
        target_contexts=targets,
        target_requirements=TASK_1_TARGET_REQUIREMENTS,
    )
    store.save_ground_session(session)
    campus = next(
        context for context in targets if context.name == "campus-wiki"
    )
    campus.add("A changed target Memory.")
    store.save(campus)
    ground_path = isolated_store / "ground-sessions" / "focus-stale.json"
    context_path = store._context_file("campus-wiki")
    ground_before = ground_path.read_bytes()
    context_before = context_path.read_bytes()

    rendered = render_ground_focus(
        session,
        "campus-wiki",
        contexts,
    )

    assert "\x1b" not in rendered
    assert "Visible�[31m Goal" in rendered
    assert "OPEN · STALE" in rendered
    assert "0 bound · 1 current Memories" in rendered
    assert "STALE BOUND MATERIAL" in rendered
    assert "campus-wiki" in rendered
    assert "before changing Goal, Rules, or Memories" in rendered
    assert "SUPPORTED SLICE" not in rendered

    focused = runner.invoke(
        app,
        [
            "ground",
            "focus-stale",
            "--focus-target",
            "campus-wiki",
        ],
    )
    revision = runner.invoke(
        app,
        [
            "ground",
            "focus-stale",
            "--revise-goal",
            "This stale revision must not be saved.",
            "--change-reason",
            "The bound target changed.",
            "--focus-target",
            "campus-wiki",
        ],
    )

    assert focused.exit_code == 0, focused.output
    assert "OPEN · STALE" in focused.output
    assert revision.exit_code == 1
    assert "workbench is stale" in revision.output
    assert ground_path.read_bytes() == ground_before
    assert context_path.read_bytes() == context_before


def test_focus_requirement_uid_prefix_is_exact_or_unambiguous(
    isolated_store,
):
    store = MemoryStore()
    raw, derived, targets, _ = _task_1_workbench(store)
    session = bind_ground_workbench(
        create_ground_session("focus-prefix"),
        description=TASK_1_DESCRIPTION,
        raw_context=raw,
        derived_context=derived,
        target_contexts=targets,
        target_requirements=TASK_1_TARGET_REQUIREMENTS,
    )
    payload = session.to_dict()
    payload["requirements"][0]["uid"] = (
        "aaaaaaaa-0000-4000-8000-000000000001"
    )
    payload["requirements"][1]["uid"] = (
        "aaaaaaaa-0000-4000-8000-000000000002"
    )
    session = GroundSession.from_dict(payload)
    store.save_ground_session(session)
    path = isolated_store / "ground-sessions" / "focus-prefix.json"
    before = path.read_bytes()

    ambiguous = runner.invoke(
        app,
        [
            "ground",
            "focus-prefix",
            "--focus-target",
            "aaaaaaaa",
        ],
    )
    ambiguous_action = runner.invoke(
        app,
        [
            "ground",
            "focus-prefix",
            "--revise-goal",
            "This ambiguous revision must not be saved.",
            "--change-reason",
            "The selector is ambiguous.",
            "--focus-target",
            "aaaaaaaa",
        ],
    )
    exact_name = runner.invoke(
        app,
        [
            "ground",
            "focus-prefix",
            "--focus-target",
            "campus-wiki",
        ],
    )

    assert ambiguous.exit_code == 1
    assert "missing or ambiguous" in ambiguous.output
    assert ambiguous_action.exit_code == 1
    assert "missing or ambiguous" in ambiguous_action.output
    assert exact_name.exit_code == 0, exact_name.output
    assert "FOCUS · campus-wiki" in exact_name.output
    assert path.read_bytes() == before

    overlap_payload = session.to_dict()
    overlap_payload["requirements"][0]["uid"] = (
        "aaaaaaaa-0000-4000-8000-000000000001"
    )
    overlap_payload["requirements"][1]["uid"] = (
        "bbbbbbbb-0000-4000-8000-000000000002"
    )
    exact_target_uid = overlap_payload["requirements"][1][
        "target_context_uid"
    ]
    for frame in overlap_payload["frames"]:
        if frame["context_uid"] == exact_target_uid:
            frame["context_name"] = "aaaaaaaa"
            break
    overlap = GroundSession.from_dict(overlap_payload)

    assert (
        resolve_ground_requirement(overlap, "aaaaaaaa").uid
        == "bbbbbbbb-0000-4000-8000-000000000002"
    )


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
            "Materialize operational access guidance in the local campus-wiki "
            "fork and retain its verified fact in the matching construction "
            "child."
        ),
        case=candidate.content,
        source_context_uid=derived.uid,
        source_memory_uid=candidate.uid,
        target_context_names=(
            "campus-wiki",
            "participant/construction-updates/building-access",
        ),
        expected=(
            "Keep one atomic building-access Memory and materialize the "
            "corresponding visitor guidance in the local fork."
        ),
        rationale=(
            "The candidate is a verified access change with both a local "
            "source role and a local materialization role."
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
        "participant/construction-updates/building-access",
    )
    assert case.expected.startswith("Keep one atomic")
    assert case.rationale.startswith("The candidate is a verified")
    round_snapshot = render_ground_snapshot(
        revised,
        (raw, derived, *targets),
    )
    assert "2 · RULES" in round_snapshot
    assert "[PROPOSED · DISTILLED]" in round_snapshot
    assert "INDUCED_FROM_CASES" not in round_snapshot
    assert "3 · MEMORIES · FIT / BOUNDARY / CONTRAST" in round_snapshot
    assert "[PROPOSED · FIT · INCLUDE]" in round_snapshot
    assert f"input: {candidate.content}" in round_snapshot
    assert "output: Keep one atomic" in round_snapshot
    assert "notes: The candidate is a verified" in round_snapshot
    assert candidate.content in round_snapshot
    assert "campus-wiki" in round_snapshot
    assert "participant/construction-updates/building-access" in round_snapshot

    accepted_memory = review_ground_item(
        revised,
        case.uid,
        action="ACCEPT",
        response="Approve the traceable Ground Memory.",
        current_contexts=(raw, derived, *targets),
    )
    accepted_snapshot = render_ground_snapshot(
        accepted_memory,
        (raw, derived, *targets),
    )
    assert "ACCEPT MEMORY" in accepted_snapshot
    assert "ACCEPT CASE" not in accepted_snapshot
    persisted_decision = accepted_memory.items_of_kind("DECISION")[0]
    assert persisted_decision.content == "ACCEPT CASE"

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
        "participant/construction-updates/event-relocations",
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
        == "participant/construction-updates/event-relocations"
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
        rule="Materialize every verified access change in the local fork.",
        case=candidate.content,
        source_context_uid=derived.uid,
        source_memory_uid=candidate.uid,
        target_context_names=(
            "participant/construction-updates/building-access",
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
            "Materialize supported campus-facing effects; preserve unresolved "
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
        == "participant/construction-updates/building-access"
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
        target_by_name["participant/construction-updates/building-access"],
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
            "Build the Task 1 source and local materialization fixtures.",
            "--description",
            TASK_1_DESCRIPTION,
            "--raw-context",
            raw.name,
            "--derived-context",
            derived.name,
            "--publication-target",
            "campus-wiki",
            "--placement-target",
            "participant/construction-updates/building-access",
            "--blocked-target",
            (
                "campus-wiki=The provisioned local-fork "
                "baseline is absent from this Ground fixture."
            ),
            "--snapshot",
        ],
    )
    assert bound.exit_code == 0, bound.output
    assert "1 · GOAL" in bound.output
    assert "2 · RULES" in bound.output
    assert "3 · MEMORIES · FIT / BOUNDARY / CONTRAST" in bound.output

    proposed = runner.invoke(
        app,
        [
            "ground",
            "task-1-cli",
            "--propose-source",
            candidate.uid[:8],
            "--propose-rule",
            "Materialize supported access effects without inventing timing.",
            "--rule-provenance",
            "DISTILLED_FROM_GOAL",
            "--propose-target",
            "participant/construction-updates/building-access",
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
                "Build traceable source and local materialization fixtures "
                "without filling evidence gaps by invention."
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


def test_cli_binding_leaves_requirements_unspecified_and_direct_rule_skips_rationale(
    isolated_store,
) -> None:
    store = MemoryStore()
    raw, derived, targets, _candidate = _task_1_workbench(store)

    bound = runner.invoke(
        app,
        [
            "ground",
            "direct-rule",
            "--goal",
            "Learn one rule from reviewed examples.",
            "--description",
            "Bind the evidence and output frames without inventing policy.",
            "--raw-context",
            raw.name,
            "--derived-context",
            derived.name,
            "--publication-target",
            targets[0].name,
            "--snapshot",
        ],
    )

    assert bound.exit_code == 0, bound.output
    assert "(not specified)" in bound.output
    assert "campus-facing" not in bound.output
    session = store.load_ground_session("direct-rule")
    assert session is not None
    assert tuple(item.description for item in session.requirements) == ("",)

    direct = runner.invoke(
        app,
        [
            "ground",
            "direct-rule",
            "--propose-rule",
            "Use actual companies and their observed tickers.",
        ],
    )

    assert direct.exit_code == 0, direct.output
    updated = store.load_ground_session("direct-rule")
    assert updated is not None
    rule = updated.items_of_kind("RULE")[0]
    assert rule.rule_provenance == "USER_STATED"
    assert rule.rationale == ""

    derived_without_reason = runner.invoke(
        app,
        [
            "ground",
            "direct-rule",
            "--propose-rule",
            "Infer a second rule from the examples.",
            "--rule-provenance",
            "DISTILLED",
        ],
    )

    assert derived_without_reason.exit_code == 1
    assert "derived rule proposal requires --rationale" in (
        derived_without_reason.output.lower()
    )
    assert store.load_ground_session("direct-rule") == updated


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
            "participant/construction-updates/building-access",
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
            "participant/construction-updates/building-access",
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
            "participant/construction-updates/building-access",
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
        == "participant/construction-updates/building-access"
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
        rule="Materialize supported access effects.",
        case=candidate.content,
        source_context_uid=derived.uid,
        source_memory_uid=candidate.uid,
        target_context_names=(
            "participant/construction-updates/building-access",
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
        == "participant/construction-updates/building-access"
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
        rule="Materialize all access changes.",
        case=candidate.content,
        source_context_uid=derived.uid,
        source_memory_uid=candidate.uid,
        target_context_names=(
            "participant/construction-updates/building-access",
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
        == "participant/construction-updates/building-access"
    )
    assert target_requirement_status(accepted, requirement) == "COVERED"

    reopened = review_ground_item(
        accepted,
        rule.uid,
        action="REFINE",
        response="Materialize only supported campus-facing access changes.",
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
            "participant/construction-updates/building-access",
        ),
        expected="Materialize the supported entrance closure.",
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
            "participant/construction-updates/building-access",
        ),
        expected="Materialize the same supported entrance closure.",
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
        == "participant/construction-updates/building-access"
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
        expected="Materialize the supported closure.",
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
    rendered = render_ground_snapshot(
        restored,
        (raw, derived, *targets),
    )
    assert "3 · MEMORIES · FIT / BOUNDARY / CONTRAST" in rendered
    assert case_payload["kind"] == "CASE"


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
        expected="Materialize the supported closure.",
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
            "participant/construction-updates/building-access",
        ),
        expected="Materialize the supported entrance closure.",
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

    for version in (True, 0, 4):
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
        expected="Materialize the supported closure.",
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
