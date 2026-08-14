"""Contracts for interface-neutral operation Help and its projections."""

import click
from typer.main import get_command

from memcommit.cli import app
from memcommit.commands.help_inventory import (
    _help_group_fragments,
    command_entries,
)
from memcommit.help_catalog import (
    OPERATION_HELP_BY_NAME,
    ExecutionKind,
    compose_operation_help,
    operation_help,
)


def _root_context():
    root = get_command(app)
    return root, click.Context(root)


def test_catalog_covers_every_visible_top_level_operation_exactly():
    root, context = _root_context()
    try:
        visible = {
            name
            for name in root.list_commands(context)
            if (command := root.get_command(context, name)) is not None
            and not command.hidden
        }
    finally:
        context.close()

    assert set(OPERATION_HELP_BY_NAME) == visible


def test_registered_cli_summaries_share_the_catalog_source():
    root, context = _root_context()
    try:
        for name, expected in OPERATION_HELP_BY_NAME.items():
            command = root.get_command(context, name)
            assert command is not None
            assert command.help == expected.summary
    finally:
        context.close()


def test_composer_keeps_common_meaning_separate_from_cli_forms():
    operation = operation_help("update")
    composed = compose_operation_help(
        operation,
        cli_forms=("mem update", "mem update --from A --to B"),
    )

    assert operation.execution is ExecutionKind.SEMANTIC
    assert [(row.label, row.value) for row in composed.overview] == [
        ("FLOW", "Source Context -> Target Context"),
        ("EXECUTION", "SEMANTIC"),
        ("EFFECT", "Changes local Target only after reviewed Apply"),
        ("RANGE", "Each endpoint exact or readable descendants"),
    ]
    assert composed.cli_forms == (
        "mem update",
        "mem update --from A --to B",
    )


def test_expanded_tui_entry_projects_composed_meaning_before_cli_forms():
    root, context = _root_context()
    try:
        entry = next(
            entry for entry in command_entries(context) if entry.name == "update"
        )
    finally:
        context.close()

    rendered = "".join(
        text
        for _style, text in _help_group_fragments(
            [(0, entry)],
            title="ANALYZE & TRANSFORM",
            width=120,
            focused=True,
            selected_index=0,
            expanded_index=0,
            selected_form=0,
        )
    )

    assert rendered.index("FLOW") < rendered.index("FORM 1")
    assert "Source Context -> Target Context" in rendered
    assert "EXECUTION · SEMANTIC" in rendered
    assert "Changes local Target only after reviewed Apply" in rendered
