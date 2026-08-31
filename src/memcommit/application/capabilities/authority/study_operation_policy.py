"""Grant-aware analysis boundaries for readable Contexts.

The module name is retained for compatibility with earlier Study prototypes.
Trace authority is now derived from Context ownership, not a Study task name.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from memcommit.application.operations.profiles.profile.config import ProfileRegistry


@dataclass(frozen=True)
class StudyOperationPolicy:
    """The analysis operations exposed at one readable Context."""

    rationale_allowed: bool
    trace_allowed: bool


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
    authorized by READ. ``trace_allowed`` specifically denotes retained
    checkpoints and command receipts: a granted READ view may expose a typed
    current-access report, but never implies retained-history authority. Every
    locally owned Context may inspect its own retained history. The unused
    registry/store parameters remain accepted so older embedders do not acquire
    a source-incompatible policy call during this migration.
    """
    del context_name, registry, store_root
    return StudyOperationPolicy(
        rationale_allowed=readable,
        trace_allowed=not granted,
    )


def analysis_boundary_label(
    context_name: str,
    *,
    granted: bool,
    readable: bool = True,
    registry: ProfileRegistry | None = None,
    store_root: Path | None = None,
) -> str:
    """Render the retained-analysis badge shared by ``ls`` and ``switch``.

    ``TRACE BLOCKED`` remains shorthand for retained history being hidden; it
    does not rule out the content-bounded current Grant report.
    """

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
        "Trace is unavailable because retained history is not readable at this Context."
    )
