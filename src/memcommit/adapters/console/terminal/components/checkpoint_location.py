"""Shared Context-location stage for checkpoint-oriented terminal flows."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.adapters.console.terminal.components.context_picker import (
    ContextMemoryRow,
    ContextSubtreeSelection,
    choose_context,
)


@dataclass(frozen=True)
class CheckpointLocationSelection:
    """One exact checkpoint chosen from a Context's nested version rows."""

    context_name: str
    checkpoint_uid: str


def _checkpoint_selection(
    context_name: str,
    checkpoint_uid: str,
) -> CheckpointLocationSelection:
    return CheckpointLocationSelection(context_name, checkpoint_uid)


def choose_history_location(
    names: Sequence[str],
    *,
    current: str | None,
    annotations: Mapping[str, str],
    title: str,
    catalog_names: Sequence[str] | None = None,
    descendant_scope_names: Sequence[str] = (),
    operation_loader: Callable[[str], Sequence[ContextMemoryRow]] | None = None,
    select_nested_checkpoints: bool = False,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> str | ContextSubtreeSelection | CheckpointLocationSelection | None:
    """Select one Context before opening its checkpoint history."""
    selectable = tuple(names)
    catalog = tuple(catalog_names or selectable)
    if not set(selectable) <= set(catalog):
        raise ValueError("History locations must belong to their Context catalog.")
    selectable_set = set(selectable)
    unavailable = tuple(name for name in catalog if name not in selectable_set)
    if not set(annotations) <= set(catalog):
        raise ValueError("History annotations must belong to the catalog.")
    subtree_names = frozenset(descendant_scope_names)
    if not subtree_names <= set(catalog):
        raise ValueError("History descendant scopes must belong to the catalog.")
    local_annotations = {
        name: label for name, label in annotations.items() if name in selectable_set
    }
    virtual_annotations = {
        name: annotations.get(
            name,
            "subtree · Enter opens all changed descendant checkpoints",
        )
        for name in unavailable
        if name in subtree_names or name in annotations
    }
    return choose_context(
        selectable,
        current=current,
        local_annotations=local_annotations,
        virtual_names=unavailable,
        virtual_annotations=virtual_annotations,
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
        title=title,
        accept_label="open checkpoints",
        nested_accept_label=(
            "review exact checkpoint" if select_nested_checkpoints else None
        ),
        initially_expand_selected=True,
        descendant_scope_names=subtree_names,
        memory_loader=operation_loader,
        nested_selection_factory=(
            _checkpoint_selection
            if select_nested_checkpoints and operation_loader is not None
            else None
        ),
    )
