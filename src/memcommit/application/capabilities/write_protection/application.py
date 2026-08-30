"""Operation-neutral contracts for changing durable write protection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, TypeAlias


ProtectionTargetKind = Literal["CONTEXT", "MEMORY", "PROFILE"]


@dataclass(frozen=True, slots=True)
class ContextProtectionRequest:
    context_locator: str | None
    current_context_name: str | None
    recursive: bool = False


@dataclass(frozen=True, slots=True)
class MemoryProtectionRequest:
    context_locator: str | None
    memory_selector: str
    current_context_name: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.memory_selector, str) or not self.memory_selector:
            raise ValueError("Write-protection Memory selector must be nonblank.")


@dataclass(frozen=True, slots=True)
class ProfileProtectionRequest:
    pass


WriteProtectionRequest: TypeAlias = (
    ContextProtectionRequest | MemoryProtectionRequest | ProfileProtectionRequest
)


@dataclass(frozen=True, slots=True)
class WriteProtectionResult:
    target_kind: ProtectionTargetKind
    protected: bool
    changed_count: int
    total_count: int
    context_name: str | None = None
    memory_uid: str | None = None
    recursive: bool = False

    def __post_init__(self) -> None:
        if self.changed_count < 0 or self.total_count < 1:
            raise ValueError("Write-protection result counts are invalid.")
        if self.changed_count > self.total_count:
            raise ValueError("Write-protection changed count exceeds its target count.")
        if self.target_kind == "PROFILE":
            if self.context_name is not None or self.memory_uid is not None:
                raise ValueError("Profile protection cannot carry Context identity.")
        elif not self.context_name:
            raise ValueError("Context and Memory protection require an owner name.")
        if self.target_kind == "MEMORY" and not self.memory_uid:
            raise ValueError("Memory protection requires one exact Memory UID.")
        if self.target_kind != "MEMORY" and self.memory_uid is not None:
            raise ValueError("Only Memory protection can carry a Memory UID.")

    @property
    def changed(self) -> bool:
        return self.changed_count > 0


class WriteProtectionPort(Protocol):
    def apply(
        self,
        request: WriteProtectionRequest,
        *,
        protected: bool,
    ) -> WriteProtectionResult: ...


def run_write_protection(
    request: WriteProtectionRequest,
    *,
    protected: bool,
    port: WriteProtectionPort,
) -> WriteProtectionResult:
    """Apply one exact Lock or Unlock effect through a shared mechanism."""

    if not isinstance(protected, bool):
        raise TypeError("Write-protection effect must be boolean.")
    if not isinstance(
        request,
        (ContextProtectionRequest, MemoryProtectionRequest, ProfileProtectionRequest),
    ):
        raise TypeError("Write protection requires a typed request.")
    result = port.apply(request, protected=protected)
    if not isinstance(result, WriteProtectionResult):
        raise TypeError("Write-protection port returned an invalid result.")
    if result.protected is not protected:
        raise RuntimeError("Write-protection result reported the wrong effect.")
    return result


__all__ = [
    "ContextProtectionRequest",
    "MemoryProtectionRequest",
    "ProfileProtectionRequest",
    "ProtectionTargetKind",
    "WriteProtectionPort",
    "WriteProtectionRequest",
    "WriteProtectionResult",
    "run_write_protection",
]

