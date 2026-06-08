"""
    In-memory operations on Context objects.
    No disk I/O — callers persist via MemoryStore.save(ctx) when needed.

    Semantic operations (forget, find_conflicts, integrate, find) require an
    LLMClient.  They live here alongside their system prompts so all logic for
    a given operation is co-located in one place.

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
from typing import TYPE_CHECKING

from memcommit.context import Context, Information, Memory

if TYPE_CHECKING:
    from memcommit.semantic.llm import LLMClient
    from memcommit.semantic.changes import ProposedChange


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
    for info in parent.memories.values():
        if isinstance(info, Context) and info.name == child.name:
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
    for info in ctx.memories.values():
        if isinstance(info, Memory):
            new_ctx.add(Memory(uid=info.uid, content=info.content))
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
    added: list[Information] = []
    for info in source.memories.values():
        if info.uid not in target.memories:
            target.add(info)
            added.append(info)
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
        for uid, info in ctx.memories.items()
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
# Semantic stubs
# ---------------------------------------------------------------------------

def find_conflicts(ctx: Context, info: str) -> list[tuple[Information, str]]:
    """
    [stub] Find information in ctx that semantically conflicts with info.

    Returns a list of (Information, conflict_level) pairs, where conflict_level
    is one of:
      "direct"    — clear factual contradiction (e.g. "Paris is in France" vs
                    "Paris is in Germany").
      "ambiguous" — potential conflict that may depend on context or time (e.g.
                    "the meeting is at 3 pm" vs "the meeting is at 4 pm" where
                    it's unclear whether they refer to the same meeting).

    Implementation sketch:
      1. Embed info and retrieve the k nearest neighbours from ctx by cosine
         similarity (candidate set).
      2. For each candidate, prompt an LLM: "Does statement A contradict
         statement B? Answer: direct / ambiguous / no conflict."
      3. Return only those classified as direct or ambiguous, together with
         the classification label.
    """
    raise NotImplementedError("'find_conflicts' is not yet implemented.")


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

    memories = [m for m in ctx.memories.values() if isinstance(m, Memory)]
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


def find(ctx: Context, query: str) -> list[Information]:
    """
    [stub] Return memories from ctx that match a natural-language query.

    Implementation sketch: embed query, rank ctx.memories by cosine similarity,
    return the top-k results above a relevance threshold.
    """
    raise NotImplementedError("'find' is not yet implemented.")


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
        TypeError  — uid resolves to an embedded Context, not a Memory
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
            f"'{uid[:8]}' is an embedded context, not a Memory — cannot chunk."
        )

    raw_chunks = chunk_content(item.content, method)
    new_memories = [Memory(uid=str(uuid.uuid4()), content=c) for c in raw_chunks]
    return item, new_memories
