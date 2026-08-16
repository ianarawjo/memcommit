from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.store import MemoryStore


runner = CliRunner()


def test_status_sb_is_one_line_with_profile_context_lineage_and_counts(
    isolated_store,
):
    store = MemoryStore()
    context = ops.init("task-2/participant/proposal-workspace")
    ops.add(context, "Draft proposal memory.")
    store.save(context)
    store.set_current(context.name)

    result = runner.invoke(app, ["status", "-sb"])

    assert result.exit_code == 0, result.output
    assert result.output.count("\n") == 1
    assert result.output.startswith(
        "## standalone :: task-2 > participant > proposal-workspace [OWNED]"
    )
    assert "Memories 1" in result.output
    assert "Checkpoints 0" in result.output


def test_status_short_does_not_change_detailed_default(isolated_store):
    store = MemoryStore()
    context = ops.init("notes")
    store.save(context)
    store.set_current(context.name)

    short = runner.invoke(app, ["status", "-s"])
    detailed = runner.invoke(app, ["status"])

    assert short.exit_code == 0, short.output
    assert short.output.startswith("notes [OWNED] · Memories 0")
    assert detailed.exit_code == 0, detailed.output
    assert "On context: notes" in detailed.output
    assert "(no memories yet)" in detailed.output


def test_status_direct_flag_preserves_the_default_output(isolated_store):
    store = MemoryStore()
    context = ops.init("notes")
    ops.add(context, "Direct note")
    store.save(context)
    store.set_current(context.name)

    default = runner.invoke(app, ["status"])
    direct = runner.invoke(app, ["status", "-d"])

    assert default.exit_code == 0, default.output
    assert direct.exit_code == 0, direct.output
    assert direct.output == default.output


def test_status_recursive_reports_descendants_and_embeds_once(isolated_store):
    store = MemoryStore()
    root = ops.init("scope")
    child = ops.init("scope/child")
    embedded = ops.init("outside")
    ops.add(root, "Root note")
    ops.add(child, "Child note one")
    ops.add(child, "Child note two")
    ops.add(embedded, "Embedded note one")
    ops.add(embedded, "Embedded note two")
    ops.add(embedded, "Embedded note three")
    ops.embed(child, root)
    ops.embed(embedded, root)
    for context in (child, embedded, root):
        store.save(context)
    store.set_current(root.name)

    direct = runner.invoke(app, ["status"])
    recursive = runner.invoke(app, ["status", "-r"])

    assert direct.exit_code == 0, direct.output
    assert "Recursive scope:" not in direct.output
    assert recursive.exit_code == 0, recursive.output
    assert "Contexts 3  |  Memories 6" in recursive.output
    assert "scope/child [OWNED]" in recursive.output
    assert "outside [OWNED]" in recursive.output
    assert "Memories 2" in recursive.output
    assert "Memories 3" in recursive.output
    # The child is both a lexical descendant and an embed, but it has one row.
    assert recursive.output.count("scope/child [OWNED]") == 1


def test_status_short_recursive_uses_one_direct_count_row_per_context(
    isolated_store,
):
    store = MemoryStore()
    root = ops.init("scope")
    child = ops.init("scope/child")
    ops.add(child, "Nested note")
    store.save(root)
    store.save(child)
    store.set_current(root.name)

    result = runner.invoke(app, ["status", "-sr"])

    assert result.exit_code == 0, result.output
    assert result.output.count("\n") == 2
    assert result.output.startswith("scope [OWNED] · Memories 0")
    assert "scope/child [OWNED] · Memories 1" in result.output


def test_status_rejects_conflicting_scope_presets(isolated_store):
    result = runner.invoke(app, ["status", "-dr"])

    assert result.exit_code == 2
    assert "Choose either --direct/-d or --recursive/-r" in result.output
