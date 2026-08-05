"""Reusable, provider-free Impact projection for operation-owned artifacts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from memcommit.resolution_workbench import ResolutionWorkbenchView


@dataclass(frozen=True)
class ImpactEntry:
    """One exact proposed effect shown before an operation applies it."""

    marker: str
    label: str
    text: str
    reason: str = ""

    def __post_init__(self) -> None:
        for label, value in (
            ("Impact marker", self.marker),
            ("Impact label", self.label),
            ("Impact text", self.text),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} must be nonempty text.")
        if not isinstance(self.reason, str):
            raise ValueError("Impact reason must be text.")


@dataclass(frozen=True)
class ImpactView:
    """Immutable read-only effect preview supplied to a host TUI or CLI."""

    operation: str
    artifact_uid: str
    revision: str
    title: str
    summary: str
    detail: str = ""
    entries: tuple[ImpactEntry, ...] = ()

    def __post_init__(self) -> None:
        for label, value in (
            ("Impact operation", self.operation),
            ("Impact artifact uid", self.artifact_uid),
            ("Impact revision", self.revision),
            ("Impact title", self.title),
            ("Impact summary", self.summary),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} must be nonempty text.")
        if not isinstance(self.detail, str):
            raise ValueError("Impact detail must be text.")
        if not isinstance(self.entries, tuple) or any(
            not isinstance(entry, ImpactEntry) for entry in self.entries
        ):
            raise ValueError("Impact entries must be a tuple of ImpactEntry values.")


class ImpactController:
    """Re-project the owning artifact without calling a provider or applying it."""

    def __init__(self, supplier: Callable[[], ImpactView]):
        if not callable(supplier):
            raise TypeError("Impact controller requires a view supplier.")
        self._supplier = supplier

    def view(self) -> ImpactView:
        view = self._supplier()
        if not isinstance(view, ImpactView):
            raise TypeError("Impact controller supplier returned an invalid view.")
        return view

    @classmethod
    def from_resolution(
        cls,
        view_or_supplier: ResolutionWorkbenchView | Callable[[], ResolutionWorkbenchView],
        *,
        title: str,
        summary: str,
        detail: str = "",
    ) -> "ImpactController":
        """Project exact results, or planned items when results do not exist."""

        supplier = (
            view_or_supplier
            if callable(view_or_supplier)
            else lambda: view_or_supplier
        )

        def project() -> ImpactView:
            resolution = supplier()
            if not isinstance(resolution, ResolutionWorkbenchView):
                raise TypeError("Impact resolution supplier returned an invalid view.")
            if resolution.results:
                entries = tuple(
                    ImpactEntry(
                        marker=result.marker,
                        label=result.label,
                        text=result.text,
                        reason=result.reason,
                    )
                    for result in resolution.results
                )
            else:
                entries = tuple(
                    ImpactEntry(
                        marker="Δ",
                        label=item.kind,
                        text="\n\n".join(
                            (
                                f"{block.heading}\n{block.text}"
                                for block in item.blocks
                            )
                        )
                        or item.summary,
                        reason=item.summary,
                    )
                    for item in resolution.items
                )
            return ImpactView(
                operation=resolution.operation,
                artifact_uid=resolution.artifact_uid,
                revision=resolution.revision,
                title=title,
                summary=summary,
                detail=detail,
                entries=entries,
            )

        return cls(project)

    @classmethod
    def from_text(
        cls,
        *,
        operation: str,
        artifact_uid: str,
        revision: str,
        title: str,
        summary: str,
        detail: str,
    ) -> "ImpactController":
        """Wrap one already-saved read-only report such as Compare."""

        return cls(
            lambda: ImpactView(
                operation=operation,
                artifact_uid=artifact_uid,
                revision=revision,
                title=title,
                summary=summary,
                detail=detail,
            )
        )
