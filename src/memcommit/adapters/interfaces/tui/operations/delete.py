"""Shared-picker projection for the unified Delete operation."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from memcommit.core.context import Context, Memory, MemoryRef, QueryContextRef
from memcommit.core.context_targeting.tui.picker import (
    ContextMemoryRow,
    ContextMemorySelection,
    ContextPickerActionReceipt,
    choose_context,
)
from memcommit.source_projection.model import (
    SourceDisplayFacts,
    SourceForm,
    SourceReach,
    SourceState,
)
from memcommit.persistence.store import MemoryStore


DeletePickerChooser = Callable[..., object]


def delete_picker_rows(context: Context) -> tuple[ContextMemoryRow, ...]:
    """Project direct items into the shared Context/Memory navigation flow."""

    rows: list[ContextMemoryRow] = []
    for item in context.iter_items():
        style: Literal["memory-object", "report-neutral"]
        if isinstance(item, Memory):
            label = item.uid[:8]
            content = item.content
            style = "memory-object"
            source = SourceDisplayFacts(form=SourceForm.MEMORY)
        elif isinstance(item, MemoryRef):
            label = item.uid[:8]
            content = (
                item.target.content
                if item.target is not None
                else item.target_context_name
            )
            style = "memory-object"
            source = SourceDisplayFacts(
                form=SourceForm.MEMORY_REF,
                states=(
                    (SourceState.READ_ONLY,)
                    if item.is_resolved
                    else (SourceState.DANGLING,)
                ),
            )
        elif isinstance(item, QueryContextRef):
            label = item.uid[:8]
            content = item.name
            style = "report-neutral"
            source = SourceDisplayFacts(form=SourceForm.QUERY_VIEW)
        elif isinstance(item, Context):
            label = item.uid[:8]
            content = item.name
            style = "report-neutral"
            source = SourceDisplayFacts(reach=SourceReach.VIA_EMBED)
        else:  # pragma: no cover - Information is a closed union.
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
    initial_target: str | ContextMemorySelection | None = None,
    item_handler: Callable[[str, str], ContextPickerActionReceipt] | None = None,
    chooser: DeletePickerChooser = choose_context,
) -> str | ContextMemorySelection | None:
    """Run the shared picker without owning Delete mutation semantics."""

    names = tuple(store.list_context_names())
    if not names:
        raise ValueError("No Contexts or direct items are available to delete.")
    selected = chooser(
        names,
        current=current_name,
        title="Delete or Remove · SELECT A CONTEXT OR DIRECT ITEM",
        accept_label="delete",
        exit_label="close",
        memory_loader=lambda name: delete_picker_rows(store.load_direct(name)),
        initially_expand_selected=True,
        initially_show_memories=True,
        selectable_memories=True,
        initial_target=initial_target,
        nested_accept_handler=item_handler,
    )
    if selected is None or isinstance(selected, (str, ContextMemorySelection)):
        return selected
    raise TypeError("Delete picker returned an unsupported target receipt.")


__all__ = ["choose_delete_target", "delete_picker_rows"]
