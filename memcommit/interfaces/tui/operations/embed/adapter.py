"""Compose the Embed TUI with one Store-backed application port."""

from __future__ import annotations

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.context_targeting.tui.picker import context_memory_rows
from memcommit.embed_application import FrozenEmbedPlan, FrozenMemoryEmbedPlan
from memcommit.authority.access import resolve_context_access
from memcommit.context_targeting.catalog import freeze_granted_context_navigation
from memcommit.embed_runtime import MemoryStoreEmbedPort
from memcommit.interfaces.tui.operations.embed.model import EmbedTuiSetup
from memcommit.interfaces.tui.operations.embed.screen import run_embed_tui
from memcommit.source_projection.presentation import (
    SourceDisplayToken,
    SourceTokenRole,
    combine_source_display_tokens,
)


def build_embed_tui_setup(port: MemoryStoreEmbedPort) -> EmbedTuiSetup:
    """Freeze visible Grant rows, EMBED eligibility, and owned targets."""

    local_names = port.local_context_names
    navigation = freeze_granted_context_navigation(port.store)
    child_names = tuple(sorted(set(local_names) | set(navigation.names)))
    selectable = set(local_names)
    annotations = dict(navigation.annotations)
    for name in navigation.names:
        try:
            access = resolve_context_access(
                port.store,
                name,
                current_name=port.current_context_name,
                required_permission="EMBED",
            )
        except (FileNotFoundError, RuntimeError, ValueError):
            continue
        selectable.add(name)
        if access.is_granted:
            # Navigation stays compact, while this operation-owned selector
            # names the extra capability that makes the row selectable here.
            annotations[name] = combine_source_display_tokens(
                annotations[name],
                SourceDisplayToken("EMBED", SourceTokenRole.CAPABILITY),
            )
    return EmbedTuiSetup(
        child_names=child_names,
        child_selectable_names=frozenset(selectable),
        into_names=local_names,
        memory_source_names=local_names,
        current_context=(
            port.current_context_name
            if port.current_context_name in local_names
            else None
        ),
        child_annotations=tuple((name, annotations[name]) for name in navigation.names),
    )


def choose_embed_setup(
    port: MemoryStoreEmbedPort,
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> FrozenEmbedPlan | FrozenMemoryEmbedPlan | None:
    """Review one relationship without letting the TUI own storage."""

    setup = build_embed_tui_setup(port)
    return run_embed_tui(
        setup,
        inspect_context=port.inspect_local_context,
        freeze_exact_gap=port.freeze_exact_gap,
        memory_loader=lambda name: context_memory_rows(
            port.inspect_local_context(name)
        ),
        freeze_memory_exact_gap=port.freeze_memory_exact_gap,
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
