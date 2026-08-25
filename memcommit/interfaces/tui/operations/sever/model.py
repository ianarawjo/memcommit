"""Typed process-local values for Sever endpoint setup."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.source_projection.presentation import (
    SourceDisplayValue,
    normalize_source_display_tokens,
)


@dataclass(frozen=True)
class SeverTuiSetup:
    """Frozen readable inputs and local output namespace supplied by Sever."""

    names: tuple[str, ...]
    local_names: tuple[str, ...]
    selectable_names: frozenset[str]
    source_name: str
    criteria_name: str
    current_context: str | None = None
    annotations: tuple[tuple[str, SourceDisplayValue], ...] = ()

    def __post_init__(self) -> None:
        if (
            len(self.names) < 2
            or len(set(self.names)) != len(self.names)
            or any(not isinstance(name, str) or not name for name in self.names)
        ):
            raise ValueError("Sever setup requires two distinct readable names.")
        if (
            not self.local_names
            or len(set(self.local_names)) != len(self.local_names)
            or not set(self.local_names) <= set(self.names)
        ):
            raise ValueError("Sever setup requires a valid local output namespace.")
        if (
            len(self.selectable_names) < 2
            or not self.selectable_names <= set(self.names)
            or not set(self.local_names) <= self.selectable_names
        ):
            raise ValueError("Sever setup requires two selectable readable Contexts.")
        if (
            self.source_name not in self.selectable_names
            or self.criteria_name not in self.selectable_names
            or self.source_name == self.criteria_name
        ):
            raise ValueError("Sever setup requires distinct available defaults.")
        labels = dict(self.annotations)
        if len(labels) != len(self.annotations) or set(labels) - set(self.names):
            raise ValueError("Sever setup annotations are outside its catalog.")
        try:
            if any(
                not normalize_source_display_tokens(annotation)
                for annotation in labels.values()
            ):
                raise ValueError
        except (TypeError, ValueError) as error:
            raise ValueError("Sever setup annotations must not be empty.") from error


@dataclass(frozen=True)
class SeverSetupReceipt:
    """One reviewed Sever scope returned without provider or durable work."""

    source_name: str
    criteria_name: str
    output_name: str
    source_descendants: bool = True
    criteria_descendants: bool = True

    def __post_init__(self) -> None:
        if (
            not self.source_name
            or not self.criteria_name
            or not self.output_name
            or self.source_name == self.criteria_name
        ):
            raise ValueError("Sever endpoint selection is incomplete or ambiguous.")
        if self.output_name == self.source_name and self.source_descendants:
            raise ValueError("Sever self-save requires an exact Source Context.")


# The interface uses endpoint-selection vocabulary, while the historical
# command path exposed SeverSetupReceipt. One exact class preserves both names.
SeverEndpointSelection = SeverSetupReceipt
