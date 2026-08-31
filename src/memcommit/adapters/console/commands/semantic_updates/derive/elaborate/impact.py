"""Plain process-local Impact for append-only Elaborate."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.adapters.console.commands.operation_lifecycle.impact.sessions import (
    process_local_impact_error,
)
from memcommit.adapters.console.terminal.components.progress import CommandProgress
from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.application.operations.semantic_updates.derive.elaborate.application import (
    ElaborateError,
    ElaborateRequest,
)
from memcommit.application.operations.semantic_updates.derive.elaborate.model import ElaborateRevision
from memcommit.application.operations.semantic_updates.derive.elaborate.runtime import (
    prepare_elaborate_with_store,
)
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.persistence.store import MemoryStore
from memcommit.providers.subscription import (
    QueryProviderError,
    connect_semantic_provider,
)


def render_elaborate_impact(revision: ElaborateRevision) -> str:
    """Render the exact append-only proposal without an interactive workbench."""

    appended = revision.continuation or "(none; the original is retained)"
    return "\n".join(
        (
            "ELABORATE IMPACT · REVIEW ONLY",
            f"CONTEXT · {safe_terminal_text(revision.context_name)}",
            f"MEMORY · [{revision.memory_uid}]",
            f"STATUS · {'APPEND' if revision.changed else 'KEEP'}",
            "",
            "ORIGINAL",
            safe_terminal_text(revision.original_content),
            "",
            "APPENDED ELABORATION",
            safe_terminal_text(appended),
            "",
            "RESULT",
            safe_terminal_text(revision.content),
            "",
            "WHY · " + safe_terminal_text(revision.reason),
            "SUPPORT · "
            + ", ".join(uid[:8] for uid in revision.source_memory_uids),
            "EFFECTS · NONE · Impact never applies or checkpoints this revision.",
        )
    )


def elaborate_cmd(
    memory_selector: Annotated[
        str,
        typer.Argument(
            help="UID/prefix or CONTEXT:UID of one directly owned Memory",
        ),
    ],
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            metavar="CONTEXT",
            help="Existing READ+UPDATE Context that owns the Memory",
        ),
    ] = None,
) -> None:
    """Preview one continuation without changing or checkpointing its Memory."""

    try:
        store = MemoryStore(create=False)
        with CommandProgress(
            "IMPACT · ELABORATE",
            "preparing exact Memory context",
            total=2,
        ) as progress:
            _port, prepared = prepare_elaborate_with_store(
                ElaborateRequest(
                    memory_selector=memory_selector,
                    context_locator=context_name,
                ),
                store=store,
                provider_factory=lambda: (
                    progress.update("writing supported continuation", step=2)
                    or connect_semantic_provider()
                ),
            )
        typer.echo(render_elaborate_impact(prepared.revision))
    except (
        ElaborateError,
        FileNotFoundError,
        KeyError,
        OSError,
        ProfileConfigError,
        ProfileError,
        QueryProviderError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        process_local_impact_error("elaborate", error)


__all__ = ["elaborate_cmd", "render_elaborate_impact"]
