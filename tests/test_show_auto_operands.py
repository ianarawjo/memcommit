"""Auto-typed Context/direct-item CLI operands for Show."""

from typer.testing import CliRunner

import memcommit.application.ops as ops
from memcommit.adapters.console.entrypoint import app
from memcommit.context import Memory
from memcommit.store import MemoryStore


runner = CliRunner(mix_stderr=False)


def test_bare_context_operand_is_not_reinterpreted_inside_current(isolated_store):
    store = MemoryStore()
    target = ops.init("task-1")
    ops.add(target, "target content")
    current = ops.init("practice/greetings")
    ops.add(current, "current content")
    for context in (target, current):
        store.save(context)
    store.set_current(current.name)

    result = runner.invoke(app, ["show", "task-1"])

    assert result.exit_code == 0, result.output
    assert "Context: task-1" in result.output
    assert "target content" in result.output
    assert "current content" not in result.output


def test_positional_context_accepts_recursive_scope(isolated_store):
    store = MemoryStore()
    root = ops.init("task-1")
    child = ops.init("task-1/child")
    current = ops.init("other")
    ops.add(root, "root content")
    ops.add(child, "child content")
    for context in (root, child, current):
        store.save(context)
    store.set_current(current.name)

    result = runner.invoke(app, ["show", "task-1", "-r"])

    assert result.exit_code == 0, result.output
    assert "Recursive scope: task-1" in result.output
    assert "root content" in result.output
    assert "child content" in result.output


def test_bare_uid_finds_one_direct_item_outside_current(isolated_store):
    store = MemoryStore()
    owner = ops.init("owner")
    memory = ops.add(owner, "remote direct item")
    current = ops.init("current")
    for context in (owner, current):
        store.save(context)
    store.set_current(current.name)

    result = runner.invoke(app, ["show", memory.uid[:8]])

    assert result.exit_code == 0, result.output
    assert result.output == f"[Memory owner:{memory.uid}] remote direct item\n"


def test_qualified_item_operand_selects_its_exact_owner(isolated_store):
    store = MemoryStore()
    owner = ops.init("branch/owner")
    memory = ops.add(owner, "qualified direct item")
    current = ops.init("branch/current")
    for context in (owner, current):
        store.save(context)
    store.set_current(current.name)

    result = runner.invoke(app, ["show", f"../owner:{memory.uid[:4]}"])

    assert result.exit_code == 0, result.output
    assert result.output == (
        f"[Memory branch/owner:{memory.uid}] qualified direct item\n"
    )


def test_bare_uid_fails_closed_when_multiple_local_owners_match(isolated_store):
    store = MemoryStore()
    uid = "aaaaaaaa-0000-0000-0000-000000000000"
    for name in ("branch/a", "branch/b"):
        context = ops.init(name)
        context.add(Memory(uid=uid, content=name))
        store.save(context)
    store.set_current("branch/a")

    result = runner.invoke(app, ["show", uid[:8]])

    assert result.exit_code == 1
    assert "multiple local matches" in result.stderr
    assert f"branch/a:{uid}" in result.stderr
    assert f"branch/b:{uid}" in result.stderr


def test_current_embedded_name_preserves_direct_item_compatibility(isolated_store):
    store = MemoryStore()
    child = ops.init("child")
    ops.add(child, "embedded child content")
    parent = ops.init("parent")
    ops.embed(child, parent)
    for context in (child, parent):
        store.save(context)
    store.set_current(parent.name)

    result = runner.invoke(app, ["show", "child"])

    assert result.exit_code == 0, result.output
    assert "Context: child" in result.output
    assert "embedded child content" in result.output
