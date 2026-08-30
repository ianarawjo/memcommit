"""Contracts for the common framed Context selector."""

from __future__ import annotations

from memcommit.adapters.console.terminal.components.operation_context_scope_editor.existing_context_selector import (
    ContextSelectorControl,
    ContextSelectorView,
)


def test_selector_supports_single_selection_without_operation_semantics() -> None:
    control = ContextSelectorControl(
        ContextSelectorView(
            names=("alpha", "beta"),
            selected=("alpha",),
            label="FROM CONTEXT",
        )
    )

    control.move(1)
    control.choose_cursor()

    assert control.selection.selected_name == "beta"


def test_selector_supports_an_empty_multiple_selection_while_editing() -> None:
    control = ContextSelectorControl(
        ContextSelectorView(
            names=("alpha", "beta"),
            selected=(),
            mode="MULTIPLE",
        )
    )

    control.choose_cursor()
    control.move(1)
    control.choose_cursor()
    assert control.selection.selected_names == ("alpha", "beta")

    control.tree.selected_name = "alpha"
    control.choose_cursor()
    assert control.selection.selected_names == ("beta",)
