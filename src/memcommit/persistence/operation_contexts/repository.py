"""Discover and decode ordinary Context files shipped with operations."""

from __future__ import annotations

import json
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path
from uuid import UUID

from memcommit.core.context import Context


def _unique_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}.")
        result[key] = value
    return result


def read_operation_json(resource: Traversable) -> object:
    return json.loads(
        resource.read_text(encoding="utf-8"), object_pairs_hook=_unique_keys
    )


def _uuid(value: object) -> None:
    if not isinstance(value, str) or str(UUID(value)) != value:
        raise ValueError("Operation Context identity must be a canonical UUID.")


def load_operation_context(
    resource: Traversable, *, expected_name: str | None = None
) -> Context:
    """Read direct state only; persisted references never authorize extra reads."""
    data = read_operation_json(resource)
    if not isinstance(data, dict) or set(data) != {"uid", "name", "memories", "order"}:
        raise ValueError("Invalid operation Context record.")
    _uuid(data["uid"])
    name, items, order = data["name"], data["memories"], data["order"]
    if (
        not isinstance(name, str)
        or not name
        or (expected_name is not None and name != expected_name)
    ):
        raise ValueError("Operation Context name does not match its resource location.")
    if not isinstance(items, dict) or not isinstance(order, list):
        raise ValueError("Invalid operation Context items or order.")
    if (
        any(not isinstance(uid, str) for uid in order)
        or len(order) != len(set(order))
        or set(order) != set(items)
    ):
        raise ValueError("Operation Context order must cover each direct item once.")
    for uid, item in items.items():
        _uuid(uid)
        if not isinstance(item, dict) or item.get("uid") != uid:
            raise ValueError("Operation Context item identity does not match its key.")
        if item.get("type") == "memory" and not isinstance(item.get("content"), str):
            raise ValueError("Memory content must be text.")
    try:
        context = Context.from_dict(data)
        # The general decoder tolerates legacy omissions. Packaged authored
        # data must not silently lose unknown fields, items, or relationships.
        if context.to_dict() != data:
            raise ValueError(
                "Operation Context contains unsupported or incomplete items."
            )
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError("Invalid operation Context structure.") from error
    return context


class OperationContextRepository:
    """A frozen package-resource catalog; construction only scans file names."""

    def __init__(self, root: Traversable | None = None):
        self.root = (
            root
            if root is not None
            else resources.files("memcommit.application.operations")
        )
        if isinstance(self.root, Path):
            self.root = self.root.resolve()
        self._resources: dict[str, Traversable] = {}

        def visit(directory: Traversable, parts: tuple[str, ...]) -> None:
            for child in sorted(directory.iterdir(), key=lambda item: item.name):
                # A source checkout may contain symlinks; neither recursive
                # discovery nor a resource read should escape the package.
                if isinstance(child, Path) and child.is_symlink():
                    continue
                if child.is_dir() and child.name != "__pycache__":
                    visit(child, (*parts, child.name))
                elif child.name == "context.json" and child.is_file() and parts:
                    self._resources["/".join(parts)] = child

        visit(self.root, ())

    def context_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._resources))

    def load_context(self, name: str) -> Context:
        resource = self._resources[name]
        if isinstance(resource, Path) and resource.resolve() != resource.absolute():
            raise ValueError("Operation Context resource changed to a symbolic link.")
        return load_operation_context(resource, expected_name=name)

    def resource_location(self, name: str) -> str:
        resource = self._resources[name]
        return str(resource.absolute()) if isinstance(resource, Path) else str(resource)
