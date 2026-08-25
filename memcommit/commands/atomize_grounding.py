"""Compatibility facade for conversational Atomize Grounding."""

from __future__ import annotations

from typing import Callable

from memcommit.atomize import AtomizeAnalysisSession
from memcommit.atomize_grounding import AtomizeGroundingSession
from memcommit.operations.atomize.grounding_application import (
    AtomizeGroundingApplicationError,
    GroundingAcceptRequest,
    GroundingApplyResult,
    GroundingKeepRequest,
    GroundingReplyRequest,
    GroundingStartRequest,
    run_atomize_grounding_accept,
    run_atomize_grounding_keep,
    run_atomize_grounding_reply,
    run_atomize_grounding_start,
)
from memcommit.atomize_grounding_provider import AtomizeGroundingProvider
from memcommit.operations.atomize.grounding_runtime import (
    MemoryStoreAtomizeGroundingPort,
    assert_current_grounding_bindings,
)
from memcommit.atomize_workbench import AtomizeWorkbenchSession
from memcommit.commands.command_progress import progressing_provider_factory
from memcommit.context import Context
from memcommit.interfaces.cli.atomize_grounding import render_grounding_session
from memcommit.store import MemoryStore


AtomizeGroundingCommandError = AtomizeGroundingApplicationError


def _progress_provider_factory(
    stage: str,
    provider_factory: Callable[[], AtomizeGroundingProvider],
):
    return progressing_provider_factory("ATOMIZE", stage, provider_factory)


def _port(store: MemoryStore) -> MemoryStoreAtomizeGroundingPort:
    return MemoryStoreAtomizeGroundingPort(
        store=store,
        provider_progress=_progress_provider_factory,
    )


def start_grounding(
    *,
    store: MemoryStore,
    ctx: Context,
    analysis: AtomizeAnalysisSession,
    workbench: AtomizeWorkbenchSession,
    selector: str,
    comment: str,
    provider_factory: Callable[[], AtomizeGroundingProvider],
) -> AtomizeGroundingSession:
    return run_atomize_grounding_start(
        GroundingStartRequest(
            context=ctx,
            analysis=analysis,
            workbench=workbench,
            selector=selector,
            comment=comment,
        ),
        port=_port(store),
        provider_factory=provider_factory,
    )


def reply_to_grounding(
    *,
    store: MemoryStore,
    ctx: Context,
    analysis: AtomizeAnalysisSession,
    workbench: AtomizeWorkbenchSession,
    reply: str,
    provider_factory: Callable[[], AtomizeGroundingProvider],
    revision: str = "EXTEND",
) -> AtomizeGroundingSession:
    return run_atomize_grounding_reply(
        GroundingReplyRequest(
            context=ctx,
            analysis=analysis,
            workbench=workbench,
            reply=reply,
            revision=revision,
        ),
        port=_port(store),
        provider_factory=provider_factory,
    )


def keep_grounding_review_only(
    *,
    store: MemoryStore,
    context_uid: str,
) -> AtomizeGroundingSession:
    return run_atomize_grounding_keep(
        GroundingKeepRequest(context_uid=context_uid),
        port=_port(store),
    )


def accept_grounding(
    *,
    store: MemoryStore,
    ctx: Context,
    analysis: AtomizeAnalysisSession,
    workbench: AtomizeWorkbenchSession,
) -> GroundingApplyResult:
    return run_atomize_grounding_accept(
        GroundingAcceptRequest(
            context=ctx,
            analysis=analysis,
            workbench=workbench,
        ),
        port=_port(store),
    )


__all__ = [
    "AtomizeGroundingCommandError",
    "GroundingApplyResult",
    "accept_grounding",
    "assert_current_grounding_bindings",
    "keep_grounding_review_only",
    "render_grounding_session",
    "reply_to_grounding",
    "start_grounding",
]
