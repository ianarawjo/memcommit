"""Shared Context-location stage for checkpoint-oriented terminal flows."""
from __future__ import annotations

from collections.abc import Mapping, Sequence

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.commands.context_picker import choose_context


def choose_history_location(
    names: Sequence[str],
    *,
    current: str | None,
    annotations: Mapping[str, str],
    title: str,
    catalog_names: Sequence[str] | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> str | None:
    """Select one Context before opening its checkpoint history."""
    selectable = tuple(names)
    catalog = tuple(catalog_names or selectable)
    if not set(selectable) <= set(catalog):
        raise ValueError("History locations must belong to their Context catalog.")
    unavailable = tuple(name for name in catalog if name not in set(selectable))
    return choose_context(
        selectable,
        current=current,
        local_annotations=annotations,
        virtual_names=unavailable,
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
        title=title,
        accept_label="open checkpoints",
        initially_expand_selected=True,
    )
