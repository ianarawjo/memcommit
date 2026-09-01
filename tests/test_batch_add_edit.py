"""Line-oriented batch Edit CLI contracts."""

from typer.testing import CliRunner

import memcommit.application.capabilities.ops as ops
from memcommit.adapters.console.entrypoint import app
from memcommit.core.context import Memory
from memcommit.persistence.store import MemoryStore


runner = CliRunner()


def invoke(*args: str, stdin: str | None = None):
    return runner.invoke(app, list(args), input=stdin)


def direct_memories(context_name: str) -> list[Memory]:
    items = list(MemoryStore().load(context_name).iter_items())
    assert all(isinstance(item, Memory) for item in items)
    return items


def test_batch_commands_require_complete_input_forms(
    isolated_store,
    tmp_path,
):
    invoke("init", "notes")
    invoke("add", "one")
    store = MemoryStore()
    memory = direct_memories("notes")[0]
    checkpoint_count = len(store.list_checkpoints("notes"))
    empty_edits = tmp_path / "empty-edits.tsv"
    empty_edits.write_text("\n \n", encoding="utf-8")

    incomplete_edit = invoke("edit", memory.uid[:8])
    no_edit_input = invoke("edit")
    empty_batch = invoke("edit", "--input", str(empty_edits))

    assert incomplete_edit.exit_code == 1
    assert "SELECTOR and CONTENT" in incomplete_edit.output
    assert no_edit_input.exit_code == 1
    assert "SELECTOR and CONTENT" in no_edit_input.output
    assert empty_batch.exit_code == 1
    assert "no edit records" in empty_batch.output
    assert direct_memories("notes")[0].content == "one"
    assert len(store.list_checkpoints("notes")) == checkpoint_count


def test_batch_edit_file_is_atomic_preserves_order_and_checkpoints_once(
    isolated_store,
    tmp_path,
):
    invoke("init", "notes")
    invoke("add", "first")
    invoke("add", "second")
    invoke("add", "third")
    store = MemoryStore()
    memories = direct_memories("notes")
    order_before = store.load("notes").ordered_uids()
    checkpoint_count = len(store.list_checkpoints("notes"))
    source = tmp_path / "edits.tsv"
    source.write_text(
        (
            f"{memories[0].uid[:8]}\tFIRST\n"
            f"{memories[1].uid}\tsecond\n"
            f"{memories[2].uid[:8]}\t  세 번째\twith tab  \n"
        ),
        encoding="utf-8",
    )

    result = invoke("edit", "--input", str(source))

    assert result.exit_code == 0
    assert "Edited 2 memories" in result.output
    assert "1 unchanged memory was skipped" in result.output
    edited_context = store.load("notes")
    assert edited_context.ordered_uids() == order_before
    assert [memory.content for memory in direct_memories("notes")] == [
        "FIRST",
        "second",
        "  세 번째\twith tab  ",
    ]
    checkpoints = store.list_checkpoints("notes")
    assert len(checkpoints) == checkpoint_count + 1
    checkpoint = checkpoints[0]
    assert checkpoint["command"] == "edit"
    assert checkpoint["args"] == {
        "input": str(source),
        "mode": "uid-tab-content",
        "count": 2,
        "uids": [memories[0].uid, memories[2].uid],
        "edits": [
            {"uid": memories[0].uid, "content": "FIRST"},
            {
                "uid": memories[2].uid,
                "content": "  세 번째\twith tab  ",
            },
        ],
    }


def test_batch_edit_context_option_accepts_context_uid(
    isolated_store,
    tmp_path,
):
    invoke("init", "notes")
    invoke("add", "before")
    store = MemoryStore()
    context = store.load_direct("notes")
    memory = direct_memories("notes")[0]
    source = tmp_path / "uid-edit.tsv"
    source.write_text(f"{memory.uid}\tafter\n", encoding="utf-8")

    result = invoke(
        "edit",
        "--input",
        str(source),
        "--context",
        context.uid[:8],
    )

    assert result.exit_code == 0, result.output
    assert direct_memories("notes")[0].content == "after"


def test_batch_edit_stdin_applies_all_changes_in_one_checkpoint(isolated_store):
    invoke("init", "notes")
    invoke("add", "one")
    invoke("add", "two")
    store = MemoryStore()
    memories = direct_memories("notes")
    checkpoint_count = len(store.list_checkpoints("notes"))

    result = invoke(
        "edit",
        "--input",
        "-",
        stdin=(f"{memories[0].uid[:8]}\tONE\n{memories[1].uid[:8]}\tTWO\n"),
    )

    assert result.exit_code == 0
    assert [memory.content for memory in direct_memories("notes")] == [
        "ONE",
        "TWO",
    ]
    assert len(store.list_checkpoints("notes")) == checkpoint_count + 1


def test_batch_edit_preserves_empty_replacement(isolated_store, tmp_path):
    invoke("init", "notes")
    invoke("add", "erase this text but keep the Memory")
    memory = direct_memories("notes")[0]
    source = tmp_path / "edits.tsv"
    source.write_text(f"{memory.uid[:8]}\t\n", encoding="utf-8")

    result = invoke("edit", "--input", str(source))

    assert result.exit_code == 0
    assert direct_memories("notes")[0].content == ""


def test_batch_edit_preflight_failure_is_all_or_nothing(
    isolated_store,
    tmp_path,
):
    invoke("init", "notes")
    invoke("add", "one")
    invoke("add", "two")
    store = MemoryStore()
    memories = direct_memories("notes")
    checkpoint_count = len(store.list_checkpoints("notes"))
    source = tmp_path / "edits.tsv"
    source.write_text(
        f"{memories[0].uid[:8]}\tONE\nmissing\tTWO\n",
        encoding="utf-8",
    )

    result = invoke("edit", "--input", str(source))

    assert result.exit_code == 1
    assert "No item with uid starting" in result.output
    assert [memory.content for memory in direct_memories("notes")] == [
        "one",
        "two",
    ]
    assert len(store.list_checkpoints("notes")) == checkpoint_count


def test_batch_edit_rejects_duplicate_canonical_uid_before_mutation(
    isolated_store,
    tmp_path,
):
    invoke("init", "notes")
    invoke("add", "one")
    store = MemoryStore()
    memory = direct_memories("notes")[0]
    checkpoint_count = len(store.list_checkpoints("notes"))
    source = tmp_path / "edits.tsv"
    source.write_text(
        f"{memory.uid[:8]}\tONE\n{memory.uid}\tONE AGAIN\n",
        encoding="utf-8",
    )

    result = invoke("edit", "--input", str(source))

    assert result.exit_code == 1
    assert "appears more than once" in result.output
    assert direct_memories("notes")[0].content == "one"
    assert len(store.list_checkpoints("notes")) == checkpoint_count


def test_batch_edit_rejects_reference_without_partial_edit(
    isolated_store,
    tmp_path,
):
    store = MemoryStore()
    source_context = ops.init("source")
    source_memory = ops.add(source_context, "source")
    parent = ops.init("parent")
    direct = ops.add(parent, "direct")
    reference = ops.embed_memory(source_memory, source_context, parent)
    store.save(source_context)
    store.save(parent)
    store.set_current("parent")
    source = tmp_path / "edits.tsv"
    source.write_text(
        f"{direct.uid[:8]}\tDIRECT\n{reference.uid[:8]}\tREFERENCE\n",
        encoding="utf-8",
    )

    result = invoke("edit", "--input", str(source))

    assert result.exit_code == 1
    assert "not a Memory directly owned" in result.output
    assert store.load("parent").memories[direct.uid].content == "direct"
    assert store.list_checkpoints("parent") == []


def test_batch_edit_all_noops_make_no_checkpoint(isolated_store, tmp_path):
    invoke("init", "notes")
    invoke("add", "one")
    invoke("add", "two")
    store = MemoryStore()
    memories = direct_memories("notes")
    checkpoint_count = len(store.list_checkpoints("notes"))
    source = tmp_path / "edits.tsv"
    source.write_text(
        (f"{memories[0].uid[:8]}\tone\n{memories[1].uid[:8]}\ttwo\n"),
        encoding="utf-8",
    )

    result = invoke("edit", "--input", str(source))

    assert result.exit_code == 0
    assert "All 2 memories are unchanged" in result.output
    assert len(store.list_checkpoints("notes")) == checkpoint_count


def test_batch_edit_malformed_or_conflicting_input_does_not_mutate(
    isolated_store,
    tmp_path,
):
    invoke("init", "notes")
    invoke("add", "one")
    store = MemoryStore()
    memory = direct_memories("notes")[0]
    checkpoint_count = len(store.list_checkpoints("notes"))
    malformed = tmp_path / "malformed.tsv"
    malformed.write_text("missing tab separator\n", encoding="utf-8")
    valid = tmp_path / "valid.tsv"
    valid.write_text(f"{memory.uid[:8]}\tONE\n", encoding="utf-8")

    bad_line = invoke("edit", "--input", str(malformed))
    conflict = invoke(
        "edit",
        memory.uid[:8],
        "ONE",
        "--input",
        str(valid),
    )

    assert bad_line.exit_code == 1
    assert "UID<TAB>replacement content" in bad_line.output
    assert conflict.exit_code == 1
    assert "cannot be combined" in conflict.output
    assert direct_memories("notes")[0].content == "one"
    assert len(store.list_checkpoints("notes")) == checkpoint_count


def test_revert_before_batch_edit_restores_every_changed_memory(
    isolated_store,
    tmp_path,
):
    invoke("init", "notes")
    invoke("add", "one")
    invoke("add", "two")
    store = MemoryStore()
    memories = direct_memories("notes")
    before_batch = store.list_checkpoints("notes")[0]
    source = tmp_path / "edits.tsv"
    source.write_text(
        (f"{memories[0].uid[:8]}\tONE\n{memories[1].uid[:8]}\tTWO\n"),
        encoding="utf-8",
    )
    invoke("edit", "--input", str(source))

    result = invoke("revert", before_batch["uid"][:8])

    assert result.exit_code == 0
    assert [memory.content for memory in direct_memories("notes")] == [
        "one",
        "two",
    ]
