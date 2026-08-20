"""Public command route tests for deterministic Find."""

from __future__ import annotations

import memcommit.commands.literal_find as literal_find_command
import memcommit.ops as ops
from typer.testing import CliRunner

from memcommit.cli import app
from memcommit.store import MemoryStore


runner = CliRunner(mix_stderr=False)


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
    assert "READ-ONLY · PROVIDER-FREE" in result.output
    assert "MATCHED 1 · OCCURRENCES 2" in result.output
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
        f"1 [{matched.uid[:8]}] needle appears here, [find/source m2]"
        in result.output
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
        literal_find_command,
        "SystemTerminalCapabilities",
        InteractiveTerminal,
    )
    monkeypatch.setattr(
        literal_find_command,
        "run_literal_find_tui",
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
        literal_find_command,
        "SystemTerminalCapabilities",
        InteractiveTerminal,
    )
    monkeypatch.setattr(literal_find_command, "run_literal_find_tui", run_tui)

    result = runner.invoke(app, ["find", "Needle", "--tui"])

    assert result.exit_code == 0, result.output + result.stderr
    assert captured["request"].pattern == "Needle"
    assert result.output == "Find closed.\n"


def test_find_inline_preview_and_all_keep_complete_match_count(isolated_store) -> None:
    context = ops.init("find/source")
    for index in range(12):
        ops.add(context, f"needle row {index}")
    store = MemoryStore()
    store.save(context)
    store.set_current("find/source")

    preview = runner.invoke(app, ["find", "--plain", "needle"])
    complete = runner.invoke(app, ["find", "--plain", "--all", "needle"])

    assert preview.exit_code == 0, preview.output + preview.stderr
    assert complete.exit_code == 0, complete.output + complete.stderr
    assert "MATCHED 12 · OCCURRENCES 12 · SHOWING 1–10 OF 12" in preview.output
    assert "11 [" not in preview.output
    assert "needle row 10, [find/source m11]" not in preview.output
    assert "2 more matches not shown; rerun with --all to show every result." in preview.output
    assert "SHOWING" not in complete.output
    assert "12 [" in complete.output
    assert "needle row 11, [find/source m12]" in complete.output


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
    monkeypatch.setattr(literal_find_command, "write_system_clipboard", copied.append)

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

    def run_compact(result):
        captured["result"] = result
        return 0

    monkeypatch.setattr(
        literal_find_command,
        "SystemTerminalCapabilities",
        InteractiveTerminal,
    )
    monkeypatch.setattr(
        literal_find_command,
        "run_compact_literal_find_result",
        run_compact,
    )

    result = runner.invoke(app, ["find", "needle"])

    assert result.exit_code == 0, result.output + result.stderr
    assert len(captured["result"].matches) == 12
    assert result.output == ""
