"""Interface-independent lifecycle for structural Atomize application."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Protocol

from memcommit.atomize import (
    AtomizeAnalysisSession,
    AtomizeApplyResult,
)
from memcommit.atomize_workbench import (
    AtomizeWorkbenchSession,
    atomize_workbench_response_digest,
    project_atomize_workbench_findings,
)


class AtomizeApplicationError(RuntimeError):
    """The accepted structural Atomize application could not commit safely."""


@dataclass(frozen=True)
class AtomizeApplicationAudit:
    """The exact unresolved review state visible at structural Apply."""

    application_mode: str
    unresolved_at_apply: tuple[dict[str, object], ...]
    workbench_uid: str | None
    workbench_response_digest: str | None

    @property
    def unresolved_at_apply_count(self) -> int:
        return len(self.unresolved_at_apply)

    def checkpoint_fields(self) -> dict[str, object]:
        return {
            "application_mode": self.application_mode,
            "unresolved_at_apply_count": self.unresolved_at_apply_count,
            "unresolved_at_apply": [dict(item) for item in self.unresolved_at_apply],
            "application_workbench_uid": self.workbench_uid,
            "application_workbench_response_digest": (
                self.workbench_response_digest
            ),
        }


@dataclass(frozen=True)
class AtomizeSessionSnapshot:
    """One immutable analysis/workbench pair under an opaque repository token."""

    analysis: AtomizeAnalysisSession
    workbench: AtomizeWorkbenchSession | None
    version_token: str


@dataclass(frozen=True)
class AtomizeMaterialization:
    """One exact in-place Context checkpoint and its reconstructed result."""

    result: AtomizeApplyResult
    context_name: str
    checkpoint_uid: str
    created: bool


@dataclass(frozen=True)
class AtomizePersistedApplyRequest:
    """Apply the exact saved Atomize revision accepted by an interface."""

    snapshot: AtomizeSessionSnapshot


@dataclass(frozen=True)
class AtomizePersistedApplyResult:
    """The complete structural effect and terminal saved-session state."""

    snapshot: AtomizeSessionSnapshot
    materialization: AtomizeMaterialization
    audit: AtomizeApplicationAudit
    recovered: bool


class AtomizeSessionRepository(Protocol):
    """Persist an analysis/workbench pair without exposing record digests."""

    def load(
        self,
        analysis: AtomizeAnalysisSession,
    ) -> AtomizeSessionSnapshot:
        """Load the exact current pair for one immutable analysis identity."""

    def replace_application(
        self,
        workbench: AtomizeWorkbenchSession,
        *,
        analysis: AtomizeAnalysisSession,
        expected_version: str,
    ) -> AtomizeSessionSnapshot:
        """Commit one terminal receipt only under the exact opaque version."""


class AtomizeOutputPort(Protocol):
    """Materialize or recover one in-place structural Atomize checkpoint."""

    def recover_materialization(
        self,
        snapshot: AtomizeSessionSnapshot,
        audit: AtomizeApplicationAudit,
    ) -> AtomizeMaterialization | None:
        """Return only a checkpoint produced by this exact accepted revision."""

    def materialize(
        self,
        snapshot: AtomizeSessionSnapshot,
        audit: AtomizeApplicationAudit,
    ) -> AtomizeMaterialization:
        """Create or concurrently recover the exact in-place checkpoint."""

    def rollback_materialization(
        self,
        materialization: AtomizeMaterialization,
    ) -> None:
        """Compensate only the untouched checkpoint created by this attempt."""


def atomize_application_audit(
    analysis: AtomizeAnalysisSession,
    workbench: AtomizeWorkbenchSession | None,
) -> AtomizeApplicationAudit:
    """Freeze unresolved state without turning silence into a decision."""

    responses = {} if workbench is None else workbench.responses
    unresolved: list[dict[str, object]] = []
    for finding in project_atomize_workbench_findings(analysis):
        if finding.kind not in {
            "AMBIGUITY",
            "CONFLICT",
            "ATOMIZE_UNCERTAINTY",
        }:
            continue
        response = responses.get(finding.uid)
        unresolved.append(
            {
                "issue_uid": finding.uid,
                "kind": finding.kind,
                "source_uids": list(finding.source_uids),
                "classification": finding.classification,
                "reason": finding.reason,
                "response_state": (
                    "ANSWERED_RETAINED"
                    if response is not None and response.answered
                    else "OPEN"
                ),
            }
        )
    return AtomizeApplicationAudit(
        application_mode="AS_IS" if unresolved else "REVIEWED",
        unresolved_at_apply=tuple(unresolved),
        workbench_uid=(workbench.uid if workbench is not None else None),
        workbench_response_digest=(
            atomize_workbench_response_digest(workbench)
            if workbench is not None
            else None
        ),
    )


def _terminal_workbench(
    snapshot: AtomizeSessionSnapshot,
    materialization: AtomizeMaterialization,
) -> AtomizeWorkbenchSession | None:
    workbench = snapshot.workbench
    if workbench is None:
        return None
    terminal = copy.deepcopy(workbench)
    terminal.record_application(
        output_context_name=materialization.context_name,
        checkpoint_uid=materialization.checkpoint_uid,
    )
    return terminal


def run_atomize_session_apply(
    request: AtomizePersistedApplyRequest,
    *,
    repository: AtomizeSessionRepository,
    output_port: AtomizeOutputPort,
) -> AtomizePersistedApplyResult:
    """Materialize and receipt one exact structural review as one outcome."""

    reviewed = request.snapshot
    current = repository.load(reviewed.analysis)
    if current != reviewed:
        raise AtomizeApplicationError(
            "The Atomize session changed before Apply. Reopen the review."
        )
    audit = atomize_application_audit(current.analysis, current.workbench)
    materialization = output_port.recover_materialization(current, audit)
    recovered = materialization is not None
    if materialization is None:
        materialization = output_port.materialize(current, audit)
        recovered = not materialization.created

    terminal = _terminal_workbench(current, materialization)
    if terminal is None:
        return AtomizePersistedApplyResult(
            snapshot=current,
            materialization=materialization,
            audit=audit,
            recovered=recovered,
        )

    if current.workbench is not None and current.workbench.application is not None:
        if current.workbench != terminal:
            raise AtomizeApplicationError(
                "The Atomize session records a different application receipt."
            )
        return AtomizePersistedApplyResult(
            snapshot=current,
            materialization=materialization,
            audit=audit,
            recovered=True,
        )

    try:
        committed = repository.replace_application(
            terminal,
            analysis=current.analysis,
            expected_version=current.version_token,
        )
    except Exception as error:
        # An atomic replacement may commit and still report an I/O error.
        # Re-read before compensation so a durable terminal receipt never
        # loses the exact checkpoint it names.
        try:
            observed = repository.load(current.analysis)
        except Exception as observation_error:
            raise AtomizeApplicationError(
                "Atomize materialization succeeded, but receipt persistence "
                "failed and its durable state could not be verified."
            ) from observation_error
        if observed.workbench == terminal:
            return AtomizePersistedApplyResult(
                snapshot=observed,
                materialization=materialization,
                audit=audit,
                recovered=recovered,
            )
        if materialization.created:
            try:
                output_port.rollback_materialization(materialization)
            except Exception as rollback_error:
                raise AtomizeApplicationError(
                    "Atomize receipt persistence failed and the exact in-place "
                    "checkpoint could not be rolled back."
                ) from rollback_error
        if observed != current:
            raise AtomizeApplicationError(
                "The Atomize session changed before its receipt could be "
                "committed; the in-place effect was rolled back."
            ) from error
        raise

    if committed.workbench != terminal:
        raise AtomizeApplicationError(
            "Atomize receipt persistence returned a different session."
        )
    return AtomizePersistedApplyResult(
        snapshot=committed,
        materialization=materialization,
        audit=audit,
        recovered=recovered,
    )
