"""Public command route tests for direct deterministic Replace."""

from __future__ import annotations

from typer.testing import CliRunner

import memcommit.adapters.console.commands.replace.command as replace_command
import memcommit.application.capabilities.ops as ops
from memcommit.adapters.console.entrypoint import app
from memcommit.core.context import Memory
from memcommit.persistence.store import MemoryStore


runner = CliRunner(mix_stderr=False)


def _memory_contents(store: MemoryStore, name: str) -> tuple[str, ...]:
    return tuple(
        item.content
        for item in store.load_direct(name).iter_items()
        if isinstance(item, Memory)
    )


def test_replace_executes_immediately_and_is_one_undoable_command(
    isolated_store,
) -> None:
    context = ops.init("replace/source")
    ops.add(context, "old and old")
    store = MemoryStore()
    store.save(context)
    store.set_current(context.name)

    result = runner.invoke(app, ["replace", "old", "new"])

    assert result.exit_code == 0, result.output + result.stderr
    assert result.output == (
        "Replaced 2 occurrences in 1 Memory in 'replace/source'.\n"
        "Undo can restore this command.\n"
    )
    assert _memory_contents(store, context.name) == ("new and new",)

    undone = runner.invoke(app, ["undo"])
    assert undone.exit_code == 0, undone.output + undone.stderr
    assert _memory_contents(store, context.name) == ("old and old",)


def test_replace_plain_is_execution_format_not_preview(isolated_store) -> None:
    context = ops.init("replace/source")
    ops.add(context, "Needle one; needle two.")
    store = MemoryStore()
    store.save(context)
    store.set_current(context.name)

    result = runner.invoke(
        app,
        ["replace", "--ignore-case", "needle", "pin"],
    )

    assert result.exit_code == 0, result.output + result.stderr
    assert "PLAN" not in result.output
    assert "Replaced 2 occurrences in 1 Memory" in result.output
    assert _memory_contents(store, context.name) == ("pin one; pin two.",)


def test_replace_no_match_reports_no_change_without_checkpoint(isolated_store) -> None:
    context = ops.init("replace/source")
    ops.add(context, "Nothing relevant.")
    store = MemoryStore()
    store.save(context)
    store.set_current(context.name)

    result = runner.invoke(app, ["replace", "writer", "author"])

    assert result.exit_code == 0, result.output + result.stderr
    assert result.output == "No matches. Nothing changed.\n"
    assert store.list_checkpoints(context.name) == []
    assert _memory_contents(store, context.name) == ("Nothing relevant.",)


def test_replace_delete_match_and_regex_execute_explicitly(isolated_store) -> None:
    literal_context = ops.init("replace/literal")
    ops.add(literal_context, "token-12 and token-34")
    regex_context = ops.init("replace/regex")
    ops.add(regex_context, "token-12 and token-34")
    delete_context = ops.init("replace/delete")
    ops.add(delete_context, "token-12 and token-34")
    store = MemoryStore()
    for context in (literal_context, regex_context, delete_context):
        store.save(context)
    store.set_current(literal_context.name)

    literal = runner.invoke(
        app,
        ["replace", "--context", literal_context.name, r"token-\d+", "value"],
    )
    regex = runner.invoke(
        app,
        [
            "replace",
            "--context",
            regex_context.name,
            "--regex",
            r"token-\d+",
            "value",
        ],
    )
    delete = runner.invoke(
        app,
        [
            "replace",
            "--context",
            delete_context.name,
            "token-",
            "--delete-match",
        ],
    )

    assert literal.exit_code == 0, literal.output + literal.stderr
    assert literal.output == "No matches. Nothing changed.\n"
    assert regex.exit_code == 0, regex.output + regex.stderr
    assert "Replaced 2 occurrences in 1 Memory" in regex.output
    assert delete.exit_code == 0, delete.output + delete.stderr
    assert "Replaced 2 occurrences in 1 Memory" in delete.output
    assert _memory_contents(store, literal_context.name) == ("token-12 and token-34",)
    assert _memory_contents(store, regex_context.name) == ("value and value",)
    assert _memory_contents(store, delete_context.name) == ("12 and 34",)


def test_replace_resolves_all_relative_roots_from_one_current_snapshot(
    isolated_store,
) -> None:
    parent = ops.init("replace")
    ops.add(parent, "needle parent")
    child = ops.init("replace/source")
    ops.add(child, "needle child")
    store = MemoryStore()
    store.save(parent)
    store.save(child)
    store.set_current(child.name)

    result = runner.invoke(
        app,
        [
            "replace",
            "--context",
            ".",
            "--context",
            "..",
            "needle",
            "pin",
        ],
    )

    assert result.exit_code == 0, result.output + result.stderr
    assert "Replaced 2 occurrences in 2 Memories across 2 Contexts." in result.output
    assert _memory_contents(store, child.name) == ("pin child",)
    assert _memory_contents(store, parent.name) == ("pin parent",)


def test_replace_complete_request_defaults_to_direct_execution_in_tty(
    isolated_store,
    monkeypatch,
) -> None:
    context = ops.init("replace/source")
    ops.add(context, "writer")
    store = MemoryStore()
    store.save(context)
    store.set_current(context.name)

    class InteractiveTerminal:
        def is_interactive(self) -> bool:
            return True

    monkeypatch.setattr(
        replace_command,
        "SystemTerminalCapabilities",
        InteractiveTerminal,
    )
    monkeypatch.setattr(
        replace_command,
        "run_replace_tui",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("a complete Replace request must not open the TUI")
        ),
    )

    result = runner.invoke(app, ["replace", "writer", "author"])

    assert result.exit_code == 0, result.output + result.stderr
    assert _memory_contents(store, context.name) == ("author",)


def test_complete_replace_request_never_opens_input_editor_in_tty(
    isolated_store,
    monkeypatch,
) -> None:
    context = ops.init("replace/source")
    store = MemoryStore()
    store.save(context)
    store.set_current(context.name)

    class InteractiveTerminal:
        def is_interactive(self) -> bool:
            return True

    monkeypatch.setattr(
        replace_command,
        "SystemTerminalCapabilities",
        InteractiveTerminal,
    )
    monkeypatch.setattr(
        replace_command,
        "run_replace_tui",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("a complete Replace request must not open the input editor")
        ),
    )

    result = runner.invoke(app, ["replace", "writer", "author"])

    assert result.exit_code == 0, result.output + result.stderr
    assert result.output == "No matches. Nothing changed.\n"


def test_replace_help_has_no_plan_or_apply_contract() -> None:
    result = runner.invoke(app, ["replace", "--help"])

    assert result.exit_code == 0, result.output + result.stderr
    assert "--apply" not in result.output
    assert "PLAN_DIGEST" not in result.output
    assert "Immediately" in result.output
