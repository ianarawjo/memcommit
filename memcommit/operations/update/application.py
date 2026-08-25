"""Operation-owned deterministic application of one staged Update plan."""
from __future__ import annotations

from dataclasses import dataclass

from memcommit.context import Context, Memory, MemoryRef, QueryContextRef
from memcommit.update import (
    AddOperation,
    EditOperation,
    RemoveOperation,
    UpdateError,
    UpdateSession,
)


class UpdateApplicationError(UpdateError):
    """A staged update cannot be applied to the supplied target graph."""


@dataclass(frozen=True)
class AppliedOwner:
    """One affected direct owner and its detached post-update record."""

    owner_context_uid: str
    owner_context_name: str
    post_image: Context


@dataclass(frozen=True)
class UpdateApplicationResult:
    """Detached post-images in canonical target-graph order."""

    session_uid: str
    target_uid: str
    target_name: str
    affected_owners: tuple[AppliedOwner, ...]

    @property
    def post_images(self) -> tuple[Context, ...]:
        """Return just the detached Context records in save order."""
        return tuple(owner.post_image for owner in self.affected_owners)


def _walk_target_contexts(root: Context) -> tuple[Context, ...]:
    """Visit explicitly embedded Contexts in their canonical direct order."""
    contexts: list[Context] = []
    visited: set[str] = set()

    def visit(context: Context) -> None:
        if context.uid in visited:
            return
        visited.add(context.uid)
        contexts.append(context)
        for item in context.iter_items():
            if isinstance(item, Context):
                visit(item)

    visit(root)
    return tuple(contexts)


def _detached_direct_copy(context: Context) -> Context:
    """Copy one persisted owner record without retaining live graph objects."""
    post_image = Context.from_dict(context.to_dict())
    # A later persistence boundary may use this load digest for optimistic
    # concurrency. Copying the immutable token does not couple the records.
    post_image._store_digest = context._store_digest
    return post_image


def _read_only_type(item: object) -> str:
    if isinstance(item, MemoryRef):
        return "MemoryRef"
    if isinstance(item, QueryContextRef):
        return "QueryContextRef"
    if isinstance(item, Context):
        return "embedded Context"
    return type(item).__name__


def prepare_update_application(
    session: UpdateSession,
    target: Context,
) -> UpdateApplicationResult:
    """Preflight a staged plan and return detached affected-owner post-images.

    The caller is responsible for proving that the session's recorded source
    and target base fingerprints are fresh. This helper still binds the plan
    to the supplied target root and validates every operation against the
    complete in-memory target graph before constructing any post-image.

    Neither success nor failure mutates ``target`` or any embedded Context.
    Persistence, multi-owner locking, checkpoints, and application receipts
    belong to the caller's transaction boundary.
    """
    if not isinstance(session, UpdateSession):
        raise TypeError("Expected an UpdateSession.")
    if not isinstance(target, Context):
        raise TypeError("Expected a target Context.")
    if session.status != "staged":
        raise UpdateApplicationError(
            "Update application requires a staged update session."
        )
    if (
        session.target_uid != target.uid
        or session.target_name != target.name
    ):
        raise UpdateApplicationError(
            "The staged update target does not match the supplied Context."
        )

    target_contexts = _walk_target_contexts(target)
    context_by_uid = {context.uid: context for context in target_contexts}
    operations_by_owner: dict[
        str,
        list[EditOperation | AddOperation | RemoveOperation],
    ] = {}
    operation_targets: set[tuple[str, str]] = set()

    # Validate the whole plan against the unchanged graph first. In
    # particular, a later invalid operation must not leave an earlier owner
    # partially updated.
    for operation in session.operations:
        if not isinstance(
            operation,
            (EditOperation, AddOperation, RemoveOperation),
        ):
            raise UpdateApplicationError(
                "The staged update contains an unsupported operation."
            )

        owner = context_by_uid.get(operation.owner_context_uid)
        if owner is None:
            raise UpdateApplicationError(
                "The staged update names a target Context that is not in "
                "the supplied target graph."
            )
        if owner.name != operation.owner_context_name:
            raise UpdateApplicationError(
                "The staged update owner identity does not match the target "
                "Context graph."
            )

        identity = (owner.uid, operation.memory_uid)
        if identity in operation_targets:
            raise UpdateApplicationError(
                "The staged update targets the same owner item more than once."
            )
        operation_targets.add(identity)

        current = owner.memories.get(operation.memory_uid)
        if isinstance(operation, EditOperation):
            if current is None:
                raise UpdateApplicationError(
                    f"Edit target '{operation.memory_uid}' does not exist in "
                    f"Context '{owner.name}'."
                )
            if not isinstance(current, Memory):
                raise UpdateApplicationError(
                    f"Edit target '{operation.memory_uid}' is a "
                    f"{_read_only_type(current)} and cannot be modified."
                )
            if current.content != operation.old_content:
                raise UpdateApplicationError(
                    f"Edit target '{operation.memory_uid}' no longer matches "
                    "the staged old content."
                )
        elif isinstance(operation, RemoveOperation):
            if current is None:
                raise UpdateApplicationError(
                    f"Removal target '{operation.memory_uid}' does not exist "
                    f"in Context '{owner.name}'."
                )
            if not isinstance(current, Memory):
                raise UpdateApplicationError(
                    f"Removal target '{operation.memory_uid}' is a "
                    f"{_read_only_type(current)} and cannot be removed."
                )
            if current.content != operation.old_content:
                raise UpdateApplicationError(
                    f"Removal target '{operation.memory_uid}' no longer "
                    "matches the staged old content."
                )
        elif current is not None:
            # Context.add replaces an existing direct uid, so every collision
            # must fail instead of silently converting an ADD into an edit.
            raise UpdateApplicationError(
                f"Addition uid '{operation.memory_uid}' already exists in "
                f"Context '{owner.name}'."
            )

        operations_by_owner.setdefault(owner.uid, []).append(operation)

    affected: list[AppliedOwner] = []
    for owner in target_contexts:
        owner_operations = operations_by_owner.get(owner.uid)
        if not owner_operations:
            continue
        post_image = _detached_direct_copy(owner)
        for operation in owner_operations:
            if isinstance(operation, EditOperation):
                post_image.replace(
                    Memory(
                        uid=operation.memory_uid,
                        content=operation.new_content,
                    )
                )
            elif isinstance(operation, RemoveOperation):
                post_image.remove(operation.memory_uid)
            else:
                post_image.add(
                    Memory(
                        uid=operation.memory_uid,
                        content=operation.new_content,
                    )
                )
        affected.append(
            AppliedOwner(
                owner_context_uid=owner.uid,
                owner_context_name=owner.name,
                post_image=post_image,
            )
        )

    return UpdateApplicationResult(
        session_uid=session.uid,
        target_uid=target.uid,
        target_name=target.name,
        affected_owners=tuple(affected),
    )
