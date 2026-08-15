"""Typer adapter for adding one or more exact Memories."""

from __future__ import annotations

import json
from typing import Annotated, Optional

import typer

from memcommit.add_application import (
    AddError,
    AddRequest,
    AddSource,
    prepare_add_target,
    run_add,
)
from memcommit.add_runtime import MemoryStoreAddTargetPort
from memcommit.commands.batch_input import parse_add_lines, read_text_input
from memcommit.authority.access import (
    context_access_display_facts,
    resolve_context_access,
)
from memcommit.commands.paste_input import PasteCancelled, capture_paste
from memcommit.context_targeting.catalog import freeze_granted_context_navigation
from memcommit.interfaces.cli.add import render_add_plain
from memcommit.interfaces.console.terminal import is_interactive_terminal
from memcommit.interfaces.tui.operations.add import AddTuiSetup, run_add_tui
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.store import ConcurrentContextUpdateError, MemoryStore


def _prepare_add_tui_setup(
    store: MemoryStore,
    *,
    current_name: str | None,
    requested_context: str | None,
) -> AddTuiSetup:
    """Freeze visible Context rows and their CREATE availability."""

    local_names = tuple(store.list_context_names())
    granted = freeze_granted_context_navigation(store)
    names = set(local_names) | set(granted.names)
    selectable = set(local_names)
    annotations = {
        name: value
        for name, value in granted.annotations.items()
        if name not in local_names
    }

    for name in granted.names:
        if name in local_names:
            continue
        try:
            access = resolve_context_access(
                store,
                name,
                current_name=current_name,
                required_permission="CREATE",
            )
        except (FileNotFoundError, OSError, ProfileError, RuntimeError, ValueError):
            continue
        selectable.add(access.display_name)

    selected: str | None = None
    if requested_context is not None:
        access = resolve_context_access(
            store,
            requested_context,
            current_name=current_name,
            required_permission="CREATE",
        )
        selected = access.display_name
        names.add(selected)
        selectable.add(selected)
        if access.is_granted:
            annotations[selected] = context_access_display_facts(access)
    elif current_name in selectable:
        selected = current_name
    elif selectable:
        selected = sorted(selectable, key=str.casefold)[0]

    if selected is None:
        raise ValueError(
            "Interactive Add requires a local or CREATE-granted target Context."
        )
    return AddTuiSetup(
        names=tuple(sorted(names, key=str.casefold)),
        selectable_names=frozenset(selectable),
        selected_context=selected,
        current_context=current_name,
        annotations=tuple(
            (name, annotations[name])
            for name in sorted(annotations, key=str.casefold)
            if name in names
        ),
    )


def cmd(
    info: Annotated[
        Optional[str],
        typer.Argument(help="One Memory to store (quote multi-word text)"),
    ] = None,
    input_source: Annotated[
        Optional[str],
        typer.Option(
            "--input",
            "-i",
            help="Add each non-empty line from a UTF-8 file; use '-' for stdin",
        ),
    ] = None,
    paste: Annotated[
        bool,
        typer.Option(
            "--paste",
            help=(
                "Capture pasted text without echoing it, then add each non-empty line"
            ),
        ),
    ] = False,
    memories: Annotated[
        Optional[list[str]],
        typer.Option(
            "--memory",
            "-m",
            help="Add one exact Memory; repeat the option to add a batch",
        ),
    ] = None,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Local Context or CREATE-granted view to receive the Memories",
        ),
    ] = None,
) -> None:
    explicit_memories = tuple(memories or ())
    source_count = sum(
        (
            info is not None,
            input_source is not None,
            paste,
            bool(explicit_memories),
        )
    )
    if source_count > 1 or (source_count == 0 and not is_interactive_terminal()):
        typer.secho(
            "Error: provide exactly one of INFO, --input, or --paste, or use "
            "repeatable --memory.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    # Capture global navigation once before file, stdin, paste, or confirmation
    # can yield control. Relative target meaning stays stable for this command.
    store = MemoryStore()
    current_name = store.current_context_name()
    port = MemoryStoreAddTargetPort(store, current_name=current_name)

    try:
        if source_count == 0:
            setup = _prepare_add_tui_setup(
                store,
                current_name=current_name,
                requested_context=context_name,
            )
            tui_result = run_add_tui(
                setup=setup,
                execute=lambda request: run_add(request, target_port=port),
            )
            if tui_result is None:
                typer.echo("Add cancelled — no changes made.")
                return
            render_add_plain(tui_result, mode="TUI_DRAFTS")
            return
        if info is not None:
            request = AddRequest(
                context_locator=context_name,
                contents=(info,),
                source=AddSource(
                    mode="SINGLE",
                    kind="argument",
                    raw_text=info,
                    parser="single-memory-v1",
                ),
            )
        elif explicit_memories:
            request = AddRequest(
                context_locator=context_name,
                contents=explicit_memories,
                source=AddSource(
                    mode="EXPLICIT_BATCH",
                    kind="arguments",
                    raw_text=json.dumps(
                        explicit_memories,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                    parser="explicit-memory-arguments-v1",
                ),
            )
        elif paste:
            frozen_target = prepare_add_target(
                context_name,
                target_port=port,
            )
            try:
                raw_text = capture_paste()
            except PasteCancelled:
                typer.echo("Aborted — no changes made.")
                return
            contents = tuple(parse_add_lines(raw_text))
            count = len(contents)
            noun = "line" if count == 1 else "lines"
            typer.secho(f"[{count} {noun} pasted]", dim=True)
            if not typer.confirm(
                f"Add {count} {'Memory' if count == 1 else 'Memories'} "
                f"to '{frozen_target.context_name}'?",
                default=False,
            ):
                typer.echo("Aborted — no changes made.")
                return
            request = AddRequest(
                context_locator=context_name,
                contents=contents,
                source=AddSource(
                    mode="PASTE",
                    kind="interactive-paste",
                    raw_text=raw_text,
                    parser="stripped-nonempty-physical-lines-v1",
                ),
            )
        else:
            assert input_source is not None
            raw_text = read_text_input(input_source)
            request = AddRequest(
                context_locator=context_name,
                contents=tuple(parse_add_lines(raw_text)),
                source=AddSource(
                    mode="LINES",
                    kind="stdin" if input_source == "-" else "utf-8-file",
                    raw_text=raw_text,
                    parser="stripped-nonempty-physical-lines-v1",
                    input_name=input_source,
                ),
            )

        result = run_add(
            request,
            target_port=port,
            frozen_target=(frozen_target if paste else None),
        )
    except (
        AddError,
        ConcurrentContextUpdateError,
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    render_add_plain(result, mode=request.source.mode)
