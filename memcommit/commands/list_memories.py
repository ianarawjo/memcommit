from typing import Annotated, Optional

import typer

from memcommit.clipboard import (
    ClipboardError,
    ClipboardPayload,
    copy_payload,
    load_payload,
)
from memcommit.context import (
    Context,
    Information,
    Memory,
    MemoryRef,
    QueryContextRef,
)
from memcommit.store import MemoryStore


_LIST_SNAPSHOT_VERSION = 1


def _one_line(content: str) -> str:
    """Render atomic Memory content as its compact, human-readable name."""
    return " ".join(content.split()) or "(empty)"


def _snapshot_item(
    item: Information,
    *,
    recursive: bool,
    ancestors: frozenset[str],
) -> dict[str, object]:
    """Freeze one visible item without opening query-only source content."""
    if isinstance(item, Context):
        cycle = recursive and item.uid in ancestors
        children: list[dict[str, object]] | None = None
        if recursive and not cycle:
            children = [
                _snapshot_item(
                    child,
                    recursive=True,
                    ancestors=ancestors | {item.uid},
                )
                for child in item.iter_items()
            ]
        return {
            "kind": "context",
            "uid": item.uid,
            "name": item.name,
            "cycle": cycle,
            "children": children,
        }
    if isinstance(item, QueryContextRef):
        # Routing metadata is part of the opaque pointer. The query-only source
        # itself is deliberately neither loaded nor copied.
        return {
            "kind": "query_context_ref",
            "uid": item.uid,
            "name": item.name,
            "target_source_uid": item.target_source_uid,
            "provider": item.provider,
        }
    if isinstance(item, MemoryRef):
        return {
            "kind": "memory_ref",
            "uid": item.uid,
            "target_context_uid": item.target_context_uid,
            "target_context_name": item.target_context_name,
            "target_memory_uid": item.target_memory_uid,
            "resolved_content": (
                item.target.content if item.target is not None else None
            ),
        }
    return {
        "kind": "memory",
        "uid": item.uid,
        "content": item.content,
    }


def _snapshot_context(
    ctx: Context,
    *,
    recursive: bool,
) -> dict[str, object]:
    """Freeze the exact object scope represented by one list invocation."""
    return {
        "schema_version": _LIST_SNAPSHOT_VERSION,
        "context": {"uid": ctx.uid, "name": ctx.name},
        "recursive": recursive,
        # Canonical object order is preserved here. Rendering reapplies the
        # Context-first display grouping without rewriting this future input.
        "items": [
            _snapshot_item(
                item,
                recursive=recursive,
                ancestors=frozenset({ctx.uid}),
            )
            for item in ctx.iter_items()
        ],
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
        if kind in {"context", "query_context_ref"}:
            contexts.append(item)
        elif kind in {"memory", "memory_ref"}:
            memories.append(item)
        else:
            raise _snapshot_error()
    return contexts, memories


def _render_snapshot_item(
    item: dict[str, object],
    *,
    indent: int,
    lines: list[str],
    with_ids: bool,
) -> None:
    prefix = " " * indent
    kind = _require_string(item, "kind")
    uid = _require_string(item, "uid")
    if kind == "context":
        expected = {"kind", "uid", "name", "cycle", "children"}
        if set(item) != expected:
            raise _snapshot_error()
        name = _require_string(item, "name")
        cycle = _require_bool(item, "cycle")
        children_value = item.get("children")
        if children_value is None:
            children = None
        else:
            children = _require_items(children_value)
        if cycle and children is not None:
            raise _snapshot_error()
        if with_ids:
            lines.append(f"{prefix}[context {uid[:8]}] {name}")
        else:
            lines.append(f"{prefix}{name}/")
        if cycle:
            lines.append(f"{' ' * (indent + 2)}(cycle)")
        elif children is not None:
            if not children:
                lines.append(f"{' ' * (indent + 2)}(no items)")
            else:
                _render_snapshot_items(
                    children,
                    indent=indent + 2,
                    lines=lines,
                    with_ids=with_ids,
                )
        return
    if kind == "query_context_ref":
        expected = {
            "kind",
            "uid",
            "name",
            "target_source_uid",
            "provider",
        }
        if set(item) != expected:
            raise _snapshot_error()
        name = _require_string(item, "name")
        _require_string(item, "target_source_uid")
        _require_string(item, "provider")
        if with_ids:
            lines.append(
                f"{prefix}[query   {uid[:8]}] {name} (query-only)"
            )
        else:
            lines.append(f"{prefix}{name}/ (query-only)")
        return
    if kind == "memory_ref":
        expected = {
            "kind",
            "uid",
            "target_context_uid",
            "target_context_name",
            "target_memory_uid",
            "resolved_content",
        }
        if set(item) != expected:
            raise _snapshot_error()
        _require_string(item, "target_context_uid")
        target_context_name = _require_string(item, "target_context_name")
        target_memory_uid = _require_string(item, "target_memory_uid")
        content = item.get("resolved_content")
        if content is None:
            if with_ids:
                lines.append(
                    f"{prefix}[ref     {uid[:8]}] (dangling) "
                    f"{target_context_name}#{target_memory_uid[:8]}"
                )
            else:
                lines.append(
                    f"{prefix}(dangling reference) {target_context_name}"
                )
        elif isinstance(content, str):
            if with_ids:
                lines.append(
                    f"{prefix}[ref     {uid[:8]}] {_one_line(content)} "
                    f"-> {target_context_name}#{target_memory_uid[:8]}"
                )
            else:
                lines.append(
                    f"{prefix}{_one_line(content)} -> {target_context_name}"
                )
        else:
            raise _snapshot_error()
        return
    if kind == "memory":
        if set(item) != {"kind", "uid", "content"}:
            raise _snapshot_error()
        content = _require_string(item, "content")
        if with_ids:
            lines.append(
                f"{prefix}[memory  {uid[:8]}] {_one_line(content)}"
            )
        else:
            lines.append(f"{prefix}{_one_line(content)}")
        return
    raise _snapshot_error()


def _render_snapshot_items(
    items: list[dict[str, object]],
    *,
    indent: int,
    lines: list[str],
    with_ids: bool,
) -> None:
    contexts, memories = _group_snapshot_items(items)
    for item in [*contexts, *memories]:
        _render_snapshot_item(
            item,
            indent=indent,
            lines=lines,
            with_ids=with_ids,
        )


def _render_snapshot(
    snapshot: dict[str, object],
    *,
    with_ids: bool = True,
) -> str:
    expected = {"schema_version", "context", "recursive", "items"}
    if set(snapshot) != expected:
        raise _snapshot_error()
    if snapshot.get("schema_version") != _LIST_SNAPSHOT_VERSION:
        raise _snapshot_error()
    context = _require_record(snapshot.get("context"))
    if set(context) != {"uid", "name"}:
        raise _snapshot_error()
    _require_string(context, "uid")
    name = _require_string(context, "name")
    _require_bool(snapshot, "recursive")
    items = _require_items(snapshot.get("items"))

    lines = [
        f"Context: {name}",
        f"  {len(items)} item{'s' if len(items) != 1 else ''}",
    ]
    if not items:
        lines.extend(["", "  (no items)"])
    else:
        lines.append("")
        _render_snapshot_items(
            items,
            indent=2,
            lines=lines,
            with_ids=with_ids,
        )
    return "\n".join(lines) + "\n"


def _snapshot_occurrence_count(snapshot: dict[str, object]) -> int:
    def count(items: list[dict[str, object]]) -> int:
        total = 0
        for item in items:
            total += 1
            children = item.get("children")
            if children is not None:
                total += count(_require_items(children))
        return total

    return count(_require_items(snapshot.get("items")))


def _emit_snapshot_text(text: str) -> None:
    """Preserve the existing bold Context heading while keeping canonical text."""
    lines = text.splitlines()
    if not lines:
        return
    typer.secho(lines[0], bold=True)
    for line in lines[1:]:
        typer.echo(line)


def render_index(ctx: Context, *, recursive: bool = False) -> None:
    """Print a compact index of a Context's logical children."""
    _emit_snapshot_text(
        _render_snapshot(_snapshot_context(ctx, recursive=recursive))
    )


def cmd(
    context_name: Annotated[Optional[str], typer.Argument(help="Context to list (defaults to current)")] = None,
    recursive: Annotated[
        bool,
        typer.Option(
            "-R",
            "--recursive",
            help="Recursively list the contents of embedded Contexts.",
        ),
    ] = False,
    copy_result: Annotated[
        bool,
        typer.Option(
            "--copy",
            help=(
                "Copy a clean list to the system clipboard and stage its "
                "structured result; add --with-ids for annotations."
            ),
        ),
    ] = False,
    with_ids: Annotated[
        bool,
        typer.Option(
            "--with-ids",
            help=(
                "Include [kind uid] annotations in text copied by --copy."
            ),
        ),
    ] = False,
    paste_result: Annotated[
        bool,
        typer.Option(
            "--paste",
            help=(
                "List the structured result currently paired with the system "
                "clipboard."
            ),
        ),
    ] = False,
) -> None:
    if copy_result and paste_result:
        typer.secho(
            "Error: --copy and --paste cannot be used together.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    if with_ids and not copy_result:
        typer.secho(
            "Error: --with-ids can only be used with --copy.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    if paste_result:
        if context_name is not None or recursive:
            typer.secho(
                "Error: CONTEXT and --recursive cannot be used with --paste; "
                "the copied scope is already frozen.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        try:
            payload = load_payload(expected_producer="list")
            annotated_text = _render_snapshot(
                payload.selection,
                with_ids=True,
            )
            clean_text = _render_snapshot(
                payload.selection,
                with_ids=False,
            )
            if payload.plain_text not in {annotated_text, clean_text}:
                raise ClipboardError(
                    "The structured clipboard text and object snapshot disagree."
                )
        except (ClipboardError, ValueError) as error:
            typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)
        _emit_snapshot_text(payload.plain_text)
        count = _snapshot_occurrence_count(payload.selection)
        source_context = _require_record(payload.selection.get("context"))
        source_name = _require_string(source_context, "name")
        typer.secho(
            f"Pasted {count} staged item{'s' if count != 1 else ''} "
            f"from '{source_name}' "
            "(no Context changes).",
            dim=True,
            err=True,
        )
        return

    store = MemoryStore()

    if context_name is None:
        context_name = store.current_context_name()
        if not context_name:
            typer.secho("No current context. Run 'mem init <name>' first.", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)

    if not store.context_exists(context_name):
        typer.secho(f"Error: context '{context_name}' not found.", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    ctx = store.load(context_name)
    snapshot = _snapshot_context(ctx, recursive=recursive)
    annotated_text = _render_snapshot(snapshot, with_ids=True)
    _emit_snapshot_text(annotated_text)

    if copy_result:
        clipboard_text = _render_snapshot(
            snapshot,
            with_ids=with_ids,
        )
        payload = ClipboardPayload.create(
            producer="list",
            plain_text=clipboard_text,
            selection=snapshot,
        )
        try:
            copy_payload(payload)
        except ClipboardError as error:
            typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)
        count = _snapshot_occurrence_count(snapshot)
        copied_style = "text with IDs" if with_ids else "clean text"
        typer.secho(
            f"Copied {count} item{'s' if count != 1 else ''}: "
            f"{copied_style} to the system clipboard; "
            "structured list staged.",
            fg=typer.colors.GREEN,
            err=True,
        )
