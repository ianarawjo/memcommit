# Elaborate Append-Only Design Rationale

> **Authorization contract updated 2026-08-30.** Permission claims below that use `EMBED`, `DERIVE`, `COMBINE`, `EXPORT`, `ACCEPT_DERIVED`, or `SAVE_*` describe the retired contract preserved for design history. The current contract uses `QUERY`, `CREATE`, `READ`, `UPDATE`, and `DELETE`; `READ` covers readable semantic use and Embed traversal, while `SHARE` remains a separate endpoint capability. See `granted-derived-ownership-design-rationale.md`.

## Decision

Elaborate revises exactly one directly owned Memory by appending a supported
continuation after its existing content. The original content is not a draft
that the provider may rewrite: the application constructs the durable result
as `original + "\n\n" + continuation`. The Memory keeps its UID and direct-item
position.

This makes Elaborate opposite to Summarize only in information-density
direction. Summarize reduces a complete frame to one read-only understanding;
Elaborate maps one selected Memory to one same-identity, more explicit
revision. It is not the inverse of Summarize's output cardinality.

## Provider and result contract

The provider receives one target plus the ordinary directly owned Memories in
the same Context as read-only support. It returns only a disposition,
continuation, reason, and temporary source aliases. It never returns the full
post-image. `EXPAND` requires a nonblank continuation and `KEEP` requires an
empty continuation. The target Memory must be cited for either disposition,
and unknown source aliases fail closed.

`KEEP` is necessary because forcing every target to grow would turn missing
support into pressure to invent content. An expansion may make implicit
conditions, relationships, or consequences explicit when the frozen frame
supports them, but it may not introduce external facts, invented examples, or
unsupported claims.

## Freeze and Apply boundary

The command captures the active Context name once, resolves `UID`,
`CONTEXT:UID`, and `--context` through the shared direct-Memory and existing
Context locator grammar, and freezes the complete direct Context record before
opening a provider. A granted target must authorize UPDATE and DERIVE. Grant
identity and Context digest are revalidated after inference and again at
Apply; the Store's compare-and-swap boundary prevents publication over a
concurrent change.

Apply replaces only the selected Memory value with the deterministic appended
post-image, preserving UID and order. A changed revision writes one
`command="elaborate"` checkpoint containing the exact before, continuation,
after, reason, and source Memory UIDs. `KEEP` writes no checkpoint. Impact
prepares the same typed revision but never applies or checkpoints it.

The checkpoint carries `contract="append-only-v1"`. Before the Makemore rename,
the old generative operation also wrote `command="elaborate"`; retained Review
uses this marker to keep those legacy Makemore receipts distinct from new
append-only Elaborate receipts.

## Execution policy

Elaborate declares `COVERAGE_MAP` because each selected target has exactly one
disposition. The initial callable accepts one target and performs one provider
turn over its complete direct-Memory support frame. Staged execution is not
enabled and oversized input is rejected rather than truncated or silently
batched.

## Minimal console surface

The initial console implementation contains only the ordinary command and a
plain, non-interactive Impact adapter. It does not add an Elaborate Review
route, workbench, selector, viewer, proposal module, or session. Provider
contract helpers remain in the application module and same-UID Apply remains
in the runtime until concrete reuse pressure proves a smaller extraction.

## Intentional non-goals

The first slice does not support multi-Memory selection, descendants, embedded
Context traversal, Ground, public Python, or agent routes. It does not insert
text within the original, correct or rephrase the original, split or merge
Memories, create sibling Memories, or share Makemore's Goal-to-Rules and
Rules-to-Cases generation models.
