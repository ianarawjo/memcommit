"""Public Atomize Grounding assembly without command or terminal dependencies."""

from __future__ import annotations

from memcommit.api._runtime import ClientRuntime
from memcommit.api._support.errors import raise_public
from memcommit.api.atomize_grounding import (
    AtomizeGroundingApplyResult as PublicAtomizeGroundingApplyResult,
    AtomizeGroundingProposalResult,
    AtomizeGroundingQuestionResult,
    AtomizeGroundingSessionResult,
)
from memcommit.api.errors import (
    AtomizeGroundingConflictError,
    AtomizeGroundingContextError,
    AtomizeGroundingExecutionError,
    AtomizeGroundingInputError,
    AtomizeGroundingProviderFailure,
    AtomizeGroundingStorageError,
)
from memcommit.operations.atomize.grounding import (
    AtomizeGroundingError as CoreAtomizeGroundingError,
    AtomizeGroundingSession,
    atomize_grounding_canonical_digest,
)
from memcommit.operations.atomize.grounding_application import (
    AtomizeGroundingApplicationError,
    GroundingAcceptRequest,
    GroundingKeepRequest,
    GroundingReplyRequest,
    GroundingStartRequest,
    run_atomize_grounding_accept,
    run_atomize_grounding_keep,
    run_atomize_grounding_reply,
    run_atomize_grounding_start,
)
from memcommit.operations.atomize.grounding_provider import AtomizeGroundingProviderError
from memcommit.operations.atomize.grounding_runtime import (
    MemoryStoreAtomizeGroundingPort,
    assert_current_grounding_bindings,
)
from memcommit.context_locator import resolve_context_locator
from memcommit.persistence.store import ConcurrentContextUpdateError


class _SafeProvider:
    """Project caller-owned provider failures into the stable public taxonomy."""

    def __init__(self, delegate: object) -> None:
        self._delegate = delegate

    def complete(self, prompt, *, operation, output_schema=None):
        try:
            complete = getattr(self._delegate, "complete")
            return complete(
                prompt,
                operation=operation,
                output_schema=output_schema,
            )
        except AtomizeGroundingProviderFailure:
            raise
        except Exception as error:
            raise_public(AtomizeGroundingProviderFailure, error)


def _provider(runtime: ClientRuntime) -> _SafeProvider:
    try:
        return _SafeProvider(runtime.semantic_provider_factory())
    except AtomizeGroundingProviderFailure:
        raise
    except Exception as error:
        raise_public(AtomizeGroundingProviderFailure, error)


def _context(runtime: ClientRuntime, context_name: str | None):
    if context_name is not None and (
        not isinstance(context_name, str) or not context_name.strip()
    ):
        raise AtomizeGroundingInputError(
            "context_name must be nonblank text when supplied."
        )
    try:
        current = (
            runtime.store.current_context_name()
            if runtime.store.state_file.exists()
            else None
        )
        operand = context_name or current
        if operand is None:
            raise FileNotFoundError(
                "No current Context; pass context_name or initialize one."
            )
        canonical = resolve_context_locator(operand, current=current)
        return runtime.store.load_direct(canonical)
    except FileNotFoundError as error:
        raise_public(AtomizeGroundingContextError, error)
    except OSError as error:
        raise_public(AtomizeGroundingStorageError, error)
    except (TypeError, ValueError) as error:
        raise_public(AtomizeGroundingInputError, error)


def _analysis_workbench(runtime: ClientRuntime, context):
    try:
        analysis = runtime.store.load_atomize_analysis(context.uid)
        if analysis is None:
            raise FileNotFoundError(
                f"No saved atomize analysis exists for {context.name!r}."
            )
        workbench = runtime.store.load_atomize_workbench(analysis)
        if workbench is None:
            raise FileNotFoundError(
                f"No saved atomize workbench exists for {context.name!r}."
            )
    except FileNotFoundError as error:
        raise_public(AtomizeGroundingContextError, error)
    except OSError as error:
        raise_public(AtomizeGroundingStorageError, error)
    except (CoreAtomizeGroundingError, TypeError, ValueError) as error:
        raise_public(AtomizeGroundingExecutionError, error)
    return analysis, workbench


def _saved_inputs(runtime: ClientRuntime, context_name: str | None):
    context = _context(runtime, context_name)
    analysis, workbench = _analysis_workbench(runtime, context)
    return context, analysis, workbench


def _project(session: AtomizeGroundingSession) -> AtomizeGroundingSessionResult:
    assessment = session.current_assessment
    application = session.application
    return AtomizeGroundingSessionResult(
        session_uid=session.uid,
        version=atomize_grounding_canonical_digest(session.to_dict()),
        context_name=session.bindings.context_name,
        state=session.state,
        issue_uid=session.anchor.issue_uid,
        issue_kind=session.anchor.kind,
        arity=session.anchor.arity,
        turn_count=len(session.turns),
        active_understanding=(
            assessment.active_understanding if assessment is not None else ()
        ),
        current_status=(
            assessment.direct.status if assessment is not None else None
        ),
        current_explanation=(
            assessment.direct.explanation if assessment is not None else None
        ),
        questions=(
            tuple(
                AtomizeGroundingQuestionResult(
                    uid=question.uid,
                    kind=question.kind,
                    priority=question.priority,
                    text=question.text,
                    reason=question.reason,
                    issue_uids=question.issue_uids,
                )
                for question in assessment.follow_ups
            )
            if assessment is not None
            else ()
        ),
        proposals=(
            tuple(
                AtomizeGroundingProposalResult(
                    uid=proposal.uid,
                    operation=proposal.operation,
                    necessity=proposal.necessity,
                    memory_uid=proposal.memory_uid,
                    content=proposal.content,
                    reason=proposal.reason,
                    issue_uids=proposal.issue_uids,
                )
                for proposal in assessment.proposals
            )
            if assessment is not None
            else ()
        ),
        ready_to_apply=session.state == "READY_TO_APPLY",
        checkpoint_uid=(
            application.checkpoint_uid if application is not None else None
        ),
    )


def _raise_execution(error: BaseException) -> None:
    message = str(error).casefold()
    if any(
        marker in message
        for marker in (
            "changed",
            "stale",
            "no longer matches",
            "during semantic assessment",
        )
    ):
        raise_public(AtomizeGroundingConflictError, error)
    raise_public(AtomizeGroundingExecutionError, error)


def _run_semantic(call):
    try:
        return call()
    except AtomizeGroundingProviderFailure:
        raise
    except AtomizeGroundingProviderError as error:
        raise_public(AtomizeGroundingProviderFailure, error)
    except ConcurrentContextUpdateError as error:
        raise_public(AtomizeGroundingConflictError, error)
    except OSError as error:
        raise_public(AtomizeGroundingStorageError, error)
    except (AtomizeGroundingApplicationError, CoreAtomizeGroundingError) as error:
        _raise_execution(error)
    except (RuntimeError, TypeError, ValueError) as error:
        raise_public(AtomizeGroundingExecutionError, error)


def open_atomize_grounding(
    runtime: ClientRuntime,
    context_name: str | None = None,
) -> AtomizeGroundingSessionResult:
    """Open one saved dialogue without provider access or mutation."""

    context = _context(runtime, context_name)
    try:
        session = runtime.store.load_atomize_grounding_session(context.uid)
        if session is None:
            raise FileNotFoundError(
                f"No atomize grounding dialogue exists for {context.name!r}."
            )
    except FileNotFoundError as error:
        raise_public(AtomizeGroundingContextError, error)
    except OSError as error:
        raise_public(AtomizeGroundingStorageError, error)
    except (CoreAtomizeGroundingError, TypeError, ValueError) as error:
        raise_public(AtomizeGroundingExecutionError, error)
    if session.state in {"AWAITING_REPLY", "READY_TO_APPLY"}:
        analysis, workbench = _analysis_workbench(runtime, context)
        try:
            assert_current_grounding_bindings(
                session,
                context,
                analysis,
                workbench,
            )
        except AtomizeGroundingApplicationError as error:
            raise_public(AtomizeGroundingConflictError, error)
    return _project(session)


def start_atomize_grounding(
    runtime: ClientRuntime,
    selector: str,
    comment: str,
    *,
    context_name: str | None = None,
) -> AtomizeGroundingSessionResult:
    """Start and assess one issue-scoped dialogue without terminal state."""

    if not isinstance(selector, str) or not selector.strip():
        raise AtomizeGroundingInputError("selector must be nonblank text.")
    if not isinstance(comment, str) or not comment.strip():
        raise AtomizeGroundingInputError("comment must be nonblank text.")
    context, analysis, workbench = _saved_inputs(runtime, context_name)
    port = MemoryStoreAtomizeGroundingPort(runtime.store)
    try:
        session = _run_semantic(
            lambda: run_atomize_grounding_start(
                GroundingStartRequest(
                    context=context,
                    analysis=analysis,
                    workbench=workbench,
                    selector=selector,
                    comment=comment,
                ),
                port=port,
                provider_factory=lambda: _provider(runtime),
            )
        )
    except AtomizeGroundingExecutionError as error:
        if "target is missing or ambiguous" in str(error).casefold():
            raise AtomizeGroundingInputError(str(error)) from error
        raise
    return _project(session)


def reply_atomize_grounding(
    runtime: ClientRuntime,
    reply: str,
    *,
    context_name: str | None = None,
    revision: str = "EXTEND",
) -> AtomizeGroundingSessionResult:
    """Append and assess one explicit revision to the saved dialogue."""

    if not isinstance(reply, str) or not reply.strip():
        raise AtomizeGroundingInputError("reply must be nonblank text.")
    if not isinstance(revision, str) or revision.upper() not in {
        "CONFIRM",
        "EXTEND",
        "CORRECT",
        "RETRACT",
    }:
        raise AtomizeGroundingInputError(
            "revision must be confirm, extend, correct, or retract."
        )
    context, analysis, workbench = _saved_inputs(runtime, context_name)
    session = _run_semantic(
        lambda: run_atomize_grounding_reply(
            GroundingReplyRequest(
                context=context,
                analysis=analysis,
                workbench=workbench,
                reply=reply,
                revision=revision,
            ),
            port=MemoryStoreAtomizeGroundingPort(runtime.store),
            provider_factory=lambda: _provider(runtime),
        )
    )
    return _project(session)


def keep_atomize_grounding(
    runtime: ClientRuntime,
    context_name: str | None = None,
) -> AtomizeGroundingSessionResult:
    """Close one dialogue as review-only without changing Memories."""

    context = _context(runtime, context_name)
    session = _run_semantic(
        lambda: run_atomize_grounding_keep(
            GroundingKeepRequest(context_uid=context.uid),
            port=MemoryStoreAtomizeGroundingPort(runtime.store),
        )
    )
    return _project(session)


def apply_atomize_grounding(
    runtime: ClientRuntime,
    context_name: str | None = None,
) -> PublicAtomizeGroundingApplyResult:
    """Apply or recover the exact ready proposal in one checkpoint."""

    context, analysis, workbench = _saved_inputs(runtime, context_name)
    result = _run_semantic(
        lambda: run_atomize_grounding_accept(
            GroundingAcceptRequest(
                context=context,
                analysis=analysis,
                workbench=workbench,
            ),
            port=MemoryStoreAtomizeGroundingPort(runtime.store),
        )
    )
    session = runtime.store.load_atomize_grounding_session(context.uid)
    if session is None:
        raise AtomizeGroundingExecutionError(
            "The applied Grounding receipt has no durable dialogue."
        )
    return PublicAtomizeGroundingApplyResult(
        session=_project(session),
        checkpoint_uid=result.checkpoint_uid,
        change_count=result.change_count,
        recovered=result.recovered,
    )


__all__ = [
    "apply_atomize_grounding",
    "keep_atomize_grounding",
    "open_atomize_grounding",
    "reply_atomize_grounding",
    "start_atomize_grounding",
]
