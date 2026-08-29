"""Context-rooted Ground workspace application and Store contracts."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from typer.testing import CliRunner

import memcommit.application.operations.ground.workspace_application as ground_workspace_application
from memcommit.core.context import Memory
from memcommit.application.capabilities.retained_history.command_history import (
    build_command_stacks,
)
from memcommit.application.operations.ground.workspace_model import (
    GROUND_WORKSPACE_LANES,
    GroundWorkspaceError,
    GroundWorkspaceManifest,
    create_ground_workspace_records,
    ground_workspace_context_names,
    load_ground_workspace_records,
)
from memcommit.application.operations.ground.workspace_application import (
    CreateGroundWorkspaceRequest,
)
from memcommit.application.operations.ground.workspace_runtime import (
    execute_ground_workspace_memory_add,
    execute_ground_workspace_creation,
    ground_workspace_exists,
    list_ground_workspace_names,
    load_ground_workspace,
)
from memcommit.application.operations.ground.workspace_history import (
    GroundWorkspaceHistoryError,
    build_ground_workspace_command_stack,
    undo_ground_workspace_command,
)
from memcommit.application.operations.ground.workspace_application import (
    AddGroundWorkspaceMemoryRequest,
)
from memcommit.adapters.console.commands.ground.workspace.location import (
    GroundWorkspaceLocationSetup,
    choose_ground_workspace_location,
)
from memcommit.adapters.console.commands.ground.workspace.viewer.model import (
    GroundWorkspaceViewerResult,
)
from memcommit.adapters.console.commands.ground.workspace.viewer.screen import (
    run_ground_workspace_viewer,
)
import memcommit.application.capabilities.ops as ops
from memcommit.adapters.console.entrypoint import app
from memcommit.persistence.store import MemoryStore


runner = CliRunner()


def test_workspace_records_are_one_real_root_and_fixed_real_subcontexts():
    workspace = create_ground_workspace_records(
        "project111",
        goal="Learn how real US ticker symbols are assigned.",
    )

    assert tuple(context.name for context in workspace.all_contexts) == (
        "project111",
        "project111/goals",
        "project111/rules",
        "project111/examples",
        "project111/contexts",
        "project111/relations",
    )
    assert len({context.uid for context in workspace.all_contexts}) == 6
    [goal] = tuple(workspace.goals.iter_items())
    assert isinstance(goal, Memory)
    assert goal.content == "Learn how real US ticker symbols are assigned."
    [manifest_memory] = tuple(workspace.root.iter_items())
    assert GroundWorkspaceManifest.from_memory(manifest_memory) == workspace.manifest


def test_workspace_name_can_be_a_real_namespaced_context_root():
    assert ground_workspace_context_names("research/project111") == (
        "research/project111",
        "research/project111/goals",
        "research/project111/rules",
        "research/project111/examples",
        "research/project111/contexts",
        "research/project111/relations",
    )


def test_manifest_is_an_ordinary_memory_with_canonical_structured_content():
    workspace = create_ground_workspace_records("project111")
    [memory] = tuple(workspace.root.iter_items())

    assert type(memory) is Memory
    assert json.loads(memory.content) == {
        "kind": "memcommit.ground-workspace",
        "revision": 0,
        "schema_version": 1,
        "status": "OPEN",
        "workspace_uid": workspace.root.uid,
    }


def test_loaded_workspace_rejects_a_missing_or_duplicate_manifest():
    workspace = create_ground_workspace_records("project111")
    workspace.root.clear()
    with pytest.raises(GroundWorkspaceError, match="exactly one manifest"):
        load_ground_workspace_records(
            workspace.root,
            **{lane: getattr(workspace, lane) for lane in GROUND_WORKSPACE_LANES},
        )


def test_application_module_has_no_store_command_typer_or_tui_imports():
    source = Path(ground_workspace_application.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.append(node.module)

    assert (
        tuple(
            name
            for name in imported
            if name == "typer"
            or name.startswith("prompt_toolkit")
            or name.startswith("memcommit.adapters.console.commands")
            or name.startswith("memcommit.adapters.interfaces")
            or name == "memcommit.store"
        )
        == ()
    )


def test_runtime_creates_the_complete_workspace_without_switching_current(
    isolated_store,
    capsys,
):
    store = MemoryStore()
    ordinary = ops.init("ordinary")
    store.create_context(ordinary)
    store.set_current(ordinary.name)

    result = execute_ground_workspace_creation(
        CreateGroundWorkspaceRequest(
            name="project111",
            goal="Learn how real US ticker symbols are assigned.",
        ),
        store=store,
    )

    assert result.name == "project111"
    assert result.context_names == ground_workspace_context_names("project111")
    assert len(set(result.context_uids)) == 6
    assert result.goal_memory_uid is not None
    assert store.current_context_name() == "ordinary"
    assert store.ground_sessions_dir.exists() is False
    restored = load_ground_workspace(store, "project111")
    assert restored.uid == result.workspace_uid
    assert tuple(context.name for context in restored.all_contexts) == (
        result.context_names
    )
    assert capsys.readouterr().out == ""


def test_creation_records_initial_checkpoints_but_not_a_global_session_file(
    isolated_store,
):
    store = MemoryStore()
    execute_ground_workspace_creation(
        CreateGroundWorkspaceRequest(name="project111"),
        store=store,
    )

    for name in ground_workspace_context_names("project111"):
        [checkpoint] = store.list_checkpoints(name)
        assert checkpoint["command"] == "ground-init"
        assert checkpoint["args"]["ground_workspace"]["workspace_name"] == (
            "project111"
        )
        assert len(checkpoint["args"]["command_contexts"]) == 6
    assert not store.ground_sessions_dir.exists()


def test_creation_is_all_new_and_rolls_back_every_context_on_collision(
    isolated_store,
):
    store = MemoryStore()
    store.create_context(ops.init("project111/examples"))

    with pytest.raises(FileExistsError, match="destination already exists"):
        execute_ground_workspace_creation(
            CreateGroundWorkspaceRequest(name="project111"),
            store=store,
        )

    assert store.list_context_names() == ["project111/examples"]


def test_workspace_catalog_uses_real_manifest_roots_only(isolated_store):
    store = MemoryStore()
    execute_ground_workspace_creation(
        CreateGroundWorkspaceRequest(name="z-project"),
        store=store,
    )
    execute_ground_workspace_creation(
        CreateGroundWorkspaceRequest(name="a-project"),
        store=store,
    )
    store.create_context(ops.init("ordinary"))

    assert list_ground_workspace_names(store) == ("a-project", "z-project")
    assert ground_workspace_exists(store, "a-project")
    assert not ground_workspace_exists(store, "ordinary")


def test_contexts_lane_accepts_the_same_memory_and_reference_shapes(
    isolated_store,
):
    store = MemoryStore()
    execute_ground_workspace_creation(
        CreateGroundWorkspaceRequest(name="project111"),
        store=store,
    )
    external = ops.init("external")
    source_memory = external.add("Apple Inc. uses AAPL.")
    store.create_context(external)
    lane = store.load_for_update("project111/contexts")
    reference = ops.embed_memory(source_memory, external, lane)
    store.save(lane)

    restored = load_ground_workspace(store, "project111")
    assert restored.contexts.memories[reference.uid].target_memory_uid == (
        source_memory.uid
    )


def test_invalid_context_name_fails_before_any_workspace_context_is_created(
    isolated_store,
):
    store = MemoryStore()

    with pytest.raises(ValueError):
        execute_ground_workspace_creation(
            CreateGroundWorkspaceRequest(name="bad//name"),
            store=store,
        )

    assert store.list_context_names() == []


def test_workspace_viewer_navigates_real_context_rows_without_store_effects():
    workspace = create_ground_workspace_records(
        "project111",
        goal="Learn real ticker rules.",
    )
    before = tuple(context.to_dict() for context in workspace.all_contexts)

    with create_pipe_input() as pipe_input:
        # Goals begins selected. Move to Rules, open its read-only Memory pane,
        # then close without invoking Switch or any workspace mutation.
        pipe_input.send_text("\x1b[B\rQ")
        result = run_ground_workspace_viewer(
            workspace,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result == GroundWorkspaceViewerResult("project111/rules")
    assert tuple(context.to_dict() for context in workspace.all_contexts) == before


def test_workspace_viewer_escape_closes_from_the_initial_real_goals_context():
    workspace = create_ground_workspace_records("project111")

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b")
        result = run_ground_workspace_viewer(
            workspace,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.context_name == "project111/goals"


def test_workspace_location_adapter_uses_shared_exact_context_name_contract():
    seen = []
    setup = GroundWorkspaceLocationSetup(
        initial_name="projects/new-ground",
        current_context="projects",
        context_names=("projects", "other"),
        validate_name=lambda value: value,
    )

    result = choose_ground_workspace_location(
        setup,
        chooser=lambda view: seen.append(view) or view.value,
    )

    assert result == "projects/new-ground"
    [view] = seen
    assert view.label == "NEW GROUND · SAVE LOCATION"
    assert view.state == "NOT CREATED"
    assert view.context_names == ("projects", "other")
    assert "created only after exact command approval" in view.detail


def test_cli_creates_and_reopens_the_physical_workspace_without_current_change(
    isolated_store,
):
    store = MemoryStore()
    store.create_context(ops.init("ordinary"))
    store.set_current("ordinary")

    created = runner.invoke(
        app,
        [
            "ground",
            "project111",
            "--goal",
            "Learn how real US ticker symbols are assigned.",
            "--snapshot",
        ],
    )

    assert created.exit_code == 0, created.output
    assert "Created Ground workspace 'project111' as 6 physical Contexts" in (
        created.output
    )
    assert "project111/goals · 1 direct item" in created.output
    assert "RAW_EVIDENCE" not in created.output
    assert "PUBLICATION_TARGET" not in created.output
    assert MemoryStore(create=False).current_context_name() == "ordinary"

    reopened = runner.invoke(app, ["ground", "project111", "--snapshot"])
    assert reopened.exit_code == 0, reopened.output
    assert "Created Ground workspace" not in reopened.output
    assert "GROUND WORKSPACE · project111" in reopened.output
    assert not (isolated_store / "ground-sessions").exists()


def test_cli_ground_goal_materializes_context_or_memory_operand_into_goals_lane(
    isolated_store,
) -> None:
    store = MemoryStore()
    source = ops.init("goal-library/cafe")
    source_goal = ops.add(
        source,
        "Help a friend's cafe improve through practical experiments.",
    )
    store.create_context(source)

    created = runner.invoke(
        app,
        [
            "ground",
            "cafe-ground",
            "--goal",
            source.name,
            "--snapshot",
        ],
    )

    assert created.exit_code == 0, created.output
    workspace = load_ground_workspace(store, "cafe-ground")
    [stored_goal] = tuple(workspace.goals.iter_items())
    assert stored_goal.content == source_goal.content
    [checkpoint] = store.list_checkpoints("cafe-ground/goals")
    assert checkpoint["args"]["goal_focus"]["kind"] == "CONTEXT"
    assert checkpoint["args"]["goal_focus"]["items"][0]["memory_uid"] == (
        source_goal.uid
    )

    replacement = ops.init("goal-library/revised")
    replacement_goal = ops.add(
        replacement,
        "Keep every recommendation reversible and affordable.",
    )
    store.create_context(replacement)
    revised = runner.invoke(
        app,
        [
            "ground",
            "cafe-ground",
            "--set-goal",
            f"{replacement.name}:{replacement_goal.uid[:8]}",
        ],
    )

    assert revised.exit_code == 0, revised.output
    [stored_goal] = tuple(
        load_ground_workspace(store, "cafe-ground").goals.iter_items()
    )
    assert stored_goal.content == replacement_goal.content
    latest = store.list_checkpoints("cafe-ground/goals")[0]
    assert latest["args"]["ground_workspace_command"]["goal_focus"]["kind"] == (
        "MEMORY"
    )


def test_cli_namespaced_workspace_is_a_real_context_subtree(isolated_store):
    result = runner.invoke(
        app,
        ["ground", "research/project111", "--snapshot"],
    )

    assert result.exit_code == 0, result.output
    assert "research/project111/relations" in result.output
    assert MemoryStore(create=False).list_context_names() == sorted(
        ground_workspace_context_names("research/project111")
    )


def test_ground_memory_add_touches_only_root_and_selected_physical_lane(
    isolated_store,
):
    store = MemoryStore()
    execute_ground_workspace_creation(
        CreateGroundWorkspaceRequest(name="project111"),
        store=store,
    )
    checkpoint_counts = {
        name: len(store.list_checkpoints(name))
        for name in ground_workspace_context_names("project111")
    }

    result = execute_ground_workspace_memory_add(
        AddGroundWorkspaceMemoryRequest(
            workspace_name="project111",
            lane="rules",
            content="Use actual US-listed companies and their real ticker symbols.",
            expected_revision=0,
        ),
        store=store,
    )

    assert result.revision == 1
    assert result.affected_context_names == (
        "project111",
        "project111/rules",
    )
    workspace = load_ground_workspace(store, "project111")
    assert workspace.manifest.revision == 1
    [rule] = tuple(workspace.rules.iter_items())
    assert isinstance(rule, Memory)
    assert rule.uid == result.memory_uid
    assert rule.content.startswith("Use actual US-listed")
    assert {
        name: len(store.list_checkpoints(name)) - checkpoint_counts[name]
        for name in checkpoint_counts
    } == {
        "project111": 1,
        "project111/goals": 0,
        "project111/rules": 1,
        "project111/examples": 0,
        "project111/contexts": 0,
        "project111/relations": 0,
    }
    root_checkpoint = store.list_checkpoints("project111")[0]
    rule_checkpoint = store.list_checkpoints("project111/rules")[0]
    assert root_checkpoint["args"]["ground_workspace_command"]["command_uid"] == (
        result.command_uid
    )
    assert rule_checkpoint["args"]["ground_workspace_command"]["command_uid"] == (
        result.command_uid
    )


def test_ground_memory_add_is_not_part_of_profile_global_undo(
    isolated_store,
):
    store = MemoryStore()
    execute_ground_workspace_creation(
        CreateGroundWorkspaceRequest(name="project111"),
        store=store,
    )
    execute_ground_workspace_memory_add(
        AddGroundWorkspaceMemoryRequest(
            workspace_name="project111",
            lane="examples",
            content="Apple Inc. is listed under AAPL.",
        ),
        store=store,
    )

    stacks = build_command_stacks(store)

    assert stacks.undo == ()
    assert stacks.redo == ()


def test_ground_memory_add_rejects_a_stale_workspace_revision(isolated_store):
    store = MemoryStore()
    execute_ground_workspace_creation(
        CreateGroundWorkspaceRequest(name="project111"),
        store=store,
    )
    execute_ground_workspace_memory_add(
        AddGroundWorkspaceMemoryRequest(
            workspace_name="project111",
            lane="rules",
            content="Use actual US-listed companies.",
        ),
        store=store,
    )

    with pytest.raises(GroundWorkspaceError, match="reviewed edit"):
        execute_ground_workspace_memory_add(
            AddGroundWorkspaceMemoryRequest(
                workspace_name="project111",
                lane="examples",
                content="Apple Inc. is listed under AAPL.",
                expected_revision=0,
            ),
            store=store,
        )


def test_ground_local_undo_restores_only_its_root_and_lane_as_one_unit(
    isolated_store,
):
    store = MemoryStore()
    execute_ground_workspace_creation(
        CreateGroundWorkspaceRequest(name="project111"),
        store=store,
    )
    rule = execute_ground_workspace_memory_add(
        AddGroundWorkspaceMemoryRequest(
            workspace_name="project111",
            lane="rules",
            content="Use actual US-listed companies.",
        ),
        store=store,
    )
    example = execute_ground_workspace_memory_add(
        AddGroundWorkspaceMemoryRequest(
            workspace_name="project111",
            lane="examples",
            content="Apple Inc. is listed under AAPL.",
        ),
        store=store,
    )
    assert [
        unit.uid
        for unit in build_ground_workspace_command_stack(store, "project111").undo
    ] == [rule.command_uid, example.command_uid]

    undone = undo_ground_workspace_command(store, "project111")

    assert undone.source_unit.uid == example.command_uid
    assert undone.revision == 3
    workspace = load_ground_workspace(store, "project111")
    assert workspace.manifest.revision == 3
    assert tuple(workspace.examples.iter_items()) == ()
    [retained_rule] = tuple(workspace.rules.iter_items())
    assert isinstance(retained_rule, Memory)
    assert retained_rule.uid == rule.memory_uid
    assert [
        unit.uid
        for unit in build_ground_workspace_command_stack(store, "project111").undo
    ] == [rule.command_uid]
    assert len(undone.checkpoints) == 2
    assert build_command_stacks(store).undo == ()


def test_ground_genesis_is_not_available_to_in_workspace_undo(isolated_store):
    store = MemoryStore()
    execute_ground_workspace_creation(
        CreateGroundWorkspaceRequest(name="project111"),
        store=store,
    )

    with pytest.raises(GroundWorkspaceHistoryError, match="no Ground-local"):
        undo_ground_workspace_command(store, "project111")


def test_ground_local_undo_fails_closed_after_direct_lane_drift(isolated_store):
    store = MemoryStore()
    execute_ground_workspace_creation(
        CreateGroundWorkspaceRequest(name="project111"),
        store=store,
    )
    execute_ground_workspace_memory_add(
        AddGroundWorkspaceMemoryRequest(
            workspace_name="project111",
            lane="rules",
            content="Use actual US-listed companies.",
        ),
        store=store,
    )
    rules = store.load_for_update("project111/rules")
    rules.add("A later external edit.")
    store.save(rules)

    with pytest.raises(Exception, match="changed after"):
        undo_ground_workspace_command(store, "project111")

    restored = load_ground_workspace(store, "project111")
    assert restored.manifest.revision == 1
    assert len(tuple(restored.rules.iter_items())) == 2


def test_cli_physical_ground_edits_and_local_undo_use_revision_guards(
    isolated_store,
):
    assert (
        runner.invoke(
            app,
            [
                "ground",
                "project111",
                "--goal",
                "Learn real ticker rules.",
                "--snapshot",
            ],
        ).exit_code
        == 0
    )

    rule = runner.invoke(
        app,
        [
            "ground",
            "project111",
            "--add-rule",
            "Use actual US-listed companies.",
            "--if-revision",
            "0",
        ],
    )
    assert rule.exit_code == 0, rule.output
    assert "Added Rule Memory" in rule.output
    assert "revision 1" in rule.output

    stale = runner.invoke(
        app,
        [
            "ground",
            "project111",
            "--add-example",
            "Apple Inc. is listed under AAPL.",
            "--if-revision",
            "0",
        ],
    )
    assert stale.exit_code == 1
    assert "changed after this command was reviewed" in stale.output

    example = runner.invoke(
        app,
        [
            "ground",
            "project111",
            "--add-example",
            "Apple Inc. is listed under AAPL.",
            "--if-revision",
            "1",
        ],
    )
    assert example.exit_code == 0, example.output
    assert "revision 2" in example.output

    undone = runner.invoke(
        app,
        ["ground", "project111", "--undo", "--if-revision", "2"],
    )
    assert undone.exit_code == 0, undone.output
    assert "Undid Ground action 'add-memory'" in undone.output
    workspace = load_ground_workspace(MemoryStore(create=False), "project111")
    assert workspace.manifest.revision == 3
    assert tuple(workspace.examples.iter_items()) == ()


def test_physical_ground_cli_no_longer_exposes_legacy_session_mutation(
    isolated_store,
):
    created = runner.invoke(app, ["ground", "project111", "--snapshot"])
    assert created.exit_code == 0, created.output

    legacy = runner.invoke(
        app,
        ["ground", "project111", "--propose-rule", "A legacy proposal"],
    )

    assert legacy.exit_code == 2
    assert "No such option: --propose-rule" in legacy.output
    assert not (isolated_store / "ground-sessions").exists()
