"""Compose the Embed workbench with one Store-backed application port."""

from __future__ import annotations

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.core.context_targeting.tui.picker import context_memory_rows
from memcommit.application.operations.embed.application import (
    FrozenEmbedPlan,
    FrozenMemoryEmbedPlan,
)
from memcommit.application.capabilities.authority.access import resolve_context_access
from memcommit.core.context_targeting.catalog import freeze_granted_context_navigation
from memcommit.application.operations.embed.runtime import MemoryStoreEmbedPort
from memcommit.adapters.console.commands.embed.workbench.model import EmbedTuiSetup
from memcommit.adapters.console.commands.embed.workbench.screen import run_embed_tui
from memcommit.source_projection.presentation import (
    SourceDisplayToken,
    SourceTokenRole,
    combine_source_display_tokens,
)


def build_embed_tui_setup(port: MemoryStoreEmbedPort) -> EmbedTuiSetup:
    """Freeze visible Grant rows, EMBED eligibility, and owned targets."""

    local_names = port.local_context_names
    navigation = (
        freeze_granted_context_navigation(port.store)
        if port.allows_granted_sources
        else None
    )
    granted_names = navigation.names if navigation is not None else ()
    navigation_annotations = navigation.annotations if navigation is not None else {}
    child_names = tuple(sorted(set(local_names) | set(granted_names)))
    child_selectable = set(local_names)
    child_annotations = dict(navigation_annotations)
    memory_source_selectable = set(local_names)
    memory_source_granted: set[str] = set()
    memory_source_annotations = dict(navigation_annotations)
    for name in granted_names:
        try:
            access = resolve_context_access(
                port.store,
                name,
                current_name=port.current_context_name,
                required_permission="EMBED",
            )
        except (FileNotFoundError, RuntimeError, ValueError):
            continue
        child_selectable.add(name)
        if access.is_granted:
            # Navigation stays compact, while this operation-owned selector
            # names the extra capability that makes the row selectable here.
            child_annotations[name] = combine_source_display_tokens(
                child_annotations[name],
                SourceDisplayToken("EMBED", SourceTokenRole.CAPABILITY),
            )
            if access.view is not None and "READ" in access.view.grant.permissions:
                # A direct Memory preview opens authority bytes, so the same
                # exact Grant must authorize both visibility and live linking.
                memory_source_selectable.add(name)
                memory_source_granted.add(name)
                memory_source_annotations[name] = combine_source_display_tokens(
                    memory_source_annotations[name],
                    SourceDisplayToken("EMBED", SourceTokenRole.CAPABILITY),
                )
    return EmbedTuiSetup(
        child_names=child_names,
        child_selectable_names=frozenset(child_selectable),
        into_names=local_names,
        memory_source_names=child_names,
        memory_source_selectable_names=frozenset(memory_source_selectable),
        memory_source_granted_names=frozenset(memory_source_granted),
        current_context=(
            port.current_context_name
            if port.current_context_name in local_names
            else None
        ),
        child_annotations=tuple(
            (name, child_annotations[name]) for name in granted_names
        ),
        memory_source_annotations=tuple(
            (name, memory_source_annotations[name]) for name in granted_names
        ),
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
            port.inspect_memory_source(name)
        ),
        freeze_memory_exact_gap=port.freeze_memory_exact_gap,
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
