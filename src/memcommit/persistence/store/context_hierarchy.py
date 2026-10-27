"""Prepare and check the complete Context hierarchy before Store publication."""

from collections.abc import Iterable
from dataclasses import replace
from uuid import uuid4

from memcommit.models.context import Context
from .checkpoint.requests import AutoCheckpointRequest
from .lookup.context_names import list_context_and_ancestor_names


def prepare_missing_ancestor_contexts(
    contexts: Iterable[Context], existing_names: Iterable[str]
) -> tuple[Context, ...]:
    contexts = tuple(contexts)
    available_names = set(existing_names) | {context.name for context in contexts}
    ancestors: list[Context] = []
    for context in contexts:
        for name in list_context_and_ancestor_names(context.name)[:-1]:
            if name not in available_names:
                ancestors.append(Context.create(name))
                available_names.add(name)
    return tuple(ancestors)


def validate_context_hierarchy(context_names: Iterable[str]) -> None:
    names = set(context_names)
    for name in sorted(names):
        for ancestor in list_context_and_ancestor_names(name)[:-1]:
            if ancestor not in names:
                raise ValueError(
                    f"Context '{name}' requires its ancestor Context '{ancestor}'."
                )


def prepare_context_creation_entries(
    entries: Iterable[tuple[Context, AutoCheckpointRequest | None]],
    existing_names: Iterable[str],
    *,
    current_before: str | None,
    current_after: str | None,
) -> tuple[tuple[Context, AutoCheckpointRequest | None], ...]:
    entries = tuple(entries)
    existing_names = set(existing_names)
    parents = prepare_missing_ancestor_contexts(
        (context for context, _ in entries), existing_names
    )
    template = next((request for _, request in entries if request is not None), None)
    entries = tuple((parent, template) for parent in parents) + entries
    created = tuple(
        context for context, _ in entries if context.name not in existing_names
    )
    # Ground owns root-scoped history; outer ancestors must not widen its lanes.
    # Other commands retain only new identities; reused parents never belong to Undo.
    if (
        template is None
        or template.command == "ground-init"
        or not created
        or not (parents or template.command == "init")
    ):
        return entries
    membership = [{"uid": context.uid, "name": context.name} for context in created]
    receipt = {
        "operation_uid": str(uuid4()),
        "contexts": membership,
        "current_before": current_before,
        "current_after": current_after,
    }
    return tuple(
        (
            context,
            replace(
                request or template,
                command_details={
                    **(request or template).command_details,
                    "context_creation_batch": receipt,
                    "command_contexts": membership,
                },
            )
            if context.name not in existing_names
            else request,
        )
        for context, request in entries
    )
