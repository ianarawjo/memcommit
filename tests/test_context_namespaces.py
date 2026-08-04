"""Tests for slash-delimited Context namespaces."""

import json

import pytest
from typer.testing import CliRunner

import memcommit.ops as ops
import memcommit.store as store_module
from memcommit.cli import app
from memcommit.context import AutoCheckpoint, Context
from memcommit.store import MemoryStore


runner = CliRunner(mix_stderr=False)


def test_nested_context_can_be_created_in_a_fresh_store(isolated_store):
    result = runner.invoke(app, ["init", "construction-updates/main"])

    assert result.exit_code == 0
    assert "Initialized context 'construction-updates/main'." in result.output

    store = MemoryStore()
    assert store.current_context_name() == "construction-updates/main"
    assert store.load_current().name == "construction-updates/main"
    assert (
        isolated_store
        / "contexts"
        / "construction-updates"
        / "main"
        / "context.json"
    ).is_file()
    assert len(store.list_checkpoints("construction-updates/main")) == 1


def test_nested_contexts_are_listed_by_full_name(isolated_store):
    store = MemoryStore()
    for name in (
        "construction-updates/route-changes",
        "alpha",
        "construction-updates",
    ):
        store.save(ops.init(name))
    store.set_current("construction-updates")

    assert store.list_context_names() == [
        "alpha",
        "construction-updates",
        "construction-updates/route-changes",
    ]

    result = runner.invoke(app, ["contexts"])
    assert result.exit_code == 0
    assert "  alpha" in result.output
    assert "* construction-updates" in result.output
    assert "  construction-updates/route-changes" in result.output


def test_nested_context_can_be_switched_and_updated(isolated_store):
    assert runner.invoke(app, ["init", "construction-updates/main"]).exit_code == 0
    assert (
        runner.invoke(app, ["init", "construction-updates/building-access"]).exit_code
        == 0
    )

    switched = runner.invoke(app, ["switch", "construction-updates/main"])
    added = runner.invoke(app, ["add", "Verified construction summary"])

    assert switched.exit_code == 0
    assert added.exit_code == 0
    store = MemoryStore()
    assert store.current_context_name() == "construction-updates/main"
    assert [
        memory.content for memory in store.load_current().memories.values()
    ] == ["Verified construction summary"]
    assert store.load("construction-updates/building-access").memories == {}


def test_nested_context_can_be_embedded_in_main(isolated_store):
    assert runner.invoke(app, ["init", "construction-updates/main"]).exit_code == 0
    assert (
        runner.invoke(app, ["init", "construction-updates/building-access"]).exit_code
        == 0
    )

    embedded = runner.invoke(
        app,
        [
            "embed",
            "construction-updates/building-access",
            "--into",
            "construction-updates/main",
        ],
    )
    listed = runner.invoke(app, ["ls", "construction-updates/main"])

    assert embedded.exit_code == 0
    assert listed.exit_code == 0
    assert "construction-updates/building-access" in listed.output
    main = MemoryStore().load("construction-updates/main")
    assert any(
        isinstance(item, Context)
        and item.name == "construction-updates/building-access"
        for item in main.iter_items()
    )


def test_branch_can_create_a_context_in_another_namespace(isolated_store):
    assert runner.invoke(app, ["init", "construction-updates/main"]).exit_code == 0

    result = runner.invoke(app, ["branch", "review/main"])

    assert result.exit_code == 0
    store = MemoryStore()
    assert store.context_exists("review/main")
    assert store.current_context_name() == "review/main"
    assert len(store.list_checkpoints("review/main")) == 1


def test_branch_does_not_leave_target_when_source_history_is_unsafe(isolated_store):
    assert runner.invoke(app, ["init", "construction-updates/main"]).exit_code == 0
    checkpoints = (
        isolated_store
        / "contexts"
        / "construction-updates"
        / "main"
        / "checkpoints"
    )
    for checkpoint in checkpoints.iterdir():
        checkpoint.unlink()
    checkpoints.rmdir()
    outside = isolated_store.parent / "outside-branch-checkpoints"
    outside.mkdir()
    checkpoints.symlink_to(outside, target_is_directory=True)

    result = runner.invoke(app, ["branch", "review/main"])

    assert result.exit_code == 1
    store = MemoryStore()
    assert not store.context_exists("review/main")
    assert store.current_context_name() == "construction-updates/main"
    assert list(outside.iterdir()) == []


def test_branch_does_not_adopt_or_delete_nonempty_target_directory(isolated_store):
    assert runner.invoke(app, ["init", "construction-updates/main"]).exit_code == 0
    target_dir = isolated_store / "contexts" / "review" / "main"
    target_dir.mkdir(parents=True)
    sentinel = target_dir / "keep-me.txt"
    sentinel.write_text("existing data")

    result = runner.invoke(app, ["branch", "review/main"])

    assert result.exit_code == 1
    assert "already exists and is not empty" in result.stderr
    assert sentinel.read_text() == "existing data"
    assert not (target_dir / "context.json").exists()
    assert MemoryStore().current_context_name() == "construction-updates/main"


def test_namespace_siblings_can_coexist(isolated_store):
    store = MemoryStore()
    store.save(ops.init("construction-updates/main"))
    store.save(ops.init("construction-updates/building-access"))

    assert store.context_exists("construction-updates/main")
    assert store.context_exists("construction-updates/building-access")
    assert not store.context_exists("construction-updates")


def test_root_and_descendant_contexts_coexist_when_root_is_created_first(
    isolated_store,
):
    store = MemoryStore()
    root = ops.init("construction-updates")
    ops.add(root, "Root summary.")
    store.save(
        root,
        AutoCheckpoint(command="init", args={}, description="root first"),
    )
    child = ops.init("construction-updates/building-access")
    ops.add(child, "Child detail.")
    store.save(
        child,
        AutoCheckpoint(command="init", args={}, description="child second"),
    )

    assert store.context_exists("construction-updates")
    assert store.context_exists("construction-updates/building-access")
    assert store.list_context_names() == [
        "construction-updates",
        "construction-updates/building-access",
    ]
    assert [item.content for item in store.load("construction-updates").iter_items()] == [
        "Root summary."
    ]
    assert [
        item.content
        for item in store.load("construction-updates/building-access").iter_items()
    ] == ["Child detail."]
    assert len(store.list_checkpoints("construction-updates")) == 1
    assert len(store.list_checkpoints("construction-updates/building-access")) == 1


def test_root_context_can_be_created_after_descendant_without_changing_child(
    isolated_store,
):
    store = MemoryStore()
    child = ops.init("construction-updates/building-access")
    ops.add(child, "Existing child detail.")
    store.save(
        child,
        AutoCheckpoint(command="init", args={}, description="child first"),
    )
    child_uid = child.uid
    child_checkpoints = store.list_checkpoints(
        "construction-updates/building-access"
    )

    root = ops.init("construction-updates")
    store.save(
        root,
        AutoCheckpoint(command="init", args={}, description="root second"),
    )

    assert store.context_exists("construction-updates")
    assert store.context_exists("construction-updates/building-access")
    reloaded_child = store.load("construction-updates/building-access")
    assert reloaded_child.uid == child_uid
    assert [item.content for item in reloaded_child.iter_items()] == [
        "Existing child detail."
    ]
    assert (
        store.list_checkpoints("construction-updates/building-access")
        == child_checkpoints
    )
    assert len(store.list_checkpoints("construction-updates")) == 1


def test_cli_initializes_root_after_child_and_switches_to_root(isolated_store):
    assert (
        runner.invoke(
            app,
            ["init", "construction-updates/building-access"],
        ).exit_code
        == 0
    )

    result = runner.invoke(app, ["init", "construction-updates"])

    assert result.exit_code == 0
    assert MemoryStore().current_context_name() == "construction-updates"
    assert MemoryStore().context_exists("construction-updates/building-access")


def test_path_descendant_is_listed_for_navigation_without_leaking_content(
    isolated_store,
):
    assert (
        runner.invoke(
            app,
            ["init", "construction-updates/building-access"],
        ).exit_code
        == 0
    )
    assert (
        runner.invoke(app, ["add", "Child-only detail."]).exit_code
        == 0
    )
    assert runner.invoke(app, ["init", "construction-updates"]).exit_code == 0

    direct = runner.invoke(app, ["ls", "construction-updates"])
    recursive = runner.invoke(app, ["ls", "-R", "construction-updates"])

    assert direct.exit_code == 0
    assert recursive.exit_code == 0
    assert "  1 item\n" in direct.output
    assert "construction-updates/building-access" in direct.output
    assert "Child-only detail." not in direct.output
    assert "construction-updates/building-access" in recursive.output
    assert "Child-only detail." in recursive.output


def test_explicit_embed_deduplicates_lexical_child_in_list(
    isolated_store,
):
    assert (
        runner.invoke(
            app,
            ["init", "construction-updates/building-access"],
        ).exit_code
        == 0
    )
    assert runner.invoke(app, ["add", "Embedded child detail."]).exit_code == 0
    assert (
        runner.invoke(
            app,
            ["init", "construction-updates/unembedded"],
        ).exit_code
        == 0
    )
    assert runner.invoke(app, ["add", "Unembedded detail."]).exit_code == 0
    assert runner.invoke(app, ["init", "construction-updates"]).exit_code == 0
    assert runner.invoke(app, ["add", "Root summary."]).exit_code == 0
    assert (
        runner.invoke(
            app,
            [
                "embed",
                "construction-updates/building-access",
                "--into",
                "construction-updates",
            ],
        ).exit_code
        == 0
    )

    direct = runner.invoke(app, ["ls", "construction-updates"])
    recursive = runner.invoke(app, ["ls", "-R", "construction-updates"])

    assert direct.exit_code == 0
    assert "  3 items\n" in direct.output
    assert direct.output.count("construction-updates/building-access") == 1
    assert direct.output.count("construction-updates/unembedded") == 1
    assert direct.output.index("construction-updates/building-access") < (
        direct.output.index("construction-updates/unembedded")
    )
    assert "Root summary." in direct.output
    assert "Embedded child detail." not in direct.output
    assert "Unembedded detail." not in direct.output
    assert recursive.exit_code == 0
    assert recursive.output.count("construction-updates/building-access") == 1
    assert recursive.output.count("construction-updates/unembedded") == 1
    assert "Embedded child detail." in recursive.output
    assert "Unembedded detail." in recursive.output


def test_ls_sorts_immediate_children_before_current_memories(isolated_store):
    assert runner.invoke(app, ["init", "test/update/to"]).exit_code == 0
    assert runner.invoke(app, ["add", "To-only detail."]).exit_code == 0
    assert runner.invoke(app, ["init", "test/update/from"]).exit_code == 0
    assert runner.invoke(app, ["add", "From-only detail."]).exit_code == 0
    assert (
        runner.invoke(app, ["init", "test/update/from/deep"]).exit_code == 0
    )
    assert runner.invoke(app, ["add", "Deep-only detail."]).exit_code == 0
    assert runner.invoke(app, ["init", "test/update"]).exit_code == 0
    assert runner.invoke(app, ["add", "Current summary."]).exit_code == 0

    direct = runner.invoke(app, ["ls", "test/update"])
    recursive = runner.invoke(app, ["ls", "-R", "test/update"])

    assert direct.exit_code == 0
    assert "  3 items\n" in direct.output
    assert "From-only detail." not in direct.output
    assert "To-only detail." not in direct.output
    assert "test/update/from/deep" not in direct.output
    assert "Deep-only detail." not in direct.output
    direct_lines = direct.output.splitlines()
    from_index = next(
        index
        for index, line in enumerate(direct_lines)
        if line.endswith("] test/update/from")
    )
    to_index = next(
        index
        for index, line in enumerate(direct_lines)
        if line.endswith("] test/update/to")
    )
    summary_index = next(
        index
        for index, line in enumerate(direct_lines)
        if "[memory  " in line
        and line.endswith("] Current summary.")
    )
    assert from_index < to_index < summary_index
    assert recursive.exit_code == 0
    assert "From-only detail." in recursive.output
    assert "To-only detail." in recursive.output
    assert "test/update/from/deep" in recursive.output
    assert "Deep-only detail." in recursive.output


def test_ls_does_not_synthesize_a_missing_intermediate_context(
    isolated_store,
):
    assert runner.invoke(app, ["init", "root/missing/leaf"]).exit_code == 0
    assert runner.invoke(app, ["add", "Leaf-only detail."]).exit_code == 0
    assert runner.invoke(app, ["init", "root"]).exit_code == 0

    direct = runner.invoke(app, ["ls", "root"])
    recursive = runner.invoke(app, ["ls", "-R", "root"])

    assert direct.exit_code == 0
    assert recursive.exit_code == 0
    assert "(no items)" in direct.output
    assert "root/missing" not in direct.output
    assert "root/missing" not in recursive.output
    assert "Leaf-only detail." not in recursive.output


def test_ls_resolves_relative_existing_context_locator(isolated_store):
    assert runner.invoke(app, ["init", "test/update/to"]).exit_code == 0
    assert runner.invoke(app, ["add", "Sibling detail."]).exit_code == 0
    assert runner.invoke(app, ["init", "test/update/from"]).exit_code == 0

    result = runner.invoke(app, ["ls", "../to"])

    assert result.exit_code == 0
    assert "Context: test/update/to" in result.output
    assert "Sibling detail." in result.output


def test_switch_and_add_to_root_is_independent_of_descendant(isolated_store):
    assert (
        runner.invoke(
            app,
            ["init", "construction-updates/building-access"],
        ).exit_code
        == 0
    )
    assert runner.invoke(app, ["add", "Child detail."]).exit_code == 0
    assert runner.invoke(app, ["init", "construction-updates"]).exit_code == 0
    assert runner.invoke(app, ["add", "Root detail."]).exit_code == 0
    assert (
        runner.invoke(
            app,
            ["switch", "construction-updates/building-access"],
        ).exit_code
        == 0
    )
    assert runner.invoke(app, ["add", "Second child detail."]).exit_code == 0
    assert (
        runner.invoke(app, ["switch", "construction-updates"]).exit_code
        == 0
    )

    store = MemoryStore()
    assert store.current_context_name() == "construction-updates"
    assert [item.content for item in store.load_current().iter_items()] == [
        "Root detail."
    ]
    assert [
        item.content
        for item in store.load(
            "construction-updates/building-access"
        ).iter_items()
    ] == ["Child detail.", "Second child detail."]


def test_clear_root_preserves_descendant_context_and_data(isolated_store):
    assert (
        runner.invoke(
            app,
            ["init", "construction-updates/building-access"],
        ).exit_code
        == 0
    )
    assert runner.invoke(app, ["add", "Child survives."]).exit_code == 0
    assert runner.invoke(app, ["init", "construction-updates"]).exit_code == 0
    assert runner.invoke(app, ["add", "Root is cleared."]).exit_code == 0
    assert (
        runner.invoke(
            app,
            [
                "embed",
                "construction-updates/building-access",
                "--into",
                "construction-updates",
            ],
        ).exit_code
        == 0
    )

    result = runner.invoke(
        app,
        ["clear", "construction-updates", "--force"],
    )

    assert result.exit_code == 0
    store = MemoryStore()
    assert store.load("construction-updates").memories == {}
    assert store.context_exists("construction-updates/building-access")
    assert [
        item.content
        for item in store.load(
            "construction-updates/building-access"
        ).iter_items()
    ] == ["Child survives."]


def test_branch_can_create_root_alongside_existing_descendant(isolated_store):
    assert runner.invoke(app, ["init", "source"]).exit_code == 0
    assert runner.invoke(app, ["add", "Branched root data."]).exit_code == 0
    assert (
        runner.invoke(app, ["init", "review/existing-child"]).exit_code
        == 0
    )
    assert runner.invoke(app, ["add", "Existing child data."]).exit_code == 0
    store = MemoryStore()
    child_before = store.load("review/existing-child")
    assert runner.invoke(app, ["switch", "source"]).exit_code == 0
    source_history = store.list_checkpoints("source")

    result = runner.invoke(app, ["branch", "review"])

    assert result.exit_code == 0
    assert store.current_context_name() == "review"
    assert store.context_exists("review")
    assert store.context_exists("review/existing-child")
    assert [item.content for item in store.load("review").iter_items()] == [
        "Branched root data."
    ]
    child_after = store.load("review/existing-child")
    assert child_after.uid == child_before.uid
    assert [item.content for item in child_after.iter_items()] == [
        "Existing child data."
    ]
    assert store.list_checkpoints("review") == source_history
    assert runner.invoke(app, ["add", "Review-only change."]).exit_code == 0
    assert store.list_checkpoints("source") == source_history
    assert len(store.list_checkpoints("review")) == len(source_history) + 1


def test_failed_root_branch_rollback_preserves_existing_descendant(
    isolated_store,
    monkeypatch,
):
    assert runner.invoke(app, ["init", "source"]).exit_code == 0
    assert runner.invoke(app, ["init", "review/existing-child"]).exit_code == 0
    store = MemoryStore()
    child_uid = store.load("review/existing-child").uid
    assert runner.invoke(app, ["switch", "source"]).exit_code == 0

    original_write = store_module._write_bytes_atomic

    def fail_copy(path, data):
        if path.parent.parent.name == "review":
            raise OSError("forced checkpoint copy failure")
        return original_write(path, data)

    monkeypatch.setattr(store_module, "_write_bytes_atomic", fail_copy)

    result = runner.invoke(app, ["branch", "review"])

    assert result.exit_code == 1
    assert "forced checkpoint copy failure" in result.stderr
    assert not store.context_exists("review")
    assert store.context_exists("review/existing-child")
    assert store.load("review/existing-child").uid == child_uid
    assert store.current_context_name() == "source"


def test_root_revert_does_not_change_descendant_data_or_history(isolated_store):
    assert runner.invoke(app, ["init", "root/child"]).exit_code == 0
    assert runner.invoke(app, ["add", "Child before root revert."]).exit_code == 0
    store = MemoryStore()
    child_uid = store.load("root/child").uid
    child_history = store.list_checkpoints("root/child")
    assert runner.invoke(app, ["init", "root"]).exit_code == 0
    root_init_checkpoint = store.list_checkpoints("root")[0]["uid"]
    assert runner.invoke(app, ["add", "Root change to revert."]).exit_code == 0

    result = runner.invoke(app, ["revert", root_init_checkpoint[:8]])

    assert result.exit_code == 0
    assert store.load("root").memories == {}
    assert store.load("root/child").uid == child_uid
    assert [
        item.content for item in store.load("root/child").iter_items()
    ] == ["Child before root revert."]
    assert store.list_checkpoints("root/child") == child_history


def test_delete_and_recreate_root_keeps_descendant_identity_and_history(
    isolated_store,
):
    store = MemoryStore()
    root = ops.init("root")
    store.save(root)
    old_root_uid = root.uid
    child = ops.init("root/child")
    ops.add(child, "Persistent child.")
    store.save(
        child,
        AutoCheckpoint(command="init", args={}, description="child"),
    )
    child_history = store.list_checkpoints("root/child")

    store.delete("root")
    result = runner.invoke(app, ["init", "root"])

    assert result.exit_code == 0
    assert store.load("root").uid != old_root_uid
    assert store.load("root").memories == {}
    assert store.load("root/child").uid == child.uid
    assert [item.content for item in store.load("root/child").iter_items()] == [
        "Persistent child."
    ]
    assert store.list_checkpoints("root/child") == child_history


@pytest.mark.parametrize(
    "name",
    [
        "",
        "/absolute",
        "trailing/",
        "double//slash",
        ".",
        "..",
        "./child",
        "parent/.",
        "parent/../sibling",
        "../escape",
        r"a\b",
        "C:/absolute",
        "control/\x1fcharacter",
        "context.json",
        "checkpoints",
        "parent/context.json",
        "parent/checkpoints",
        "CONTEXT.JSON/child",
        "Checkpoints/child",
    ],
)
def test_invalid_context_names_cannot_be_saved(isolated_store, name):
    store = MemoryStore()

    with pytest.raises(ValueError, match="Context name|Invalid context name"):
        store.save(ops.init(name))

    assert store.list_context_names() == []


def test_cli_rejects_invalid_name_without_partial_state(isolated_store):
    result = runner.invoke(app, ["init", "../outside"])

    assert result.exit_code == 1
    assert "Invalid context name" in result.stderr
    assert MemoryStore().current_context_name() is None
    assert not (isolated_store.parent / "outside").exists()


@pytest.mark.parametrize(
    "name",
    [
        "context.json",
        "checkpoints",
        "parent/context.json",
        "parent/checkpoints",
        "CONTEXT.JSON/child",
        "Checkpoints/child",
    ],
)
def test_cli_rejects_reserved_storage_segments_without_partial_state(
    isolated_store,
    name,
):
    result = runner.invoke(app, ["init", name])

    assert result.exit_code == 1
    assert "reserved for Context storage" in result.stderr
    assert MemoryStore().current_context_name() is None
    assert MemoryStore().list_context_names() == []


def test_checkpoint_requires_saved_context_and_leaves_no_orphan_directory(
    isolated_store,
):
    store = MemoryStore()
    unsaved = ops.init("unsaved/root")

    with pytest.raises(FileNotFoundError, match="must be saved"):
        store.checkpoint(unsaved, "must fail")

    assert not (
        isolated_store / "contexts" / "unsaved" / "root" / "checkpoints"
    ).exists()


def test_init_rejects_file_used_as_namespace_component(isolated_store):
    MemoryStore()
    blocker = isolated_store / "contexts" / "blocked"
    blocker.write_text("existing data")

    result = runner.invoke(app, ["init", "blocked/main"])

    assert result.exit_code == 1
    assert "is not a directory" in result.stderr
    assert blocker.read_text() == "existing data"
    assert MemoryStore().current_context_name() is None


def test_namespace_symlink_cannot_escape_store(isolated_store):
    store = MemoryStore()
    outside = isolated_store.parent / "outside"
    outside.mkdir()
    (isolated_store / "contexts" / "escape").symlink_to(
        outside,
        target_is_directory=True,
    )

    with pytest.raises(ValueError, match="symbolic links are not allowed"):
        store.save(ops.init("escape/context"))

    assert not (outside / "context" / "context.json").exists()


def test_namespace_symlink_alias_cannot_delete_real_context(isolated_store):
    store = MemoryStore()
    store.save(ops.init("real/context"))
    (isolated_store / "contexts" / "alias").symlink_to(
        isolated_store / "contexts" / "real",
        target_is_directory=True,
    )

    with pytest.raises(FileNotFoundError):
        store.delete("alias/context")

    assert store.context_exists("real/context")


def test_ancestor_context_file_symlink_does_not_hide_nested_context(isolated_store):
    store = MemoryStore()
    namespace = isolated_store / "contexts" / "namespace"
    namespace.mkdir()
    outside_context = isolated_store.parent / "outside-context.json"
    outside_context.write_text(json.dumps(ops.init("namespace").to_dict()))
    (namespace / "context.json").symlink_to(outside_context)

    store.save(ops.init("namespace/main"))

    assert not store.context_exists("namespace")
    assert store.context_exists("namespace/main")
    assert store.list_context_names() == ["namespace/main"]


def test_checkpoint_symlink_cannot_write_outside_store(isolated_store):
    store = MemoryStore()
    context = ops.init("construction-updates/main")
    store.save(context)
    checkpoints = (
        isolated_store
        / "contexts"
        / "construction-updates"
        / "main"
        / "checkpoints"
    )
    checkpoints.rmdir()
    outside = isolated_store.parent / "outside-checkpoints"
    outside.mkdir()
    checkpoints.symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="checkpoints.*symbolic link"):
        store.save(
            context,
            AutoCheckpoint(command="test", args={}, description="must stay local"),
        )

    assert list(outside.iterdir()) == []


def test_deleting_leaf_preserves_sibling_and_prunes_empty_namespace(isolated_store):
    store = MemoryStore()
    root = ops.init("construction-updates")
    ops.add(root, "Root remains.")
    store.save(root)
    store.save(ops.init("construction-updates/main"))
    store.save(ops.init("construction-updates/building-access"))
    store.set_current("construction-updates/building-access")

    store.delete("construction-updates/main")

    assert not store.context_exists("construction-updates/main")
    assert store.context_exists("construction-updates")
    assert store.context_exists("construction-updates/building-access")
    assert store.current_context_name() == "construction-updates/building-access"
    assert (isolated_store / "contexts" / "construction-updates").is_dir()

    store.delete("construction-updates/building-access")

    assert store.context_exists("construction-updates")
    assert [item.content for item in store.load("construction-updates").iter_items()] == [
        "Root remains."
    ]
    assert (isolated_store / "contexts" / "construction-updates").is_dir()
    assert store.current_context_name() is None


def test_deleting_root_preserves_descendant_context_and_history(isolated_store):
    store = MemoryStore()
    root = ops.init("parent")
    ops.add(root, "Root data.")
    store.save(
        root,
        AutoCheckpoint(command="init", args={}, description="root"),
    )
    child = ops.init("parent/child")
    ops.add(child, "Child data.")
    store.save(
        child,
        AutoCheckpoint(command="init", args={}, description="child"),
    )
    child_uid = child.uid
    child_checkpoints = store.list_checkpoints("parent/child")
    store.set_current("parent/child")

    store.delete("parent")

    assert not store.context_exists("parent")
    assert store.context_exists("parent/child")
    assert store.current_context_name() == "parent/child"
    assert store.load("parent/child").uid == child_uid
    assert [item.content for item in store.load("parent/child").iter_items()] == [
        "Child data."
    ]
    assert store.list_checkpoints("parent/child") == child_checkpoints
    root_dir = isolated_store / "contexts" / "parent"
    assert not (root_dir / "context.json").exists()
    assert not (root_dir / "checkpoints").exists()
    assert (root_dir / "child" / "context.json").is_file()


def test_deleting_current_root_clears_current_but_preserves_child(isolated_store):
    store = MemoryStore()
    store.save(ops.init("parent"))
    store.save(ops.init("parent/child"))
    store.set_current("parent")

    store.delete("parent")

    assert store.current_context_name() is None
    assert not store.context_exists("parent")
    assert store.context_exists("parent/child")


def test_delete_rejects_checkpoint_symlink_without_touching_child_or_target(
    isolated_store,
):
    store = MemoryStore()
    root = ops.init("parent")
    store.save(root)
    store.save(ops.init("parent/child"))
    checkpoints = isolated_store / "contexts" / "parent" / "checkpoints"
    checkpoints.rmdir()
    outside = isolated_store.parent / "outside-root-delete"
    outside.mkdir()
    sentinel = outside / "keep.txt"
    sentinel.write_text("keep")
    checkpoints.symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="checkpoints.*symbolic link"):
        store.delete("parent")

    assert store.context_exists("parent")
    assert store.context_exists("parent/child")
    assert sentinel.read_text() == "keep"


def test_load_rejects_context_name_mismatch(isolated_store):
    store = MemoryStore()
    store.save(ops.init("construction-updates/main"))
    context_file = (
        isolated_store
        / "contexts"
        / "construction-updates"
        / "main"
        / "context.json"
    )
    data = json.loads(context_file.read_text())
    data["name"] = "other/context"
    context_file.write_text(json.dumps(data))

    with pytest.raises(ValueError, match="declares a different name"):
        store.load("construction-updates/main")


def test_mismatched_context_is_not_listed_or_switchable(isolated_store):
    assert runner.invoke(app, ["init", "valid/main"]).exit_code == 0
    store = MemoryStore()
    store.save(ops.init("broken/main"))
    context_file = (
        isolated_store / "contexts" / "broken" / "main" / "context.json"
    )
    data = json.loads(context_file.read_text())
    data["name"] = "spoofed/main"
    context_file.write_text(json.dumps(data))

    listed = runner.invoke(app, ["contexts"])
    switched = runner.invoke(app, ["switch", "broken/main"])

    assert listed.exit_code == 0
    assert "broken/main" not in listed.output
    assert switched.exit_code == 1
    assert "declares a different name" in switched.stderr
    assert MemoryStore().current_context_name() == "valid/main"


@pytest.mark.parametrize(
    "malformed",
    [
        None,
        [],
        {},
        {"name": "broken/main"},
        {"uid": "uid", "name": "broken/main", "memories": []},
    ],
)
def test_malformed_context_is_not_listed_or_switchable(
    isolated_store,
    malformed,
):
    assert runner.invoke(app, ["init", "valid/main"]).exit_code == 0
    broken_dir = isolated_store / "contexts" / "broken" / "main"
    broken_dir.mkdir(parents=True)
    (broken_dir / "context.json").write_text(json.dumps(malformed))

    listed = runner.invoke(app, ["contexts"])
    switched = runner.invoke(app, ["switch", "broken/main"])

    assert listed.exit_code == 0
    assert "broken/main" not in listed.output
    assert switched.exit_code == 1
    assert MemoryStore().current_context_name() == "valid/main"


def test_checkpoint_artifact_is_not_listed_as_nested_context(isolated_store):
    store = MemoryStore()
    store.save(ops.init("construction-updates"))
    context = ops.init("construction-updates/main")
    store.save(
        context,
        AutoCheckpoint(command="init", args={}, description="initial"),
    )
    fake_context_file = (
        isolated_store
        / "contexts"
        / "construction-updates"
        / "main"
        / "checkpoints"
        / "context.json"
    )
    fake_context_file.write_text(
        json.dumps(ops.init("construction-updates/main/checkpoints").to_dict())
    )

    assert store.list_context_names() == [
        "construction-updates",
        "construction-updates/main",
    ]

    store.delete("construction-updates/main")

    assert not store.context_exists("construction-updates/main")
    assert store.context_exists("construction-updates")
