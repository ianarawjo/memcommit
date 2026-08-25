"""Typed ordinary-local Context-or-checkpoint operand resolution."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

from memcommit.context_locator import (
    resolve_context_locator,
    suggest_context_locators,
)
from memcommit.name_suggestions import did_you_mean_suffix
from memcommit.context_targeting.memory_focus import is_memory_uid_selector
from memcommit.context_targeting.model import CheckpointTarget, ContextTarget
from memcommit.uid_locator import resolve_exact_or_unique_uid


class LocalCheckpointCatalog(Protocol):
    """The narrow store surface needed to freeze checkpoint identities."""

    def list_context_names(self) -> list[str]: ...

    def list_checkpoints(self, name: str) -> list[dict]: ...


def freeze_local_checkpoint_targets(
    store: LocalCheckpointCatalog,
    *,
    context_names: Sequence[str] | None = None,
) -> tuple[CheckpointTarget, ...]:
    """Freeze exact checkpoint coordinates without loading Context contents."""

    names = tuple(context_names) if context_names is not None else tuple(
        store.list_context_names()
    )
    targets: list[CheckpointTarget] = []
    for name in names:
        for record in store.list_checkpoints(name):
            if not isinstance(record, Mapping):
                raise ValueError(f"Context '{name}' has an invalid checkpoint record.")
            checkpoint_uid = record.get("uid")
            if not isinstance(checkpoint_uid, str) or not checkpoint_uid:
                raise ValueError(f"Context '{name}' has a checkpoint without a UID.")
            targets.append(CheckpointTarget(name, checkpoint_uid))
    return tuple(targets)


def resolve_local_checkpoint_target(
    store: LocalCheckpointCatalog,
    selector: str,
    *,
    context_names: Sequence[str] | None = None,
) -> CheckpointTarget:
    """Resolve one exact or unambiguous prefix across frozen local histories."""

    return resolve_exact_or_unique_uid(
        freeze_local_checkpoint_targets(store, context_names=context_names),
        selector,
        uid=lambda target: target.checkpoint_uid,
        label="Checkpoint",
    )


def resolve_local_context_checkpoint_target(
    store: LocalCheckpointCatalog,
    operand: str,
    *,
    current: str | None,
) -> ContextTarget | CheckpointTarget:
    """Resolve one overloaded Context-or-checkpoint operand without guessing.

    Relative syntax is always a Context locator. Bare UUID-shaped values may
    select a checkpoint only when no exact Context with the same spelling is
    present and the checkpoint prefix is unique across the frozen local
    catalog.
    """

    names = tuple(store.list_context_names())
    context_name = resolve_context_locator(operand, current=current)
    context_exists = context_name in names
    relative = operand in {".", ".."} or operand.startswith(("./", "../"))
    if relative:
        if context_exists:
            return ContextTarget(context_name)
        raise ValueError(f"Context '{context_name}' is unavailable.")

    targets = (
        freeze_local_checkpoint_targets(store, context_names=names)
        if is_memory_uid_selector(operand)
        else ()
    )
    checkpoint_matches = tuple(
        target for target in targets if target.checkpoint_uid.startswith(operand)
    )
    if context_exists and checkpoint_matches:
        raise ValueError(
            f"Diff target '{operand}' matches both Context '{context_name}' and "
            "a checkpoint; disambiguate with --context or --checkpoint."
        )
    if context_exists:
        return ContextTarget(context_name)
    if checkpoint_matches:
        return resolve_exact_or_unique_uid(
            targets,
            operand,
            uid=lambda target: target.checkpoint_uid,
            label="Checkpoint",
        )
    suggestions = suggest_context_locators(
        operand,
        current=current,
        available_names=names,
    )
    raise ValueError(
        f"Diff target '{operand}' is neither an existing Context nor an "
        "available checkpoint UID."
        + did_you_mean_suffix(suggestions)
    )
