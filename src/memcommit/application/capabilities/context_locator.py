"""Application-level lexical resolution for existing-Context operands."""
from __future__ import annotations

from collections.abc import Sequence

from memcommit.application.capabilities.name_suggestions import (
    canonical_name_suggestions,
)


def is_relative_context_locator(locator: str) -> bool:
    """Return whether a locator explicitly opts into current-relative lookup."""
    return locator in {".", ".."} or locator.startswith(("./", "../"))


def resolve_context_locator(
    locator: str,
    *,
    current: str | None,
) -> str:
    """Resolve one explicit relative locator to a canonical Context name.

    Bare names remain global for compatibility. Resolution is lexical over
    slash-delimited Context names and never consults the shell working
    directory, the filesystem, or Context embedding relationships.
    """
    if not isinstance(locator, str) or not locator:
        raise ValueError("Context locator must be a non-empty string.")
    if not is_relative_context_locator(locator):
        return locator
    if not isinstance(current, str) or not current:
        raise ValueError(
            f"relative Context selector '{locator}' requires a current "
            "Context."
        )

    parts = current.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError(
            "Current Context name is not a canonical namespace name."
        )

    selector_parts = locator.split("/")
    # A single trailing slash is spelling, not another namespace segment.
    # Repeated or interior empty segments remain invalid instead of being
    # silently normalized into a different user request.
    if selector_parts[-1] == "":
        selector_parts.pop()
    if not selector_parts or any(part == "" for part in selector_parts):
        raise ValueError(
            f"relative Context selector '{locator}' contains an empty segment."
        )

    for part in selector_parts:
        if part == ".":
            continue
        if part == "..":
            if not parts:
                raise ValueError(
                    f"relative Context selector '{locator}' escapes above the "
                    "namespace root."
                )
            parts.pop()
            continue
        parts.append(part)

    if not parts:
        raise ValueError(
            f"relative Context selector '{locator}' resolves to the namespace "
            "root, which is not a Context."
        )
    return "/".join(parts)


def suggest_context_locators(
    locator: str,
    *,
    current: str | None,
    available_names: Sequence[str],
) -> tuple[str, ...]:
    """Suggest existing canonical Contexts after exact interpretation fails.

    This is deliberately separate from :func:`resolve_context_locator`:
    similarity can improve a failure receipt, but it must never select or load
    a Context. Relative input is compared in its resolved canonical namespace.
    """

    candidate = resolve_context_locator(locator, current=current)
    names = tuple(dict.fromkeys(available_names))
    if any(not isinstance(name, str) or not name for name in names):
        raise ValueError("Context suggestion catalog contains an invalid name.")
    return canonical_name_suggestions(
        candidate,
        {name: name for name in names},
    )


__all__ = [
    "is_relative_context_locator",
    "resolve_context_locator",
    "suggest_context_locators",
]
