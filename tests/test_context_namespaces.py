"""Tests for slash-delimited Context namespaces."""

import json

import pytest
from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.context import AutoCheckpoint, Context
from memcommit.store import MemoryStore


runner = CliRunner()


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
        "construction-updates/main",
    ):
        store.save(ops.init(name))
    store.set_current("construction-updates/main")

    assert store.list_context_names() == [
        "alpha",
        "construction-updates/main",
        "construction-updates/route-changes",
    ]

    result = runner.invoke(app, ["contexts"])
    assert result.exit_code == 0
    assert "  alpha" in result.output
    assert "* construction-updates/main" in result.output
    assert "  construction-updates/route-changes" in result.output
    assert "\n  construction-updates\n" not in result.output


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


def test_existing_context_cannot_become_a_namespace(isolated_store):
    store = MemoryStore()
    store.save(ops.init("construction-updates"))

    with pytest.raises(ValueError, match="conflicts with existing context"):
        store.save(ops.init("construction-updates/main"))

    assert not store.context_exists("construction-updates/main")


def test_existing_namespace_cannot_become_a_context(isolated_store):
    store = MemoryStore()
    store.save(ops.init("construction-updates/main"))

    with pytest.raises(ValueError, match="conflicts with existing context"):
        store.save(ops.init("construction-updates"))

    assert store.context_exists("construction-updates/main")
    assert not store.context_exists("construction-updates")


def test_cli_reports_prefix_conflict_without_changing_current(isolated_store):
    assert runner.invoke(app, ["init", "construction-updates/main"]).exit_code == 0

    result = runner.invoke(app, ["init", "construction-updates"])

    assert result.exit_code == 1
    assert "conflicts with existing context" in result.stderr
    assert MemoryStore().current_context_name() == "construction-updates/main"


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
    store.save(ops.init("construction-updates/main"))
    store.save(ops.init("construction-updates/building-access"))
    store.set_current("construction-updates/building-access")

    store.delete("construction-updates/main")

    assert not store.context_exists("construction-updates/main")
    assert store.context_exists("construction-updates/building-access")
    assert store.current_context_name() == "construction-updates/building-access"
    assert (isolated_store / "contexts" / "construction-updates").is_dir()

    store.delete("construction-updates/building-access")

    assert not (isolated_store / "contexts" / "construction-updates").exists()
    assert store.current_context_name() is None


def test_delete_refuses_corrupt_prefix_tree(isolated_store):
    store = MemoryStore()
    store.save(ops.init("parent"))

    child_dir = isolated_store / "contexts" / "parent" / "child"
    child_dir.mkdir()
    (child_dir / "context.json").write_text(
        json.dumps(ops.init("parent/child").to_dict())
    )

    with pytest.raises(ValueError, match="nested contexts exist"):
        store.delete("parent")

    assert store.context_exists("parent")
    assert store.context_exists("parent/child")


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

    assert store.list_context_names() == ["construction-updates/main"]

    store.delete("construction-updates/main")

    assert not store.context_exists("construction-updates/main")
