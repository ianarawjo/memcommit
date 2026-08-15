---
name: memcommit-add
description: Use the registered memcommit_add_memories tool to append one exact ordered batch of Memories to an existing local or CREATE-granted MemCommit Context and publish one Add checkpoint. Use when the user explicitly asks to remember, add, or store supplied Memory text. Do not use for edits, replacement, semantic rewriting, uncertain targets, inferred content the user has not approved, or any operation other than Add.
---

# MemCommit Add

Invoke `memcommit_add_memories` directly. Do not reconstruct the operation with
`mem add`, Python snippets, provider calls, or filesystem writes.

## Prepare one exact batch

- Confirm that the user authorized durable storage. Do not turn an exploratory
  discussion or an unapproved inference into a Memory.
- Put each intended Memory in one `contents` item. Preserve item order, exact
  duplicates, punctuation, spacing, and embedded newlines. Do not split, merge,
  summarize, normalize, or rewrite the supplied text.
- Supply `context_name` only when the intended existing Context is known. Omit
  it only when the host's frozen current Context is intentionally the target.
  Never invent or create a Context as part of Add.
- Always send `version: 1` and `kind: memories`. Make one tool call for the one
  reviewed batch; one successful call produces one checkpoint.

Do not reinterpret revise, remove, forget, update, or merge requests as Add.

## Interpret the receipt

- On `ok: true`, verify that `count` and the ordered `memories` cover the full
  requested batch. Report the canonical Context, created Memory UIDs, and the
  single `checkpoint_uid` when those details are useful.
- Do not claim that Add created a Context, changed the current Context, called
  a semantic provider, or performed a separate review session.
- A delay or missing response is not a success receipt. Do not repeat the call
  merely to check status because version 1 has no idempotency key.

## Handle failures

- Never retry an Add failure automatically. The operation mutates durable state
  and this contract has no idempotency or status endpoint.
- Correct `invalid_request` locally only when the exact intended values are
  already known. Ask for the target when it is missing or uncertain.
- Treat `authority_denied`, `concurrent_update`, `storage_failure`,
  `execution_failed`, `add_failed`, and `internal_error` as lacking a complete
  Add receipt. State the public failure and wait for the user or host operator;
  do not speculate about hidden paths, grants, storage, or implementation state.

If `memcommit_add_memories` is unavailable, state that the host has not
registered the required tool. Do not fall back to shell access unless the user
separately asks for CLI use.
