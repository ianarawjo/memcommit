"""Operation-adaptive, non-applying semantic review reports."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Literal

from memcommit.resolution_workbench import ResolutionWorkbenchView


ReviewReportKind = Literal[
    "READ_ONLY",
    "RESOLUTION",
    "DISCLOSURE",
    "CLARIFICATION",
    "CHANGE_PLAN",
]


@dataclass(frozen=True)
class ReviewReport:
    """One revision-bound report; reviewing it never authorizes application."""

    operation: str
    artifact_uid: str
    revision: str
    kind: ReviewReportKind
    title: str
    summary: str
    view: ResolutionWorkbenchView | None = None
    report_text: str = ""

    def __post_init__(self) -> None:
        for label, value in (
            ("Review operation", self.operation),
            ("Review artifact uid", self.artifact_uid),
            ("Review revision", self.revision),
            ("Review title", self.title),
            ("Review summary", self.summary),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} must be nonempty text.")
        if self.kind not in {
            "READ_ONLY",
            "RESOLUTION",
            "DISCLOSURE",
            "CLARIFICATION",
            "CHANGE_PLAN",
        }:
            raise ValueError("Unsupported Review report kind.")
        if not isinstance(self.report_text, str):
            raise ValueError("Review report text must be text.")
        if self.view is None and not self.report_text.strip():
            raise ValueError("A Review report requires a view or report text.")
        if self.view is not None:
            if (
                self.view.operation.upper() != self.operation.upper()
                or self.view.artifact_uid != self.artifact_uid
                or self.view.revision != self.revision
            ):
                raise ValueError("Review view does not match its report identity.")
            if "ACCEPT" in self.view.capabilities or self.view.accept_enabled:
                raise ValueError("Review reports cannot expose Accept or Apply.")


class ReviewReportController:
    """Reload and project one operation-owned report without applying it."""

    def __init__(self, supplier: Callable[[], ReviewReport]):
        if not callable(supplier):
            raise TypeError("Review report controller requires a supplier.")
        self._supplier = supplier

    def report(self) -> ReviewReport:
        report = self._supplier()
        if not isinstance(report, ReviewReport):
            raise TypeError("Review report supplier returned an invalid report.")
        return report

    @classmethod
    def from_resolution(
        cls,
        view_or_supplier: ResolutionWorkbenchView | Callable[[], ResolutionWorkbenchView],
        *,
        kind: ReviewReportKind,
        title: str,
        summary: str,
        report_text: str = "",
    ) -> "ReviewReportController":
        supplier = (
            view_or_supplier if callable(view_or_supplier) else lambda: view_or_supplier
        )

        def project() -> ReviewReport:
            source = supplier()
            if not isinstance(source, ResolutionWorkbenchView):
                raise TypeError("Review resolution supplier returned an invalid view.")
            # Apply is a sibling operation boundary. Keep semantic response
            # capabilities, but a report can never smuggle target acceptance.
            view = replace(
                source,
                title=title,
                status=f"{source.status} · REVIEW",
                overview=f"{summary}\n\n{source.overview}",
                list_label="REVIEW ITEMS",
                capabilities=frozenset(
                    capability
                    for capability in source.capabilities
                    if capability != "ACCEPT"
                ),
                accept_enabled=False,
            )
            return ReviewReport(
                operation=view.operation,
                artifact_uid=view.artifact_uid,
                revision=view.revision,
                kind=kind,
                title=title,
                summary=summary,
                view=view,
                report_text=report_text,
            )

        return cls(project)

    @classmethod
    def from_text(
        cls,
        *,
        operation: str,
        artifact_uid: str,
        revision: str,
        kind: ReviewReportKind,
        title: str,
        summary: str,
        report_text: str,
    ) -> "ReviewReportController":
        return cls(
            lambda: ReviewReport(
                operation=operation,
                artifact_uid=artifact_uid,
                revision=revision,
                kind=kind,
                title=title,
                summary=summary,
                report_text=report_text,
            )
        )
