"""Frozen Memory projections and selected endpoint values; no screen configuration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class EndpointSetupMemory:
    """One frozen direct Memory projection offered by an endpoint role."""

    context_name: str
    uid: str
    preview: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.context_name, str)
            or not self.context_name
            or any(character in self.context_name for character in "\r\n")
            or not isinstance(self.uid, str)
            or not self.uid
            or any(character in self.uid for character in "\r\n")
            or not isinstance(self.preview, str)
        ):
            raise ValueError(
                "Endpoint setup Memories require stable Context, uid, and preview text."
            )


@dataclass(frozen=True)
class EndpointSetupValue:
    """One exact endpoint selected in a completed setup draft."""

    role_uid: str
    context_name: str
    include_descendants: bool = False
    memory_uid: str | None = None
    create: bool = False
    inline_memory_content: str | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.role_uid, str)
            or not self.role_uid
            or not isinstance(self.context_name, str)
            or type(self.include_descendants) is not bool
            or type(self.create) is not bool
            or (
                self.memory_uid is not None
                and (
                    not isinstance(self.memory_uid, str)
                    or not self.memory_uid
                    or any(character in self.memory_uid for character in "\r\n")
                )
            )
            or (
                self.inline_memory_content is not None
                and (
                    not isinstance(self.inline_memory_content, str)
                    or not self.inline_memory_content.strip()
                    or any(
                        character in self.inline_memory_content for character in "\r\n"
                    )
                )
            )
        ):
            raise ValueError("Endpoint setup values require one exact typed range.")
        if self.inline_memory_content is None and not self.context_name:
            raise ValueError("A Context endpoint requires one exact Context name.")
        if self.inline_memory_content is not None and (
            self.context_name
            or self.include_descendants
            or self.memory_uid is not None
            or self.create
        ):
            raise ValueError(
                "Inline Memory input cannot retain Context range or creation state."
            )
        if self.memory_uid is not None and self.include_descendants:
            raise ValueError(
                "Endpoint setup values cannot focus one Memory across descendants."
            )
        if self.create and (self.include_descendants or self.memory_uid is not None):
            raise ValueError(
                "A new endpoint cannot retain descendant or Memory focus state."
            )

    @property
    def source_type(self) -> Literal["CONTEXT", "STORED_MEMORY", "INLINE_MEMORY"]:
        if self.inline_memory_content is not None:
            return "INLINE_MEMORY"
        if self.memory_uid is not None:
            return "STORED_MEMORY"
        return "CONTEXT"


@dataclass(frozen=True)
class EndpointSetupDraft:
    """Process-local operation shape returned without durable mutation."""

    mode_uid: str
    values: tuple[EndpointSetupValue, ...]

    def value(self, role_uid: str) -> EndpointSetupValue:
        try:
            return next(value for value in self.values if value.role_uid == role_uid)
        except StopIteration as error:
            raise KeyError(role_uid) from error


DraftValidator = Callable[[EndpointSetupDraft], str | None]
