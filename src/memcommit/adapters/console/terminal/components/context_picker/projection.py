"""Domain-to-row and clipboard projections for the terminal Context picker."""

from __future__ import annotations

from collections.abc import Sequence
from typing import AbstractSet, Mapping

from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.core.context import Context, Memory, MemoryRef, QueryContextRef
from memcommit.core.context_targeting.tui.tree import ContextTreeRow
from memcommit.source_projection.model import (
    SourceDisplayFacts,
    SourceForm,
    SourceReach,
    SourceState,
)
from memcommit.source_projection.presentation import (
    SourceDisplayToken,
    SourceDisplayValue,
    SourceTokenRole,
    source_object_label,
)
from memcommit.adapters.console.terminal.components.context_picker.model import (
    ContextMemoryRow,
    ContextPickerClipboardProjection,
)
from memcommit.adapters.console.terminal.components.context_picker.rendering import (
    render_context_memory_previews,
    render_context_options,
)


def context_memory_rows(context: Context) -> tuple[ContextMemoryRow, ...]:
    """Project every direct Context item as one picker row.

    Keeping this projection beside the common renderer gives ``mem switch``
    and embedded browse-only trees the same Memory, pointer, and embedded-
    Context presentation. It deliberately returns no Context-selection receipt
    or persistence hook.
    """

    rows: list[ContextMemoryRow] = []
    for item in context.iter_items():
        if isinstance(item, Memory):
            rows.append(
                ContextMemoryRow(
                    item.uid[:8],
                    item.content,
                    selector=item.uid,
                    source=SourceDisplayFacts(form=SourceForm.MEMORY),
                )
            )
        elif isinstance(item, MemoryRef):
            form = (
                SourceForm.MEMORY_REFERENCE
                if item.is_snapshot
                else SourceForm.MEMORY_EMBED
            )
            content = (
                item.target.content
                if item.target is not None
                else f"(dangling reference) {item.target_context_name}"
            )
            rows.append(
                ContextMemoryRow(
                    item.uid[:8],
                    content,
                    source=SourceDisplayFacts(
                        form=form,
                        states=(
                            (SourceState.READ_ONLY,)
                            if item.target is not None
                            else (SourceState.DANGLING,)
                        ),
                    ),
                )
            )
        elif isinstance(item, QueryContextRef):
            rows.append(
                ContextMemoryRow(
                    item.uid[:8],
                    item.name,
                    style="report-neutral",
                    source=SourceDisplayFacts(form=SourceForm.QUERY_VIEW),
                    object_label_override="context",
                    supplemental_annotations=(
                        SourceDisplayToken("QUERY ONLY", SourceTokenRole.FORM),
                    ),
                    annotation_style="context-query-only",
                )
            )
        elif isinstance(item, Context):
            rows.append(
                ContextMemoryRow(
                    item.uid[:8],
                    item.name,
                    style="report-neutral",
                    source=SourceDisplayFacts(
                        form=SourceForm.CONTEXT,
                        reach=SourceReach.VIA_EMBED,
                    ),
                    annotation_style="context-embedded",
                )
            )
    return tuple(rows)


def _clipboard_memory_row(memory: ContextMemoryRow) -> ContextMemoryRow:
    """Return the compact one-line form shared by human clipboard output."""

    return ContextMemoryRow(
        label=memory.label,
        content=" ".join(memory.content.split()) or "(empty)",
        style=memory.style,
        object_label_override=memory.object_label_override,
        supplemental_annotations=memory.supplemental_annotations,
        annotation_style=memory.annotation_style,
        label_style=memory.label_style,
        selector=memory.selector,
        source=memory.source,
        badges=memory.badges,
    )


def _clipboard_fragment_text(fragments: Sequence[tuple[str, str]]) -> str:
    return "".join(
        text for style, text in fragments if style != "[SetCursorPosition]"
    ).rstrip("\n")


def _visible_branch_rows(
    rows: Sequence[ContextTreeRow],
    selected: str,
) -> tuple[ContextTreeRow, ...]:
    """Return one selected row and only its already visible descendants."""

    visible = tuple(rows)
    try:
        start = next(index for index, row in enumerate(visible) if row.name == selected)
    except StopIteration as error:
        raise ValueError("Clipboard Context is not visible in the picker.") from error
    root = visible[start]
    end = start + 1
    while end < len(visible) and visible[end].depth > root.depth:
        end += 1
    return visible[start:end]


def project_context_picker_clipboard(
    rows: Sequence[ContextTreeRow],
    *,
    selected: str,
    current: str | None,
    annotations: Mapping[str, SourceDisplayValue] | None = None,
    memories_by_context: Mapping[str, Sequence[ContextMemoryRow]] | None = None,
    visible_memory_contexts: AbstractSet[str] = frozenset(),
    display_names: Mapping[str, str] | None = None,
    memory_anchor: tuple[str, int] | None = None,
    visible_branch: bool = False,
) -> ContextPickerClipboardProjection:
    """Project semantic focus without terminal wrapping, styles, or hidden rows.

    Lowercase ``y`` uses the focused item path. Uppercase ``Y`` opts a focused
    Context into the second path, which includes only rows and Memory previews
    already visible in the frozen picker. A focused Memory is already an atomic
    scope, so both keys produce the same one-line Memory projection.
    """

    visible = tuple(rows)
    memory_map = memories_by_context or {}
    if memory_anchor is not None:
        context_name, memory_index = memory_anchor
        owner = next((row for row in visible if row.name == context_name), None)
        memories = memory_map.get(context_name, ())
        if owner is None or not 0 <= memory_index < len(memories):
            raise ValueError("Clipboard Memory is not visible in the picker.")
        memory = _clipboard_memory_row(memories[memory_index])
        fragments = render_context_memory_previews(
            owner,
            (memory,),
            wrap_width=None,
            memory_anchor=None,
        )
        text = _clipboard_fragment_text(fragments)
        if text.startswith("\n"):
            text = text[1:]
        object_label = (
            source_object_label(memory.source) if memory.source is not None else ""
        )
        display_label = (f"{object_label} " if object_label else "") + memory.label
        return ContextPickerClipboardProjection(
            text=text,
            scope="ITEM",
            label=f"[{display_label}]",
            context_count=0,
            memory_count=1,
        )

    selected_rows = (
        _visible_branch_rows(visible, selected)
        if visible_branch
        else _visible_branch_rows(visible, selected)[:1]
    )
    included_names = frozenset(row.name for row in selected_rows)
    included_memory_contexts = (
        frozenset(visible_memory_contexts).intersection(included_names)
        if visible_branch
        else frozenset()
    )
    normalized_memories = {
        name: tuple(
            _clipboard_memory_row(memory) for memory in memory_map.get(name, ())
        )
        for name in included_names
    }
    fragments = render_context_options(
        selected_rows,
        selected=selected,
        current=current,
        annotations=annotations,
        memories_by_context=(
            normalized_memories if memories_by_context is not None else None
        ),
        visible_memory_contexts=included_memory_contexts,
        display_names=display_names,
        wrap_width=None,
        memory_anchor=None,
    )
    memory_count = sum(
        len(normalized_memories.get(name, ())) for name in included_memory_contexts
    )
    return ContextPickerClipboardProjection(
        text=_clipboard_fragment_text(fragments),
        scope="VISIBLE_BRANCH" if visible_branch else "ITEM",
        label=display_escape_text((display_names or {}).get(selected, selected)),
        context_count=len(selected_rows),
        memory_count=memory_count,
    )
