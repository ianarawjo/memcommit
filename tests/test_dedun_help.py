"""Public Help contracts for semantic Dedun's whole-Memory boundary."""

import click
from typer.main import get_command

from memcommit.adapters.console.entrypoint import app
from memcommit.adapters.console.commands.help_inventory.command import _help_group_fragments, command_entries
from memcommit.application.operations.operation_catalog import operation_help


def _dedun_entry():
    root = get_command(app)
    context = click.Context(root)
    try:
        return next(
            entry for entry in command_entries(context) if entry.name == "dedun"
        )
    finally:
        context.close()


def test_dedun_exposes_partial_overlap_as_a_tool_selection_boundary():
    [detail] = operation_help("dedun").details

    assert detail.id == "partial-overlap"
    assert detail.kind.value == "SEMANTIC_BOUNDARY"
    assert detail.discovery.value == "TOOL_SELECTION"
    assert detail.discovery_summary == (
        "Dedun judges complete stored Memories; partial-claim overlap requires "
        "Atomize first."
    )
    assert "abc and bcd sharing bc" in detail.body
    assert "OVERLAP, not semantic redundancy" in detail.body
    assert "run Atomize first" in detail.body


def test_partial_overlap_note_appears_only_in_expanded_dedun_help():
    entry = _dedun_entry()
    collapsed = "".join(
        text
        for _style, text in _help_group_fragments(
            [(0, entry)],
            title="A–Z",
            width=180,
            focused=True,
            selected_index=0,
            expanded_index=None,
            selected_form=None,
        )
    )
    expanded = "".join(
        text
        for _style, text in _help_group_fragments(
            [(0, entry)],
            title="A–Z",
            width=180,
            focused=True,
            selected_index=0,
            expanded_index=0,
            selected_form=None,
        )
    )

    assert "PARTIAL OVERLAP" not in collapsed
    assert "PARTIAL OVERLAP" in expanded
    assert "abc and bcd sharing bc" in expanded
    assert "run Atomize first" in expanded
