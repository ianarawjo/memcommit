"""Participant-visible analysis boundaries for a composed Study run."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from memcommit.profile_config import (
    ProfileRegistry,
    load_profile_registry,
    profile_store_dir,
)


_STUDY_RUN_SOURCE_KIND = "STUDY_RUN"


@dataclass(frozen=True)
class StudyOperationPolicy:
    """The analysis operations exposed at one participant Context."""

    rationale_allowed: bool
    trace_allowed: bool
    study_task: int | None


def _task_number(context_name: str) -> int | None:
    root = context_name.split("/", 1)[0]
    if root not in {"task-1", "task-2", "task-3"}:
        return None
    return int(root[-1])


def operation_policy(
    context_name: str,
    *,
    granted: bool,
    readable: bool = True,
    registry: ProfileRegistry | None = None,
    store_root: Path | None = None,
) -> StudyOperationPolicy:
    """Return the effective Rationale/Trace boundary for one visible Context.

    Rationale is a content interpretation over the same ordinary-Memory frame
    authorized by READ. Trace is different: it opens retained checkpoints and
    command receipts, so a granted READ view never implies Trace authority.
    During a participant Study run, local Trace is intentionally confined to
    Task 3, whose task design explicitly exercises personal-memory history.
    """

    registry = registry or load_profile_registry()
    source = registry.active.source
    if (
        store_root is not None
        and Path(store_root).resolve() != profile_store_dir(registry.active).resolve()
    ):
        source = None
    task = (
        _task_number(context_name)
        if isinstance(source, dict) and source.get("kind") == _STUDY_RUN_SOURCE_KIND
        else None
    )
    return StudyOperationPolicy(
        rationale_allowed=readable,
        trace_allowed=not granted and (task is None or task == 3),
        study_task=task,
    )


def analysis_boundary_label(
    context_name: str,
    *,
    granted: bool,
    readable: bool = True,
    registry: ProfileRegistry | None = None,
    store_root: Path | None = None,
) -> str:
    """Render the compact operation badge shared by ``ls`` and ``switch``."""

    policy = operation_policy(
        context_name,
        granted=granted,
        readable=readable,
        registry=registry,
        store_root=store_root,
    )
    rationale = "RATIONALE SUBTREE" if policy.rationale_allowed else "RATIONALE BLOCKED"
    trace = "TRACE ALLOWED" if policy.trace_allowed else "TRACE BLOCKED"
    return f"{rationale} + {trace}"


def require_trace_access(
    context_name: str,
    *,
    granted: bool,
    registry: ProfileRegistry | None = None,
    store_root: Path | None = None,
) -> None:
    """Fail closed before any retained history is opened."""

    policy = operation_policy(
        context_name,
        granted=granted,
        registry=registry,
        store_root=store_root,
    )
    if policy.trace_allowed:
        return
    if granted:
        raise PermissionError(
            "Trace is unavailable for a granted READ view because READ does not "
            "expose authority checkpoint or command-log history."
        )
    raise PermissionError(
        "Trace is available only in the Task 3 subtree during a Study run."
    )
