"""Operation-owned contract for reviewed Search result materialization."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

from memcommit.application.operations.search.application import SearchResponse


SearchMaterializationMode = Literal["COPY", "REFERENCE"]


class SearchMaterializationError(RuntimeError):
    """A reviewed Search result set cannot safely become a new Context."""


@dataclass(frozen=True)
class SearchMaterializationRequest:
    """One exact reviewed result selection and require-new destination."""

    response: SearchResponse
    selected_result_indices: tuple[int, ...]
    mode: SearchMaterializationMode
    destination_name: str

    def __post_init__(self) -> None:
        if not isinstance(self.response, SearchResponse):
            raise SearchMaterializationError(
                "Search materialization requires one typed search response."
            )
        if self.mode not in {"COPY", "REFERENCE"}:
            raise SearchMaterializationError("Choose COPY or REFERENCE.")
        if (
            not isinstance(self.destination_name, str)
            or not self.destination_name.strip()
        ):
            raise SearchMaterializationError(
                "Search materialization requires a destination Context name."
            )
        indices = self.selected_result_indices
        if not indices:
            raise SearchMaterializationError("Check at least one Search result.")
        if len(set(indices)) != len(indices) or any(
            isinstance(index, bool)
            or not isinstance(index, int)
            or not 0 <= index < len(self.response.results)
            for index in indices
        ):
            raise SearchMaterializationError("Search selected an invalid result row.")

        identities: set[tuple[str, str]] = set()
        for index in indices:
            result = self.response.results[index]
            if result.kind not in {"memory", "ref"}:
                raise SearchMaterializationError(
                    f"{result.kind} results cannot become Memory copies or references."
                )
            source_context_name = result.source_context_name
            source_context_uid = result.source_context_uid
            source_memory_uid = result.source_memory_uid
            if not (source_context_name and source_context_uid and source_memory_uid):
                raise SearchMaterializationError(
                    "This Search result has no frozen source-Memory identity."
                )
            identity = (source_context_uid, source_memory_uid)
            if identity in identities:
                raise SearchMaterializationError(
                    f"Source Memory [{source_memory_uid[:8]}] was selected "
                    "more than once."
                )
            identities.add(identity)


@dataclass(frozen=True)
class FrozenSearchMaterialization:
    """Adapter-validated effect plan with an opaque persistence token."""

    mode: SearchMaterializationMode
    destination_name: str
    source_count: int
    token: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.mode not in {"COPY", "REFERENCE"}:
            raise SearchMaterializationError("A frozen Search plan has invalid mode.")
        if not self.destination_name or self.source_count < 1:
            raise SearchMaterializationError("A frozen Search plan is incomplete.")


@dataclass(frozen=True)
class SearchMaterializationResult:
    """Durable receipt for one newly created Search result Context."""

    mode: SearchMaterializationMode
    context_name: str
    context_uid: str
    checkpoint_uid: str
    item_uids: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.mode not in {"COPY", "REFERENCE"}:
            raise SearchMaterializationError("A Search receipt has invalid mode.")
        if not all((self.context_name, self.context_uid, self.checkpoint_uid)):
            raise SearchMaterializationError("A Search receipt is incomplete.")
        if not self.item_uids or any(not uid for uid in self.item_uids):
            raise SearchMaterializationError("A Search receipt requires created items.")


class SearchMaterializationPort(Protocol):
    """Validate live sources, then publish one exact require-new result."""

    def prepare(
        self,
        request: SearchMaterializationRequest,
    ) -> FrozenSearchMaterialization:
        """Freeze live source, authority, destination, and checkpoint inputs."""

    def materialize(
        self,
        prepared: FrozenSearchMaterialization,
    ) -> SearchMaterializationResult:
        """Publish only the exact prepared plan under its runtime locks."""


def run_search_materialization(
    request: SearchMaterializationRequest,
    *,
    port: SearchMaterializationPort,
) -> SearchMaterializationResult:
    """Run one reviewed write without CLI, TUI, or provider dependencies."""

    prepared = port.prepare(request)
    if (
        prepared.mode != request.mode
        or prepared.destination_name != request.destination_name
        or prepared.source_count != len(request.selected_result_indices)
    ):
        raise SearchMaterializationError(
            "The prepared Search materialization does not match the reviewed request."
        )
    result = port.materialize(prepared)
    if (
        result.mode != request.mode
        or result.context_name != request.destination_name
        or len(result.item_uids) != prepared.source_count
    ):
        raise SearchMaterializationError(
            "Search materialization returned a receipt outside the reviewed request."
        )
    return result


__all__ = [
    "SearchMaterializationError",
    "SearchMaterializationMode",
    "SearchMaterializationPort",
    "SearchMaterializationRequest",
    "SearchMaterializationResult",
    "FrozenSearchMaterialization",
    "run_search_materialization",
]
