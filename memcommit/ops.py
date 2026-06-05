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


def integrate(ctx: Context, info: str) -> dict:
    """
    [stub] Intelligently update ctx with new info — smarter than a plain add().

    Performs three passes before committing any change:
      1. Duplicate check: embed info and find semantically near-identical memories
         (above a similarity threshold). If a match is found, skip or update the
         existing memory rather than adding a duplicate.
      2. Conflict check: call find_conflicts(ctx, info). If conflicts are found,
         surface them for resolution before proceeding. In the CLI this means an
         interactive prompt; in the API it means returning the conflict list for
         the caller to resolve.
      3. Write: once duplicates and conflicts are handled, call ops.add() (or an
         edit operation if an existing memory is being updated).

    Returns a result dict describing what happened, e.g.:
      {"action": "added",    "memory": <Memory>}
      {"action": "updated",  "memory": <Memory>, "previous": <Memory>}
      {"action": "skipped",  "reason": "duplicate", "existing": <Memory>}
      {"action": "conflict", "conflicts": [(Information, str), ...]}
    """
    raise NotImplementedError("'integrate' is not yet implemented.")


def find(ctx: Context, query: str) -> list[Information]:
    """
    [stub] Return memories from ctx that match a natural-language query.

    Implementation sketch: embed query, rank ctx.memories by cosine similarity,
    return the top-k results above a relevance threshold.
    """
    raise NotImplementedError("'find' is not yet implemented.")
