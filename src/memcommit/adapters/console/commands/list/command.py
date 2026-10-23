from collections.abc import Iterable
import shutil
from typing import Annotated, Literal, Optional

import typer
from prompt_toolkit.utils import get_cwidth

from memcommit.adapters.console.clipboard import (
    ClipboardError,
    write_system_clipboard,
)
from memcommit.models.context import Context
from memcommit.models.memory import Memory
from memcommit.adapters.console.coordination.context_scope_options import (
    ContextScopePreset,
    resolve_scope_preset,
)
from memcommit.adapters.console.terminal.core.identity import (
    collision_safe_uid_prefixes,
)
from memcommit.adapters.console.terminal.core.text import (
    display_escape_text,
)
from memcommit.application.operations.profile.config import (
    ProfileConfigError,
)
from memcommit.application.operations.profile.model import ProfileError
from memcommit.application.operations.list.application import ListRequest
from memcommit.application.operations.list.runtime import (
    context_record_display_uids,
    execute_list,
)
from memcommit.persistence.store import MemoryStore
from memcommit.source_projection.model import (
    SourceDisplayFacts,
    SourceForm,
    SourceReach,
    SourceState,
)
from memcommit.source_projection.console import (
    styled_source_reach_label,
)
from memcommit.source_projection.presentation import (
    source_annotation_text,
    source_object_label,
    source_reach_label,
)


_LIST_SNAPSHOT_VERSION = 3
_MemoryLayout = Literal["hanging", "inline"]
_MIN_HANGING_CONTENT_WIDTH = 20


def _one_line(content: str) -> str:
    """Render atomic Memory content as its compact, human-readable name."""
    return " ".join(content.split()) or "(empty)"


def _wrap_display_words(content: str, width: int) -> tuple[str, ...]:
    """Wrap normalized text by terminal cells while preserving word boundaries."""

    if width < 1:
        raise ValueError("display wrap width must be positive")

    def split_word(word: str) -> list[str]:
        chunks: list[str] = []
        current = ""
        for character in word:
            if current and get_cwidth(current + character) > width:
                chunks.append(current)
                current = ""
            current += character
        if current:
            chunks.append(current)
        return chunks

    lines: list[str] = []
    current = ""
    for word in content.split(" "):
        candidate = word if not current else f"{current} {word}"
        if get_cwidth(candidate) <= width:
            current = candidate
            continue
        if current:
            lines.append(current)
            current = ""
        chunks = split_word(word)
        lines.extend(chunks[:-1])
        current = chunks[-1]
    if current:
        lines.append(current)
    return tuple(lines) or ("",)


def _hanging_memory_lines(
    label: str,
    content: str,
    *,
    indent: int,
    terminal_width: int,
) -> tuple[str, ...]:
    """Put content beside its selector and align visual continuation rows."""

    content_column = get_cwidth(label) + 1
    available = terminal_width - content_column
    if available < _MIN_HANGING_CONTENT_WIDTH:
        # Very deep recursive rows cannot retain a useful content column beside
        # the selector. Preserve readable content instead of forcing a narrow
        # vertical strip or overflowing the terminal.
        continuation = " " * (indent + 2)
        fallback_width = max(
            _MIN_HANGING_CONTENT_WIDTH,
            terminal_width - get_cwidth(continuation),
        )
        wrapped = _wrap_display_words(content, fallback_width)
        return (label, *(continuation + line for line in wrapped))
    continuation = " " * content_column
    wrapped = _wrap_display_words(content, available)
    return (
        f"{label} {wrapped[0]}",
        *(continuation + line for line in wrapped[1:]),
    )


def _immediate_namespace_child_names(
    parent_name: str,
    context_names: tuple[str, ...],
) -> list[str]:
    """Return materialized one-segment descendants from one frozen catalog."""
    return sorted(
        name
        for name in context_names
        if _is_immediate_namespace_child(parent_name, name)
    )


def _is_immediate_namespace_child(
    parent_name: str,
    child_name: str,
) -> bool:
    """Validate one exact materialized namespace edge lexically."""
    prefix = f"{parent_name}/"
    if not child_name.startswith(prefix):
        return False
    remainder = child_name[len(prefix) :]
    return bool(remainder) and "/" not in remainder


def _snapshot_context_entry(
    ctx: Context,
    *,
    kind: Literal["namespace_context"],
    store: MemoryStore,
    context_names: tuple[str, ...],
    recursive: bool,
    ancestors: frozenset[str],
) -> dict[str, object]:
    """Freeze one local namespace Context occurrence."""
    cycle = recursive and ctx.uid in ancestors
    children: list[dict[str, object]] | None = None
    if recursive and not cycle:
        children = _snapshot_visible_items(
            ctx,
            store=store,
            context_names=context_names,
            recursive=True,
            ancestors=ancestors | {ctx.uid},
        )
    return {
        "kind": kind,
        "uid": ctx.uid,
        "name": ctx.name,
        "cycle": cycle,
        "children": children,
    }


def _snapshot_item(
    item: Memory,
    *,
    store: MemoryStore,
    context_names: tuple[str, ...],
    recursive: bool,
    ancestors: frozenset[str],
) -> dict[str, object]:
    """Freeze one directly owned Memory as a read-only list row."""
    return {
        "kind": "memory",
        "uid": item.uid,
        "content": item.content,
    }


def _snapshot_visible_items(
    ctx: Context,
    *,
    store: MemoryStore,
    context_names: tuple[str, ...],
    recursive: bool,
    ancestors: frozenset[str],
) -> list[dict[str, object]]:
    """Combine read-only namespace navigation with persisted direct items."""
    direct_items = list(ctx.iter_memories())
    child_items: list[dict[str, object]] = []
    for child_name in _immediate_namespace_child_names(
        ctx.name,
        context_names,
    ):
        try:
            child = (
                store.load(child_name) if recursive else store.load_direct(child_name)
            )
        except (OSError, ValueError):
            # The catalog and child read are separate filesystem snapshots. A
            # disappearing or newly broken child must not hide valid parent
            # Memories from this read-only navigation command.
            continue
        child_items.append(
            _snapshot_context_entry(
                child,
                kind="namespace_context",
                store=store,
                context_names=context_names,
                recursive=recursive,
                ancestors=ancestors,
            )
        )

    return [
        *child_items,
        *[
            _snapshot_item(
                item,
                store=store,
                context_names=context_names,
                recursive=recursive,
                ancestors=ancestors,
            )
            for item in direct_items
        ],
    ]


def _snapshot_context(
    ctx: Context,
    *,
    store: MemoryStore,
    context_names: tuple[str, ...],
    recursive: bool,
    readable_uids: Iterable[str] = (),
) -> dict[str, object]:
    """Freeze the exact navigation scope represented by one list invocation."""
    items = _snapshot_visible_items(
        ctx,
        store=store,
        context_names=context_names,
        recursive=recursive,
        ancestors=frozenset({ctx.uid}),
    )
    visible_uids = tuple(dict.fromkeys(_snapshot_display_uids(items)))
    all_prefixes = collision_safe_uid_prefixes((*readable_uids, *visible_uids))
    return {
        "schema_version": _LIST_SNAPSHOT_VERSION,
        "context": {"uid": ctx.uid, "name": ctx.name},
        "recursive": recursive,
        # Store only visible projections, not the UIDs of unrelated readable
        # Contexts that caused a prefix to grow.
        "uid_prefixes": {uid: all_prefixes[uid] for uid in visible_uids},
        # Persisted object order is preserved within the logical items.
        # Namespace children precede them as deterministic navigation rows.
        "items": items,
    }


def _snapshot_error() -> ValueError:
    return ValueError("The staged list snapshot is invalid.")


def _require_record(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise _snapshot_error()
    return value


def _require_string(record: dict[str, object], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str):
        raise _snapshot_error()
    return value


def _require_bool(record: dict[str, object], key: str) -> bool:
    value = record.get(key)
    if not isinstance(value, bool):
        raise _snapshot_error()
    return value


def _require_items(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise _snapshot_error()
    return [_require_record(item) for item in value]


def _group_snapshot_items(
    items: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    contexts: list[dict[str, object]] = []
    memories: list[dict[str, object]] = []
    for item in items:
        kind = _require_string(item, "kind")
        if kind == "namespace_context":
            contexts.append(item)
        elif kind == "memory":
            memories.append(item)
        else:
            raise _snapshot_error()
    return contexts, memories


def _snapshot_display_uids(
    items: list[dict[str, object]],
) -> tuple[str, ...]:
    """Collect every UID rendered in one already-frozen list snapshot."""

    values: list[str] = []
    for item in items:
        kind = _require_string(item, "kind")
        values.append(_require_string(item, "uid"))
        if kind == "namespace_context":
            children = item.get("children")
            if children is not None:
                values.extend(_snapshot_display_uids(_require_items(children)))
        elif kind != "memory":
            raise _snapshot_error()
    return tuple(values)


def _require_uid_prefixes(
    snapshot: dict[str, object],
    visible_uids: tuple[str, ...],
) -> dict[str, str]:
    raw = _require_record(snapshot.get("uid_prefixes"))
    distinct_uids = tuple(dict.fromkeys(visible_uids))
    if set(raw) != set(distinct_uids):
        raise _snapshot_error()
    visible_minimums = collision_safe_uid_prefixes(distinct_uids)
    prefixes: dict[str, str] = {}
    for uid in distinct_uids:
        prefix = raw.get(uid)
        if (
            not isinstance(prefix, str)
            or prefix != uid[: len(prefix)]
            or len(prefix) < len(visible_minimums[uid])
        ):
            raise _snapshot_error()
        prefixes[uid] = prefix
    return prefixes


def _render_snapshot_item(
    item: dict[str, object],
    *,
    parent_name: str,
    indent: int,
    lines: list[str],
    with_ids: bool,
    memory_layout: _MemoryLayout,
    terminal_width: int,
    separate_context_blocks: bool,
    style_relationships: bool,
    uid_prefixes: dict[str, str],
) -> None:
    prefix = " " * indent
    kind = _require_string(item, "kind")
    uid = _require_string(item, "uid")
    if kind == "namespace_context":
        expected = {"kind", "uid", "name", "cycle", "children"}
        if set(item) != expected:
            raise _snapshot_error()
        name = _require_string(item, "name")
        if kind == "namespace_context" and not _is_immediate_namespace_child(
            parent_name,
            name,
        ):
            raise _snapshot_error()
        cycle = _require_bool(item, "cycle")
        children_value = item.get("children")
        if children_value is None:
            children = None
        else:
            children = _require_items(children_value)
        if cycle and children is not None:
            raise _snapshot_error()
        context_facts = SourceDisplayFacts(
            reach=SourceReach.DESCENDANT,
            states=(SourceState.CYCLE,) if cycle else (),
        )
        # Reach explains why this Context row occurs in the selected tree,
        # so it leads the row instead of looking like a trailing property
        # of the canonical Context identity.
        reach_label = (
            styled_source_reach_label(context_facts.reach)
            if style_relationships
            else source_reach_label(context_facts.reach)
        )
        context_label = source_object_label(context_facts)
        state_annotation = source_annotation_text(
            SourceDisplayFacts(states=context_facts.states)
        )
        if with_ids:
            lines.append(
                f"{prefix}{reach_label} · "
                f"[{context_label} {uid_prefixes[uid]}] {name}"
                + (f"  {state_annotation}" if state_annotation else "")
            )
        else:
            lines.append(
                f"{prefix}{reach_label} · {name}/"
                + (f" · {state_annotation}" if state_annotation else "")
            )
        if not cycle and children is not None:
            if not children:
                lines.append(f"{' ' * (indent + 2)}(empty)")
            else:
                _render_snapshot_items(
                    children,
                    parent_name=name,
                    indent=indent + 2,
                    lines=lines,
                    with_ids=with_ids,
                    memory_layout=memory_layout,
                    terminal_width=terminal_width,
                    separate_context_blocks=separate_context_blocks,
                    style_relationships=style_relationships,
                    uid_prefixes=uid_prefixes,
                )
        return
    if kind == "memory":
        if set(item) != {"kind", "uid", "content"}:
            raise _snapshot_error()
        content = _require_string(item, "content")
        if with_ids:
            memory_label = source_object_label(SourceForm.MEMORY)
            label = f"{prefix}[{memory_label} {uid_prefixes[uid]}]"
            if memory_layout == "hanging":
                lines.extend(
                    _hanging_memory_lines(
                        label,
                        _one_line(content),
                        indent=indent,
                        terminal_width=terminal_width,
                    )
                )
            else:
                lines.append(f"{label} {_one_line(content)}")
        else:
            lines.append(f"{prefix}{_one_line(content)}")
        return
    raise _snapshot_error()


def _render_snapshot_items(
    items: list[dict[str, object]],
    *,
    parent_name: str,
    indent: int,
    lines: list[str],
    with_ids: bool,
    memory_layout: _MemoryLayout,
    terminal_width: int,
    separate_context_blocks: bool,
    style_relationships: bool,
    uid_prefixes: dict[str, str],
) -> None:
    contexts, memories = _group_snapshot_items(items)
    for index, item in enumerate(contexts):
        if separate_context_blocks and index:
            # Recursive Contexts read as sections; separate siblings without
            # adding whitespace at the start or end of their containing list.
            lines.append("")
        _render_snapshot_item(
            item,
            parent_name=parent_name,
            indent=indent,
            lines=lines,
            with_ids=with_ids,
            memory_layout=memory_layout,
            terminal_width=terminal_width,
            separate_context_blocks=separate_context_blocks,
            style_relationships=style_relationships,
            uid_prefixes=uid_prefixes,
        )
    if contexts and memories:
        lines.append("")
    for item in memories:
        _render_snapshot_item(
            item,
            parent_name=parent_name,
            indent=indent,
            lines=lines,
            with_ids=with_ids,
            memory_layout=memory_layout,
            terminal_width=terminal_width,
            separate_context_blocks=separate_context_blocks,
            style_relationships=style_relationships,
            uid_prefixes=uid_prefixes,
        )


def _memory_count_text(count: int) -> str:
    return f"{count} {'memory' if count == 1 else 'memories'}"


def _subcontext_count_text(count: int) -> str:
    return f"{count} subcontext{'s' if count != 1 else ''}"


def _render_snapshot(
    snapshot: dict[str, object],
    *,
    with_ids: bool = True,
    memory_layout: _MemoryLayout,
    terminal_width: int = 100,
    style_relationships: bool = False,
) -> str:

    if memory_layout not in {"hanging", "inline"}:
        raise _snapshot_error()
    if terminal_width < 1:
        raise _snapshot_error()
    expected = {
        "schema_version",
        "context",
        "recursive",
        "uid_prefixes",
        "items",
    }
    if set(snapshot) != expected:
        raise _snapshot_error()
    if snapshot.get("schema_version") != _LIST_SNAPSHOT_VERSION:
        raise _snapshot_error()
    context = _require_record(snapshot.get("context"))
    if set(context) != {"uid", "name"}:
        raise _snapshot_error()
    _require_string(context, "uid")
    name = _require_string(context, "name")
    recursive = _require_bool(snapshot, "recursive")
    items = _require_items(snapshot.get("items"))
    uid_prefixes = _require_uid_prefixes(snapshot, _snapshot_display_uids(items))

    contexts, memories = _group_snapshot_items(items)
    lines = [
        f"Context: {name}"
        ,
        f"  {_memory_count_text(len(memories))}",
        f"  {_subcontext_count_text(len(contexts))}",
    ]
    if not items:
        lines.extend(["", "  (empty)"])
    else:
        lines.append("")
        _render_snapshot_items(
            items,
            parent_name=name,
            indent=2,
            lines=lines,
            with_ids=with_ids,
            memory_layout=memory_layout,
            terminal_width=terminal_width,
            separate_context_blocks=recursive,
            style_relationships=style_relationships,
            uid_prefixes=uid_prefixes,
        )
    return "\n".join(lines) + "\n"


def _snapshot_occurrence_counts(snapshot: dict[str, object]) -> tuple[int, int]:
    """Count displayed Memory rows and subcontext rows independently."""

    def count(items: list[dict[str, object]]) -> tuple[int, int]:
        contexts, memories = _group_snapshot_items(items)
        memory_count = len(memories)
        subcontext_count = len(contexts)
        for item in items:
            children = item.get("children")
            if children is not None:
                nested_memories, nested_subcontexts = count(_require_items(children))
                memory_count += nested_memories
                subcontext_count += nested_subcontexts
        return memory_count, subcontext_count

    return count(_require_items(snapshot.get("items")))


def _occurrence_count_text(memory_count: int, subcontext_count: int) -> str:
    return (
        f"{_memory_count_text(memory_count)} and "
        f"{_subcontext_count_text(subcontext_count)}"
    )


def _emit_snapshot_text(
    text: str,
    *,
    header_notes: tuple[str, ...] = (),
) -> None:
    """Preserve the existing bold Context heading while keeping canonical text."""
    lines = text.splitlines()
    if not lines:
        return
    typer.secho(lines[0], bold=True)
    for note in header_notes:
        typer.echo(note)
    for line in lines[1:]:
        typer.echo(line)


def render_index(ctx: Context, *, recursive: bool = False) -> None:
    """Print a compact index of a Context's visible navigation children."""
    store = MemoryStore(create=False)
    readable_uids = tuple(
        uid
        for context in store.load_direct_context_graph_strict()
        for uid in context_record_display_uids(context)
    )
    _emit_snapshot_text(
        _render_snapshot(
            _snapshot_context(
                ctx,
                store=store,
                context_names=tuple(store.list_context_names()),
                recursive=recursive,
                readable_uids=readable_uids,
            ),
            memory_layout="hanging",
            terminal_width=shutil.get_terminal_size(fallback=(100, 24)).columns,
            style_relationships=True,
        )
    )


def cmd(
    context_name: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Existing Context to list by canonical name or explicit "
                "relative locator; omit to list the current Context"
            )
        ),
    ] = None,
    recursive: Annotated[
        bool,
        typer.Option(
            "-r",
            "-R",
            "--recursive",
            "--expand",
            help=("Expand every descendant namespace."),
        ),
    ] = False,
    direct: Annotated[
        bool,
        typer.Option(
            "-d",
            "--direct",
            help="List only the selected Context without recursive expansion.",
        ),
    ] = False,
    copy_result: Annotated[
        bool,
        typer.Option(
            "--copy",
            help=(
                "Copy a clean list to the system clipboard; add --with-ids for annotations."
            ),
        ),
    ] = False,
    with_ids: Annotated[
        bool,
        typer.Option(
            "--with-ids",
            help=("Include [kind uid] annotations in text copied by --copy."),
        ),
    ] = False,
) -> None:
    try:
        recursive = (
            resolve_scope_preset(
                direct=direct,
                recursive=recursive,
                default=ContextScopePreset.DIRECT,
            )
            is ContextScopePreset.RECURSIVE
        )
    except ValueError as error:
        typer.secho(
            f"Error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    if with_ids and not copy_result:
        typer.secho(
            "Error: --with-ids can only be used with --copy.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    active_store = MemoryStore()
    current_context_name = active_store.current_context_name()
    try:
        selection = execute_list(
            active_store,
            ListRequest(
                context_locator=context_name,
                current_context_name=current_context_name,
                recursive=recursive,
            ),
        )
        ctx = selection.context
        store = selection.catalog
        context_names = selection.context_names
        readable_uids = selection.readable_uids
    except (
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        ValueError,
    ) as error:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    snapshot = _snapshot_context(
        ctx,
        store=store,
        context_names=context_names,
        recursive=recursive,
        readable_uids=readable_uids,
    )
    annotated_text = _render_snapshot(
        snapshot,
        with_ids=True,
        memory_layout="hanging",
        terminal_width=shutil.get_terminal_size(fallback=(100, 24)).columns,
        style_relationships=True,
    )
    _emit_snapshot_text(
        annotated_text,
        header_notes=(()),
    )
    if copy_result:
        clipboard_text = _render_snapshot(
            snapshot,
            with_ids=with_ids,
            memory_layout="inline",
        )
        try:
            write_system_clipboard(clipboard_text)
        except ClipboardError as error:
            typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)
        memory_count, subcontext_count = _snapshot_occurrence_counts(snapshot)
        copied_style = "text with IDs" if with_ids else "clean text"
        typer.secho(
            f"Copied {_occurrence_count_text(memory_count, subcontext_count)}: "
            f"{copied_style} to the system clipboard.",
            fg=typer.colors.GREEN,
            err=True,
        )
