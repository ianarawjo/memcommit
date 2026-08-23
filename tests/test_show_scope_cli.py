"""CLI coverage for direct and recursive Show scope presets."""

from __future__ import annotations

from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.store import MemoryStore


runner = CliRunner(mix_stderr=False)


def _recursive_fixture() -> MemoryStore:
    store = MemoryStore()
    root = ops.init("scope")
    child = ops.init("scope/child")
    other = ops.init("scope/other")
    embedded = ops.init("outside")
    ops.add(root, "Root note")
    ops.add(child, "Child note one")
    ops.add(child, "Child note two")
    ops.add(other, "Other descendant note")
    ops.add(embedded, "Embedded note one")
    ops.add(embedded, "Embedded note two")
    ops.add(embedded, "Embedded note three")
    ops.reference_query_context(
        "scope/concealed",
        "query-source-identity-must-remain-hidden",
        root,
    )
    # The child is reachable both lexically and by Embed. Recursive Show must
    # preserve one Context block rather than duplicating its complete body.
    ops.embed(child, root)
    ops.embed(embedded, root)
    for context in (child, other, embedded, root):
        store.save(context)
    store.set_current(root.name)
    return store


def test_direct_flag_preserves_default_show_output(isolated_store):
    store = MemoryStore()
    context = ops.init("notes")
    ops.add(context, "Direct note")
    store.save(context)
    store.set_current(context.name)

    default = runner.invoke(app, ["show"])
    direct = runner.invoke(app, ["show", "-d"])

    assert default.exit_code == 0, default.output
    assert direct.exit_code == 0, direct.output
    assert direct.output == default.output


def test_recursive_show_groups_complete_direct_contents_once_per_context(
    isolated_store,
):
    _recursive_fixture()

    result = runner.invoke(app, ["show", "-r", "--context", "scope"])

    assert result.exit_code == 0, result.output
    assert (
        "Recursive scope: scope\n"
        "  Contexts 4  |  Memories 7  |  Memory Refs 0  |  Query Views 1"
        "  |  Embedded Contexts 2"
    ) in result.output
    for name in ("scope", "scope/child", "scope/other", "outside"):
        assert result.output.count(f"Context: {name}\n") == 1
    for content in (
        "Root note",
        "Child note one",
        "Child note two",
        "Other descendant note",
        "Embedded note one",
        "Embedded note two",
        "Embedded note three",
    ):
        assert content in result.output
    assert "Reach: VIA EMBED" in result.output
    assert "Reach: DESCENDANT" in result.output
    assert "scope/concealed" in result.output
    assert "query-source-identity-must-remain-hidden" not in result.output


def test_show_rejects_conflicting_scope_presets(isolated_store):
    result = runner.invoke(app, ["show", "-dr"])

    assert result.exit_code == 2
    assert "Choose either --direct/-d or --recursive/-r" in result.stderr


def test_recursive_show_rejects_direct_item_selector(isolated_store):
    store = MemoryStore()
    context = ops.init("notes")
    memory = ops.add(context, "Direct note")
    store.save(context)
    store.set_current(context.name)

    result = runner.invoke(app, ["show", memory.uid[:8], "-r"])

    assert result.exit_code == 2
    assert "cannot be combined with a direct-item selector" in result.stderr
