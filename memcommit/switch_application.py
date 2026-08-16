"""Terminal-independent application contract for selecting a current Context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from memcommit.context_locator import (
    is_relative_context_locator,
    resolve_context_locator,
)


class SwitchContextError(RuntimeError):
    """The requested current-Context transition could not be completed."""


@dataclass(frozen=True)
class SwitchContextRequest:
    """One exact selector resolved against one command-start current snapshot."""

    selector: str
    expected_current: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.selector, str) or not self.selector:
            raise SwitchContextError("A Context selector is required.")
        if self.expected_current is not None and (
            not isinstance(self.expected_current, str)
            or not self.expected_current
        ):
            raise SwitchContextError("Expected current Context is invalid.")


@dataclass(frozen=True)
class SwitchContextTarget:
    """Infrastructure-confirmed identity selected by one successful transition."""

    context_name: str
    granted: bool

    def __post_init__(self) -> None:
        if not isinstance(self.context_name, str) or not self.context_name:
            raise SwitchContextError("Selected Context identity is invalid.")
        if type(self.granted) is not bool:
            raise SwitchContextError("Selected Context authority kind is invalid.")


@dataclass(frozen=True)
class SwitchContextResult:
    """Typed current-pointer receipt shared by console presentation routes."""

    previous_context_name: str | None
    context_name: str
    changed: bool
    granted: bool


class SwitchContextPort(Protocol):
    """Authorize, validate, and CAS-publish one canonical current Context."""

    def local_context_exists(self, context_name: str) -> bool:
        """Return whether the active Store owns this exact ordinary Context."""

    def select(
        self,
        *,
        expected_current: str | None,
        context_name: str,
    ) -> SwitchContextTarget:
        """Return the exact identity selected after the current-pointer CAS."""


def resolve_switch_context_name(request: SwitchContextRequest) -> str:
    """Resolve only explicit lexical relative syntax against the frozen current."""

    selector = request.selector
    if not is_relative_context_locator(selector):
        # Bare names remain canonical global names for script compatibility.
        return selector
    current = request.expected_current
    if current is None:
        raise SwitchContextError(
            f"cannot switch to '{selector}': no current context is set."
        )
    if selector == ".." and "/" not in current:
        raise SwitchContextError(
            f"context '{current}' has no namespace parent."
        )
    try:
        return resolve_context_locator(selector, current=current)
    except ValueError as error:
        raise SwitchContextError(str(error)) from error


def switch_context(
    request: SwitchContextRequest,
    *,
    port: SwitchContextPort,
) -> SwitchContextResult:
    """Select one Context through a typed port without CLI or TUI dependencies."""

    context_name = resolve_switch_context_name(request)
    if (
        is_relative_context_locator(request.selector)
        and request.expected_current is not None
        and port.local_context_exists(request.expected_current)
        and not port.local_context_exists(context_name)
    ):
        if request.selector == "..":
            raise SwitchContextError(
                f"namespace parent context '{context_name}' does not exist."
            )
        raise SwitchContextError(f"context '{context_name}' does not exist.")
    target = port.select(
        expected_current=request.expected_current,
        context_name=context_name,
    )
    if target.context_name != context_name:
        raise SwitchContextError(
            "Context selection returned an identity outside the requested target."
        )
    return SwitchContextResult(
        previous_context_name=request.expected_current,
        context_name=context_name,
        changed=request.expected_current != context_name,
        granted=target.granted,
    )
