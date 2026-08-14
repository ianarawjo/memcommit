"""Application contract for reviewed Find result materialization."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

from memcommit.find_application import FindSearchResponse


FindMaterializationMode = Literal["COPY", "REFERENCE"]


class FindMaterializationError(RuntimeError):
    """A reviewed Find result set cannot safely become a new Context."""


@dataclass(frozen=True)
class FindMaterializationRequest:
    """One exact reviewed result selection and require-new destination."""

    response: FindSearchResponse
    selected_result_indices: tuple[int, ...]
    mode: FindMaterializationMode
    destination_name: str

    def __post_init__(self) -> None:
        if not isinstance(self.response, FindSearchResponse):
            raise FindMaterializationError(
                "Find materialization requires one typed search response."
            )
        if self.response.mode != "CURRENT":
            raise FindMaterializationError(
                "History results are evidence views and cannot be saved as a new "
                "Context."
            )
        if self.mode not in {"COPY", "REFERENCE"}:
            raise FindMaterializationError("Choose COPY or REFERENCE.")
        if (
            not isinstance(self.destination_name, str)
            or not self.destination_name.strip()
        ):
            raise FindMaterializationError(
                "Find materialization requires a destination Context name."
            )
        indices = self.selected_result_indices
        if not indices:
            raise FindMaterializationError("Check at least one Find result.")
        if len(set(indices)) != len(indices) or any(
            isinstance(index, bool)
            or not isinstance(index, int)
            or not 0 <= index < len(self.response.results)
            for index in indices
        ):
            raise FindMaterializationError("Find selected an invalid result row.")

        identities: set[tuple[str, str]] = set()
        for index in indices:
            result = self.response.results[index]
            if result.kind not in {"memory", "ref"}:
                raise FindMaterializationError(
                    f"{result.kind} results cannot become Memory copies or references."
                )
            source_context_name = result.source_context_name
            source_context_uid = result.source_context_uid
            source_memory_uid = result.source_memory_uid
            if not (source_context_name and source_context_uid and source_memory_uid):
                raise FindMaterializationError(
                    "This Find result has no frozen source-Memory identity."
                )
            identity = (source_context_uid, source_memory_uid)
            if identity in identities:
                raise FindMaterializationError(
                    f"Source Memory [{source_memory_uid[:8]}] was selected "
                    "more than once."
                )
            identities.add(identity)


@dataclass(frozen=True)
class FrozenFindMaterialization:
    """Adapter-validated effect plan with an opaque persistence token."""

    mode: FindMaterializationMode
    destination_name: str
    source_count: int
    token: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.mode not in {"COPY", "REFERENCE"}:
            raise FindMaterializationError("A frozen Find plan has invalid mode.")
        if not self.destination_name or self.source_count < 1:
            raise FindMaterializationError("A frozen Find plan is incomplete.")


@dataclass(frozen=True)
class FindMaterializationResult:
    """Durable receipt for one newly created Find result Context."""

    mode: FindMaterializationMode
    context_name: str
    context_uid: str
    checkpoint_uid: str
    item_uids: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.mode not in {"COPY", "REFERENCE"}:
            raise FindMaterializationError("A Find receipt has invalid mode.")
        if not all((self.context_name, self.context_uid, self.checkpoint_uid)):
            raise FindMaterializationError("A Find receipt is incomplete.")
        if not self.item_uids or any(not uid for uid in self.item_uids):
            raise FindMaterializationError("A Find receipt requires created items.")


class FindMaterializationPort(Protocol):
    """Validate live sources, then publish one exact require-new result."""

    def prepare(
        self,
        request: FindMaterializationRequest,
    ) -> FrozenFindMaterialization:
        """Freeze live source, authority, destination, and checkpoint inputs."""

    def materialize(
        self,
        prepared: FrozenFindMaterialization,
    ) -> FindMaterializationResult:
        """Publish only the exact prepared plan under its runtime locks."""


def run_find_materialization(
    request: FindMaterializationRequest,
    *,
    port: FindMaterializationPort,
) -> FindMaterializationResult:
    """Run one reviewed write without CLI, TUI, or provider dependencies."""

    prepared = port.prepare(request)
    if (
        prepared.mode != request.mode
        or prepared.destination_name != request.destination_name
        or prepared.source_count != len(request.selected_result_indices)
    ):
        raise FindMaterializationError(
            "The prepared Find materialization does not match the reviewed request."
        )
    result = port.materialize(prepared)
    if (
        result.mode != request.mode
        or result.context_name != request.destination_name
        or len(result.item_uids) != prepared.source_count
    ):
        raise FindMaterializationError(
            "Find materialization returned a receipt outside the reviewed request."
        )
    return result


__all__ = [
    "FindMaterializationError",
    "FindMaterializationMode",
    "FindMaterializationPort",
    "FindMaterializationRequest",
    "FindMaterializationResult",
    "FrozenFindMaterialization",
    "run_find_materialization",
]
