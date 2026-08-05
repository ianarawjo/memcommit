import shutil
import sys
from typing import Annotated, Literal, Optional

import typer
from prompt_toolkit.utils import get_cwidth

from memcommit.clipboard import (
    ClipboardError,
    ClipboardPayload,
    copy_payload,
    load_payload,
    selection_digest,
)
from memcommit.context import (
    Context,
    Information,
    MemoryRef,
    QueryContextRef,
)
from memcommit.commands.granted_context import (
    ContextAccess,
    GrantedReadStore,
    attached_grants,
    freeze_granted_context_binding,
    resolve_context_access,
    revalidate_granted_context_binding,
)
from memcommit.commands.readable_context_catalog import (
    freeze_readable_context_catalog,
)
from memcommit.commands.context_picker import (
    ContextMemoryRow,
    ContextTree,
    choose_context,
)
from memcommit.commands.tui_primitives import display_escape_text
from memcommit.profile_config import AuthorityGrant, ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.store import MemoryStore
from memcommit.update import GrantedUpdateTarget
from memcommit.study_operation_policy import analysis_boundary_label, operation_policy


_LIST_SNAPSHOT_VERSION = 2
_GRANTED_LIST_RECEIPT_VERSION = 1
_MemoryLayout = Literal["hanging", "inline"]
_MIN_HANGING_CONTENT_WIDTH = 20


def _interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


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
    kind: Literal["context", "namespace_context"],
    store: MemoryStore,
    context_names: tuple[str, ...],
    recursive: bool,
    ancestors: frozenset[str],
) -> dict[str, object]:
    """Freeze one embedded or namespace-derived Context occurrence."""
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
    item: Information,
    *,
    store: MemoryStore,
    context_names: tuple[str, ...],
    recursive: bool,
    ancestors: frozenset[str],
) -> dict[str, object]:
    """Freeze one persisted item without opening query-only source content."""
    if isinstance(item, Context):
        return _snapshot_context_entry(
            item,
            kind="context",
            store=store,
            context_names=context_names,
            recursive=recursive,
            ancestors=ancestors,
        )
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


def _snapshot_visible_items(
    ctx: Context,
    *,
    store: MemoryStore,
    context_names: tuple[str, ...],
    recursive: bool,
    ancestors: frozenset[str],
) -> list[dict[str, object]]:
    """Combine read-only namespace navigation with persisted direct items."""
    direct_items = list(ctx.iter_items())
    embedded_contexts = {
        item.name: item
        for item in direct_items
        if isinstance(item, Context)
    }
    listed_embed_uids: set[str] = set()
    child_items: list[dict[str, object]] = []
    for child_name in _immediate_namespace_child_names(
        ctx.name,
        context_names,
    ):
        try:
            child = (
                store.load(child_name)
                if recursive
                else store.load_direct(child_name)
            )
        except (OSError, ValueError):
            # The catalog and child read are separate filesystem snapshots. A
            # disappearing or newly broken child must not hide valid parent
            # Memories from this read-only navigation command.
            continue
        embedded = embedded_contexts.get(child.name)
        if embedded is not None and embedded.uid == child.uid:
            # Keep the persisted relation typed as an embed, but place it in
            # the sorted namespace-child group so merely embedding a child
            # cannot reorder the directory-like listing.
            child = embedded
            kind: Literal["context", "namespace_context"] = "context"
            listed_embed_uids.add(embedded.uid)
        else:
            kind = "namespace_context"
            if embedded is not None:
                # A delete/recreate race can leave the already loaded parent
                # holding the old UID while the later child read sees the new
                # UID. The canonical locator can name only the new Context, so
                # suppress the stale occurrence instead of printing one path
                # twice with conflicting identities.
                listed_embed_uids.add(embedded.uid)
        child_items.append(
            _snapshot_context_entry(
                child,
                kind=kind,
                store=store,
                context_names=context_names,
                recursive=recursive,
                ancestors=ancestors,
            )
        )

    # Namespace rows are a list-time projection. They must never be added to
    # the in-memory Context, where they could later be mistaken for embeds.
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
            if not (
                isinstance(item, Context) and item.uid in listed_embed_uids
            )
        ],
    ]


def _snapshot_context(
    ctx: Context,
    *,
    store: MemoryStore,
    context_names: tuple[str, ...],
    recursive: bool,
) -> dict[str, object]:
    """Freeze the exact navigation scope represented by one list invocation."""
    return {
        "schema_version": _LIST_SNAPSHOT_VERSION,
        "context": {"uid": ctx.uid, "name": ctx.name},
        "recursive": recursive,
        # Persisted object order is preserved within the logical items.
        # Namespace children precede them as deterministic navigation rows.
        "items": _snapshot_visible_items(
            ctx,
            store=store,
            context_names=context_names,
            recursive=recursive,
            ancestors=frozenset({ctx.uid}),
        ),
    }


def _snapshot_memory_rows(
    snapshot: dict[str, object],
) -> tuple[ContextMemoryRow, ...]:
    """Adapt only direct Memory occurrences to the shared tree presentation."""

    rows: list[ContextMemoryRow] = []
    for item in _require_items(snapshot.get("items")):
        kind = _require_string(item, "kind")
        uid = _require_string(item, "uid")
        if kind == "memory":
            rows.append(
                ContextMemoryRow(
                    f"memory {uid[:8]}",
                    _require_string(item, "content"),
                )
            )
        elif kind == "memory_ref":
            content = item.get("resolved_content")
            target_name = _require_string(item, "target_context_name")
            rows.append(
                ContextMemoryRow(
                    f"ref {uid[:8]}",
                    content
                    if isinstance(content, str)
                    else f"(dangling reference) {target_name}",
                )
            )
    return tuple(rows)


def _snapshot_browser_tree(
    snapshot: dict[str, object],
) -> tuple[
    ContextTree,
    tuple[str, ...],
    tuple[str, ...],
    dict[str, str],
    dict[str, str],
    dict[str, tuple[ContextMemoryRow, ...]],
]:
    """Adapt the frozen recursive occurrence graph to the common tree UI.

    Occurrence IDs, rather than Context names, preserve repeated embeds and
    cycles. They remain process-local and are never returned as locators.
    """

    root = _require_record(snapshot.get("context"))
    root_name = _require_string(root, "name")
    root_id = "occurrence:0"
    ordered: list[str] = [root_id]
    virtual: list[str] = []
    children: dict[str, tuple[str, ...]] = {}
    parents: dict[str, str | None] = {root_id: None}
    labels = {root_id: root_name}
    annotations: dict[str, str] = {}
    memories: dict[str, tuple[ContextMemoryRow, ...]] = {}

    def visit(parent_id: str, items: list[dict[str, object]]) -> None:
        memories[parent_id] = _snapshot_memory_rows({"items": items})
        child_ids: list[str] = []
        contexts, _ = _group_snapshot_items(items)
        for index, item in enumerate(contexts):
            kind = _require_string(item, "kind")
            child_id = f"{parent_id}/{index}"
            child_ids.append(child_id)
            ordered.append(child_id)
            parents[child_id] = parent_id
            if kind == "query_context_ref":
                labels[child_id] = _require_string(item, "name")
                annotations[child_id] = "[query-only]"
                virtual.append(child_id)
                children[child_id] = ()
                continue
            labels[child_id] = _require_string(item, "name")
            cycle = _require_bool(item, "cycle")
            if cycle:
                annotations[child_id] = "[cycle]"
                child_items: list[dict[str, object]] = []
            else:
                value = item.get("children")
                child_items = [] if value is None else _require_items(value)
            visit(child_id, child_items)
        children[parent_id] = tuple(child_ids)

    visit(root_id, _require_items(snapshot.get("items")))
    materialized = tuple(name for name in ordered if name not in set(virtual))
    tree = ContextTree(
        roots=(root_id,),
        children_by_name=children,
        parent_by_name=parents,
        materialized_names=frozenset(materialized),
    )
    return (
        tree,
        materialized,
        tuple(virtual),
        labels,
        annotations,
        memories,
    )


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
        if kind in {"context", "namespace_context", "query_context_ref"}:
            contexts.append(item)
        elif kind in {"memory", "memory_ref"}:
            memories.append(item)
        else:
            raise _snapshot_error()
    return contexts, memories


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
) -> None:
    prefix = " " * indent
    kind = _require_string(item, "kind")
    uid = _require_string(item, "uid")
    if kind in {"context", "namespace_context"}:
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
                    parent_name=name,
                    indent=indent + 2,
                    lines=lines,
                    with_ids=with_ids,
                    memory_layout=memory_layout,
                    terminal_width=terminal_width,
                    separate_context_blocks=separate_context_blocks,
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
            label = f"{prefix}[memory  {uid[:8]}]"
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
        )
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
        )


def _render_snapshot(
    snapshot: dict[str, object],
    *,
    with_ids: bool = True,
    memory_layout: _MemoryLayout,
    terminal_width: int = 100,
) -> str:
    if memory_layout not in {"hanging", "inline"}:
        raise _snapshot_error()
    if terminal_width < 1:
        raise _snapshot_error()
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
    recursive = _require_bool(snapshot, "recursive")
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
            parent_name=name,
            indent=2,
            lines=lines,
            with_ids=with_ids,
            memory_layout=memory_layout,
            terminal_width=terminal_width,
            separate_context_blocks=recursive,
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


def _granted_list_receipt(
    snapshot: dict[str, object],
    *,
    binding: GrantedUpdateTarget,
    with_ids: bool,
) -> dict[str, object]:
    """Persist grant identity and snapshot digests without authority text."""

    return {
        "kind": "GRANTED_LIST_RECEIPT",
        "schema_version": _GRANTED_LIST_RECEIPT_VERSION,
        "binding": binding.to_dict(),
        "recursive": _require_bool(snapshot, "recursive"),
        "with_ids": with_ids,
        "snapshot_sha256": selection_digest(snapshot),
    }


def _restore_granted_list_receipt(
    receipt: dict[str, object],
) -> tuple[dict[str, object], bool]:
    expected = {
        "kind",
        "schema_version",
        "binding",
        "recursive",
        "with_ids",
        "snapshot_sha256",
    }
    if set(receipt) != expected:
        raise ClipboardError("The granted list receipt is invalid.")
    if (
        receipt.get("kind") != "GRANTED_LIST_RECEIPT"
        or receipt.get("schema_version") != _GRANTED_LIST_RECEIPT_VERSION
    ):
        raise ClipboardError("The granted list receipt is invalid.")
    recursive = receipt.get("recursive")
    with_ids = receipt.get("with_ids")
    expected_digest = receipt.get("snapshot_sha256")
    if (
        not isinstance(recursive, bool)
        or not isinstance(with_ids, bool)
        or not isinstance(expected_digest, str)
    ):
        raise ClipboardError("The granted list receipt is invalid.")
    try:
        binding = GrantedUpdateTarget.from_dict(receipt.get("binding"))
        access = revalidate_granted_context_binding(binding)
        granted_store = GrantedReadStore(access)
        context_names = tuple(granted_store.list_context_names())
        context = (
            granted_store.load(access.display_name)
            if recursive
            else granted_store.load_direct(access.display_name)
        )
        snapshot = _snapshot_context(
            context,
            store=granted_store,
            context_names=context_names,
            recursive=recursive,
        )
    except (FileNotFoundError, OSError, ProfileConfigError, ProfileError, ValueError) as error:
        raise ClipboardError(
            "The granted list source is no longer available under its exact grant."
        ) from error
    if selection_digest(snapshot) != expected_digest:
        raise ClipboardError(
            "The granted list source changed after it was copied."
        )
    return snapshot, with_ids


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


def _permission_text(permissions: tuple[str, ...]) -> str:
    return " + ".join(
        "SAVE QUERY SESSION" if item == "SESSION_LOG" else item
        for item in permissions
    )


def _boundary_value(permission: str, permissions: set[str]) -> str:
    return "allowed" if permission in permissions else "blocked"


def _derived_boundary_lines(
    grant: AuthorityGrant,
    *,
    indent: str = "  ",
) -> tuple[str, ...]:
    permissions = set(grant.permissions)
    return (
        indent
        + "Source boundary: "
        + f"DERIVE {_boundary_value('DERIVE', permissions)} · "
        + f"COMBINE {_boundary_value('COMBINE', permissions)} · "
        + f"EXPORT {_boundary_value('EXPORT', permissions)}",
        indent
        + "Target/artifact boundary: "
        + "ACCEPT_DERIVED "
        + _boundary_value("ACCEPT_DERIVED", permissions)
        + " · SAVE_BOUND_ANALYSIS "
        + _boundary_value("SAVE_BOUND_ANALYSIS", permissions)
        + " · SAVE_ANALYSIS "
        + _boundary_value("SAVE_ANALYSIS", permissions),
    )


def _granted_access_notes(access: ContextAccess) -> tuple[str, ...]:
    view = access.view
    if view is None:
        return ()
    grant = view.grant
    return (
        "  Access: GRANTED VIEW · from "
        + display_escape_text(view.authority.name)
        + f" · grant {grant.uid[:8]} revision {grant.revision}",
        "  Permissions: " + _permission_text(grant.permissions),
        "  Analysis: "
        + analysis_boundary_label(
            access.display_name,
            granted=True,
            readable="READ" in grant.permissions,
        ),
        *_derived_boundary_lines(grant),
    )


def _local_analysis_notes(
    context_name: str,
    store: MemoryStore,
) -> tuple[str, ...]:
    policy = operation_policy(
        context_name,
        granted=False,
        store_root=store.store_dir,
    )
    if policy.study_task is None:
        return ()
    return (
        "  Analysis: "
        + analysis_boundary_label(
            context_name,
            granted=False,
            store_root=store.store_dir,
        ),
    )


def _emit_grant_notes(attachment_name: str) -> None:
    registry, grants = attached_grants(attachment_name)
    if not grants:
        return
    profiles = {profile.uid: profile.name for profile in registry.profiles}
    typer.secho("Authority views:", bold=True)
    for grant in grants:
        typer.echo(
            "  "
            + display_escape_text(grant.public_name)
            + "/ · from "
            + display_escape_text(profiles[grant.authority_profile_uid])
            + f" · grant {grant.uid[:8]} revision {grant.revision}"
        )
        typer.echo("    Permissions: " + _permission_text(grant.permissions))
        typer.echo(
            "    Analysis: "
            + analysis_boundary_label(
                grant.public_name,
                granted=True,
                readable="READ" in grant.permissions,
                registry=registry,
            )
        )
        for line in _derived_boundary_lines(grant, indent="    "):
            typer.echo(line)


def render_index(ctx: Context, *, recursive: bool = False) -> None:
    """Print a compact index of a Context's visible navigation children."""
    store = MemoryStore(create=False)
    _emit_snapshot_text(
        _render_snapshot(
            _snapshot_context(
                ctx,
                store=store,
                context_names=tuple(store.list_context_names()),
                recursive=recursive,
            ),
            memory_layout="hanging",
            terminal_width=shutil.get_terminal_size(fallback=(100, 24)).columns,
        )
    )


def cmd(
    context_name: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Existing Context to list by canonical name or explicit "
                "relative locator (defaults to current)"
            )
        ),
    ] = None,
    recursive: Annotated[
        bool,
        typer.Option(
            "-R",
            "--recursive",
            "--expand",
            help=(
                "Expand every descendant namespace and embedded Context."
            ),
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
            if payload.selection.get("kind") == "GRANTED_LIST_RECEIPT":
                snapshot, copied_with_ids = _restore_granted_list_receipt(
                    payload.selection
                )
                replay_text = _render_snapshot(
                    snapshot,
                    with_ids=copied_with_ids,
                    memory_layout="inline",
                )
                if not payload.matches_text(replay_text):
                    raise ClipboardError(
                        "The granted list receipt and system clipboard disagree."
                    )
                staged_text = replay_text
            else:
                snapshot = payload.selection
                annotated_text = _render_snapshot(
                    snapshot,
                    with_ids=True,
                    memory_layout="inline",
                )
                clean_text = _render_snapshot(
                    snapshot,
                    with_ids=False,
                    memory_layout="inline",
                )
                if payload.plain_text not in {annotated_text, clean_text}:
                    raise ClipboardError(
                        "The structured clipboard text and object snapshot disagree."
                    )
                assert payload.plain_text is not None
                staged_text = payload.plain_text
        except (ClipboardError, ValueError) as error:
            typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)
        _emit_snapshot_text(staged_text)
        count = _snapshot_occurrence_count(snapshot)
        source_context = _require_record(snapshot.get("context"))
        source_name = _require_string(source_context, "name")
        typer.secho(
            f"Pasted {count} staged item{'s' if count != 1 else ''} "
            f"from '{source_name}' "
            "(no Context changes).",
            dim=True,
            err=True,
        )
        return

    active_store = MemoryStore()
    current_context_name = active_store.current_context_name()
    try:
        access = resolve_context_access(
            active_store,
            context_name,
            current_name=current_context_name,
            required_permission="READ",
        )
        store = freeze_readable_context_catalog(active_store, access)
        context_names = tuple(store.list_context_names())
        if (
            copy_result
            and recursive
            and not access.is_granted
            and store.granted_names_below(access.display_name)
        ):
            raise RuntimeError(
                "Copying a mixed local and granted recursive list is not yet "
                "supported. Copy the granted Context explicitly so its exact "
                "grant receipt can be retained."
            )
        # Load resolves direct MemoryRefs even when presentation is collapsed;
        # ``recursive`` below controls what the snapshot exposes.
        ctx = store.load(access.display_name)
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
    )
    if (
        not copy_result
        and _interactive_terminal()
    ):
        browser_snapshot = (
            snapshot
            if recursive
            else _snapshot_context(
                ctx,
                store=store,
                context_names=context_names,
                recursive=True,
            )
        )
        (
            browser_tree,
            browser_names,
            browser_virtual_names,
            browser_labels,
            browser_annotations,
            browser_memories,
        ) = _snapshot_browser_tree(browser_snapshot)
        root_id = browser_tree.roots[0]

        choose_context(
            browser_names,
            current=root_id,
            title=f"List · {access.display_name}",
            virtual_names=browser_virtual_names,
            virtual_annotations=browser_annotations,
            memory_loader=lambda occurrence: browser_memories.get(
                occurrence, ()
            ),
            browse_only=True,
            initially_expand_selected=not recursive,
            initially_expand_all=recursive,
            initially_show_memories=True,
            tree_override=browser_tree,
            display_names=browser_labels,
        )
        return
    annotated_text = _render_snapshot(
        snapshot,
        with_ids=True,
        memory_layout="hanging",
        terminal_width=shutil.get_terminal_size(fallback=(100, 24)).columns,
    )
    _emit_snapshot_text(
        annotated_text,
        header_notes=(
            _granted_access_notes(access)
            if access.is_granted
            else _local_analysis_notes(access.context_name, active_store)
        ),
    )
    if not access.is_granted:
        _emit_grant_notes(access.context_name)

    if copy_result:
        clipboard_text = _render_snapshot(
            snapshot,
            with_ids=with_ids,
            memory_layout="inline",
        )
        staged_selection = snapshot
        redact_plain_text = False
        if access.is_granted:
            staged_selection = _granted_list_receipt(
                snapshot,
                binding=freeze_granted_context_binding(access),
                with_ids=with_ids,
            )
            redact_plain_text = True
        payload = ClipboardPayload.create(
            producer="list",
            plain_text=clipboard_text,
            selection=staged_selection,
            redact_plain_text=redact_plain_text,
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
