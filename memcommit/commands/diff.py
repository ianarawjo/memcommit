"""Render the active staged or locally applied update without a model."""
from __future__ import annotations

import difflib
import json
import re
from typing import Annotated

import typer

from memcommit.store import MemoryStore
from memcommit.update import (
    AddOperation,
    EditOperation,
    UpdateSession,
    applied_session_matches,
    count_operations,
    session_matches,
)


def _short_uid_map(session: UpdateSession) -> dict[str, str]:
    """Return collision-safe UID prefixes, using at least eight characters."""
    uids = {
        operation.memory_uid
        for operation in session.operations
    }
    uids.update(
        source.memory_uid
        for operation in session.operations
        for source in operation.source_refs
    )
    prefixes: dict[str, str] = {}
    for uid in uids:
        if len(uid) <= 8:
            prefixes[uid] = uid
            continue
        width = 8
        while width < len(uid) and any(
            other != uid and other.startswith(uid[:width])
            for other in uids
        ):
            width += 1
        prefixes[uid] = uid[:width]
    return prefixes


def _shown_uid(
    uid: str,
    prefixes: dict[str, str],
    *,
    verbose: bool,
) -> str:
    return uid if verbose else prefixes.get(uid, uid[:8])


def _summary(session: UpdateSession) -> str:
    edits, additions = count_operations(session)
    total = edits + additions
    return (
        f"{total} change{'s' if total != 1 else ''} · "
        f"{edits} edited · {additions} added"
    )


def _render_header(session: UpdateSession, *, verbose: bool) -> None:
    heading = (
        "Applied local update"
        if session.status == "applied"
        else "Update preview"
    )
    typer.secho(heading, fg=typer.colors.CYAN, bold=True)
    typer.secho(
        f"{session.source_name} → {session.target_name}",
        bold=True,
    )
    typer.echo(_summary(session))
    if verbose:
        typer.secho(f"Update  {session.uid}", dim=True)
        typer.secho(
            f"Source  {session.source_uid}  {session.source_digest}",
            dim=True,
        )
        typer.secho(
            f"Base    {session.target_uid}  {session.target_digest}",
            dim=True,
        )
        if session.application is not None:
            typer.secho(
                f"Result  {session.target_uid}  "
                f"{session.application.target_digest}",
                dim=True,
            )


def _word_tokens(text: str) -> list[str]:
    return re.findall(r"\S+|\s+", text)


def _styled_word_diff(old_line: str, new_line: str) -> tuple[str, str]:
    """Color both lines and bold only changed word spans."""
    old_tokens = _word_tokens(old_line)
    new_tokens = _word_tokens(new_line)
    old_parts = [typer.style("  - ", fg=typer.colors.RED)]
    new_parts = [typer.style("  + ", fg=typer.colors.GREEN)]
    matcher = difflib.SequenceMatcher(
        None,
        old_tokens,
        new_tokens,
        autojunk=False,
    )
    for tag, old_start, old_end, new_start, new_end in matcher.get_opcodes():
        old_text = "".join(old_tokens[old_start:old_end])
        new_text = "".join(new_tokens[new_start:new_end])
        if old_text:
            old_parts.append(
                typer.style(
                    old_text,
                    fg=typer.colors.RED,
                    bold=tag != "equal",
                )
            )
        if new_text:
            new_parts.append(
                typer.style(
                    new_text,
                    fg=typer.colors.GREEN,
                    bold=tag != "equal",
                )
            )
    return "".join(old_parts), "".join(new_parts)


def _render_semantic_edit(operation: EditOperation) -> None:
    old_lines = operation.old_content.splitlines() or [""]
    new_lines = operation.new_content.splitlines() or [""]
    matcher = difflib.SequenceMatcher(
        None,
        old_lines,
        new_lines,
        autojunk=False,
    )
    for tag, old_start, old_end, new_start, new_end in matcher.get_opcodes():
        if tag == "equal":
            for line in old_lines[old_start:old_end]:
                typer.secho(f"    {line}", dim=True)
        elif tag == "replace":
            old_chunk = old_lines[old_start:old_end]
            new_chunk = new_lines[new_start:new_end]
            paired = min(len(old_chunk), len(new_chunk))
            for index in range(paired):
                old_output, new_output = _styled_word_diff(
                    old_chunk[index],
                    new_chunk[index],
                )
                typer.echo(old_output)
                typer.echo(new_output)
            for line in old_chunk[paired:]:
                typer.secho(f"  - {line}", fg=typer.colors.RED)
            for line in new_chunk[paired:]:
                typer.secho(f"  + {line}", fg=typer.colors.GREEN)
        elif tag == "delete":
            for line in old_lines[old_start:old_end]:
                typer.secho(f"  - {line}", fg=typer.colors.RED)
        elif tag == "insert":
            for line in new_lines[new_start:new_end]:
                typer.secho(f"  + {line}", fg=typer.colors.GREEN)

    old_terminal_newline = operation.old_content.endswith(("\n", "\r"))
    new_terminal_newline = operation.new_content.endswith(("\n", "\r"))
    if old_terminal_newline != new_terminal_newline:
        change = "added" if new_terminal_newline else "removed"
        typer.secho(f"    terminal newline {change}", dim=True)


def _render_metadata(
    operation: EditOperation | AddOperation,
    prefixes: dict[str, str],
    *,
    verbose: bool,
) -> None:
    sources = ", ".join(
        f"{source.context_name} "
        f"[{_shown_uid(source.memory_uid, prefixes, verbose=verbose)}]"
        for source in operation.source_refs
    )
    typer.secho(f"  Source  {sources}", fg=typer.colors.CYAN)
    typer.secho(f"  Reason  {operation.reason}", dim=True)


def _render_semantic_operation(
    operation: EditOperation | AddOperation,
    prefixes: dict[str, str],
    *,
    verbose: bool,
) -> None:
    shown_uid = _shown_uid(
        operation.memory_uid,
        prefixes,
        verbose=verbose,
    )
    if isinstance(operation, EditOperation):
        typer.secho(
            f"EDIT  {operation.owner_context_name}  [{shown_uid}]",
            fg=typer.colors.YELLOW,
            bold=True,
        )
        _render_semantic_edit(operation)
    else:
        typer.secho(
            f"ADD   {operation.owner_context_name}  [new:{shown_uid}]",
            fg=typer.colors.GREEN,
            bold=True,
        )
        for line in operation.new_content.splitlines() or [""]:
            typer.secho(f"  + {line}", fg=typer.colors.GREEN)
    typer.echo()
    _render_metadata(operation, prefixes, verbose=verbose)


def _memory_label(context_name: str, memory_uid: str) -> str:
    return f"{context_name}#{memory_uid}"


def _encoded_lines(content: str) -> list[str]:
    """Encode line text and its terminator so raw diff preserves newlines."""
    encoded: list[str] = []
    for line in content.splitlines(keepends=True):
        if line.endswith("\r\n"):
            text = line[:-2]
            has_newline = True
        elif line.endswith("\n") or line.endswith("\r"):
            text = line[:-1]
            has_newline = True
        else:
            text = line
            has_newline = False
        encoded.append(
            json.dumps(
                [text, has_newline],
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
    return encoded


def _unified_lines(
    operation: EditOperation | AddOperation,
) -> list[str]:
    label = _memory_label(
        operation.owner_context_name,
        operation.memory_uid,
    )
    if isinstance(operation, EditOperation):
        old_lines = _encoded_lines(operation.old_content)
        from_file = f"a/{label}"
    else:
        old_lines = []
        from_file = "/dev/null"
    return list(
        difflib.unified_diff(
            old_lines,
            _encoded_lines(operation.new_content),
            fromfile=from_file,
            tofile=f"b/{label}",
            lineterm="",
        )
    )


def _render_raw_line(line: str) -> None:
    if line.startswith("--- ") or line.startswith("+++ "):
        typer.secho(line, bold=True)
    elif line.startswith("@@"):
        typer.secho(line, fg=typer.colors.CYAN)
    elif line.startswith("+"):
        typer.secho(line, fg=typer.colors.GREEN)
    elif line.startswith("-"):
        typer.secho(line, fg=typer.colors.RED)
    else:
        typer.echo(line)


def _render_encoded_raw_line(line: str) -> None:
    if not line or line[0] not in {" ", "+", "-"}:
        _render_raw_line(line)
        return
    try:
        value = json.loads(line[1:])
    except json.JSONDecodeError:
        _render_raw_line(line)
        return
    if (
        not isinstance(value, list)
        or len(value) != 2
        or not isinstance(value[0], str)
        or not isinstance(value[1], bool)
    ):
        _render_raw_line(line)
        return
    rendered = f"{line[0]}{value[0]}"
    if line[0] == "+":
        typer.secho(rendered, fg=typer.colors.GREEN)
    elif line[0] == "-":
        typer.secho(rendered, fg=typer.colors.RED)
    else:
        typer.echo(rendered)
    if not value[1]:
        typer.echo("\\ No newline at end of file")


def _render_raw_operation(operation: EditOperation | AddOperation) -> None:
    label = _memory_label(
        operation.owner_context_name,
        operation.memory_uid,
    )
    typer.secho(f"diff --mem {label}", bold=True)
    if isinstance(operation, AddOperation):
        typer.secho("new memory", dim=True)
    for line in _unified_lines(operation):
        if (
            line.startswith("--- ")
            or line.startswith("+++ ")
            or line.startswith("@@")
        ):
            _render_raw_line(line)
        else:
            _render_encoded_raw_line(line)
    sources = ", ".join(
        f"{source.context_name}#{source.memory_uid}"
        for source in operation.source_refs
    )
    typer.secho(f"Sources: {sources}", dim=True)
    typer.secho(f"Reason: {operation.reason}", dim=True)


def render_diff(
    session: UpdateSession,
    *,
    raw: bool = False,
    stat: bool = False,
    verbose: bool = False,
) -> None:
    """Render one validated staged or locally applied session."""
    _render_header(session, verbose=verbose)
    if stat:
        return
    if not session.operations:
        message = (
            "No local changes were needed."
            if session.status == "applied"
            else "No staged changes."
        )
        typer.echo(f"\n{message}")
        return

    prefixes = _short_uid_map(session)
    for index, operation in enumerate(session.operations):
        typer.echo()
        if raw:
            _render_raw_operation(operation)
        else:
            _render_semantic_operation(
                operation,
                prefixes,
                verbose=verbose,
            )
        if index != len(session.operations) - 1:
            typer.echo()
            typer.secho("─" * 64, dim=True)


def cmd(
    raw: Annotated[
        bool,
        typer.Option(
            "--raw",
            help="Show the exact Git-style unified diff",
        ),
    ] = False,
    stat: Annotated[
        bool,
        typer.Option(
            "--stat",
            help="Show only the change summary",
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Show full UIDs and source/target fingerprints",
        ),
    ] = False,
) -> None:
    if raw and stat:
        typer.secho(
            "Diff error: '--raw' and '--stat' cannot be used together.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)

    store = MemoryStore(create=False)
    try:
        session = store.load_staged_update()
    except (OSError, ValueError) as error:
        typer.secho(f"Diff error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    if session is None:
        typer.secho(
            "Diff error: no local update. Run 'mem update --to <context>' "
            "first.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    if session.status not in {"staged", "applied"}:
        typer.secho(
            "Diff error: the saved record is not an update result.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    fresh = False
    try:
        source = store.load(session.source_name)
        target = store.load(session.target_name)
        if session.status == "applied":
            fresh = applied_session_matches(session, source, target)
        else:
            fresh = session_matches(session, source, target)
    except (OSError, ValueError):
        fresh = False

    if not fresh:
        timing = (
            "after this update was applied"
            if session.status == "applied"
            else "after this update was staged"
        )
        typer.secho(
            f"STALE — source or target changed {timing}",
            fg=typer.colors.YELLOW,
            bold=True,
            err=True,
        )
    render_diff(
        session,
        raw=raw,
        stat=stat,
        verbose=verbose,
    )
    if not fresh:
        typer.secho(
            "Review the local fork and re-run impact/update before "
            "contributing.",
            fg=typer.colors.YELLOW,
            err=True,
        )
        raise typer.Exit(1)
