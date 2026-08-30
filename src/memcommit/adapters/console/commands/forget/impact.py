"""Forget-owned process-local Impact adapter."""

from __future__ import annotations

import sys
from typing import Annotated, Optional

import typer

from memcommit.adapters.console.commands.forget.setup import choose_forget_setup
from memcommit.adapters.console.commands.forget.workbench.presentation import (
    ForgetResolutionWorkbenchAdapter,
    forget_memory_changes,
)
from memcommit.adapters.console.commands.impact.sessions import (
    ImpactSessionPresentation,
    process_local_impact_error,
    show_process_local_impact,
)
from memcommit.adapters.console.coordination.context_operand import (
    ContextOperandSnapshot,
)
from memcommit.adapters.console.terminal.components.impact import ImpactController
from memcommit.adapters.console.terminal.components.progress import CommandProgress
from memcommit.application.capabilities.authority.context_access import (
    context_access_display_facts,
    resolve_context_access,
)
from memcommit.application.operations.forget.application import (
    ForgetAnalysisRequest,
    ForgetAnalysisResult,
    run_forget_analysis,
)
from memcommit.application.operations.forget.runtime import (
    MemoryStoreForgetSourcePort,
    connect_forget_provider,
)
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.core.context_targeting.readable_catalog import (
    freeze_profile_readable_context_catalog,
)
from memcommit.persistence.store import MemoryStore
from memcommit.providers.subscription import QueryProviderError


def forget_impact_presentation(
    result: ForgetAnalysisResult,
) -> ImpactSessionPresentation:
    """Project Forget's complete process-local review as in-place changes."""

    view = ForgetResolutionWorkbenchAdapter(result.snapshot.review).view()
    return ImpactSessionPresentation(
        view=view,
        controller=ImpactController.from_memory_changes(
            operation=view.operation,
            artifact_uid=view.artifact_uid,
            revision=view.revision,
            title="IMPACT · FORGET · SAME SOURCE",
            summary=(
                "These are the complete reviewed in-place Source transitions. "
                "This Impact view cannot apply them."
            ),
            changes=forget_memory_changes(result.snapshot.review),
        ),
        handoff_available=False,
    )


def forget_cmd(
    instruction: Annotated[
        Optional[str],
        typer.Argument(
            show_default=False,
            help=(
                "Description of Memories to forget; omit in a terminal to "
                "choose one direct Source and enter the instruction"
            ),
        ),
    ] = None,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Exact readable Source Context (defaults to current)",
        ),
    ] = None,
) -> None:
    """Prepare Forget decisions and inspect them without changing the Source."""

    if instruction is None and not (sys.stdin.isatty() and sys.stdout.isatty()):
        process_local_impact_error(
            "forget",
            ValueError("INSTRUCTION is required outside a terminal."),
        )
    try:
        store = MemoryStore(create=False)
        snapshot = ContextOperandSnapshot.capture(store)
        source_locator = context_name
        if instruction is None:
            access = resolve_context_access(
                store,
                context_name,
                current_name=snapshot.current_name,
                required_permission="READ",
            )
            catalog = freeze_profile_readable_context_catalog(
                store,
                access,
                include_query_routes=False,
            )
            names = tuple(catalog.list_context_names())
            annotations = {
                name: context_access_display_facts(catalog.access_for(name))
                for name in names
                if catalog.access_for(name).is_granted
            }
            receipt = choose_forget_setup(
                names,
                current=access.display_name,
                annotations=annotations,
            )
            if receipt is None:
                typer.echo("Forget Impact cancelled.")
                return
            source_locator = receipt.context_name
            instruction = receipt.instruction
        assert instruction is not None
        request = ForgetAnalysisRequest(source_locator, instruction)
        source_port = MemoryStoreForgetSourcePort(
            store,
            current_name=snapshot.current_name,
        )
        with CommandProgress(
            "IMPACT · FORGET",
            "preparing source",
            total=2,
        ) as progress:
            result = run_forget_analysis(
                request,
                source_port=source_port,
                provider_factory=lambda: (
                    progress.update("analyzing decisions", step=2)
                    or connect_forget_provider()
                ),
            )
        show_process_local_impact(
            forget_impact_presentation(result),
            operation="forget",
        )
    except (
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        QueryProviderError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        process_local_impact_error("forget", error)


__all__ = ["forget_cmd", "forget_impact_presentation"]
