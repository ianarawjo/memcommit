from __future__ import annotations

from typer.testing import CliRunner

import memcommit.application.capabilities.ops as ops
from memcommit.adapters.console.entrypoint import app
from memcommit.core.context import Memory
from memcommit.persistence.store import MemoryStore


runner = CliRunner(mix_stderr=False)


def _direct_memories(store: MemoryStore, context_name: str) -> list[Memory]:
    return [
        item
        for item in store.load_direct(context_name).iter_items()
        if isinstance(item, Memory)
    ]


def test_chunk_without_selector_chunks_current_context_by_sentences(isolated_store):
    assert runner.invoke(app, ["init", "notes"]).exit_code == 0
    assert (
        runner.invoke(app, ["add", "First sentence. Second sentence."]).exit_code == 0
    )
    assert runner.invoke(app, ["add", "Already atomic."]).exit_code == 0
    assert runner.invoke(app, ["add", "Question? Answer!"]).exit_code == 0
    store = MemoryStore()
    context = store.load_current_direct()
    first, unchanged, third = _direct_memories(store, context.name)

    result = runner.invoke(app, ["chunk"])

    assert result.exit_code == 0, result.output + result.stderr
    assert "Apply?" not in result.output
    assert "2 direct Memories / 4 chunks (method=sentences)" in result.output
    after = _direct_memories(store, context.name)
    assert [memory.content for memory in after] == [
        "First sentence.",
        "Second sentence.",
        "Already atomic.",
        "Question?",
        "Answer!",
    ]
    assert first.uid not in {memory.uid for memory in after}
    assert unchanged.uid in {memory.uid for memory in after}
    assert third.uid not in {memory.uid for memory in after}

    checkpoint = store.list_checkpoints(context.name)[0]
    assert checkpoint["command"] == "chunk"
    assert checkpoint["args"]["method"] == "sentences"
    assert [record["uid"] for record in checkpoint["args"]["splits"]] == [
        first.uid,
        third.uid,
    ]

    for selector in (first.uid[:8], after[0].uid[:8]):
        trace = runner.invoke(app, ["trace", selector, "--verbose"])
        assert trace.exit_code == 0, trace.output + trace.stderr
        assert "SPLIT" in trace.output
        assert "RECORDED" in trace.output
        assert "mapping could not be reconstructed" not in trace.output


def test_chunk_context_option_does_not_change_or_mutate_current_context(
    isolated_store,
):
    store = MemoryStore()
    current = ops.init("current")
    current_memory = ops.add(current, "Leave this. Entirely alone.")
    target = ops.init("work/target")
    target_memory = ops.add(target, "Split this. Split that.")
    store.save(current)
    store.save(target)
    store.set_current(current.name)

    result = runner.invoke(
        app,
        ["chunk", "--context", target.name],
    )

    assert result.exit_code == 0, result.output + result.stderr
    assert "Context 'work/target'" in result.output
    assert store.current_context_name() == current.name
    assert [memory.uid for memory in _direct_memories(store, current.name)] == [
        current_memory.uid
    ]
    target_after = _direct_memories(store, target.name)
    assert target_memory.uid not in {memory.uid for memory in target_after}
    assert [memory.content for memory in target_after] == ["Split this.", "Split that."]


def test_chunk_auto_types_bare_context_operand(isolated_store):
    store = MemoryStore()
    current = ops.init("current")
    target = ops.init("work/target")
    original = ops.add(target, "Split this. Split that.")
    for context in (current, target):
        store.save(context)
    store.set_current(current.name)

    result = runner.invoke(app, ["chunk", target.name])

    assert result.exit_code == 0, result.output + result.stderr
    assert "Context 'work/target'" in result.output
    assert store.current_context_name() == current.name
    after = _direct_memories(store, target.name)
    assert original.uid not in {memory.uid for memory in after}
    assert [memory.content for memory in after] == ["Split this.", "Split that."]


def test_chunk_auto_types_bare_memory_and_finds_its_owner(isolated_store):
    store = MemoryStore()
    target = ops.init("work/target")
    selected = ops.add(target, "Alpha. beta continues.")
    other = ops.add(target, "Other. memory stays.")
    current = ops.init("current")
    for context in (target, current):
        store.save(context)
    store.set_current(current.name)

    result = runner.invoke(app, ["chunk", selected.uid[:7]])

    assert result.exit_code == 0, result.output + result.stderr
    assert "in Context 'work/target'" in result.output
    after = _direct_memories(store, target.name)
    assert [memory.content for memory in after] == [
        "Alpha.",
        "beta continues.",
        "Other. memory stays.",
    ]
    assert other.uid == after[-1].uid


def test_chunk_one_memory_uses_sentence_default_in_explicit_context(isolated_store):
    store = MemoryStore()
    current = ops.init("current")
    target = ops.init("target")
    selected = ops.add(target, "Alpha. beta continues.")
    other = ops.add(target, "Other. memory stays.")
    store.save(current)
    store.save(target)
    store.set_current(current.name)

    result = runner.invoke(
        app,
        ["chunk", selected.uid[:8], "--context", target.name],
    )

    assert result.exit_code == 0, result.output + result.stderr
    assert "method=sentences" in result.output
    assert "in Context 'target'" in result.output
    after = _direct_memories(store, target.name)
    assert [memory.content for memory in after] == [
        "Alpha.",
        "beta continues.",
        "Other. memory stays.",
    ]
    assert other.uid == after[-1].uid


def test_chunk_context_applies_immediately_as_one_undoable_command(isolated_store):
    store = MemoryStore()
    context = ops.init("notes")
    originals = (
        ops.add(context, "One. Two."),
        ops.add(context, "Three. Four."),
    )
    store.save(context)
    store.set_current(context.name)

    result = runner.invoke(app, ["chunk"])

    assert result.exit_code == 0, result.output + result.stderr
    assert "Apply?" not in result.output
    after = _direct_memories(store, context.name)
    assert [memory.content for memory in after] == ["One.", "Two.", "Three.", "Four."]
    assert len(store.list_checkpoints(context.name)) == 1

    undone = runner.invoke(app, ["undo"])
    assert undone.exit_code == 0, undone.output + undone.stderr
    restored = _direct_memories(store, context.name)
    assert [memory.uid for memory in restored] == [memory.uid for memory in originals]

    redone = runner.invoke(app, ["redo"])
    assert redone.exit_code == 0, redone.output + redone.stderr
    assert [memory.content for memory in _direct_memories(store, context.name)] == [
        "One.",
        "Two.",
        "Three.",
        "Four.",
    ]


def test_chunk_context_records_literal_boundary_for_trace(isolated_store):
    assert runner.invoke(app, ["init", "notes"]).exit_code == 0
    assert runner.invoke(app, ["add", "Alpha,beta,gamma."]).exit_code == 0
    store = MemoryStore()
    original = _direct_memories(store, "notes")[0]

    result = runner.invoke(
        app,
        ["chunk", "--break-on", ","],
    )

    assert result.exit_code == 0, result.output + result.stderr
    assert [memory.content for memory in _direct_memories(store, "notes")] == [
        "Alpha,",
        "beta,",
        "gamma.",
    ]
    checkpoint = store.list_checkpoints("notes")[0]
    assert checkpoint["args"]["break_on"] == ","
    trace = runner.invoke(app, ["trace", original.uid[:8], "--verbose"])
    assert trace.exit_code == 0, trace.output + trace.stderr
    assert "SPLIT" in trace.output
    assert "RECORDED" in trace.output


def test_chunk_validates_literal_boundary_in_empty_context(isolated_store):
    store = MemoryStore()
    context = ops.init("empty")
    store.save(context)
    store.set_current(context.name)

    result = runner.invoke(app, ["chunk", "--break-on", "letter"])

    assert result.exit_code == 1
    assert "break_on" in result.stderr


def test_chunk_clauses_break_on_and_character_limits_are_applied_and_recorded(
    isolated_store,
):
    assert runner.invoke(app, ["init", "notes"]).exit_code == 0
    assert (
        runner.invoke(
            app,
            ["add", "Alpha, beta; gamma: delta — epsilon. Next sentence."],
        ).exit_code
        == 0
    )
    store = MemoryStore()
    context = store.load_current_direct()
    original = _direct_memories(store, context.name)[0]

    result = runner.invoke(
        app,
        [
            "chunk",
            original.uid[:8],
            "--method",
            "clauses",
            "--break-on",
            ",",
            "--min-chars",
            "10",
            "--max-chars",
            "18",
        ],
    )

    assert result.exit_code == 0, result.output + result.stderr
    assert "method=clauses" in result.output
    assert "break_on=','" in result.output
    assert "min_chars=10" in result.output
    assert "max_chars=18" in result.output
    assert "1 chunk(s) remain below min_chars=10" in result.output
    after = _direct_memories(store, context.name)
    assert [memory.content for memory in after] == [
        "Alpha, beta;",
        "gamma: delta —",
        "epsilon.",
        "Next sentence.",
    ]

    checkpoint = store.list_checkpoints(context.name)[0]
    assert checkpoint["args"]["method"] == "clauses"
    assert checkpoint["args"]["break_on"] == ","
    assert checkpoint["args"]["min_chars"] == 10
    assert checkpoint["args"]["max_chars"] == 18

    trace = runner.invoke(app, ["trace", after[0].uid[:8], "--verbose"])
    assert trace.exit_code == 0, trace.output + trace.stderr
    assert "SPLIT" in trace.output
    assert "mapping could not be reconstructed" not in trace.output


def test_chunk_rejects_inverted_character_range_without_mutation(isolated_store):
    store = MemoryStore()
    context = ops.init("notes")
    original = ops.add(context, "One. Two.")
    store.save(context)
    store.set_current(context.name)

    result = runner.invoke(
        app,
        ["chunk", original.uid[:8], "--min-chars", "20", "--max-chars", "10"],
    )

    assert result.exit_code == 1
    assert "min_chars cannot be greater than max_chars" in result.stderr
    after = _direct_memories(store, context.name)
    assert [memory.uid for memory in after] == [original.uid]
    assert store.list_checkpoints(context.name) == []
