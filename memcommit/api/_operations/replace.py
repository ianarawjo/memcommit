"""Public application assembly for deterministic Replace."""

from __future__ import annotations

from collections.abc import Sequence

from memcommit.api._runtime import ClientRuntime
from memcommit.api._support.errors import raise_public
from memcommit.api.errors import (
    ReplaceConflictError,
    ReplaceContextError,
    ReplaceExecutionError,
    ReplaceInputError,
    ReplaceStorageError,
)
from memcommit.api.replace import (
    ReplaceApplyReceipt,
    ReplaceCheckpointResult,
    ReplaceContextPlanResult,
    ReplaceMemoryPlanResult,
    ReplacePlanResult,
    ReplaceSpanResult,
)
from memcommit.context_locator import resolve_context_locator
from memcommit.operations.replace.application import (
    ReplaceError,
    ReplaceInputError as InternalReplaceInputError,
    ReplaceRequest,
    ReplaceStalePlanError,
)
from memcommit.operations.replace.runtime import (
    MemoryStoreReplacePort,
    execute_replace_plan,
)
from memcommit.store import ConcurrentContextUpdateError
from memcommit.write_protection import WriteProtectionError


def _current_name(runtime: ClientRuntime) -> str | None:
    try:
        return runtime.store.current_context_name()
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as error:
        raise_public(ReplaceStorageError, error)


def _canonical_targets(
    runtime: ClientRuntime,
    context_names: Sequence[str],
    *,
    current_name: str | None,
) -> tuple[str, ...]:
    if isinstance(context_names, (str, bytes)):
        raise TypeError("Replace Context names must be a sequence.")
    operands = tuple(context_names)
    if not operands:
        if current_name is None:
            raise FileNotFoundError("No current Context is available.")
        operands = (current_name,)
    canonical = tuple(
        resolve_context_locator(name, current=current_name) for name in operands
    )
    if len(set(canonical)) != len(canonical):
        raise ValueError("Replace Context names must not repeat.")
    if any(not runtime.store.context_exists(name) for name in canonical):
        raise FileNotFoundError(
            "Replace targets must be ordinary local Contexts in this Store."
        )
    return canonical


def _project_plan(plan, port, runtime: ClientRuntime) -> ReplacePlanResult:
    return ReplacePlanResult(
        pattern=plan.request.pattern,
        replacement=plan.request.replacement,
        context_names=plan.request.target_names,
        include_descendants=plan.request.include_descendants,
        follow_embeds=plan.request.follow_embeds,
        mode=plan.request.mode,
        ignore_case=plan.request.ignore_case,
        plan_digest=plan.plan_digest,
        scanned_context_count=plan.scanned_context_count,
        scanned_memory_count=plan.scanned_memory_count,
        matched_memory_count=plan.matched_memory_count,
        changed_memory_count=plan.changed_memory_count,
        occurrence_count=plan.occurrence_count,
        contexts=tuple(
            ReplaceContextPlanResult(
                context_name=context.context_name,
                context_uid=context.context_uid,
                context_digest=context.context_digest,
                scanned_memory_count=context.scanned_memory_count,
                matches=tuple(
                    ReplaceMemoryPlanResult(
                        memory_uid=match.memory_uid,
                        before_content=match.before_content,
                        after_content=match.after_content,
                        changed=match.changed,
                        spans=tuple(
                            ReplaceSpanResult(span.start, span.end, span.text)
                            for span in match.spans
                        ),
                    )
                    for match in context.matches
                ),
            )
            for context in plan.contexts
        ),
        _handle=(runtime.store_root, plan, port),
    )


def plan_replace(
    runtime: ClientRuntime,
    pattern: str,
    replacement: str,
    context_names: Sequence[str] = (),
    *,
    include_descendants: bool = False,
    follow_embeds: bool = False,
    regex: bool = False,
    ignore_case: bool = False,
) -> ReplacePlanResult:
    try:
        current_name = _current_name(runtime)
        targets = _canonical_targets(
            runtime,
            context_names,
            current_name=current_name,
        )
        request = ReplaceRequest(
            pattern=pattern,
            replacement=replacement,
            target_names=targets,
            include_descendants=include_descendants,
            follow_embeds=follow_embeds,
            mode="REGEX" if regex else "LITERAL",
            ignore_case=ignore_case,
        )
        port = MemoryStoreReplacePort(runtime.store)
        from memcommit.operations.replace.application import plan_replace as prepare

        return _project_plan(prepare(request, port=port), port, runtime)
    except ReplaceStorageError:
        raise
    except (InternalReplaceInputError, TypeError, ValueError) as error:
        raise_public(ReplaceInputError, error)
    except (FileNotFoundError, KeyError) as error:
        raise_public(ReplaceContextError, error)
    except (ConcurrentContextUpdateError, ReplaceStalePlanError) as error:
        raise_public(ReplaceConflictError, error)
    except OSError as error:
        raise_public(ReplaceStorageError, error)
    except (ReplaceError, RuntimeError, WriteProtectionError) as error:
        raise_public(ReplaceExecutionError, error)


def apply_replace(
    runtime: ClientRuntime,
    reviewed: ReplacePlanResult,
) -> ReplaceApplyReceipt:
    if not isinstance(reviewed, ReplacePlanResult):
        raise ReplaceInputError("Replace Apply requires a ReplacePlanResult.")
    try:
        handle = reviewed._handle
        if (
            not isinstance(handle, tuple)
            or len(handle) != 3
            or handle[0] != runtime.store_root
            or not isinstance(handle[2], MemoryStoreReplacePort)
        ):
            raise ReplaceInputError(
                "Replace plan does not belong to this MemCommitClient."
            )
        _root, plan, port = handle
        if plan.plan_digest != reviewed.plan_digest:
            raise ReplaceInputError("Replace plan digest was modified after review.")
        result = execute_replace_plan(plan, port=port)
        return ReplaceApplyReceipt(
            plan_digest=result.plan_digest,
            applied=result.applied,
            scanned_context_count=result.scanned_context_count,
            scanned_memory_count=result.scanned_memory_count,
            matched_memory_count=result.matched_memory_count,
            changed_memory_count=result.changed_memory_count,
            occurrence_count=result.occurrence_count,
            checkpoints=tuple(
                ReplaceCheckpointResult(
                    context_name=checkpoint.context_name,
                    context_uid=checkpoint.context_uid,
                    checkpoint_uid=checkpoint.checkpoint_uid,
                )
                for checkpoint in result.checkpoints
            ),
        )
    except (ReplaceInputError, ReplaceConflictError):
        raise
    except (ConcurrentContextUpdateError, ReplaceStalePlanError) as error:
        raise_public(ReplaceConflictError, error)
    except (FileNotFoundError, KeyError) as error:
        raise_public(ReplaceContextError, error)
    except OSError as error:
        raise_public(ReplaceStorageError, error)
    except (ReplaceError, RuntimeError, WriteProtectionError) as error:
        raise_public(ReplaceExecutionError, error)


__all__ = ["apply_replace", "plan_replace"]
