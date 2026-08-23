"""
    In-memory operations on Context objects.
    No disk I/O — callers persist via MemoryStore.save(ctx) when needed.

    Semantic operations require either an LLMClient or a validated one-shot
    prompt provider. Newer provider-backed implementations live in focused
    modules and retain thin wrappers here as the public in-memory API.

    Public API:
        import memcommit.ops as ops
        mem  = ops.add(ctx, "some information")
        ops.embed(child_ctx, parent_ctx)

        # Semantic — forget candidate generation (non-mutating):
        proposals, history = ops.forget(ctx, "elephants", llm_client)
        proposals, history = ops.revise_forget("keep only the edit", llm_client, history, ctx)
        from memcommit.semantic.changes import apply_changes
        apply_changes(ctx, proposals)
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Callable

from memcommit.context import Context, Information, Memory, MemoryRef, QueryContextRef
from memcommit.context_naming import validate_portable_context_name

if TYPE_CHECKING:
    from memcommit.atomize import (
        AtomizeImpactReport,
        AtomizeProvider,
    )
    from memcommit.findings import (
        AmbiguityReport,
        ConflictReport,
        DuplicateReport,
        FindingsProvider,
    )
    from memcommit.exact_dedup import ExactDuplicateReport
    from memcommit.search import PromptProvider, SearchMatch
    from memcommit.semantic.llm import LLMClient
    from memcommit.semantic.changes import ProposedChange
    from memcommit.translate import (
        DerivedTranslationApplyResult,
        TranslationApplyResult,
        TranslationPlan,
        TranslationProvider,
    )


# ---------------------------------------------------------------------------
# Structural operations (no LLM)
# ---------------------------------------------------------------------------


def init(name: str) -> Context:
    """Create a new, empty Context. Does not persist — caller must store.save(ctx)."""
    return Context(
        uid=str(uuid.uuid4()),
        name=validate_portable_context_name(name),
    )


def add(ctx: Context, content: str) -> Memory:
    """Add a new Memory to ctx. Returns the created Memory."""
    result = ctx.add(content)
    assert isinstance(result, Memory)
    return result


def add_many(ctx: Context, contents: list[str]) -> list[Memory]:
    """Append multiple Memories in input order and return the created records."""
    memories = [Memory(uid=str(uuid.uuid4()), content=content) for content in contents]
    for memory in memories:
        ctx.add(memory)
    return memories


def resolve_direct_memory(ctx: Context, selector: str) -> Memory:
    """Resolve one ordinary directly owned Memory with Edit's prefix grammar."""

    matches = [uid for uid in ctx.memories if uid.startswith(selector)]
    if not matches:
        raise KeyError(f"No item with uid starting with '{selector}'.")
    if len(matches) > 1:
        raise ValueError(
            f"Ambiguous prefix '{selector}' matches {len(matches)} items: "
            + ", ".join(uid[:8] for uid in matches)
        )

    item = ctx.memories[matches[0]]
    if not isinstance(item, Memory):
        raise TypeError(
            f"'{selector}' is not a Memory directly owned by this Context — "
            "cannot edit."
        )
    return item


def edit(ctx: Context, selector: str, content: str) -> Memory:
    """
    Replace one directly owned Memory's content while preserving its uid and order.

    *selector* is resolved as an exact uid or unambiguous uid prefix.  The
    original Memory is returned as a detached before-edit view.  Supplying the
    existing content is a no-op.  References and embedded Contexts are
    intentionally read-only through this operation.
    """
    item = resolve_direct_memory(ctx, selector)

    original = Memory(uid=item.uid, content=item.content)
    if item.content != content:
        ctx.replace(Memory(uid=item.uid, content=content))
    return original


def edit_many(
    ctx: Context,
    edits: list[tuple[str, str]],
) -> list[tuple[Memory, Memory]]:
    """
    Apply multiple direct-Memory replacements as one in-memory operation.

    Every selector is resolved and validated before the Context is mutated.
    The same canonical Memory uid may appear only once.  Returned pairs contain
    ``(before, after)`` records for actual changes; exact no-ops are omitted.
    """
    prepared: list[tuple[Memory, Memory]] = []
    seen_uids: set[str] = set()

    for selector, content in edits:
        matches = [uid for uid in ctx.memories if uid.startswith(selector)]
        if not matches:
            raise KeyError(f"No item with uid starting with '{selector}'.")
        if len(matches) > 1:
            raise ValueError(
                f"Ambiguous prefix '{selector}' matches {len(matches)} items: "
                + ", ".join(uid[:8] for uid in matches)
            )

        item = ctx.memories[matches[0]]
        if not isinstance(item, Memory):
            raise TypeError(
                f"'{selector}' is not a Memory directly owned by this Context "
                "— cannot edit."
            )
        if item.uid in seen_uids:
            raise ValueError(
                f"Memory [{item.uid[:8]}] appears more than once in the edit input."
            )
        seen_uids.add(item.uid)

        if item.content != content:
            prepared.append(
                (
                    Memory(uid=item.uid, content=item.content),
                    Memory(uid=item.uid, content=content),
                )
            )

    for _, replacement in prepared:
        ctx.replace(replacement)
    return prepared


def _direct_source_memory(
    memory: Memory,
    source: Context,
) -> Memory:
    """Return the exact directly owned Source object behind one request."""

    source_item = source.memories.get(memory.uid)
    if not isinstance(source_item, Memory):
        raise ValueError(
            f"Memory [{memory.uid[:8]}] is not directly owned by '{source.name}'."
        )
    return source_item


def embed_memory(
    memory: Memory,
    source: Context,
    target: Context,
    *,
    position: int | None = None,
) -> MemoryRef:
    """Add a read-only live Memory link whose content resolves from Source."""

    if source.uid == target.uid:
        raise ValueError("Cannot embed a Memory into its owning Context.")
    memory = _direct_source_memory(memory, source)
    if position is not None and not 0 <= position <= len(target.ordered_uids()):
        raise ValueError(
            "Memory Embed position must be between 0 and "
            f"{len(target.ordered_uids())}."
        )

    for info in target.iter_items():
        if (
            isinstance(info, MemoryRef)
            and info.is_live
            and info.target_context_uid == source.uid
            and info.target_memory_uid == memory.uid
        ):
            raise ValueError(
                f"Memory [{memory.uid[:8]}] from '{source.name}' is already "
                f"embedded in '{target.name}'."
            )

    ref = MemoryRef(
        uid=str(uuid.uuid4()),
        target_context_uid=source.uid,
        target_context_name=source.name,
        target_memory_uid=memory.uid,
        target=memory,
    )
    target.add(ref, position=position)
    return ref


def reference_memory(
    memory: Memory,
    source: Context,
    target: Context,
) -> MemoryRef:
    """Add an immutable read-only snapshot of one directly owned Memory."""

    memory = _direct_source_memory(memory, source)
    digest = hashlib.sha256(memory.content.encode("utf-8")).hexdigest()
    for info in target.iter_items():
        if (
            isinstance(info, MemoryRef)
            and info.is_snapshot
            and info.target_context_uid == source.uid
            and info.target_memory_uid == memory.uid
            and info.snapshot_content_sha256 == digest
        ):
            raise ValueError(
                f"Memory [{memory.uid[:8]}] from '{source.name}' already has "
                f"this exact snapshot in '{target.name}'."
            )
    ref = MemoryRef(
        uid=str(uuid.uuid4()),
        target_context_uid=source.uid,
        target_context_name=source.name,
        target_memory_uid=memory.uid,
        target=memory,
        snapshot_content_sha256=digest,
    )
    target.add(ref)
    return ref


def reference_context(
    snapshot,
    target: Context,
):
    """Add one immutable Context snapshot as a read-only direct item.

    The snapshot is constructed by the operation runtime because its package
    binds a complete reviewed read scope. This domain boundary owns duplicate
    and self-reference checks without importing Store or CLI concerns.
    """

    from memcommit.context_snapshot import ContextSnapshotRef

    if not isinstance(snapshot, ContextSnapshotRef):
        raise TypeError("Context Reference requires a ContextSnapshotRef.")
    if snapshot.target_context_uid == target.uid:
        raise ValueError("Cannot reference a Context into itself.")
    for item in target.iter_items():
        if (
            isinstance(item, ContextSnapshotRef)
            and item.target_context_uid == snapshot.target_context_uid
            and item.snapshot_content_sha256
            == snapshot.snapshot_content_sha256
        ):
            raise ValueError(
                f"Context '{snapshot.target_context_name}' already has this "
                f"exact snapshot in '{target.name}'."
            )
    target.add(snapshot)
    return snapshot


def reference_query_context(
    name: str,
    target_source_uid: str,
    target: Context,
    provider: str = "codex_chatgpt",
) -> QueryContextRef:
    """Attach an opaque query-only source to a Context."""
    for info in target.iter_items():
        if (
            isinstance(info, QueryContextRef)
            and info.target_source_uid == target_source_uid
        ):
            raise ValueError(
                f"Query source '{name}' is already referenced in '{target.name}'."
            )
        if isinstance(info, (Context, QueryContextRef)) and info.name == name:
            raise ValueError(
                f"A context-like item named '{name}' already exists in "
                f"'{target.name}'."
            )

    ref = QueryContextRef(
        uid=str(uuid.uuid4()),
        name=name,
        target_source_uid=target_source_uid,
        provider=provider,
    )
    target.add(ref)
    return ref


def resolve(ctx: Context, selector: str) -> Information:
    """
    Resolve one direct child of *ctx* by UID prefix or embedded-context name.

    Atomic memories currently have no name, so they can only be selected by
    UID (or an unambiguous UID prefix). Embedded contexts can additionally be
    selected by their exact name. Raises KeyError if nothing matches and
    ValueError if the selector is ambiguous.
    """
    matches = [
        info
        for uid, info in ctx.iter_entries()
        if uid.startswith(selector)
        or (isinstance(info, (Context, QueryContextRef)) and info.name == selector)
    ]
    if not matches:
        raise KeyError(f"No direct item matching '{selector}' in context '{ctx.name}'.")
    if len(matches) > 1:
        raise ValueError(
            f"Ambiguous selector '{selector}' matches {len(matches)} items: "
            + ", ".join(item.uid[:8] for item in matches)
        )
    return matches[0]


def remove(ctx: Context, uid: str) -> Information:
    """
    Remove an item from ctx by uid or unambiguous prefix.
    Returns the removed item. Raises KeyError if not found, ValueError if ambiguous.
    """
    matches = [k for k in ctx.memories if k.startswith(uid)]
    if not matches:
        raise KeyError(f"No item with uid starting with '{uid}'.")
    if len(matches) > 1:
        raise ValueError(
            f"Ambiguous prefix '{uid}' matches {len(matches)} items: "
            + ", ".join(m[:8] for m in matches)
        )
    full_uid = matches[0]
    item = ctx.memories[full_uid]
    ctx.remove(full_uid)
    return item


def validate_embed(
    child: Context,
    parent: Context,
    *,
    position: int | None = None,
) -> None:
    """Validate one live Context insertion without mutating either Context."""

    if position is not None and (
        isinstance(position, bool)
        or not isinstance(position, int)
        or not 0 <= position <= len(parent.ordered_uids())
    ):
        raise ValueError(
            "Embed position must be between 0 and "
            f"{len(parent.ordered_uids())}."
        )
    if child.uid == parent.uid:
        raise ValueError("Cannot embed a context into itself.")
    for info in parent.iter_items():
        # Context.add() deliberately replaces an existing direct item with the
        # same UID.  Embed must reject that generic update behavior because two
        # public Grant aliases can identify one authority Context: accepting the
        # second alias would silently replace the first durable relationship.
        if info.uid == child.uid:
            if isinstance(info, Context):
                raise ValueError(
                    f"'{child.name}' has the same Context identity as already "
                    f"embedded '{info.name}' in '{parent.name}'."
                )
            raise ValueError(
                f"Cannot embed '{child.name}' in '{parent.name}': its Context "
                f"identity [{child.uid[:8]}] is already used by a direct item."
            )
        if isinstance(info, (Context, QueryContextRef)) and info.name == child.name:
            raise ValueError(f"'{child.name}' is already embedded in '{parent.name}'.")


def embed(
    child: Context,
    parent: Context,
    *,
    position: int | None = None,
) -> None:
    """
    Embed child inside parent (as a live reference).
    New embeds append unless an exact direct-item insertion position is supplied.
    Raises ValueError if already embedded, self-referential, or out of range.
    """
    validate_embed(child, parent, position=position)
    # Context.add historically clamps positions for generic callers. Embed's
    # reviewed gap is an exact safety boundary, so validate it before mutation.
    parent.add(child, position=position)


def _branch_memory_uid_map(
    ctx: Context,
    supplied: Mapping[str, str] | None,
    *,
    allow_source_uids: bool = False,
) -> dict[str, str]:
    """Freeze fresh occurrence identities for every current direct Memory."""

    source_uids = {
        item.uid for item in ctx.iter_items() if isinstance(item, Memory)
    }
    result = (
        {uid: str(uuid.uuid4()) for uid in source_uids}
        if supplied is None
        else dict(supplied)
    )
    if set(result) != source_uids:
        raise ValueError(
            "Branch Memory identity map must cover exactly the current Memories."
        )
    if any(
        not isinstance(source_uid, str)
        or not source_uid
        or not isinstance(target_uid, str)
        or not target_uid
        or (source_uid == target_uid and not allow_source_uids)
        for source_uid, target_uid in result.items()
    ):
        raise ValueError("Branch Memory identity map is invalid.")
    target_uids = tuple(result.values())
    if len(target_uids) != len(set(target_uids)):
        raise ValueError("Branch Memory identity map contains duplicate targets.")
    direct_non_memory_uids = {
        item.uid for item in ctx.iter_items() if not isinstance(item, Memory)
    }
    if set(target_uids) & direct_non_memory_uids:
        raise ValueError("Branch Memory identity collides with a direct item.")
    return result


def _copy_context_for_branch(
    ctx: Context,
    new_name: str,
    *,
    memory_uid_map: Mapping[str, str] | None,
    allow_source_memory_uids: bool,
) -> Context:
    new_ctx = Context(
        uid=str(uuid.uuid4()),
        name=validate_portable_context_name(new_name),
    )
    from memcommit.context_snapshot import ContextSnapshotRef

    uid_map = _branch_memory_uid_map(
        ctx,
        memory_uid_map,
        allow_source_uids=allow_source_memory_uids,
    )
    for info in ctx.iter_items():
        if isinstance(info, Memory):
            new_ctx.add(Memory(uid=uid_map[info.uid], content=info.content))
        elif isinstance(info, (MemoryRef, QueryContextRef)):
            new_ctx.add(info.copy())
        elif isinstance(info, ContextSnapshotRef):
            new_ctx.add(info.copy())
        else:
            new_ctx.add(info)
    return new_ctx


def branch(
    ctx: Context,
    new_name: str,
    *,
    memory_uid_map: Mapping[str, str] | None = None,
) -> Context:
    """
    Create a new Context that is a copy of ctx under new_name.

    Direct Memory items are copied as independent objects with fresh occurrence
    UIDs. The durable Branch checkpoint, rather than a shared writable address,
    records how those occurrences descend from the Source. Embedded Context
    references are carried over as-is (live-reference semantics are preserved;
    the sub-contexts themselves are not cloned).
    """

    return _copy_context_for_branch(
        ctx,
        new_name,
        memory_uid_map=memory_uid_map,
        allow_source_memory_uids=False,
    )


def _atomize_projection(ctx: Context, new_name: str) -> Context:
    """Copy one Atomize analysis frame without changing its evidence keys.

    Atomize indexes its reviewed, process-local plan by Source Memory UID and
    assigns output provenance during final Save As. Keeping those temporary
    keys is not the durable Branch identity contract.
    """

    return _copy_context_for_branch(
        ctx,
        new_name,
        memory_uid_map={
            item.uid: item.uid
            for item in ctx.iter_items()
            if isinstance(item, Memory)
        },
        allow_source_memory_uids=True,
    )


def branch_subtree(
    contexts: Sequence[Context],
    source_root: str,
    new_root: str,
    *,
    memory_uid_maps: Mapping[str, Mapping[str, str]] | None = None,
) -> tuple[Context, ...]:
    """Copy one frozen lexical Context subtree under a fresh root.

    Context and direct-Memory occurrence identities are regenerated because
    every branch is independently editable. The publishing checkpoint retains
    their lineage explicitly. Persisted pointers whose targets are inside the
    frozen subtree follow the new Context and Memory identities; outside
    pointers retain the ordinary shallow Branch live-reference behavior.
    """
    sources = tuple(contexts)
    if not sources:
        raise ValueError("A subtree branch requires at least one Context.")
    if not source_root or not new_root or source_root == new_root:
        raise ValueError("A subtree branch requires distinct named roots.")

    source_by_name = {context.name: context for context in sources}
    if len(source_by_name) != len(sources) or source_root not in source_by_name:
        raise ValueError("A subtree branch requires one distinct Source root.")
    if len({context.uid for context in sources}) != len(sources):
        raise ValueError("A subtree branch requires distinct Context identities.")

    prefix = source_root + "/"
    if any(
        context.name != source_root and not context.name.startswith(prefix)
        for context in sources
    ):
        raise ValueError("A subtree branch received a Context outside its Source root.")

    target_names = {
        source.name: new_root + source.name[len(source_root) :] for source in sources
    }
    for target_name in target_names.values():
        validate_portable_context_name(target_name)
    if len(set(target_names.values())) != len(sources):
        raise ValueError("A subtree branch produced duplicate target names.")

    targets = {
        source.name: Context(uid=str(uuid.uuid4()), name=target_names[source.name])
        for source in sources
    }
    supplied_maps = dict(memory_uid_maps or {})
    if set(supplied_maps) - {source.uid for source in sources}:
        raise ValueError("Subtree Branch Memory map names an unknown Context.")
    uid_maps = {
        source.uid: _branch_memory_uid_map(
            source,
            supplied_maps.get(source.uid),
        )
        for source in sources
    }
    from memcommit.context_snapshot import ContextSnapshotRef

    # Populate every target Memory first so an internal live reference can
    # bind to the independently owned target occurrence regardless of Context
    # traversal order.
    for source in sources:
        target = targets[source.name]
        for item in source.iter_items():
            if isinstance(item, Memory):
                target.add(
                    Memory(
                        uid=uid_maps[source.uid][item.uid],
                        content=item.content,
                    )
                )

    for source in sources:
        target = targets[source.name]
        for item in source.iter_items():
            if isinstance(item, Memory):
                continue
            elif isinstance(item, MemoryRef):
                if item.is_snapshot:
                    # A snapshot records the original Source identity. Branch
                    # copies the retained evidence but must not retarget its
                    # provenance to the new branch.
                    target.add(item.copy())
                    continue
                internal_owner = source_by_name.get(item.target_context_name)
                if internal_owner is None:
                    target.add(item.copy())
                    continue
                if internal_owner.uid != item.target_context_uid:
                    raise ValueError(
                        "A subtree Branch found a stale internal Memory reference."
                    )
                internal_memory = internal_owner.memories.get(item.target_memory_uid)
                if not isinstance(internal_memory, Memory):
                    raise ValueError(
                        "A subtree Branch found an unavailable internal Memory target."
                    )
                target_owner = targets[internal_owner.name]
                target_memory_uid = uid_maps[internal_owner.uid][
                    item.target_memory_uid
                ]
                target_memory = target_owner.memories.get(target_memory_uid)
                if not isinstance(target_memory, Memory):
                    raise ValueError(
                        "A subtree Branch lost an internal Memory occurrence."
                    )
                target.add(
                    MemoryRef(
                        uid=item.uid,
                        target_context_uid=target_owner.uid,
                        target_context_name=target_owner.name,
                        target_memory_uid=target_memory_uid,
                        target=target_memory,
                    )
                )
            elif isinstance(item, QueryContextRef):
                target.add(item.copy())
            elif isinstance(item, ContextSnapshotRef):
                # A Context Reference is already an immutable value. Branch
                # preserves its historical Source identity and scope.
                target.add(item.copy())
            else:
                internal_context = source_by_name.get(item.name)
                if internal_context is None:
                    # Context serialization stores only uid/name. Use a fresh
                    # stub so the branch cannot share a mutable object merely
                    # because an external live reference was retained.
                    target.add(Context(uid=item.uid, name=item.name))
                    continue
                if internal_context.uid != item.uid:
                    raise ValueError(
                        "A subtree Branch found a stale internal Context reference."
                    )
                target.add(targets[internal_context.name])
        target.order = [
            (
                uid_maps[source.uid][item.uid]
                if isinstance(item, Memory)
                else (
                    targets[item.name].uid
                    if isinstance(item, Context) and item.name in targets
                    else item.uid
                )
            )
            for item in source.iter_items()
        ]
        ordinary_names = {
            item.name for item in target.iter_items() if isinstance(item, Context)
        }
        query_names = {
            item.name
            for item in target.iter_items()
            if isinstance(item, QueryContextRef)
        }
        collisions = ordinary_names & query_names
        if collisions:
            raise ValueError(
                "A subtree Branch would give ordinary and query-only Context "
                "pointers the same name: "
                + ", ".join(repr(name) for name in sorted(collisions))
            )
    return tuple(targets[source.name] for source in sources)


def merge(source: Context, target: Context) -> list[Information]:
    """
    Merge all Information from source into target without semantic checks.

    Items whose uid is already present in target are skipped, so repeating the
    same in-memory Source is idempotent. This compatibility helper has no Store
    or checkpoint access and therefore cannot reconcile fresh Branch occurrence
    UIDs; the durable Merge application/runtime owns that lineage-aware path.
    Returns the list of items that were newly added to target.
    """
    # Preflight context-like names before mutating target. Name-based resolve
    # must remain unambiguous after a merge.
    context_names: dict[str, Context | QueryContextRef] = {
        info.name: info
        for info in target.iter_items()
        if isinstance(info, (Context, QueryContextRef))
    }
    query_sources = {
        info.target_source_uid
        for info in target.iter_items()
        if isinstance(info, QueryContextRef)
    }
    for info in source.iter_items():
        if info.uid in target.memories:
            continue
        if not isinstance(info, (Context, QueryContextRef)):
            continue
        if (
            isinstance(info, QueryContextRef)
            and info.target_source_uid in query_sources
        ):
            continue
        existing = context_names.get(info.name)
        if existing is not None:
            raise ValueError(
                f"Cannot merge context-like item '{info.name}': that name "
                f"already exists in '{target.name}'."
            )
        context_names[info.name] = info
        if isinstance(info, QueryContextRef):
            query_sources.add(info.target_source_uid)

    added: list[Information] = []
    for info in source.iter_items():
        if info.uid in target.memories:
            continue
        if isinstance(info, MemoryRef) and any(
            isinstance(existing, MemoryRef)
            and existing.is_snapshot == info.is_snapshot
            and existing.target_context_uid == info.target_context_uid
            and existing.target_memory_uid == info.target_memory_uid
            and (
                info.is_live
                or existing.snapshot_content_sha256
                == info.snapshot_content_sha256
            )
            for existing in target.iter_items()
        ):
            continue
        if isinstance(info, QueryContextRef) and any(
            isinstance(existing, QueryContextRef)
            and existing.target_source_uid == info.target_source_uid
            for existing in target.iter_items()
        ):
            continue
        item = info.copy() if isinstance(info, (MemoryRef, QueryContextRef)) else info
        target.add(item)
        added.append(item)
    return added


# ---------------------------------------------------------------------------
# Semantic operation: forget (compatibility facade)
# ---------------------------------------------------------------------------


def analyze_forget(ctx: Context, query: str, llm: object):
    """Analyze Forget through the operation-owned provider module."""

    from memcommit.forget_provider import analyze_forget as _analyze_forget

    return _analyze_forget(ctx, query, llm)


def forget(
    ctx: Context,
    query: str,
    llm: object,
) -> tuple[list[ProposedChange], list[dict[str, object]]]:
    """Return Forget proposals without mutating the Source Context."""

    from memcommit.forget_provider import forget as _forget

    return _forget(ctx, query, llm)


def revise_forget(
    feedback: str,
    llm: object,
    history: list[dict[str, object]],
    ctx: Context,
) -> tuple[list[ProposedChange], list[dict[str, object]]]:
    """Revise Forget proposals through the operation-owned provider module."""

    from memcommit.forget_provider import revise_forget as _revise_forget

    return _revise_forget(feedback, llm, history, ctx)


# ---------------------------------------------------------------------------
# Semantic operation: integrate
# ---------------------------------------------------------------------------

#: Maximum total characters of memory content sent to the LLM in one integrate call.
#: A single memory exceeding this limit is still sent alone in its own batch.
INTEGRATE_BATCH_CHAR_LIMIT = 8_000

_INTEGRATE_SYSTEM = """\
You are a memory integration assistant. Your job is to decide how a piece of new \
information should be integrated into an existing set of memories.

You will be shown a batch of existing memories and a piece of new information. Classify the \
relationship, propose any required changes, then report whether the new information is now \
captured in the context.

Respond with ONLY a valid JSON object — no prose, no markdown fences. Use this schema:
{
  "analysis": "<one-sentence summary of your decision>",
  "already_captured": <true or false>,
  "proposed_changes": [
    {"operation": "edit", "uid": "<uid>", "new_content": "<full revised text>", "reason": "<why>"}
  ]
}

STEP 1 — Classify the new information against existing memories:

  DUPLICATE  The new information is semantically equivalent to an existing memory.
             → No changes. Set "already_captured": true.

  UPDATE     The new information refines, corrects, extends, or fully replaces information \
in an existing memory (whether a partial update or a complete rewrite of that memory).
             → You MUST propose an "edit" of that memory.
               Write new_content as the full revised text of the memory: incorporate the new \
information for the relevant part, and preserve any other facts in that memory that are \
unrelated to the update.
               Set "already_captured": true.

  NOVEL      The new information is unrelated to any existing memory.
             → No changes. Set "already_captured": false (the caller will add it).

STEP 2 — Apply these rules strictly:
  - "already_captured": true  means the new information is fully represented in the context \
after your changes.
  - "already_captured": false means the new information is NOT yet in the context — \
the caller will add it as a new memory.
  - If UPDATE: you MUST propose an edit. Do not skip.
  - The only valid operation is "edit". Never propose "remove".
  - An edit may completely rewrite a memory when the entire content is superseded.
  - When only part of a memory is affected, preserve the unrelated content in new_content.
  - Only reference uids from the memories shown in this batch. Preserve exact uid strings.
"""


def _make_integrate_batches(
    memories: list[Memory],
    char_limit: int,
) -> list[list[Memory]]:
    """
    Group memories into batches whose total content length stays within char_limit.
    A single memory exceeding char_limit is placed in a batch of its own.
    """
    batches: list[list[Memory]] = []
    current: list[Memory] = []
    current_len = 0

    for mem in memories:
        n = len(mem.content)
        if current and current_len + n > char_limit:
            batches.append(current)
            current = [mem]
            current_len = n
        else:
            current.append(mem)
            current_len += n

    if current:
        batches.append(current)

    return batches


def _run_integrate_batch(
    new_info: str,
    batch: list[Memory],
    ctx: Context,
    llm: "LLMClient",
) -> "tuple[list[ProposedChange], list[dict], bool]":
    """Run one LLM call for a single integrate batch. Returns (proposals, history, should_add)."""
    from memcommit.semantic.changes import parse_proposals
    from memcommit.semantic.utils import build_messages, extract_json

    lines = [f"[{m.uid}] {m.content}" for m in batch]
    memory_block = "\n".join(lines) or "(no memories in this batch)"
    user_msg = (
        f"## Existing memories\n{memory_block}\n\n"
        f'## New information\n"{new_info}"\n\n'
        "Respond with valid JSON only."
    )
    messages = build_messages(_INTEGRATE_SYSTEM, user_msg)
    text = llm.chat(messages)
    history = messages + [{"role": "assistant", "content": text}]
    data = extract_json(text)
    # already_captured=true  → should_add=false (caller should NOT add)
    # already_captured=false → should_add=true  (caller SHOULD add)
    # Default: if field is missing, assume novel → should add.
    should_add: bool = not bool(data.get("already_captured", False))
    # Integrate never removes — filter defensively in case the model misbehaves.
    from memcommit.semantic.changes import RemoveChange

    proposals = [
        p for p in parse_proposals(data, ctx) if not isinstance(p, RemoveChange)
    ]
    return proposals, history, should_add


# ---------------------------------------------------------------------------
# Read-only semantic quality finders
# ---------------------------------------------------------------------------


def impact_atomize(
    ctx: Context,
    provider_factory: Callable[[], "AtomizeProvider"],
    *,
    declared_frames: dict[str, str] | None = None,
    memory_selector: str | None = None,
) -> "AtomizeImpactReport":
    """Preview direct-Memory atomization without mutating *ctx*."""
    from memcommit.atomize import impact_atomize as _impact_atomize

    return _impact_atomize(
        ctx,
        provider_factory,
        declared_frames=declared_frames,
        memory_selector=memory_selector,
    )


def find_redundancies(
    ctx: Context,
    provider_factory: Callable[[], "FindingsProvider"],
    *,
    context_name_by_uid: "Mapping[str, str] | None" = None,
) -> "DuplicateReport":
    """Find exact DUP and semantic-DUN evidence without mutating *ctx*."""
    from memcommit.findings import find_redundancies as _find_redundancies

    return _find_redundancies(
        ctx,
        provider_factory,
        context_name_by_uid=context_name_by_uid,
    )


def find_duplicates(
    ctx: Context,
) -> "ExactDuplicateReport":
    """Find byte-identical direct-Memory groups without provider inference."""
    from memcommit.exact_dedup import find_exact_duplicates

    return find_exact_duplicates(ctx)


def find_ambiguities(
    ctx: Context,
    provider_factory: Callable[[], "FindingsProvider"],
    *,
    context_name_by_uid: "Mapping[str, str] | None" = None,
) -> "AmbiguityReport":
    """Find ambiguous direct Memories without mutating *ctx*."""
    from memcommit.findings import find_ambiguities as _find_ambiguities

    return _find_ambiguities(
        ctx,
        provider_factory,
        context_name_by_uid=context_name_by_uid,
    )


def find_conflicts(
    ctx: Context,
    provider_factory: Callable[[], "FindingsProvider"],
    *,
    context_name_by_uid: "Mapping[str, str] | None" = None,
) -> "ConflictReport":
    """Find conflicting direct-Memory pairs without mutating *ctx*."""
    from memcommit.findings import find_conflicts as _find_conflicts

    return _find_conflicts(
        ctx,
        provider_factory,
        context_name_by_uid=context_name_by_uid,
    )


def integrate(
    ctx: Context,
    new_info: str,
    llm: "LLMClient",
) -> "tuple[list[ProposedChange], list[list[dict]]]":
    """
    Propose changes to intelligently integrate new_info into ctx.

    Existing memories are processed in batches capped at
    INTEGRATE_BATCH_CHAR_LIMIT characters of content each. A single memory
    that exceeds the limit on its own is still processed in a batch by itself.

    An AddChange is included only when *every* batch agrees the information is
    novel (i.e. no batch found a duplicate or absorbed it via an edit).

    Returns ``(proposals, batch_histories)`` where ``batch_histories[i]`` is
    the raw message list for batch i; pass it to ``revise_integrate()`` for
    interactive follow-up.

    Does NOT mutate ctx — call apply_changes(ctx, proposals) then
    store.save(ctx) to commit.
    """
    from memcommit.semantic.changes import AddChange

    memories = [m for m in ctx.iter_items() if isinstance(m, Memory)]
    batches = _make_integrate_batches(memories, INTEGRATE_BATCH_CHAR_LIMIT)

    all_proposals: list[ProposedChange] = []
    all_histories: list[list[dict]] = []
    all_should_add: list[bool] = []

    for batch in batches:
        proposals, history, should_add = _run_integrate_batch(new_info, batch, ctx, llm)
        all_proposals.extend(proposals)
        all_histories.append(history)
        all_should_add.append(should_add)

    # Add iff every batch (including the vacuous case of an empty context) agrees.
    if all(all_should_add):
        all_proposals.insert(
            0,
            AddChange(
                content=new_info,
                reason="Novel — not found in existing memories.",
            ),
        )

    return all_proposals, all_histories


def revise_integrate(
    feedback: str,
    llm: "LLMClient",
    batch_histories: "list[list[dict]]",
    ctx: Context,
    new_info: str,
) -> "tuple[list[ProposedChange], list[list[dict]]]":
    """
    Re-run each integrate batch with user feedback appended, return revised proposals.

    Pass the batch_histories returned by integrate() or a prior revise_integrate().
    Returns (revised_proposals, updated_batch_histories).
    """
    from memcommit.semantic.changes import AddChange, parse_proposals
    from memcommit.semantic.utils import build_messages, extract_json

    all_proposals: list[ProposedChange] = []
    new_histories: list[list[dict]] = []
    all_should_add: list[bool] = []

    for history in batch_histories:
        messages = build_messages(history=history, feedback=feedback)
        text = llm.chat(messages)
        updated = messages + [{"role": "assistant", "content": text}]
        data = extract_json(text)
        from memcommit.semantic.changes import RemoveChange

        batch_proposals = [
            p for p in parse_proposals(data, ctx) if not isinstance(p, RemoveChange)
        ]
        all_proposals.extend(batch_proposals)
        new_histories.append(updated)
        all_should_add.append(not bool(data.get("already_captured", False)))

    if all(all_should_add):
        all_proposals.insert(
            0,
            AddChange(
                content=new_info,
                reason="Novel — not found in existing memories.",
            ),
        )

    return all_proposals, new_histories


def find(
    ctx: Context,
    query: str,
    provider_factory: Callable[[], "PromptProvider"],
    *,
    recursive: bool = True,
    limit: int = 5,
    additional_roots: Sequence[Context] = (),
) -> "list[SearchMatch]":
    """
    Rank visible Context items for a natural-language query.

    The provider selects short candidate IDs only. Returned matches always
    point back to the canonical local Information objects. QueryContextRefs
    contribute their public names but never their concealed source contents.
    ``additional_roots`` lets a store-aware caller freeze lexical namespace
    descendants without teaching this in-memory operation about persistence.
    """
    from memcommit.search import (
        FindError,
        collect_candidates_from_roots,
        rank_candidates,
    )

    if not isinstance(query, str) or not query.strip():
        raise FindError("Find query must be non-empty.")
    if not 1 <= limit <= 20:
        raise FindError("Find limit must be between 1 and 20.")

    candidates = collect_candidates_from_roots(
        (ctx, *additional_roots),
        recursive=recursive,
    )
    if not candidates:
        return []
    provider = provider_factory()
    return rank_candidates(query, candidates, provider, limit=limit)


# ---------------------------------------------------------------------------
# Semantic operation: translate
# ---------------------------------------------------------------------------


def translate(
    ctx: Context,
    target_language: str,
    provider_factory: Callable[[], "TranslationProvider"],
    *,
    selector: str | None = None,
    allocate_operation_uid: bool = True,
) -> "TranslationPlan":
    """Plan translations of directly owned Memories without mutating ctx."""
    from memcommit.translate import plan_translation

    return plan_translation(
        ctx,
        target_language,
        provider_factory,
        selector=selector,
        allocate_operation_uid=allocate_operation_uid,
    )


def apply_translation(
    ctx: Context,
    plan: "TranslationPlan",
) -> "TranslationApplyResult":
    """Apply one exact translation plan to its unchanged direct Context."""
    from memcommit.translate import apply_translation as apply_plan

    return apply_plan(ctx, plan)


def derive_translation_context(
    source: Context,
    plan: "TranslationPlan",
    destination_name: str,
) -> "DerivedTranslationApplyResult":
    """Apply one exact plan as replacements in a new derived Context."""
    from memcommit.translate import derive_translation_context as derive

    return derive(source, plan, destination_name)


# ---------------------------------------------------------------------------
# Structural operation: chunk
# ---------------------------------------------------------------------------


def chunk(
    ctx: Context,
    uid: str,
    method: str,
    *,
    break_on: str | None = None,
    min_chars: int | None = None,
    max_chars: int | None = None,
) -> tuple[Memory, list[Memory]]:
    """
    Propose a chunked split of a Memory without mutating ctx.

    Resolves *uid* (or an unambiguous prefix) to a Memory, applies the named
    chunking method and optional literal/length constraints, and returns
    ``(original_memory, new_memories)``.

    When ``len(new_memories) <= 1`` the content could not be split further
    with the chosen method — the caller should take no action.

    Raises:
        KeyError   — uid not found in ctx
        ValueError — ambiguous prefix or unknown method name
        TypeError  — uid resolves to a reference or embedded Context, not a Memory
    """
    from memcommit.chunking import chunk_content

    matches = [k for k in ctx.memories if k.startswith(uid)]
    if not matches:
        raise KeyError(f"No item with uid starting with '{uid}'.")
    if len(matches) > 1:
        raise ValueError(
            f"Ambiguous prefix '{uid}' matches {len(matches)} items: "
            + ", ".join(m[:8] for m in matches)
        )
    full_uid = matches[0]
    item = ctx.memories[full_uid]
    if not isinstance(item, Memory):
        raise TypeError(
            f"'{uid[:8]}' is not a Memory directly owned by this Context — cannot chunk."
        )

    raw_chunks = chunk_content(
        item.content,
        method,
        break_on=break_on,
        min_chars=min_chars,
        max_chars=max_chars,
    )
    new_memories = [Memory(uid=str(uuid.uuid4()), content=c) for c in raw_chunks]
    return item, new_memories
