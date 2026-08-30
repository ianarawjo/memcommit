---
name: memcommit-atomize
description: Use the registered memcommit_atomize tool to inspect and apply structural Atomize analysis in an existing local MemCommit Context. Supports whole-Context or exact-Memory analysis, saved/prepared reuse, explicit provider refresh, read-only issue evidence, version-bound Output planning, in-place Apply, and require-new Save As. Use when the user asks to split composite Memories, inspect Atomize cache/provider origin, or publish an exact Atomize result. Do not use for issue resolution, conversational Grounding, arbitrary rewriting, or unapproved mutation.
---

# MemCommit Atomize

Invoke `memcommit_atomize` directly. Do not reconstruct the operation with
shell commands, Python snippets, provider calls, or filesystem access.

## Open and inspect

- Send `version: 1` and `kind: open`. Supply the intended existing
  `context_name`, or omit it only when the frozen current Context is intended.
- Add `memory_selector` to focus one exact Memory. Use a UID/prefix or exact
  selector returned by MemCommit; do not invent one.
- Normally keep `refresh: false` and `use_prepared: true`. Set `refresh: true`
  only for an explicitly requested fresh provider analysis. Set
  `use_prepared: false` only to bypass hidden prepared analysis.
- Interpret `origin`, `provider_used`, `cache_used`, and `effect` literally.
  `SAVED` is provider-free and has no new effect; `EXACT_PREWARM` is cached;
  `PROVIDER` performs inference. Opening never edits the Source Context.

Review the overview, every item and proposed child, evidence spans, read-only
issues, Output Context, action permissions, and returned `version`. Atomize
records ambiguity and conflict but does not collect or incorporate responses.
Use the newest proposal version after every successful action. Never reuse an
older version after an Output change.

## Plan the exact Output

- To change where the result will be published, send
  `kind: plan_output`, the exact version, and `output_context_name`. The Source
  name means in-place Apply. Any different name is a require-new Save As plan:
  it must not already exist and planning it creates nothing.
- Output planning is a provider-free derived-session change. Present the
  returned proposal and continue only with its new version.

## Materialize only an approved proposal

- For an in-place plan, send `kind: apply_as_is` with the exact current
  `expected_version` only after explicit approval and only when its action is
  allowed.
- For a distinct Output, send `kind: save_as` with the exact current
  version only after explicit approval. Save As leaves Source unchanged,
  creates the require-new Output with one checkpoint, and selects it.
- Report the checkpoint UID, split/child/preserved counts, source-to-result
  lineage, unresolved-at-Apply count, whether a Context was created, and
  `recovered`. Final application runs only Atomize's normal-form verification;
  it does not resolve or reinterpret recorded issues.

If a final Apply or Save As response is lost, repeat the exact same payload at
most once. `recovered: true` confirms the original checkpoint. Never change the
Context, action, destination plan, or version during that retry.

## Handle failures

- On `stale_state`, reopen and present the new exact proposal. Require fresh
  authorization before any final effect.
- Retry `provider_failure` at most once only for a still-requested provider
  action. Output planning does not use it.
- Correct `invalid_request` only when the intended exact value is already
  known. Treat all other failure categories as lacking a complete outcome and
  do not speculate about hidden provider, Store, cache, or host details.

If `memcommit_atomize` is unavailable, state that the host has not registered
the required tool. Do not fall back to shell access unless separately asked.
When an issue needs resolution, report its evidence and leave the follow-up to
the caller; Atomize deliberately exposes no response or Grounding action.
