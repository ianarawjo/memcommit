---
name: memcommit-atomize
description: Use the registered memcommit_atomize tool to inspect and complete structural Atomize reviews in an existing local MemCommit Context. Supports whole-Context or exact-Memory analysis, saved/prepared reuse, explicit provider refresh, version-bound response and Output-plan edits, unary response reanalysis, in-place Apply, reviewed require-new Save As, and one approved incorporate-and-apply action. Use when the user asks to review or split composite Memories, inspect Atomize cache/provider origin, resolve a structural review, or publish an exact reviewed Atomize result. Do not use for conversational Atomize Grounding, arbitrary rewriting, or unapproved mutation.
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

Review the overview, every item and proposed child, evidence spans, issues,
current responses, Output Context, action permissions, and returned `version`.
Use the newest proposal version after every successful action. Never reuse an
older version after a response or Output change.

## Edit the exact review

- To replace one issue response, send `kind: respond`, the proposal's exact
  `expected_version`, `issue_uid`, `option_uid` (or `null`), and the complete
  `comment`. This replaces the prior response. Send both `option_uid: null`
  and `comment: ""` to clear it.
- To change where the reviewed result will be published, send
  `kind: plan_output`, the exact version, and `output_context_name`. The Source
  name means in-place Apply. Any different name is a require-new Save As plan:
  it must not already exist and planning it creates nothing.
- Both edits are provider-free derived-session changes. Present the returned
  proposal and continue only with its new version.

## Incorporate responses

- Send `kind: reanalyze` only when the proposal advertises that action as
  allowed and the user wants answered unary guidance incorporated. This makes
  one provider turn, replaces the saved analysis/workbench pair atomically,
  preserves the reviewed Output plan, and returns a new proposal/version.
- Do not present pairwise conflict responses as incorporated. Atomize keeps
  those review-visible but does not flatten them into unary provider frames.
- When the user explicitly approves both incorporation and the resulting
  materialization as one action, `kind: incorporate_and_apply` performs the
  provider reanalysis and then follows the reviewed in-place or Save As plan.
  Otherwise use `reanalyze`, show its new proposal, and ask for Apply approval.

## Materialize only an approved proposal

- For an in-place plan, send `kind: apply_as_is` with the exact current
  `expected_version` only after explicit approval and only when its action is
  allowed.
- For a distinct reviewed Output, send `kind: save_as` with the exact current
  version only after explicit approval. Save As leaves Source unchanged,
  creates the require-new Output with one checkpoint, and selects it.
- Report the checkpoint UID, split/child/preserved counts, source-to-result
  lineage, unresolved-at-Apply count, whether a Context was created, and
  `recovered`. Final application is provider-free unless the caller selected
  the explicit compound incorporate-and-apply action.

If a final Apply or Save As response is lost, repeat the exact same payload at
most once. `recovered: true` confirms the original checkpoint. Never change the
Context, action, destination plan, or version during that retry.

## Handle failures

- On `stale_state`, reopen and present the new exact proposal. Require fresh
  authorization before any final effect.
- Retry `provider_failure` at most once only for a still-requested provider
  action. Response edits, Output planning, Apply, and Save As do not use it.
- Correct `invalid_request` only when the intended exact value is already
  known. Treat all other failure categories as lacking a complete outcome and
  do not speculate about hidden provider, Store, cache, or host details.

If `memcommit_atomize` is unavailable, state that the host has not registered
the required tool. Do not fall back to shell access unless separately asked.
Use `memcommit_atomize_grounding` when the request is to discuss or resolve an
Atomize issue conversationally rather than operate the structural review.
