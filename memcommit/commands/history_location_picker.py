"""Shared Context-location stage for checkpoint-oriented terminal flows."""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.commands.context_picker import (
    ContextMemoryRow,
    ContextSubtreeSelection,
    choose_context,
)


def choose_history_location(
    names: Sequence[str],
    *,
    current: str | None,
    annotations: Mapping[str, str],
    title: str,
    catalog_names: Sequence[str] | None = None,
    descendant_scope_names: Sequence[str] = (),
    operation_loader: Callable[[str], Sequence[ContextMemoryRow]] | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> str | ContextSubtreeSelection | None:
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
        name: label
        for name, label in annotations.items()
        if name in selectable_set
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
        initially_expand_selected=True,
        descendant_scope_names=subtree_names,
        memory_loader=operation_loader,
    )
