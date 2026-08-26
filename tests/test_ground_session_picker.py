from __future__ import annotations

from dataclasses import replace
import os

import pytest
from typer.testing import CliRunner

import memcommit.commands.ground.command as ground_command
import memcommit.commands.shared.operation_launcher_location as launcher_location_module
import memcommit.ops as ops
from memcommit.cli import app
from memcommit.commands.ground.session_picker import (
    ground_session_picker_location,
    list_ground_session_catalog,
    list_ground_session_entries,
    reload_selected_ground_session,
)
from memcommit.commands.ground.workspace_picker import (
    list_ground_workspace_draft_catalog,
    list_ground_workspace_catalog,
    reload_selected_ground_workspace_draft,
    reload_selected_ground_workspace,
)
from memcommit.commands.ground.shell import (
    GroundShellProposal,
    GroundShellResult,
)
from memcommit.interfaces.tui.components.operation_launcher.session import SessionOpenReceipt
from memcommit.ground import (
    GroundTargetSpec,
    bind_ground_workbench,
    create_ground_session,
)
from memcommit.ground_workspace_draft import GroundWorkspaceDraft
from memcommit.ground_workspace_draft_store import GroundWorkspaceDraftStore
from memcommit.ground_workspace_application import CreateGroundWorkspaceRequest
from memcommit.ground_workspace_runtime import (
    execute_ground_workspace_creation,
    ground_workspace_exists,
)
from memcommit.profile_config import (
    AUTHORING_PROFILE_UID,
    ProfileEntry,
    ProfileRegistry,
)
from memcommit.store import MemoryStore


runner = CliRunner()


def _workspace_draft() -> GroundWorkspaceDraft:
    return GroundWorkspaceDraft.create(
        workspace_name="projects/ticker-ground",
        goal="Find how real US ticker symbols are assigned.",
        understanding="Use actual US-listed companies.",
        question="Approve this Goal?",
        submitted_turns=("I want to understand real ticker assignment.",),
    )


def test_ground_session_entries_are_read_only_and_carry_exact_reopen_argv(
    isolated_store,
):
    store = MemoryStore(create=False)
    older = create_ground_session("older-ground", goal="Older Goal.")
    newer = create_ground_session("newer-ground", goal="Newer Goal.")
    store.save_ground_session(older)
    store.save_ground_session(newer)
    older_path = isolated_store / "ground-sessions" / "older-ground.json"
    newer_path = isolated_store / "ground-sessions" / "newer-ground.json"
    os.utime(older_path, (10, 10))
    os.utime(newer_path, (20, 20))
    before = {
        path.name: path.read_bytes()
        for path in (older_path, newer_path)
    }

    entries = list_ground_session_entries(store)

    assert {entry.key for entry in entries} == {
        "older-ground",
        "newer-ground",
    }
    by_key = {entry.key: entry for entry in entries}
    assert by_key["newer-ground"].sort_timestamp == 20
    assert by_key["newer-ground"].group == "Unbound"
    assert by_key["newer-ground"].reopen_argv == (
        "mem",
        "ground",
        "newer-ground",
    )
    assert {
        path.name: path.read_bytes()
        for path in (older_path, newer_path)
    } == before


def test_bound_ground_groups_by_raw_context_and_retains_all_contexts_in_detail(
    isolated_store,
):
    store = MemoryStore()
    raw = ops.init("temp/task-1")
    derived = ops.init("temp/task-1-atomized")
    target = ops.init("campus-wiki")
    session = bind_ground_workbench(
        create_ground_session(
            "task-1-fixture",
            goal="Build a traceable Task 1 fixture.",
        ),
        description="Use Task 1 source material to build the campus wiki.",
        raw_context=raw,
        derived_context=derived,
        target_contexts=(target,),
        target_requirements=(
            GroundTargetSpec(
                context_name=target.name,
                description="Cover the campus wiki target.",
            ),
        ),
    )
    store.save_ground_session(session)

    picker_entry = list_ground_session_entries(store)[0]

    assert picker_entry.group == "temp/task-1"
    assert (
        "Contexts: temp/task-1, temp/task-1-atomized, campus-wiki"
        in picker_entry.detail
    )


def test_physical_ticker_ground_is_listed_and_reopened_without_switching(
    isolated_store,
    monkeypatch,
):
    goal = (
        "Find reusable rules for generating consistent company tickers "
        "from company names and share-class details."
    )
    created_ground = runner.invoke(
        app,
        ["ground", "ticker-rules", "--goal", goal, "--snapshot"],
    )
    assert created_ground.exit_code == 0, created_ground.output
    rule = runner.invoke(
        app,
        [
            "ground",
            "ticker-rules",
            "--add-rule",
            "Use actual US-listed companies and their real ticker symbols.",
        ],
    )
    example = runner.invoke(
        app,
        ["ground", "ticker-rules", "--add-example", "Apple Inc. → AAPL"],
    )
    assert rule.exit_code == 0, rule.output
    assert example.exit_code == 0, example.output

    store = MemoryStore(create=False)
    catalog = list_ground_workspace_catalog(store)
    [selected] = catalog
    saved = reload_selected_ground_workspace(store, selected)
    entry = selected.picker_entry
    assert entry.kind == "ground-workspace"
    assert entry.title == "ticker-rules"
    assert entry.group == "Ground workspaces"
    assert "Physical Contexts: 6" in entry.detail

    before = {
        path.relative_to(isolated_store).as_posix(): path.read_bytes()
        for path in isolated_store.rglob("*")
        if path.is_file()
    }
    opened = []
    monkeypatch.setattr(ground_command, "_interactive_terminal", lambda: True)
    monkeypatch.setattr(
        ground_command,
        "choose_session",
        lambda *_args, **_kwargs: SessionOpenReceipt(
            kind="ground-workspace",
            key="ticker-rules",
            argv=("mem", "ground", "ticker-rules"),
        ),
    )
    monkeypatch.setattr(
        ground_command,
        "run_ground_workspace_tui",
        lambda workspace, **_kwargs: opened.append(workspace),
    )

    reopened = runner.invoke(app, ["ground"])

    assert reopened.exit_code == 0, reopened.output
    assert [(workspace.uid, workspace.name) for workspace in opened] == [
        (saved.uid, saved.name)
    ]
    assert {
        path.relative_to(isolated_store).as_posix(): path.read_bytes()
        for path in isolated_store.rglob("*")
        if path.is_file()
    } == before


def test_goal_draft_appears_in_the_same_ground_session_list(isolated_store):
    store = MemoryStore()
    draft = _workspace_draft()
    GroundWorkspaceDraftStore(store).save(draft, expected_digest=None)

    [entry] = list_ground_workspace_draft_catalog(store)
    picker = entry.picker_entry

    assert picker.kind == "ground-workspace-draft"
    assert picker.title == "projects/ticker-ground"
    assert picker.status == "DRAFT · rev 0 · NOT CREATED"
    assert picker.subtitle == draft.goal
    assert picker.reopen_argv == (
        "mem",
        "ground",
        "--resume-draft",
        draft.uid,
    )
    assert reload_selected_ground_workspace_draft(store, entry) == draft
    assert store.list_context_names() == []


def test_ground_picker_opens_a_draft_row_without_provider_replay(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    draft = _workspace_draft()
    GroundWorkspaceDraftStore(store).save(draft, expected_digest=None)
    opened = []

    monkeypatch.setattr(
        ground_command,
        "choose_session",
        lambda entries, **_kwargs: SessionOpenReceipt(
            kind="ground-workspace-draft",
            key=draft.uid,
            argv=("mem", "ground", "--resume-draft", draft.uid),
        ),
    )
    monkeypatch.setattr(
        ground_command,
        "_run_new_ground_shell",
        lambda *args, **kwargs: opened.append((args, kwargs)) or "CLOSED",
    )

    ground_command._run_ground_session_picker(store)

    assert opened == [((), {"draft": draft})]


def test_closing_a_goal_proposal_publishes_only_a_session_list_draft(
    isolated_store,
    monkeypatch,
):
    proposal = GroundShellProposal(
        ground_name="projects/ticker-ground",
        goal="Find how real US ticker symbols are assigned.",
        understanding="Use actual US-listed companies.",
        question="Approve this Goal?",
    )
    monkeypatch.setattr(
        ground_command,
        "run_ground_shell",
        lambda **_kwargs: GroundShellResult(
            status="CANCELLED",
            proposal=proposal,
            submitted_turns=(
                "I want to understand real ticker assignment.",
            ),
        ),
    )

    outcome = ground_command._run_new_ground_shell()

    assert outcome == "CLOSED"
    [draft] = GroundWorkspaceDraftStore(MemoryStore(create=False)).list()
    assert draft.workspace_name == proposal.ground_name
    assert draft.goal == proposal.goal
    assert MemoryStore(create=False).list_context_names() == []


def test_relocated_draft_materializes_only_at_exact_apply_and_then_disappears(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    draft = _workspace_draft()
    GroundWorkspaceDraftStore(store).save(draft, expected_digest=None)
    opened = []

    monkeypatch.setattr(
        ground_command,
        "_choose_ground_workspace_save_location",
        lambda _store, **_kwargs: "research/ticker-ground",
    )

    def apply(proposal):
        execute_ground_workspace_creation(
            CreateGroundWorkspaceRequest(
                name=proposal.ground_name,
                goal=proposal.goal,
            ),
            store=MemoryStore(),
        )
        return "created"

    def shell(**kwargs):
        resumed = kwargs["initial_proposal"]
        selected = kwargs["choose_save_location"](resumed.ground_name)
        assert selected == "research/ticker-ground"
        relocated = replace(resumed, ground_name=selected)
        kwargs["apply"](relocated)
        return GroundShellResult(
            status="APPLIED",
            proposal=relocated,
            actual_output="created",
            submitted_turns=kwargs["initial_submitted_turns"],
        )

    monkeypatch.setattr(ground_command, "_apply_new_ground_proposal", apply)
    monkeypatch.setattr(ground_command, "run_ground_shell", shell)
    monkeypatch.setattr(
        ground_command,
        "run_ground_workspace_tui",
        lambda workspace, **_kwargs: opened.append(workspace.name),
    )

    outcome = ground_command._run_new_ground_shell(draft=draft)

    assert outcome == "CLOSED"
    assert opened == ["research/ticker-ground"]
    assert ground_workspace_exists(store, "research/ticker-ground")
    assert not ground_workspace_exists(store, draft.workspace_name)
    assert GroundWorkspaceDraftStore(store).list() == ()


def test_ground_session_entries_do_not_create_missing_storage(isolated_store):
    store = MemoryStore(create=False)

    assert list_ground_session_entries(store) == ()
    assert not isolated_store.exists()


def test_empty_ground_catalog_still_opens_launcher_with_new_session_action(
    isolated_store,
    monkeypatch,
):
    seen = []

    def choose(entries, **kwargs):
        seen.append((tuple(entries), kwargs))
        return None

    monkeypatch.setattr(ground_command, "choose_session", choose)

    ground_command._run_ground_session_picker(MemoryStore(create=False))

    assert len(seen) == 1
    entries, kwargs = seen[0]
    assert entries == ()
    assert kwargs["title"] == "MEM GROUND · SESSIONS"
    assert kwargs["new_receipt"].action_label == "START NEW GROUND SESSION"
    assert "Start blank" in kwargs["new_receipt"].action_description
    assert "above the Goal" in kwargs["new_receipt"].action_description
    assert not isolated_store.exists()


def test_ground_picker_location_matches_frozen_store_not_live_active_profile(
    tmp_path,
    monkeypatch,
):
    authoring_root = tmp_path / "authoring"
    task_root = tmp_path / "task-1"
    task_uid = "11111111-1111-1111-1111-111111111111"
    registry = ProfileRegistry(
        generation=2,
        active_uid=task_uid,
        profiles=(
            ProfileEntry(
                uid=AUTHORING_PROFILE_UID,
                name="authoring",
                kind="AUTHORING",
            ),
            ProfileEntry(
                uid=task_uid,
                name="task-1",
                kind="MANAGED",
            ),
        ),
    )
    monkeypatch.setattr(launcher_location_module.store_module, "STORE_DIR", authoring_root)
    monkeypatch.setattr(launcher_location_module, "load_profile_registry", lambda: registry)
    monkeypatch.setattr(
        launcher_location_module,
        "profile_store_dir",
        lambda profile: authoring_root if profile.name == "authoring" else task_root,
    )

    location = ground_session_picker_location()

    assert location.profile_name == "authoring"
    assert location.store_path == str(authoring_root)


def test_ground_picker_location_marks_an_isolated_store_unregistered(
    isolated_store,
    monkeypatch,
):
    registry = ProfileRegistry(
        generation=1,
        active_uid=AUTHORING_PROFILE_UID,
        profiles=(
            ProfileEntry(
                uid=AUTHORING_PROFILE_UID,
                name="authoring",
                kind="AUTHORING",
            ),
        ),
    )
    monkeypatch.setattr(launcher_location_module, "load_profile_registry", lambda: registry)
    monkeypatch.setattr(
        launcher_location_module,
        "profile_store_dir",
        lambda _profile: isolated_store.parent / "other",
    )

    location = ground_session_picker_location()

    assert location.profile_name == "(unregistered)"
    assert location.store_path == str(isolated_store)


def test_ground_session_entries_reject_untrusted_storage_entry(
    isolated_store,
):
    root = isolated_store / "ground-sessions"
    root.mkdir(parents=True)
    (root / "unexpected.txt").write_text("not a Ground", encoding="utf-8")

    with pytest.raises(ValueError, match="storage is invalid"):
        list_ground_session_entries(MemoryStore(create=False))


def test_ground_catalog_ignores_atomic_writer_scratch_file(isolated_store):
    store = MemoryStore(create=False)
    session = create_ground_session("stable-ground")
    store.save_ground_session(session)
    scratch = (
        isolated_store
        / "ground-sessions"
        / ".stable-ground.json.write-0123456789abcdef0123456789abcdef"
    )
    scratch.write_text("unfinished", encoding="utf-8")

    catalog = list_ground_session_catalog(store)

    assert [entry.picker_entry.key for entry in catalog] == ["stable-ground"]


def test_ground_catalog_rejects_replacement_under_selected_name(isolated_store):
    store = MemoryStore(create=False)
    original = create_ground_session("stable-ground", goal="Original Goal.")
    store.save_ground_session(original)
    selected = list_ground_session_catalog(store)[0]
    replacement = create_ground_session(
        "stable-ground",
        goal="Replacement Goal.",
    )
    store.save_ground_session(replacement, replace=True)

    with pytest.raises(ValueError, match="changed while the list was open"):
        reload_selected_ground_session(store, selected)
