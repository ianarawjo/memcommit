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
from memcommit.help_catalog.best_for import BEST_FOR_BY_OPERATION


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


def test_every_operation_has_one_reviewed_best_for_value():
    assert set(BEST_FOR_BY_OPERATION) == set(OPERATION_HELP_BY_NAME)
    assert all(
        operation.best_for == BEST_FOR_BY_OPERATION[name] and operation.best_for.strip()
        for name, operation in OPERATION_HELP_BY_NAME.items()
    )


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

    assert operation.summary == (
        "Update Memories in the Target Context from Memories in the Source Context, "
        "asking the user to review and choose when needed."
    )
    assert operation.execution is ExecutionKind.SEMANTIC
    assert [(row.label, row.value) for row in composed.overview] == [
        ("FLOW", "Source Context -> Target Context"),
        ("EXECUTION", "SEMANTIC"),
        ("EFFECT", "Changes only the local Target after Apply"),
        ("RANGE", "Each endpoint exact or readable descendants"),
        ("BEST FOR", "Updating an existing Context using newly verified Memories."),
    ]
    assert composed.cli_forms == (
        "mem update",
        "mem update --from A --to B",
    )


def test_compare_help_includes_the_reviewed_use_case():
    composed = compose_operation_help(operation_help("compare"))

    assert (
        "BEST FOR",
        "Comparing two Contexts as a whole to understand where they align and differ.",
    ) in [(row.label, row.value) for row in composed.overview]


def test_meld_help_distinguishes_symmetric_and_directional_modes():
    composed = compose_operation_help(operation_help("meld"))
    overview = [(row.label, row.value) for row in composed.overview]

    assert composed.operation.summary == (
        "Semantically reconcile two Contexts into either a separate Result or "
        "an authoritative Baseline."
    )
    assert ("FLOW", "PEER A + PEER B -> RESULT; INCOMING -> BASELINE") in overview
    assert (
        "EFFECT",
        "Symmetric mode requires a distinct empty Result; directional mode "
        "changes only the Baseline after reviewed Apply",
    ) in overview
    assert (
        "BEST FOR",
        "Combining separately developed Contexts into a shared Result, or "
        "incorporating proposed changes into an existing Baseline.",
    ) in overview


def test_merge_help_distinguishes_structural_selection_from_meld_synthesis():
    composed = compose_operation_help(operation_help("merge"))
    overview = [(row.label, row.value) for row in composed.overview]

    assert composed.operation.summary == (
        "Add Source-only items to the current Target, choosing Source or Target "
        "wherever stored items conflict."
    )
    assert ("EXECUTION", "DETERMINISTIC") in overview
    assert (
        "BEST FOR",
        "Bringing work from a copied or branched Context back into the current "
        "Context.",
    ) in overview


def test_distill_help_separates_case_propositions_from_goal_focus():
    assert operation_help("distill").summary == (
        "Derive reusable Rules from Case or Example propositions in a selected "
        "Context scope, using an optional Goal to focus relevance."
    )


def test_elaborate_help_separates_candidate_rules_from_concrete_cases():
    assert operation_help("elaborate").summary == (
        "Propose candidate Rules from a Goal, or concrete Case propositions from "
        "existing Rules."
    )
    assert BEST_FOR_BY_OPERATION["elaborate"] == (
        "An abstract Goal needs starter Rule candidates, or existing Rules need "
        "additional concrete Case propositions for review."
    )
    assert operation_help("elaborate").flow == (
        "Goal -> suggested Rules; Rules -> suggested Case propositions"
    )


def test_collapsed_by_kind_row_shows_summary_and_best_for_side_by_side():
    root, context = _root_context()
    try:
        entry = next(
            entry for entry in command_entries(context) if entry.name == "compare"
        )
    finally:
        context.close()

    fragments = _help_group_fragments(
        [(0, entry)],
        title="ANALYZE & TRANSFORM",
        width=180,
        focused=True,
        selected_index=0,
        expanded_index=None,
        selected_form=None,
    )
    rendered = "".join(text for _style, text in fragments)
    lines = rendered.splitlines()
    command_line = next(line for line in lines if "▸ mem compare" in line)

    assert all(len(line) == 180 for line in lines)
    assert "Compare Memories in two Contexts" in command_line
    assert "│ USE WHEN: Comparing two Contexts" in command_line
    row_content = command_line[2:-2]
    summary_column, use_case_column = row_content.split(" │ ", 1)
    assert abs(len(summary_column) - len(use_case_column)) <= 1
    assert use_case_column.startswith("USE WHEN: Comparing two Contexts")
    assert any(
        style == "class:help-command.selected bold" and text == "USE WHEN:"
        for style, text in fragments
    )
    assert "BEST FOR" not in rendered
    assert "FORM 1" not in rendered


def test_collapsed_a_z_rows_use_the_same_best_for_column():
    root, context = _root_context()
    try:
        entries = command_entries(context)
    finally:
        context.close()
    indexed = list(enumerate(entries))
    compare_index = next(index for index, entry in indexed if entry.name == "compare")

    rendered = "".join(
        text
        for _style, text in _help_group_fragments(
            indexed,
            title="A–Z",
            width=180,
            focused=True,
            selected_index=compare_index,
            expanded_index=None,
            selected_form=None,
        )
    )
    command_line = next(
        line for line in rendered.splitlines() if "▸ mem compare" in line
    )

    assert "│ USE WHEN: Comparing two Contexts" in command_line
    assert "BEST FOR" not in rendered


def test_collapsed_narrow_row_stacks_best_for_below_the_summary():
    root, context = _root_context()
    try:
        entry = next(
            entry for entry in command_entries(context) if entry.name == "compare"
        )
    finally:
        context.close()

    rendered = "".join(
        text
        for _style, text in _help_group_fragments(
            [(0, entry)],
            title="ANALYZE & TRANSFORM",
            width=90,
            focused=False,
            selected_index=0,
            expanded_index=None,
            selected_form=None,
        )
    )
    lines = rendered.splitlines()
    command_index = next(
        index for index, line in enumerate(lines) if "▸ mem compare" in line
    )
    best_for_index = next(
        index
        for index, line in enumerate(lines)
        if "Comparing two Contexts as a whole" in line
    )

    assert all(len(line) == 90 for line in lines)
    assert best_for_index > command_index
    summary_start = lines[command_index].index("Compare Memories")
    label_start = lines[best_for_index].index("USE WHEN:")
    use_case_start = lines[best_for_index].index("Comparing two Contexts")
    continuation = next(line for line in lines if "align and differ." in line)
    assert label_start == summary_start
    assert use_case_start == label_start + len("USE WHEN: ")
    assert continuation.index("align and differ.") == use_case_start
    assert "BEST FOR" not in rendered


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
    assert "Changes only the local Target after Apply" in rendered
    assert "Updating an existing Context using newly verified Memories." in rendered
    assert "BEST FOR" not in rendered
    assert (
        rendered.count("Updating an existing Context using newly verified Memories.")
        == 1
    )
