"""Operation-owned provider-free exact duplicate discovery and Apply."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from memcommit.authority.access import (
    ContextAccess,
    GrantedReadStore,
    authorized_context_mutation,
    grant_checkpoint_args,
)
from memcommit.context import AutoCheckpoint, Context, Memory, MemoryRef
from memcommit.context_targeting.model import ContextScope
from memcommit.context_targeting.readable_catalog import ReadableContextCatalog
from memcommit.context_targeting.resolution import expand_lexical_context_names
from memcommit.reviewing.direct_item_duplicates import (
    ExactDuplicateGroup,
    ExactDuplicateKind,
    find_exact_duplicate_groups,
)
from memcommit.operations.profile.config import ProfileRegistry
from memcommit.persistence.store import MemoryStore, context_record_digest


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


@dataclass(frozen=True)
class ExactDuplicateContextReport:
    """One independently judged direct Context inside a lexical scope."""

    context_name: str
    context_uid: str
    report: ExactDuplicateReport


@dataclass(frozen=True)
class ExactDuplicateScopeReport:
    """Complete exact-DUP discovery for one direct or lexical Context scope."""

    root_name: str
    include_descendants: bool
    contexts: tuple[ExactDuplicateContextReport, ...]

    @property
    def item_count(self) -> int:
        return sum(frame.report.item_count for frame in self.contexts)

    @property
    def memory_count(self) -> int:
        return sum(frame.report.memory_count for frame in self.contexts)

    @property
    def group_count(self) -> int:
        return sum(len(frame.report.groups) for frame in self.contexts)

    @property
    def duplicate_count(self) -> int:
        return sum(frame.report.duplicate_count for frame in self.contexts)


@dataclass(frozen=True)
class ExactDedupScopeReceipt:
    """Atomic exact-Dedup result across independent direct Context frames."""

    root_name: str
    include_descendants: bool
    contexts: tuple[ExactDedupReceipt, ...]
    operation_uid: str | None = None

    @property
    def groups(self) -> tuple[ExactDuplicateGroup, ...]:
        return tuple(group for receipt in self.contexts for group in receipt.groups)

    @property
    def removed_count(self) -> int:
        return sum(receipt.removed_count for receipt in self.contexts)

    @property
    def checkpoint_uids(self) -> tuple[str, ...]:
        return tuple(
            receipt.checkpoint_uid
            for receipt in self.contexts
            if receipt.checkpoint_uid is not None
        )


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


def find_exact_duplicate_scope(
    active_store: MemoryStore,
    access: ContextAccess,
    *,
    include_descendants: bool,
    registry: ProfileRegistry | None = None,
) -> ExactDuplicateScopeReport:
    """Freeze and inspect each readable lexical Context as an independent frame."""

    if not isinstance(active_store, MemoryStore) or not isinstance(
        access,
        ContextAccess,
    ):
        raise TypeError("Find Duplicates requires a Store and Context access.")
    if type(include_descendants) is not bool:
        raise TypeError("Find Duplicates descendant reach must be a boolean.")

    if not include_descendants:
        context = (
            GrantedReadStore(access, registry=registry).load_direct(access.display_name)
            if access.is_granted
            else access.store.load_direct(access.context_name)
        )
        return ExactDuplicateScopeReport(
            root_name=access.display_name,
            include_descendants=False,
            contexts=(
                ExactDuplicateContextReport(
                    context_name=access.display_name,
                    context_uid=context.uid,
                    report=find_exact_duplicates(context),
                ),
            ),
        )

    catalog = ReadableContextCatalog(
        active_store,
        access,
        registry=registry,
        include_query_routes=False,
    )
    names = expand_lexical_context_names(
        ContextScope.create((access.display_name,), include_descendants=True),
        catalog.list_context_names(),
    )
    return ExactDuplicateScopeReport(
        root_name=access.display_name,
        include_descendants=True,
        contexts=tuple(
            ExactDuplicateContextReport(
                context_name=name,
                context_uid=context.uid,
                report=find_exact_duplicates(context),
            )
            for name in names
            for context in (catalog.load_direct(name),)
        ),
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


def apply_exact_dedup_scope(
    active_store: MemoryStore,
    access: ContextAccess,
    *,
    include_descendants: bool,
    registry: ProfileRegistry | None = None,
) -> ExactDedupScopeReceipt:
    """Apply exact Dedup per Context, publishing a recursive scope atomically."""

    if not isinstance(active_store, MemoryStore) or not isinstance(
        access,
        ContextAccess,
    ):
        raise TypeError("Exact Dedup requires a Store and Context access.")
    if type(include_descendants) is not bool:
        raise TypeError("Exact Dedup descendant reach must be a boolean.")
    if not include_descendants:
        context = access.store.load_direct(access.context_name)
        receipt = apply_exact_dedup(access, context)
        return ExactDedupScopeReceipt(
            root_name=access.display_name,
            include_descendants=False,
            contexts=(receipt,),
        )

    # A recursive mutation must stay inside one Store transaction. Read-only
    # discovery may include granted public descendants, but following that
    # namespace during Apply would cross independently owned authority stores.
    if access.is_granted:
        raise ExactDedupError(
            "Recursive exact Dedup cannot start from a granted Context; "
            "deduplicate that Context exactly."
        )
    readable = ReadableContextCatalog(
        active_store,
        access,
        registry=registry,
        include_query_routes=False,
    )
    granted_descendants = readable.granted_names_below(access.display_name)
    if granted_descendants:
        raise ExactDedupError(
            "Recursive exact Dedup cannot cross granted Context boundaries: "
            + ", ".join(repr(name) for name in granted_descendants)
            + ". Deduplicate those Contexts exactly."
        )

    store = access.store
    catalog_names = tuple(store.list_context_names())
    context_names = expand_lexical_context_names(
        ContextScope.create((access.context_name,), include_descendants=True),
        catalog_names,
    )
    frames = tuple(
        (
            context,
            context_record_digest(context),
            find_exact_duplicate_groups(context),
        )
        for name in context_names
        for context in (store.load_direct(name),)
    )
    changed = tuple(frame for frame in frames if frame[2])
    if not changed:
        return ExactDedupScopeReceipt(
            root_name=access.display_name,
            include_descendants=True,
            contexts=tuple(
                ExactDedupReceipt(context.name, (), None)
                for context, _digest, _groups in frames
            ),
        )

    # Freeze the complete local graph before publication. Supplying every
    # unchanged record as a source binding closes the gap between this inbound
    # Reference scan and Store's locked batch validation: a new reference or
    # namespace member makes the whole command stale before its first write.
    graph = tuple(store.load_direct_context_graph_strict())
    graph_digests = {
        context.name: context_record_digest(context) for context in graph
    }
    absorbed_by_context_uid = {
        context.uid: {
            uid
            for group in groups
            if group.item_kind == "MEMORY"
            for uid in group.absorbed_uids
        }
        for context, _digest, groups in changed
    }
    inbound: list[tuple[str, str]] = []
    for owner in graph:
        for item in owner.iter_items():
            if (
                isinstance(item, MemoryRef)
                and item.target_memory_uid
                in absorbed_by_context_uid.get(item.target_context_uid, set())
            ):
                inbound.append((owner.name, item.uid))
    if inbound:
        locations = ", ".join(
            f"{owner}#{reference_uid[:8]}" for owner, reference_uid in inbound
        )
        raise ExactDedupError(
            "Recursive exact Dedup cannot remove a Memory with an inbound "
            "reference: " + locations
        )

    operation_uid = str(uuid.uuid4())
    membership = [
        {"uid": context.uid, "name": context.name}
        for context, _digest, _groups in changed
    ]
    tree_receipt = {
        "version": 1,
        "operation_uid": operation_uid,
        "root": access.display_name,
        "include_descendants": True,
    }
    total_removed = sum(
        len(group.absorbed_uids)
        for _context, _digest, groups in changed
        for group in groups
    )
    description = (
        f"Removed {total_removed} exact duplicate direct item(s) from "
        f"{len(changed)} Context(s) under '{access.display_name}'"
    )
    entries = []
    changed_names: set[str] = set()
    for context, digest, groups in changed:
        changed_names.add(context.name)
        absorbed_uids = tuple(
            uid for group in groups for uid in group.absorbed_uids
        )
        for uid in absorbed_uids:
            context.remove(uid)
        entries.append(
            (
                context,
                AutoCheckpoint(
                    command="dedup",
                    args={
                        "contract": EXACT_DEDUP_CONTRACT_VERSION,
                        "context": context.name,
                        "recursive": True,
                        "groups": [
                            {
                                "item_kind": group.item_kind,
                                "survivor_uid": group.survivor_uid,
                                "absorbed_uids": list(group.absorbed_uids),
                            }
                            for group in groups
                        ],
                        "dedup_tree": tree_receipt,
                        "command_contexts": membership,
                        **grant_checkpoint_args(access),
                    },
                    description=description,
                ),
                digest,
            )
        )
    unchanged_bindings = tuple(
        (context.name, context.uid, graph_digests[context.name])
        for context in graph
        if context.name not in changed_names
    )
    with authorized_context_mutation(
        access,
        required_permissions=("READ", "DELETE"),
    ):
        checkpoints = store.save_context_command_batch(
            entries,
            source_bindings=unchanged_bindings,
            expected_context_catalog=catalog_names,
        )
    checkpoint_by_name = {
        context.name: checkpoint.uid
        for (context, _checkpoint, _digest), checkpoint in zip(
            entries,
            checkpoints,
            strict=True,
        )
    }
    return ExactDedupScopeReceipt(
        root_name=access.display_name,
        include_descendants=True,
        contexts=tuple(
            ExactDedupReceipt(
                context.name,
                groups,
                checkpoint_by_name.get(context.name),
            )
            for context, _digest, groups in frames
        ),
        operation_uid=operation_uid,
    )


__all__ = [
    "EXACT_DEDUP_CONTRACT_VERSION",
    "ExactDedupError",
    "ExactDedupReceipt",
    "ExactDedupScopeReceipt",
    "ExactDuplicateGroup",
    "ExactDuplicateKind",
    "ExactDuplicateContextReport",
    "ExactDuplicateReport",
    "ExactDuplicateScopeReport",
    "apply_exact_dedup",
    "apply_exact_dedup_scope",
    "find_exact_duplicate_scope",
    "find_exact_duplicate_groups",
    "find_exact_duplicates",
]
