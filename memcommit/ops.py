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

import uuid
from typing import TYPE_CHECKING, Callable

from memcommit.context import Context, Information, Memory, MemoryRef, QueryContextRef

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
    from memcommit.search import PromptProvider, SearchMatch
    from memcommit.semantic.llm import LLMClient
    from memcommit.semantic.changes import ProposedChange
    from memcommit.translate import (
        TranslationApplyResult,
        TranslationPlan,
        TranslationProvider,
    )


# ---------------------------------------------------------------------------
# Structural operations (no LLM)
# ---------------------------------------------------------------------------

def init(name: str) -> Context:
    """Create a new, empty Context. Does not persist — caller must store.save(ctx)."""
    return Context(uid=str(uuid.uuid4()), name=name)


def add(ctx: Context, content: str) -> Memory:
    """Add a new Memory to ctx. Returns the created Memory."""
    result = ctx.add(content)
    assert isinstance(result, Memory)
    return result


def add_many(ctx: Context, contents: list[str]) -> list[Memory]:
    """Append multiple Memories in input order and return the created records."""
    memories = [
        Memory(uid=str(uuid.uuid4()), content=content)
        for content in contents
    ]
    for memory in memories:
        ctx.add(memory)
    return memories


def edit(ctx: Context, selector: str, content: str) -> Memory:
    """
    Replace one directly owned Memory's content while preserving its uid and order.

    *selector* is resolved as an exact uid or unambiguous uid prefix.  The
    original Memory is returned as a detached before-edit view.  Supplying the
    existing content is a no-op.  References and embedded Contexts are
    intentionally read-only through this operation.
    """
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


def reference_memory(
    memory: Memory,
    source: Context,
    target: Context,
) -> MemoryRef:
    """
    Add a read-only live reference to a directly owned source Memory.

    The reference has its own uid and stores only target identity metadata.
    Target content is refreshed whenever the containing Context is reloaded.
    """
    source_item = source.memories.get(memory.uid)
    if not isinstance(source_item, Memory):
        raise ValueError(
            f"Memory [{memory.uid[:8]}] is not directly owned by '{source.name}'."
        )
    memory = source_item

    for info in target.iter_items():
        if (
            isinstance(info, MemoryRef)
            and info.target_context_uid == source.uid
            and info.target_memory_uid == memory.uid
        ):
            raise ValueError(
                f"Memory [{memory.uid[:8]}] from '{source.name}' is already "
                f"referenced in '{target.name}'."
            )

    ref = MemoryRef(
        uid=str(uuid.uuid4()),
        target_context_uid=source.uid,
        target_context_name=source.name,
        target_memory_uid=memory.uid,
        target=memory,
    )
    target.add(ref)
    return ref


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
        or (
            isinstance(info, (Context, QueryContextRef))
            and info.name == selector
        )
    ]
    if not matches:
        raise KeyError(
            f"No direct item matching '{selector}' in context '{ctx.name}'."
        )
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


def embed(child: Context, parent: Context) -> None:
    """
    Embed child inside parent (as a live reference).
    Raises ValueError if already embedded or if child and parent are the same.
    """
    if child.uid == parent.uid:
        raise ValueError("Cannot embed a context into itself.")
    for info in parent.iter_items():
        if (
            isinstance(info, (Context, QueryContextRef))
            and info.name == child.name
        ):
            raise ValueError(f"'{child.name}' is already embedded in '{parent.name}'.")
    parent.add(child)


def branch(ctx: Context, new_name: str) -> Context:
    """
    Create a new Context that is a copy of ctx under new_name.

    Direct Memory items are copied as independent objects but preserve their uids,
    so a later merge() can deduplicate by uid without re-adding items that originated
    here. Embedded Context references are carried over as-is (live-reference semantics
    are preserved; the sub-contexts themselves are not cloned).
    """
    new_ctx = Context(uid=str(uuid.uuid4()), name=new_name)
    for info in ctx.iter_items():
        if isinstance(info, Memory):
            new_ctx.add(Memory(uid=info.uid, content=info.content))
        elif isinstance(info, (MemoryRef, QueryContextRef)):
            new_ctx.add(info.copy())
        else:
            new_ctx.add(info)
    return new_ctx


def merge(source: Context, target: Context) -> list[Information]:
    """
    Merge all Information from source into target without semantic checks.

    Items whose uid is already present in target are skipped, so merging a
    branch back into its origin (or merging twice) is idempotent. Returns
    the list of items that were newly added to target.
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
            and existing.target_context_uid == info.target_context_uid
            and existing.target_memory_uid == info.target_memory_uid
            for existing in target.iter_items()
        ):
            continue
        if isinstance(info, QueryContextRef) and any(
            isinstance(existing, QueryContextRef)
            and existing.target_source_uid == info.target_source_uid
            for existing in target.iter_items()
        ):
            continue
        item = (
            info.copy()
            if isinstance(info, (MemoryRef, QueryContextRef))
            else info
        )
        target.add(item)
        added.append(item)
    return added


# ---------------------------------------------------------------------------
# Semantic operation: forget
# ---------------------------------------------------------------------------

_FORGET_SYSTEM = """\
You are a memory management assistant. Your job is to identify which stored memories \
should be removed or edited based on a user's forget request.

Respond with ONLY a valid JSON object — no prose, no markdown fences. Use this schema:
{
  "analysis": "<one-sentence summary of what matched>",
  "proposed_changes": [
    {"operation": "remove", "uid": "<uid>", "reason": "<why>"},
    {"operation": "edit",   "uid": "<uid>", "new_content": "<revised text>", "reason": "<why>"}
  ]
}

Rules:
- Use "remove" when the entire memory is about the forget topic.
- Use "edit" when only part of the memory mentions the forget topic; preserve everything else.
- Preserve the exact uid strings from the input — do not invent or alter them.
- Only include memories that are relevant to the forget request.
- If nothing matches, return {"analysis": "...", "proposed_changes": []}.
"""


def _format_forget_user_msg(ctx: Context, query: str) -> str:
    lines = [
        f"[{uid}] {info.content}"
        for uid, info in ctx.iter_entries()
        if isinstance(info, Memory)
    ]
    memory_block = "\n".join(lines) or "(no memories)"
    return (
        f"## Memories\n{memory_block}\n\n"
        f'## Forget request\n"{query}"\n\n'
        "Respond with valid JSON only."
    )


def forget(
    ctx: Context,
    query: str,
    llm: LLMClient,
) -> tuple[list[ProposedChange], list[dict]]:
    """
    Ask the LLM to identify which memories match the forget request.

    Returns (proposals, history) where:
      proposals — list of RemoveChange / EditChange (does NOT modify ctx)
      history   — raw message list; pass to revise_forget() for follow-up turns
    """
    from memcommit.semantic.changes import parse_proposals
    from memcommit.semantic.utils import build_messages, extract_json

    messages = build_messages(_FORGET_SYSTEM, _format_forget_user_msg(ctx, query))
    text = llm.chat(messages)
    history = messages + [{"role": "assistant", "content": text}]
    proposals = parse_proposals(extract_json(text), ctx)
    return proposals, history


def revise_forget(
    feedback: str,
    llm: LLMClient,
    history: list[dict],
    ctx: Context,
) -> tuple[list[ProposedChange], list[dict]]:
    """
    Send user feedback to the LLM and get a revised set of forget proposals.

    Pass the history returned by a prior forget() or revise_forget()
    call. The full conversation is preserved so the LLM sees the negotiation context.
    Returns (revised_proposals, updated_history).
    """
    from memcommit.semantic.changes import parse_proposals
    from memcommit.semantic.utils import build_messages, extract_json

    messages = build_messages(history=history, feedback=feedback)
    text = llm.chat(messages)
    updated_history = messages + [{"role": "assistant", "content": text}]
    proposals = parse_proposals(extract_json(text), ctx)
    return proposals, updated_history


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
    proposals = [p for p in parse_proposals(data, ctx) if not isinstance(p, RemoveChange)]
    return proposals, history, should_add


# ---------------------------------------------------------------------------
# Read-only semantic quality finders
# ---------------------------------------------------------------------------

def impact_atomize(
    ctx: Context,
    provider_factory: Callable[[], "AtomizeProvider"],
    *,
    declared_frames: dict[str, str] | None = None,
) -> "AtomizeImpactReport":
    """Preview direct-Memory atomization without mutating *ctx*."""
    from memcommit.atomize import impact_atomize as _impact_atomize

    return _impact_atomize(
        ctx,
        provider_factory,
        declared_frames=declared_frames,
    )


def find_duplicates(
    ctx: Context,
    provider_factory: Callable[[], "FindingsProvider"],
) -> "DuplicateReport":
    """Find duplicate direct-Memory pairs without mutating *ctx*."""
    from memcommit.findings import find_duplicates as _find_duplicates

    return _find_duplicates(ctx, provider_factory)


def find_ambiguities(
    ctx: Context,
    provider_factory: Callable[[], "FindingsProvider"],
) -> "AmbiguityReport":
    """Find ambiguous direct Memories without mutating *ctx*."""
    from memcommit.findings import find_ambiguities as _find_ambiguities

    return _find_ambiguities(ctx, provider_factory)


def find_conflicts(
    ctx: Context,
    provider_factory: Callable[[], "FindingsProvider"],
) -> "ConflictReport":
    """Find conflicting direct-Memory pairs without mutating *ctx*."""
    from memcommit.findings import find_conflicts as _find_conflicts

    return _find_conflicts(ctx, provider_factory)


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
        all_proposals.insert(0, AddChange(
            content=new_info,
            reason="Novel — not found in existing memories.",
        ))

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
        batch_proposals = [p for p in parse_proposals(data, ctx) if not isinstance(p, RemoveChange)]
        all_proposals.extend(batch_proposals)
        new_histories.append(updated)
        all_should_add.append(not bool(data.get("already_captured", False)))

    if all(all_should_add):
        all_proposals.insert(0, AddChange(
            content=new_info,
            reason="Novel — not found in existing memories.",
        ))

    return all_proposals, new_histories


def find(
    ctx: Context,
    query: str,
    provider_factory: Callable[[], "PromptProvider"],
    *,
    recursive: bool = True,
    limit: int = 5,
) -> "list[SearchMatch]":
    """
    Rank visible Context items for a natural-language query.

    The provider selects short candidate IDs only. Returned matches always
    point back to the canonical local Information objects. QueryContextRefs
    contribute their public names but never their concealed source contents.
    """
    from memcommit.search import (
        FindError,
        collect_candidates,
        rank_candidates,
    )

    if not isinstance(query, str) or not query.strip():
        raise FindError("Find query must be non-empty.")
    if not 1 <= limit <= 20:
        raise FindError("Find limit must be between 1 and 20.")

    candidates = collect_candidates(ctx, recursive=recursive)
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
) -> "TranslationPlan":
    """Plan translated copies of directly owned Memories without mutating ctx."""
    from memcommit.translate import plan_translation

    return plan_translation(
        ctx,
        target_language,
        provider_factory,
        selector=selector,
    )


def apply_translation(
    ctx: Context,
    plan: "TranslationPlan",
) -> "TranslationApplyResult":
    """Apply one exact translation plan to its unchanged direct Context."""
    from memcommit.translate import apply_translation as apply_plan

    return apply_plan(ctx, plan)


# ---------------------------------------------------------------------------
# Structural operation: chunk
# ---------------------------------------------------------------------------

def chunk(ctx: Context, uid: str, method: str) -> tuple[Memory, list[Memory]]:
    """
    Propose a chunked split of a Memory without mutating ctx.

    Resolves *uid* (or an unambiguous prefix) to a Memory, applies the named
    chunking method, and returns ``(original_memory, new_memories)``.

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

    raw_chunks = chunk_content(item.content, method)
    new_memories = [Memory(uid=str(uuid.uuid4()), content=c) for c in raw_chunks]
    return item, new_memories
