from typer.testing import CliRunner

import memcommit.application.ops as ops
from memcommit.adapters.console.entrypoint import app
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
    assert "Checkpoints 0" not in result.output


def test_status_short_does_not_change_detailed_default(isolated_store):
    store = MemoryStore()
    context = ops.init("notes")
    store.save(context)
    store.set_current(context.name)

    short = runner.invoke(app, ["status", "-s"])
    detailed = runner.invoke(app, ["status"])

    assert short.exit_code == 0, short.output
    assert short.output == "notes [OWNED] · Direct inventory empty\n"
    assert detailed.exit_code == 0, detailed.output
    assert "On context: notes" in detailed.output
    assert "Inventory · Direct inventory empty" in detailed.output
    assert "Memory preview:" not in detailed.output
    assert "Recent changes:" not in detailed.output


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
    assert "Recursive scope" not in direct.output
    assert recursive.exit_code == 0, recursive.output
    assert "Recursive scope · Contexts 3  |  Memories 6" in recursive.output
    assert "Embedded Contexts 2" in recursive.output
    assert "scope/child [OWNED]" in recursive.output
    assert "outside [OWNED]" in recursive.output
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
    assert result.output.startswith("scope [OWNED] · Direct inventory empty")
    assert "scope/child [OWNED] · Memories 1" in result.output


def test_status_recursive_compacts_context_rows_and_omits_zero_counts(
    isolated_store,
):
    store = MemoryStore()
    root = ops.init("practice")
    description = ops.init("practice/description")
    source = ops.init("practice/source")
    ops.add(description, "Description one")
    ops.add(description, "Description two")
    for index in range(12):
        ops.add(source, f"Source {index}")
    for context in (root, description, source):
        store.save(context)
    store.set_current(root.name)

    result = runner.invoke(app, ["status", "-r"])

    assert result.exit_code == 0, result.output
    assert "Inventory" not in result.output
    assert "Recursive scope · Contexts 3  |  Memories 14" in result.output
    assert "practice [OWNED] · CURRENT · Direct inventory empty" in result.output
    assert "practice/description [OWNED] · Memories 2" in result.output
    assert "practice/source [OWNED] · Memories 12" in result.output
    assert "Memory Refs 0" not in result.output
    assert "Memory preview:" not in result.output
    assert "Recent changes:" not in result.output


def test_status_rejects_conflicting_scope_presets(isolated_store):
    result = runner.invoke(app, ["status", "-dr"])

    assert result.exit_code == 2
    assert "Choose either --direct/-d or --recursive/-r" in result.output


def test_status_previews_first_five_memories_and_latest_five_checkpoints(
    isolated_store,
):
    store = MemoryStore()
    context = ops.init("preview")
    memories = [ops.add(context, f"Memory {index}") for index in range(7)]
    store.save(context)
    store.set_current(context.name)
    for index in range(7):
        store.checkpoint(
            context,
            message=f"Change {index}",
            command="edit",
            description=f"Change {index}",
            auto=True,
        )

    result = runner.invoke(app, ["status"])
    recursive = runner.invoke(app, ["status", "-r"])

    assert result.exit_code == 0, result.output
    assert "Memory preview · first 5 of 7:" in result.output
    for memory in memories[:5]:
        assert f"[{memory.uid[:8]}]" in result.output
    for memory in memories[5:]:
        assert f"[{memory.uid[:8]}]" not in result.output
    assert "Recent changes · latest 5 of 7 checkpoints:" in result.output
    assert "Change 6" in result.output
    assert "Change 2" in result.output
    assert "Change 1" not in result.output
    assert "Change 0" not in result.output
    assert recursive.exit_code == 0, recursive.output
    assert (
        "Recursive scope · Contexts 1  |  Memories 7  |  Checkpoints 7"
        in recursive.output
    )
    assert "Memory preview" not in recursive.output
    assert "Recent changes" not in recursive.output


def test_status_lists_direct_pointer_and_embed_relationships(isolated_store):
    store = MemoryStore()
    source = ops.init("source")
    source_memory = ops.add(source, "Shared source Memory")
    child = ops.init("child")
    parent = ops.init("parent")
    reference = ops.embed_memory(source_memory, source, parent)
    ops.embed(child, parent)
    for context in (source, child, parent):
        store.save(context)
    store.set_current(parent.name)

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0, result.output
    assert "Relationships:" in result.output
    assert (
        f"MEMORY REF [{reference.uid[:8]}] source#{source_memory.uid[:8]}"
        in result.output
    )
    assert f"EMBEDDED CONTEXT [{child.uid[:8]}] child" in result.output


def test_status_help_describes_inventory_preview_relationships_and_scope():
    result = runner.invoke(app, ["status", "--help"])

    assert result.exit_code == 0, result.output
    assert "inventory, first five direct Memories" in result.output
    assert "relationships, and latest checkpoints" in result.output
    assert "Show orientation and item counts on one line" in result.output
    assert "Include readable lexical descendants and embedded" in result.output
    assert "Contexts in inventory totals" in result.output
