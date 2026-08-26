"""Operation-neutral inheritance state for one exact Context-name draft."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence


def _one_line(value: str, *, label: str, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{label} must be text.")
    if any(character in value for character in "\r\n"):
        raise ValueError(f"{label} must stay on one line.")
    if not allow_empty and not value.strip():
        raise ValueError(f"{label} must be nonempty text.")
    return value


def infer_context_parent(
    exact_name: str,
    context_names: Sequence[str],
    *,
    fallback: str | None = None,
) -> str:
    """Return the nearest existing lexical parent for one exact name."""

    value = _one_line(exact_name, label="Context name")
    names = tuple(context_names)
    if not names:
        raise ValueError("Context parent inference requires a Context catalog.")
    if any(not isinstance(name, str) or not name for name in names):
        raise ValueError("Context parent inference received an invalid catalog.")
    ancestors = tuple(name for name in names if value.startswith(name + "/"))
    if ancestors:
        return max(ancestors, key=lambda name: (name.count("/"), len(name)))
    if fallback in names:
        assert fallback is not None
        return fallback
    if value in names:
        return value
    return names[0]


@dataclass
class ContextNameDraftState:
    """Keep automatic placement inheritance separate from direct ownership.

    Suggestions and parent choices may rewrite an untouched exact name. The
    first person-authored edit makes the exact field authoritative; later
    automatic inheritance must then leave it alone.
    """

    exact_name: str
    parent_name: str | None = None
    edited: bool = False

    def __post_init__(self) -> None:
        self.exact_name = _one_line(self.exact_name, label="Context name")
        if self.parent_name is not None:
            self.parent_name = _one_line(
                self.parent_name,
                label="Parent Context",
            )

    def record_direct_edit(self, value: str) -> str:
        """Adopt one person-authored value, including a temporarily empty one."""

        self.exact_name = _one_line(
            value,
            label="Context name",
            allow_empty=True,
        )
        self.edited = True
        return self.exact_name

    def replace_programmatically(self, value: str) -> str:
        """Synchronize control text without changing direct-edit ownership."""

        self.exact_name = _one_line(value, label="Context name")
        return self.exact_name

    def inherit_suggestion(
        self,
        value: str,
        *,
        parent_name: str | None = None,
    ) -> str:
        """Refresh an untouched suggestion and its inferred parent."""

        candidate = _one_line(value, label="Context name")
        parent = (
            _one_line(parent_name, label="Parent Context")
            if parent_name is not None
            else None
        )
        if self.edited:
            return self.exact_name
        self.exact_name = candidate
        if parent is not None:
            self.parent_name = parent
        return self.exact_name

    def choose_parent(self, parent_name: str) -> str:
        """Select a parent and reparent only an untouched exact draft."""

        parent = _one_line(parent_name, label="Parent Context")
        previous_parent = self.parent_name
        self.parent_name = parent
        if self.edited:
            return self.exact_name

        value = self.exact_name.strip()
        if not value:
            raise ValueError("Context name must be nonempty text.")
        if parent == value:
            return self.exact_name
        prefix = f"{previous_parent}/" if previous_parent else ""
        suffix = (
            value[len(prefix) :]
            if prefix and value.startswith(prefix)
            else value.rsplit("/", 1)[-1]
        )
        if not suffix:
            raise ValueError("Context name must end with an exact name segment.")
        self.exact_name = f"{parent}/{suffix}"
        return self.exact_name
