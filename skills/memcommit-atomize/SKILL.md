---
name: memcommit-atomize
description: Use the registered memcommit_atomize tool to inspect structural atomicity in an existing local MemCommit Context, reuse saved or exact prepared analysis, request an explicit fresh analysis, and optionally apply one exact reviewed proposal in place. Use when the user asks to review or split composite Memories, run structural Atomize, inspect Atomize cache/provider origin, or apply an already reviewed Atomize result. Do not use for Save As, response editing, conversational Atomize Grounding, arbitrary rewriting, or unapproved mutation.
---

# MemCommit Atomize

Invoke `memcommit_atomize` directly. Do not reconstruct the operation with
`mem atomize`, Python snippets, provider calls, or filesystem access.

## Open one structural review

- Always send `version: 1` and `kind: open`.
- Supply `context_name` when the intended existing local Context is known.
  Omit it only when the host's frozen current Context is intentionally the
  Source. Never invent or create a Context.
- Normally keep `refresh: false` and `use_prepared: true`. Set `refresh: true`
  only when the user explicitly requests a fresh provider analysis. Set
  `use_prepared: false` only when the user explicitly asks to bypass hidden
  prepared analysis; this does not bypass an exact saved-session hit.
- Interpret `origin`, `provider_used`, `cache_used`, and `effect` literally.
  `SAVED` is provider-free with `effect: NONE`; `EXACT_PREWARM` is cached but
  materializes a `DERIVED_SESSION`; `PROVIDER` uses the provider and creates a
  `DERIVED_SESSION`. None of these open paths edits the Source Context.

Review the overview, every item classification and action, proposed children
and evidence spans, unresolved issues, Output Context, and
`in_place_apply_allowed`. Present the material consequences to the user. Do
not call `apply_as_is` merely because `open` succeeded.

## Apply only the exact reviewed proposal

- Apply only after the user explicitly authorizes the proposal returned by
  `open`. Copy its `apply_as_is.expected_version` exactly; do not synthesize,
  shorten, normalize, or replace the token.
- Send `version: 1`, `kind: apply_as_is`, the same `context_name`, and that
  exact `expected_version`. Do not refresh, reopen, or edit the workbench
  between review and Apply.
- Proceed only when `apply_as_is.allowed` and `in_place_apply_allowed` are
  true. If either is false, explain that this tool cannot execute the Output
  plan; Save As and response editing remain in the reviewed CLI/TUI lifecycle.
- On success, report `checkpoint_uid`, split/child/preserved counts, lineage,
  unresolved-at-Apply count, and `recovered`. Apply is provider-free and its
  effect is exactly `CONTEXT_CHECKPOINT`.

If an Apply response is lost at the transport boundary, repeat the exact same
`apply_as_is` payload at most once. A successful retry with `recovered: true`
confirms the original checkpoint. Never change the Context or version during
that retry.

## Handle failures

- For `stale_state`, do not retry Apply. Reopen the review and present the new
  exact proposal; require fresh user authorization before using its version.
- Retry `provider_failure` for `open` at most once and only while it still
  matches the user's request. Apply never needs a provider retry.
- Correct `invalid_request` locally only when the exact intended value is
  already known. Treat `context_unavailable`, `storage_failure`,
  `execution_failed`, `atomize_failed`, and `internal_error` as lacking a
  complete requested outcome. Do not speculate about hidden provider, Store,
  cache, or host details.

If `memcommit_atomize` is unavailable, state that the host has not registered
the required tool. Do not fall back to shell access unless the user separately
asks for CLI use. Use `memcommit_atomize_grounding`, not this Skill, when the
request is to discuss or resolve an Atomize issue conversationally.
