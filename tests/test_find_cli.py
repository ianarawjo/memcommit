"""Public command route tests for deterministic Find."""

from __future__ import annotations

import memcommit.adapters.console.commands.find.command as find_command
import memcommit.application.capabilities.ops as ops
from typer.testing import CliRunner

from memcommit.adapters.console.entrypoint import app
from memcommit.persistence.store import MemoryStore


runner = CliRunner(mix_stderr=False)


def test_find_help_distinguishes_target_and_result_breadth() -> None:
    result = runner.invoke(app, ["find", "--help"])

    assert result.exit_code == 0, result.output + result.stderr
    assert "--all" in result.output
    assert "all readable" in result.output
    assert "active" in result.output
    assert "Profile" in result.output
    assert "--all-results" in result.output
    assert "every matching row" in result.output


def test_find_plain_matches_every_literal_occurrence(isolated_store) -> None:
    context = ops.init("find/source")
    ops.add(context, "Needle one; needle two.")
    store = MemoryStore()
    store.save(context)
    store.set_current("find/source")

    result = runner.invoke(
        app,
        ["find", "--plain", "--ignore-case", "needle"],
    )

    assert result.exit_code == 0, result.output + result.stderr
    assert "SCANNED 1 · MATCHED 1 · OCCURRENCES 2" in result.output
    assert "1 [" in result.output
    assert "] Needle one; needle two. [find/source m1]" in result.output
    assert "SPANS" not in result.output


def test_find_row_distinguishes_match_order_from_frozen_source_position(
    isolated_store,
) -> None:
    context = ops.init("find/source")
    ops.add(context, "This earlier Memory does not match.")
    matched = ops.add(context, "needle appears here")
    store = MemoryStore()
    store.save(context)
    store.set_current("find/source")

    result = runner.invoke(app, ["find", "--plain", "needle"])

    assert result.exit_code == 0, result.output + result.stderr
    assert (
        f"1 [{matched.uid[:8]}] needle appears here, [find/source m2]" in result.output
    )


def test_find_regex_is_explicit_and_rejects_zero_width(isolated_store) -> None:
    context = ops.init("find/source")
    ops.add(context, "alpha beta")
    store = MemoryStore()
    store.save(context)
    store.set_current("find/source")

    literal = runner.invoke(app, ["find", "--plain", "a.*a"])
    invalid = runner.invoke(app, ["find", "--plain", "--regex", "^|"])

    assert literal.exit_code == 0, literal.output + literal.stderr
    assert "MATCHED 0" in literal.output
    assert invalid.exit_code == 1
    assert "must consume at least one character" in invalid.stderr


def test_find_repeated_context_roots_and_descendants_are_complete(
    isolated_store,
) -> None:
    root = ops.init("find/root")
    ops.add(root, "needle root")
    child = ops.init("find/root/child")
    ops.add(child, "needle child")
    peer = ops.init("find/peer")
    ops.add(peer, "needle peer")
    store = MemoryStore()
    for context in (root, child, peer):
        store.save(context)
    store.set_current("find/root")

    result = runner.invoke(
        app,
        [
            "find",
            "--plain",
            "--context",
            "find/root",
            "--context",
            "find/peer",
            "--descendants",
            "needle",
        ],
    )

    assert result.exit_code == 0, result.output + result.stderr
    assert "SCANNED 3 · MATCHED 3 · OCCURRENCES 3" in result.output


def test_find_requires_pattern_outside_tty(isolated_store) -> None:
    context = ops.init("find/source")
    store = MemoryStore()
    store.save(context)
    store.set_current("find/source")

    result = runner.invoke(app, ["find"])

    assert result.exit_code == 1
    assert "PATTERN is required outside a terminal" in result.stderr


def test_find_pattern_defaults_to_inline_result_in_tty(
    isolated_store,
    monkeypatch,
) -> None:
    context = ops.init("find/source")
    ops.add(context, "Needle in an inline result.")
    store = MemoryStore()
    store.save(context)
    store.set_current("find/source")

    class InteractiveTerminal:
        def is_interactive(self) -> bool:
            return True

    monkeypatch.setattr(
        find_command,
        "SystemTerminalCapabilities",
        InteractiveTerminal,
    )
    monkeypatch.setattr(
        find_command,
        "run_find_workbench",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("a supplied pattern must not open the Find TUI")
        ),
    )

    result = runner.invoke(app, ["find", "Needle"])

    assert result.exit_code == 0, result.output + result.stderr
    assert "FIND RESULTS" in result.output
    assert "MATCHED 1 · OCCURRENCES 1" in result.output
    assert "Needle in an inline result." in result.output


def test_find_tui_flag_still_opens_supplied_pattern_in_tty(
    isolated_store,
    monkeypatch,
) -> None:
    context = ops.init("find/source")
    store = MemoryStore()
    store.save(context)
    store.set_current("find/source")
    captured = {}

    class InteractiveTerminal:
        def is_interactive(self) -> bool:
            return True

    def run_tui(request, **_kwargs):
        captured["request"] = request
        return None

    monkeypatch.setattr(
        find_command,
        "SystemTerminalCapabilities",
        InteractiveTerminal,
    )
    monkeypatch.setattr(find_command, "run_find_workbench", run_tui)

    result = runner.invoke(app, ["find", "Needle", "--tui"])

    assert result.exit_code == 0, result.output + result.stderr
    assert captured["request"].pattern == "Needle"
    assert result.output == "Find closed.\n"


def test_find_inline_preview_and_all_results_keep_complete_match_count(
    isolated_store,
) -> None:
    context = ops.init("find/source")
    for index in range(12):
        ops.add(context, f"needle row {index}")
    store = MemoryStore()
    store.save(context)
    store.set_current("find/source")

    preview = runner.invoke(app, ["find", "--plain", "needle"])
    complete = runner.invoke(
        app,
        ["find", "--plain", "--all-results", "needle"],
    )

    assert preview.exit_code == 0, preview.output + preview.stderr
    assert complete.exit_code == 0, complete.output + complete.stderr
    assert "MATCHED 12 · OCCURRENCES 12 · SHOWING 1–10 OF 12" in preview.output
    assert "11 [" not in preview.output
    assert "needle row 10, [find/source m11]" not in preview.output
    assert (
        "2 more matches not shown; rerun with --all-results to show every result."
        in preview.output
    )
    assert "SHOWING" not in complete.output
    assert "12 [" in complete.output
    assert "needle row 11, [find/source m12]" in complete.output


def test_find_all_and_short_alias_search_every_readable_context(
    isolated_store,
) -> None:
    first = ops.init("find/first")
    second = ops.init("find/second")
    ops.add(first, "needle from first")
    ops.add(second, "needle from second")
    store = MemoryStore()
    store.save(first)
    store.save(second)
    store.set_current(first.name)

    long_option = runner.invoke(app, ["find", "--plain", "--all", "needle"])
    short_option = runner.invoke(app, ["find", "--plain", "-a", "needle"])

    assert long_option.exit_code == 0, long_option.output + long_option.stderr
    assert short_option.exit_code == 0, short_option.output + short_option.stderr
    assert short_option.output == long_option.output
    assert (
        "SCOPE · ALL READABLE CONTEXTS · EXACT · EXCLUDE EMBEDS" in long_option.output
    )
    assert "SCOPE · find/first + find/second" not in long_option.output
    assert "SCANNED 2 · MATCHED 2 · OCCURRENCES 2" in long_option.output
    assert "needle from first" in long_option.output
    assert "needle from second" in long_option.output


def test_find_all_rejects_explicit_context(isolated_store) -> None:
    context = ops.init("find/source")
    store = MemoryStore()
    store.save(context)
    store.set_current(context.name)

    result = runner.invoke(
        app,
        ["find", "--all", "--context", context.name, "needle"],
    )

    assert result.exit_code == 1
    assert "--all/-a cannot be combined with --context/-c" in result.stderr


def test_find_copy_remains_complete_when_terminal_output_is_previewed(
    isolated_store,
    monkeypatch,
) -> None:
    context = ops.init("find/source")
    for index in range(11):
        ops.add(context, f"needle row {index}")
    store = MemoryStore()
    store.save(context)
    store.set_current("find/source")
    copied: list[str] = []
    monkeypatch.setattr(find_command, "write_system_clipboard", copied.append)

    result = runner.invoke(app, ["find", "--plain", "--copy", "needle"])

    assert result.exit_code == 0, result.output + result.stderr
    assert "11 [" not in result.output
    assert "needle row 10, [find/source m11]" not in result.output
    assert len(copied) == 1
    assert "11 [" in copied[0]
    assert "needle row 10, [find/source m11]" in copied[0]


def test_find_long_tty_result_uses_compact_pager(isolated_store, monkeypatch) -> None:
    context = ops.init("find/source")
    for index in range(12):
        ops.add(context, f"needle row {index}")
    store = MemoryStore()
    store.save(context)
    store.set_current("find/source")
    captured = {}

    class InteractiveTerminal:
        def is_interactive(self) -> bool:
            return True

    def run_compact(result, *, all_readable_contexts=False):
        captured["result"] = result
        captured["all_readable_contexts"] = all_readable_contexts
        return 0

    monkeypatch.setattr(
        find_command,
        "SystemTerminalCapabilities",
        InteractiveTerminal,
    )
    monkeypatch.setattr(
        find_command,
        "run_compact_find_result",
        run_compact,
    )

    result = runner.invoke(app, ["find", "-a", "needle"])

    assert result.exit_code == 0, result.output + result.stderr
    assert len(captured["result"].matches) == 12
    assert captured["all_readable_contexts"] is True
    assert result.output == ""
