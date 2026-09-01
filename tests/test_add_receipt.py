"""Unified line-oriented receipt contracts for completed Add results."""

from __future__ import annotations

import click
from click.testing import CliRunner

from memcommit.adapters.console.commands.add.receipt import render_add_receipt
from memcommit.adapters.console.terminal.core.theme import (
    SemanticColorRole,
    memory_object_color_rgb,
    semantic_color_rgb,
)
from memcommit.application.operations.add.application import AddedMemory, AddResult


def _result(*contents: str) -> AddResult:
    return AddResult(
        context_name="target",
        context_uid="context-uid",
        memories=tuple(
            AddedMemory(
                uid=f"{index:08x}-0000-0000-0000-000000000000",
                content=content,
            )
            for index, content in enumerate(contents, start=1)
        ),
        checkpoint_uid="cccccccc-0000-0000-0000-000000000000",
    )


def _render(result: AddResult, *, color: bool) -> str:
    @click.command()
    def receipt() -> None:
        render_add_receipt(result)

    rendered = CliRunner().invoke(receipt, color=color)
    assert rendered.exit_code == 0, rendered.output
    return rendered.output


def test_every_add_count_uses_one_complete_receipt_shape() -> None:
    assert _render(_result("Only Memory."), color=False) == (
        "Added 1 Memory to 'target'.\n"
        "  [00000001] Only Memory.\n"
        "Operation Checkpoint [cccccccc].\n"
    )
    assert _render(_result("First\nline.", "Second Memory."), color=False) == (
        "Added 2 Memories to 'target'.\n"
        r"  [00000001] First\nline."
        "\n"
        "  [00000002] Second Memory.\n"
        "Operation Checkpoint [cccccccc].\n"
    )


def test_add_receipt_styles_only_typed_semantics_without_changing_text() -> None:
    result = _result("Added content.")
    plain = _render(result, color=False)
    colored = _render(result, color=True)

    assert click.unstyle(colored) == plain
    assert (
        click.style(
            "Added",
            fg=semantic_color_rgb(SemanticColorRole.ADD),
            bold=True,
        )
        in colored
    )
    assert (
        click.style(
            "Added content.",
            fg=memory_object_color_rgb(),
        )
        in colored
    )
    assert (
        click.style(
            "Checkpoint",
            fg=semantic_color_rgb(SemanticColorRole.HISTORY),
            bold=True,
        )
        in colored
    )
