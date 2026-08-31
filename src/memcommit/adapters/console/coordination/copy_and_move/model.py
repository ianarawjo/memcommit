"""Coordinated setup state for interactive direct-Memory Copy and Move."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.source_projection.presentation import SourceDisplayValue


@dataclass(frozen=True)
class CopyAndMoveTuiSetup:
    """Frozen role-specific Source and Target catalogs for one launch.

    ``source_names`` may contain explicitly READ-granted public names for
    Copy. ``local_source_names`` is the only catalog searched for an
    unqualified Memory UID and is also the complete Move Source catalog. The
    Target catalog stays independently owned and local for both operations.
    """

    source_names: tuple[str, ...]
    local_source_names: tuple[str, ...]
    into_names: tuple[str, ...]
    current_context: str | None = None
    source_annotations: tuple[tuple[str, SourceDisplayValue], ...] = ()

    def __post_init__(self) -> None:
        catalogs = (
            self.source_names,
            self.local_source_names,
            self.into_names,
        )
        if any(
            not names
            or len(set(names)) != len(names)
            or any(not isinstance(name, str) or not name for name in names)
            for names in catalogs
        ):
            raise ValueError(
                "Interactive Copy/Move requires distinct nonempty role catalogs."
            )
        source_set = set(self.source_names)
        local_set = set(self.local_source_names)
        if not local_set <= source_set:
            raise ValueError(
                "Copy/Move local Sources must be present in the Source catalog."
            )
        if (
            self.current_context is not None
            and self.current_context not in self.into_names
        ):
            raise ValueError(
                "Copy/Move current Context is outside the local catalog."
            )
        annotation_names = tuple(name for name, _value in self.source_annotations)
        if (
            len(set(annotation_names)) != len(annotation_names)
            or any(name not in source_set for name in annotation_names)
        ):
            raise ValueError(
                "Copy/Move Source annotations must name distinct visible rows."
            )


__all__ = ["CopyAndMoveTuiSetup"]
