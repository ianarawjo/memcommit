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
