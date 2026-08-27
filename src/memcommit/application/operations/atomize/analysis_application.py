"""Terminal-independent contract for opening an Atomize analysis session."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal, Protocol

from memcommit.application.operations.atomize.domain import (
    AtomizeAnalysisSession,
    AtomizeFrameOrigin,
    AtomizeProvider,
    atomize_analysis_matches_context,
)
from memcommit.application.operations.atomize.workbench import (
    AtomizeWorkbenchSession,
    atomize_workbench_issue_projection,
)
from memcommit.context import Context


AtomizeAnalysisOrigin = Literal["SAVED", "EXACT_PREWARM", "PROVIDER"]
AtomizeProviderFactory = Callable[[], AtomizeProvider]


class AtomizeAnalysisApplicationError(RuntimeError):
    """An Atomize analysis open request returned an invalid outcome."""


@dataclass(frozen=True)
class AtomizeAnalysisOpenRequest:
    """One analysis scope and publication policy independent of CLI/TUI state."""

    context: Context
    refresh: bool = False
    declared_frames: dict[str, str] | None = None
    declared_frame_origins: dict[str, AtomizeFrameOrigin] | None = None
    source_review_uid: str | None = None
    source_review_digest: str | None = None
    output_context_name: str | None = None
    memory_selector: str | None = None
    allow_prepared: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.context, Context):
            raise TypeError("Atomize analysis open requires a Context.")
        if not isinstance(self.refresh, bool) or not isinstance(
            self.allow_prepared,
            bool,
        ):
            raise TypeError("Atomize analysis open controls must be booleans.")
        if self.output_context_name is not None and (
            not isinstance(self.output_context_name, str)
            or not self.output_context_name
        ):
            raise AtomizeAnalysisApplicationError(
                "Atomize Output must be a nonempty Context name."
            )
        if self.memory_selector is not None and (
            not isinstance(self.memory_selector, str)
            or not self.memory_selector.strip()
        ):
            raise AtomizeAnalysisApplicationError(
                "Atomize Memory selector must be nonempty text."
            )
        reviewed = (
            bool(self.declared_frames)
            or bool(self.declared_frame_origins)
            or self.source_review_uid is not None
            or self.source_review_digest is not None
        )
        if reviewed and self.allow_prepared:
            raise AtomizeAnalysisApplicationError(
                "Reviewed Atomize reanalysis cannot use a prepared analysis."
            )
        if self.refresh and self.allow_prepared:
            raise AtomizeAnalysisApplicationError(
                "Refreshed Atomize analysis cannot use a prepared analysis."
            )


@dataclass(frozen=True)
class AtomizeAnalysisOpenResult:
    """One durable analysis/workbench pair and its semantic origin."""

    analysis: AtomizeAnalysisSession
    workbench: AtomizeWorkbenchSession
    origin: AtomizeAnalysisOrigin

    @property
    def created_analysis(self) -> bool:
        return self.origin == "PROVIDER"

    @property
    def materialized_prepared(self) -> bool:
        return self.origin == "EXACT_PREWARM"


class AtomizeAnalysisOpenPort(Protocol):
    """Authorize, reuse or analyze, and publish one complete session pair."""

    def open(
        self,
        request: AtomizeAnalysisOpenRequest,
        *,
        provider_factory: AtomizeProviderFactory,
    ) -> AtomizeAnalysisOpenResult:
        """Return a complete durable pair without terminal interaction."""


def _validate_result(
    request: AtomizeAnalysisOpenRequest,
    result: AtomizeAnalysisOpenResult,
) -> AtomizeAnalysisOpenResult:
    analysis = result.analysis
    workbench = result.workbench
    if result.origin not in {"SAVED", "EXACT_PREWARM", "PROVIDER"}:
        raise AtomizeAnalysisApplicationError(
            "Atomize analysis returned an unknown origin."
        )
    if (
        analysis.context_uid != request.context.uid
        or analysis.context_name != request.context.name
        or not atomize_analysis_matches_context(analysis, request.context)
    ):
        raise AtomizeAnalysisApplicationError(
            "Atomize analysis returned a result outside the requested Context."
        )
    if not workbench.matches_analysis(
        analysis_uid=analysis.uid,
        context_uid=analysis.context_uid,
        context_name=analysis.context_name,
        context_digest=analysis.context_digest,
        issues=atomize_workbench_issue_projection(analysis),
    ):
        raise AtomizeAnalysisApplicationError(
            "Atomize analysis returned a mismatched workbench."
        )
    if (
        request.output_context_name is not None
        and workbench.output_context_name != request.output_context_name
    ):
        raise AtomizeAnalysisApplicationError(
            "Atomize analysis returned a different Output plan."
        )
    if request.refresh and result.origin != "PROVIDER":
        raise AtomizeAnalysisApplicationError(
            "Atomize refresh did not produce a new provider analysis."
        )
    if result.origin == "EXACT_PREWARM" and not request.allow_prepared:
        raise AtomizeAnalysisApplicationError(
            "Atomize analysis reused a prepared result outside its request."
        )
    if request.source_review_uid is not None and (
        analysis.source_review_uid != request.source_review_uid
        or analysis.source_review_digest != request.source_review_digest
    ):
        raise AtomizeAnalysisApplicationError(
            "Atomize analysis did not retain the reviewed revision."
        )
    return result


def run_atomize_analysis_open(
    request: AtomizeAnalysisOpenRequest,
    *,
    port: AtomizeAnalysisOpenPort,
    provider_factory: AtomizeProviderFactory,
) -> AtomizeAnalysisOpenResult:
    """Open one exact Atomize session without CLI or TUI dependencies."""

    if not isinstance(request, AtomizeAnalysisOpenRequest):
        raise TypeError("Atomize analysis open requires a typed request.")
    return _validate_result(
        request,
        port.open(request, provider_factory=provider_factory),
    )


__all__ = [
    "AtomizeAnalysisApplicationError",
    "AtomizeAnalysisOpenPort",
    "AtomizeAnalysisOpenRequest",
    "AtomizeAnalysisOpenResult",
    "AtomizeAnalysisOrigin",
    "AtomizeProviderFactory",
    "run_atomize_analysis_open",
]
