"""Operation-neutral contract for saving selected Memories as a Context."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol


SaveContextMode = Literal["COPY", "REFERENCE", "EMBED"]


class SaveContextFromSelectionError(RuntimeError):
    """A reviewed Memory selection cannot safely become a new Context."""


@dataclass(frozen=True, slots=True)
class SelectionOrigin:
    """Operation input that explains why these exact rows were selected."""

    operation: str
    arguments: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.operation, str) or not self.operation.strip():
            raise SaveContextFromSelectionError(
                "A saved selection requires its Source operation."
            )
        keys: set[str] = set()
        for key, value in self.arguments:
            if (
                not isinstance(key, str)
                or not key.strip()
                or not isinstance(value, str)
            ):
                raise SaveContextFromSelectionError(
                    "Saved-selection origin arguments must be named text values."
                )
            if key in keys:
                raise SaveContextFromSelectionError(
                    f"Saved-selection origin argument {key!r} appears more than once."
                )
            keys.add(key)


@dataclass(frozen=True, slots=True)
class SelectedMemory:
    """One displayed row bound to its exact directly owned Source Memory."""

    position: int
    source_kind: str
    source_context_name: str
    source_context_uid: str
    source_memory_uid: str
    content: str
    relevance: str | None = None

    def __post_init__(self) -> None:
        if (
            isinstance(self.position, bool)
            or not isinstance(self.position, int)
            or self.position < 1
        ):
            raise SaveContextFromSelectionError(
                "A selected Memory requires a positive Source position."
            )
        required_text = (
            self.source_kind,
            self.source_context_name,
            self.source_context_uid,
            self.source_memory_uid,
            self.content,
        )
        if any(not isinstance(value, str) or not value.strip() for value in required_text):
            raise SaveContextFromSelectionError(
                "A selected Memory has incomplete Source identity or content."
            )
        if self.relevance is not None and (
            not isinstance(self.relevance, str) or not self.relevance.strip()
        ):
            raise SaveContextFromSelectionError(
                "Selected-Memory relevance must be nonblank text when present."
            )


@dataclass(frozen=True, slots=True)
class SaveContextFromSelectionRequest:
    """One exact reviewed selection and require-new local destination."""

    selection: tuple[SelectedMemory, ...]
    mode: SaveContextMode
    destination_name: str
    origin: SelectionOrigin

    def __post_init__(self) -> None:
        if not isinstance(self.selection, tuple) or not self.selection:
            raise SaveContextFromSelectionError("Select at least one Memory.")
        if any(not isinstance(item, SelectedMemory) for item in self.selection):
            raise SaveContextFromSelectionError(
                "Saving a Context requires typed selected Memories."
            )
        if self.mode not in {"COPY", "REFERENCE", "EMBED"}:
            raise SaveContextFromSelectionError(
                "Choose COPY, REFERENCE, or EMBED."
            )
        if (
            not isinstance(self.destination_name, str)
            or not self.destination_name.strip()
        ):
            raise SaveContextFromSelectionError(
                "Saving a selection requires a destination Context name."
            )
        if not isinstance(self.origin, SelectionOrigin):
            raise SaveContextFromSelectionError(
                "Saving a selection requires typed origin evidence."
            )
        positions = [item.position for item in self.selection]
        if len(set(positions)) != len(positions):
            raise SaveContextFromSelectionError(
                "A Source result position was selected more than once."
            )
        identities = [
            (item.source_context_uid, item.source_memory_uid)
            for item in self.selection
        ]
        if len(set(identities)) != len(identities):
            duplicate = next(
                identity
                for identity in identities
                if identities.count(identity) > 1
            )
            raise SaveContextFromSelectionError(
                f"Source Memory [{duplicate[1][:8]}] was selected more than once."
            )


@dataclass(frozen=True, slots=True)
class FrozenContextSelectionSave:
    """Adapter-validated save plan with an opaque persistence token."""

    mode: SaveContextMode
    destination_name: str
    source_count: int
    token: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.mode not in {"COPY", "REFERENCE", "EMBED"}:
            raise SaveContextFromSelectionError(
                "A frozen selected-Context save has an invalid mode."
            )
        if not self.destination_name or self.source_count < 1:
            raise SaveContextFromSelectionError(
                "A frozen selected-Context save is incomplete."
            )


@dataclass(frozen=True, slots=True)
class SaveContextFromSelectionResult:
    """Durable receipt for one newly created Context."""

    mode: SaveContextMode
    context_name: str
    context_uid: str
    checkpoint_uid: str
    item_uids: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.mode not in {"COPY", "REFERENCE", "EMBED"}:
            raise SaveContextFromSelectionError(
                "A selected-Context save receipt has an invalid mode."
            )
        if not all((self.context_name, self.context_uid, self.checkpoint_uid)):
            raise SaveContextFromSelectionError(
                "A selected-Context save receipt is incomplete."
            )
        if not self.item_uids or any(not uid for uid in self.item_uids):
            raise SaveContextFromSelectionError(
                "A selected-Context save receipt requires created items."
            )


class SaveContextFromSelectionPort(Protocol):
    """Validate live Sources, then publish one exact require-new Context."""

    def prepare(
        self,
        request: SaveContextFromSelectionRequest,
    ) -> FrozenContextSelectionSave: ...

    def save(
        self,
        prepared: FrozenContextSelectionSave,
    ) -> SaveContextFromSelectionResult: ...


def save_context_from_selection(
    request: SaveContextFromSelectionRequest,
    *,
    port: SaveContextFromSelectionPort,
) -> SaveContextFromSelectionResult:
    """Save one reviewed selection without operation or presentation coupling."""

    if not isinstance(request, SaveContextFromSelectionRequest):
        raise TypeError("Saving a Context requires a typed selection request.")
    prepared = port.prepare(request)
    if (
        prepared.mode != request.mode
        or prepared.destination_name != request.destination_name
        or prepared.source_count != len(request.selection)
    ):
        raise SaveContextFromSelectionError(
            "The prepared Context save does not match the reviewed selection."
        )
    result = port.save(prepared)
    if (
        result.mode != request.mode
        or result.context_name != request.destination_name
        or len(result.item_uids) != prepared.source_count
    ):
        raise SaveContextFromSelectionError(
            "The Context save receipt is outside the reviewed selection."
        )
    return result


__all__ = [
    "FrozenContextSelectionSave",
    "SaveContextFromSelectionError",
    "SaveContextFromSelectionPort",
    "SaveContextFromSelectionRequest",
    "SaveContextFromSelectionResult",
    "SaveContextMode",
    "SelectedMemory",
    "SelectionOrigin",
    "save_context_from_selection",
]
