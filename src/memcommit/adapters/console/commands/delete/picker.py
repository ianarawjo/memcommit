"""Shared-picker projection for the unified Delete operation."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from memcommit.models.context import Context
from memcommit.models.memory import Memory
from memcommit.adapters.console.terminal.components.context_picker import (
    ContextMemoryRow,
    ContextPickerActionReceipt,
    choose_context,
)
from memcommit.persistence.store import MemoryStore
from memcommit.source_projection.model import (
    SourceDisplayFacts,
    SourceForm,
)


DeletePickerChooser = Callable[..., object]


def delete_picker_rows(context: Context) -> tuple[ContextMemoryRow, ...]:
    """Project direct items into the shared Context/Memory navigation flow."""

    rows: list[ContextMemoryRow] = []
    for item in context.iter_memories():
        style: Literal["memory-object", "report-neutral"]
        if isinstance(item, Memory):
            label = item.uid[:8]
            content = item.content
            style = "memory-object"
            source = SourceDisplayFacts(form=SourceForm.MEMORY)
        else:
            continue
        rows.append(
            ContextMemoryRow(
                label,
                content,
                style=style,
                selector=item.uid,
                source=source,
            )
        )
    return tuple(rows)


def choose_delete_target(
    store: MemoryStore,
    *,
    current_name: str | None,
    initial_target: str | tuple[str, str] | None = None,
    item_handler: Callable[[str, str], ContextPickerActionReceipt] | None = None,
    chooser: DeletePickerChooser = choose_context,
) -> str | tuple[str, str] | None:
    """Run the shared picker without owning Delete mutation semantics."""

    if current_name is None:
        raise ValueError("No current Context. Run 'mem switch' or 'mem init' first.")
    names = (current_name,)

    def reject_context(_name: str) -> ContextPickerActionReceipt:
        return ContextPickerActionReceipt(
            label="SELECT A MEMORY",
            detail="Use 'mem delete --context' to delete the current Context itself.",
        )

    selected = chooser(
        names,
        current=current_name,
        title="Delete · SELECT A MEMORY IN THE CURRENT CONTEXT",
        accept_label="delete",
        exit_label="close",
        memory_loader=lambda name: delete_picker_rows(store.load_direct(name)),
        initially_expand_selected=True,
        initially_show_memories=True,
        selectable_memories=True,
        initial_target=initial_target,
        nested_accept_handler=item_handler,
        context_accept_handler=reject_context,
    )
    if selected is None or isinstance(selected, (str, tuple)):
        return selected
    raise TypeError("Delete picker returned an unsupported target receipt.")


__all__ = ["choose_delete_target", "delete_picker_rows"]
