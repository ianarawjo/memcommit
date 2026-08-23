"""Provider-free role-aware exact duplicate removal for one direct Context."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.authority.access import (
    ContextAccess,
    authorized_context_mutation,
    grant_checkpoint_args,
)
from memcommit.context import AutoCheckpoint, Context, Memory, MemoryRef
from memcommit.direct_item_duplicates import (
    ExactDuplicateGroup,
    ExactDuplicateKind,
    find_exact_duplicate_groups,
)
from memcommit.store import MemoryStore, context_record_digest


EXACT_DEDUP_CONTRACT_VERSION = "exact-dedup-v2"


class ExactDedupError(RuntimeError):
    """The exact duplicate frame cannot be applied safely."""


@dataclass(frozen=True)
class ExactDuplicateReport:
    """Complete provider-free role-aware exact discovery for one Context."""

    memory_count: int
    groups: tuple[ExactDuplicateGroup, ...]
    item_count: int = 0

    @property
    def duplicate_count(self) -> int:
        return sum(len(group.absorbed_uids) for group in self.groups)


@dataclass(frozen=True)
class ExactDedupReceipt:
    """Result of one direct exact-dedup invocation."""

    context_name: str
    groups: tuple[ExactDuplicateGroup, ...]
    checkpoint_uid: str | None

    @property
    def removed_count(self) -> int:
        return sum(len(group.absorbed_uids) for group in self.groups)


def find_exact_duplicates(context: Context) -> ExactDuplicateReport:
    """Return every same-role exact group without provider access or mutation."""

    if not isinstance(context, Context):
        raise TypeError("Find Duplicates requires one Context.")
    memory_count = sum(1 for item in context.iter_items() if isinstance(item, Memory))
    return ExactDuplicateReport(
        memory_count=memory_count,
        groups=find_exact_duplicate_groups(context),
        item_count=len(context.ordered_uids()),
    )


def _inbound_references(
    store: MemoryStore,
    *,
    context_uid: str,
    absorbed_uids: set[str],
) -> tuple[tuple[str, str], ...]:
    inbound: list[tuple[str, str]] = []
    for context in store.load_direct_context_graph_strict():
        for item in context.iter_items():
            if (
                isinstance(item, MemoryRef)
                and item.target_context_uid == context_uid
                and item.target_memory_uid in absorbed_uids
            ):
                inbound.append((context.name, item.uid))
    return tuple(inbound)


def apply_exact_dedup(
    access: ContextAccess,
    context: Context,
) -> ExactDedupReceipt:
    """Remove every later same-role exact occurrence atomically."""

    if not isinstance(access, ContextAccess) or not isinstance(context, Context):
        raise TypeError("Exact Dedup requires frozen Context access and content.")
    groups = find_exact_duplicate_groups(context)
    if not groups:
        return ExactDedupReceipt(access.display_name, (), None)

    expected_digest = context_record_digest(context)
    absorbed_uids = tuple(uid for group in groups for uid in group.absorbed_uids)
    absorbed_memory_uids = {
        uid
        for group in groups
        if group.item_kind == "MEMORY"
        for uid in group.absorbed_uids
    }
    with authorized_context_mutation(
        access,
        required_permissions=("READ", "DELETE"),
    ):
        # Reference validation and deletion share the command lock so no new
        # live pointer can appear between the safety check and publication.
        with access.store._command_write_lock():  # noqa: SLF001
            current = access.store.load_for_update(access.context_name)
            if (
                current.uid != context.uid
                or context_record_digest(current) != expected_digest
            ):
                raise ExactDedupError(
                    "The exact Dedup Context changed before removal; nothing was written."
                )
            inbound = _inbound_references(
                access.store,
                context_uid=context.uid,
                absorbed_uids=absorbed_memory_uids,
            )
            if inbound:
                locations = ", ".join(
                    f"{owner}#{reference_uid[:8]}" for owner, reference_uid in inbound
                )
                raise ExactDedupError(
                    "Exact Dedup cannot remove a Memory with an inbound reference: "
                    + locations
                )
            for uid in absorbed_uids:
                current.remove(uid)
            checkpoint = access.store._save_command_locked(  # noqa: SLF001
                current,
                AutoCheckpoint(
                    command="dedup",
                    args={
                        "contract": EXACT_DEDUP_CONTRACT_VERSION,
                        "context": access.display_name,
                        "groups": [
                            {
                                "item_kind": group.item_kind,
                                "survivor_uid": group.survivor_uid,
                                "absorbed_uids": list(group.absorbed_uids),
                            }
                            for group in groups
                        ],
                        **grant_checkpoint_args(access),
                    },
                    description=(
                        f"Removed {len(absorbed_uids)} exact duplicate direct "
                        f"item(s) from '{access.display_name}'"
                    ),
                ),
                expected_context_digest=expected_digest,
            )
            if checkpoint is None:
                raise ExactDedupError(
                    "Exact Dedup removed items without recording a checkpoint."
                )
    return ExactDedupReceipt(access.display_name, groups, checkpoint.uid)


__all__ = [
    "EXACT_DEDUP_CONTRACT_VERSION",
    "ExactDedupError",
    "ExactDedupReceipt",
    "ExactDuplicateGroup",
    "ExactDuplicateKind",
    "ExactDuplicateReport",
    "apply_exact_dedup",
    "find_exact_duplicate_groups",
    "find_exact_duplicates",
]
