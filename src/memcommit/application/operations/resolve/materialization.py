"""Collapse reviewed Context changes into one cumulative Memory plan."""

from __future__ import annotations

from memcommit.application.operations.merge.analysis.candidate import digest
from memcommit.application.operations.update.model import (
    AddOperation,
    EditOperation,
    RemoveOperation,
    UpdatePlan,
)
from memcommit.core.context import Context, Memory

from .model import ResolveError


def compose_plan(before: Context, after: Context, plans, *, refs=None) -> UpdatePlan:
    """Collapse sequential edits to one operation per original owner/Memory."""
    by_uid = {}
    for plan in plans:
        if plan is not None:
            for operation in plan.operations:
                by_uid.setdefault(operation.memory_uid, []).append(operation)
    operations = []
    for uid in dict.fromkeys((*before.ordered_uids(), *after.ordered_uids())):
        old, new = before.memories.get(uid), after.memories.get(uid)
        if not isinstance(old, Memory) and not isinstance(new, Memory):
            continue
        if (
            old is not None
            and not isinstance(old, Memory)
            or new is not None
            and not isinstance(new, Memory)
        ):
            raise ResolveError("Memory planning cannot replace a pointer.")
        parents = tuple(
            dict.fromkeys(
                ref
                for operation in by_uid.get(uid, ())
                for ref in operation.source_refs
            )
        )
        parents = parents or (refs or {}).get(uid, ())
        arguments = dict(
            owner_context_uid=before.uid,
            owner_context_name=before.name,
            memory_uid=uid,
            source_refs=parents,
            reason="Apply the reviewed issue decisions.",
        )
        if old is None:
            operations.append(AddOperation(**arguments, new_content=new.content))
        elif new is None:
            operations.append(RemoveOperation(**arguments, old_content=old.content))
        elif old.content != new.content or old.to_dict() != new.to_dict():
            operations.append(
                EditOperation(
                    **arguments, old_content=old.content, new_content=new.content
                )
            )
    return UpdatePlan(
        uid="resolve-" + digest([operation.to_dict() for operation in operations]),
        target_uid=before.uid,
        target_name=before.name,
        operations=tuple(operations),
    )
