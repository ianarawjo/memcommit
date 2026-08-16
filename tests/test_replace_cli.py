"""Public command route tests for reviewed deterministic Replace."""

from __future__ import annotations

import re

from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.context import Memory
from memcommit.store import MemoryStore


runner = CliRunner(mix_stderr=False)


def _memory_contents(store: MemoryStore, name: str) -> tuple[str, ...]:
    return tuple(
        item.content
        for item in store.load_direct(name).iter_items()
        if isinstance(item, Memory)
    )


def _digest(output: str) -> str:
    matched = re.search(r"^PLAN DIGEST · ([0-9a-f]{64})$", output, re.MULTILINE)
    assert matched is not None, output
    return matched.group(1)


def test_replace_plain_previews_every_change_without_mutating(isolated_store) -> None:
    context = ops.init("replace/source")
    ops.add(context, "Needle one; needle two.")
    store = MemoryStore()
    store.save(context)
    store.set_current(context.name)

    result = runner.invoke(
        app,
        ["replace", "--plain", "--ignore-case", "needle", "pin"],
    )

    assert result.exit_code == 0, result.output + result.stderr
    assert "REPLACE PLAN · NOT APPLIED" in result.output
    assert "MATCHED 1 · CHANGED 1 · OCCURRENCES 2" in result.output
    assert "+ pin one; pin two." in result.output
    assert _memory_contents(store, context.name) == ("Needle one; needle two.",)


def test_replace_apply_requires_and_consumes_exact_reviewed_digest(
    isolated_store,
) -> None:
    context = ops.init("replace/source")
    ops.add(context, "old and old")
    store = MemoryStore()
    store.save(context)
    store.set_current(context.name)

    preview = runner.invoke(app, ["replace", "--plain", "old", "new"])
    assert preview.exit_code == 0, preview.output + preview.stderr

    applied = runner.invoke(
        app,
        ["replace", "old", "new", "--apply", _digest(preview.output)],
    )

    assert applied.exit_code == 0, applied.output + applied.stderr
    assert "REPLACE COMPLETE" in applied.output
    assert "STATUS · APPLIED · MATCHED 1 · CHANGED 1 · OCCURRENCES 2" in applied.output
    assert _memory_contents(store, context.name) == ("new and new",)


def test_replace_rejects_unreviewed_or_stale_digest_without_mutation(
    isolated_store,
) -> None:
    context = ops.init("replace/source")
    ops.add(context, "old")
    store = MemoryStore()
    store.save(context)
    store.set_current(context.name)

    result = runner.invoke(app, ["replace", "old", "new", "--apply", "0" * 64])

    assert result.exit_code == 1
    assert "does not match the reviewed plan" in result.stderr
    assert _memory_contents(store, context.name) == ("old",)


def test_replace_delete_match_and_regex_are_explicit(isolated_store) -> None:
    context = ops.init("replace/source")
    ops.add(context, "token-12 and token-34")
    store = MemoryStore()
    store.save(context)
    store.set_current(context.name)

    literal = runner.invoke(
        app,
        ["replace", "--plain", r"token-\d+", "value"],
    )
    regex = runner.invoke(
        app,
        ["replace", "--plain", "--regex", r"token-\d+", "value"],
    )
    delete = runner.invoke(
        app,
        ["replace", "--plain", "token-", "--delete-match"],
    )

    assert literal.exit_code == 0, literal.output + literal.stderr
    assert "MATCHED 0" in literal.output
    assert regex.exit_code == 0, regex.output + regex.stderr
    assert "MATCHED 1 · CHANGED 1 · OCCURRENCES 2" in regex.output
    assert delete.exit_code == 0, delete.output + delete.stderr
    assert "REPLACEMENT · (empty · remove matched text)" in delete.output


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
            "--plain",
            "--context",
            ".",
            "--context",
            "..",
            "needle",
            "pin",
        ],
    )

    assert result.exit_code == 0, result.output + result.stderr
    assert "CONTEXT · replace/source" in result.output
    assert "CONTEXT · replace" in result.output
