"""Public command route tests for deterministic Find."""

from __future__ import annotations

from typer.testing import CliRunner

import memcommit.ops as ops
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
    assert "SPANS · 0:6, 12:18" in result.output


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
