"""Help presentation copy layered over the localized operation catalog."""

from __future__ import annotations

from memcommit.adapters.console.commands.help.command import (
    CommandEntry,
    _help_command_rows,
)
from memcommit.adapters.console.commands.help.localized_copy import (
    category_description,
    validate_help_translation_coverage,
)
from memcommit.operation_catalog import (
    OPERATION_BY_NAME,
    operation_help,
)


def test_help_copy_validates_catalog_and_interface_language_coverage() -> None:
    validate_help_translation_coverage(set(OPERATION_BY_NAME))


def test_help_projects_catalog_owned_family_copy() -> None:
    assert category_description("EN", "SEMANTIC TRANSFORMATIONS").startswith(
        "Uses LLM semantic analysis"
    )
    assert category_description(
        "KO",
        "SEMANTIC TRANSFORMATIONS",
    ).startswith("LLM semantic analysis")


def test_help_row_combines_command_form_with_catalog_translation() -> None:
    operation = operation_help("atomize")
    entry = CommandEntry(
        name=operation.name,
        annotation=None,
        description=operation.summary,
        command=object(),
        forms=("mem atomize",),
        operation_help=operation,
    )

    rows = _help_command_rows(
        entry,
        command_prefixes=("mem atomize ",),
        content_width=100,
        language="KO",
    )
    rendered = "\n".join(
        prefix + connector + body for prefix, connector, body, _ in rows
    )

    assert "현재 Context를 독립적으로" in rendered
    assert "mem atomize" in rendered
