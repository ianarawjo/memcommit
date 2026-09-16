"""Bind ordinary Context Memories to Rationale's structured execution inputs."""

from __future__ import annotations

from importlib.resources.abc import Traversable

from memcommit.application.operations.rationale.model import RationaleRulesError
from memcommit.core.context import Memory
from memcommit.persistence.operation_contexts.repository import (
    load_operation_context,
    read_operation_json,
)

_PROSE_FIELDS = frozenset(
    {
        "content",
        "description",
        "invariant",
        "invariants",
        "provenance",
        "reason",
        "title",
        "warnings",
    }
)


def read_memory_document(resource: Traversable, *, memory_uids: set[str]) -> object:
    """Reconstruct the unchanged execution contract from exact authored text.

    Bindings carry control metadata and prose slots, not another copy of the
    prose. These slots are operation-local bindings, not durable MemoryRefs.
    """
    try:
        context = load_operation_context(resource.joinpath("context.json"))
        binding = read_operation_json(resource.joinpath("bindings.json"))
    except (OSError, ValueError) as error:
        raise RationaleRulesError(
            f"Could not read Rationale Context: {error}"
        ) from error
    if (
        not isinstance(binding, dict)
        or set(binding) != {"schema_version", "document"}
        or type(binding["schema_version"]) is not int
        or binding["schema_version"] != 1
    ):
        raise RationaleRulesError("Invalid Rationale document bindings.")
    used: list[str] = []

    def project(value: object, field: str | None = None) -> object:
        if isinstance(value, dict):
            if "$memory" in value:
                uid = value["$memory"]
                if (
                    set(value) != {"$memory"}
                    or field not in _PROSE_FIELDS
                    or not isinstance(uid, str)
                ):
                    raise RationaleRulesError("Invalid Rationale Memory binding.")
                memory = context.memories.get(uid)
                if not isinstance(memory, Memory) or not memory.content.strip():
                    raise RationaleRulesError(
                        "Rationale prose must bind a nonempty Memory."
                    )
                if uid in memory_uids:
                    raise RationaleRulesError("Duplicate Rationale Memory identity.")
                memory_uids.add(uid)
                used.append(uid)
                return memory.content
            return {key: project(child, key) for key, child in value.items()}
        if isinstance(value, list):
            return [project(child, field) for child in value]
        if field in _PROSE_FIELDS and isinstance(value, str) and value.strip():
            raise RationaleRulesError(f"Rationale {field} must bind a Memory.")
        return value

    projected = project(binding["document"])
    # Reject unbound prose or a conflicting order rather than displaying one
    # set of instructions while silently executing a different set.
    if used != context.order:
        raise RationaleRulesError(
            "Rationale bindings must cover Context Memories in order."
        )
    return projected
