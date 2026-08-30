# Makemore Rename Design Rationale

## Decision

The existing top-down generative operation is named **Makemore**. It still
turns one Goal into an exact number of suggested Rules, or one or more Rules
into an exact number of suggested Cases. The rename covers the CLI and TUI,
Impact and Review routes, application package, Ground composition, public
Python client, agent tool, provider contract vocabulary, fixtures, tests, and
operation evidence registries.

The name `elaborate` is not retained as a callable alias. It is intentionally
vacant for a later operation with different per-Memory revision semantics.

## Behavior-preserving boundary

This migration changes the operation namespace, not its semantic contract.
Makemore preserves the former operation's:

- Goal-to-Rules and Rules-to-Cases directions;
- exact proposal-count validation and default count;
- best-effort default and explicit strict Case-validation gate;
- Target ambient-context authority and disclosure rules;
- provider-call, prepared-result, atomic Add, Ground adoption, and read-only
  Review boundaries; and
- unverified result status and existing provider/agent payload shapes apart
  from operation-name tokens.

Provider contract version 14, checkpoint payload version 5, and agent contract
version 5 therefore remain unchanged. A version increase would suggest a
semantic or structural migration that did not occur.

## Persisted-record compatibility

New checkpoints write `command="makemore"` with a nested `makemore` payload,
and new Ground adoption receipts identify their source operation as
`makemore`.

Existing terminal checkpoints may contain `command="elaborate"` and an
`args.elaborate` payload. `mem review makemore` recognizes those records and
projects them under the canonical Makemore name. The compatibility is
deliberately read-only and exists at the retained-history boundary; it does not
reintroduce `mem elaborate`, `client.elaborate()`, or an Elaborate agent tool.
The Ground adoption request also accepts the old stored source-operation token
so a proposal retained before the rename is not invalidated.

## Evidence and history

Current operation evidence is registered under Makemore. Historical execution
outputs and terminal captures keep their original Elaborate filenames and
visible labels because they record what the product displayed at that time;
rewriting them would falsify provenance. New terminal captures establish the
Makemore command and review path without replacing that history. The ordered
capture log is under
`agent-records/docs/screenshots/makemore-rename-20260830/`.

## Intentional non-goals

This step does not revise Makemore's console workflow, prompt semantics,
quality policy, or shared Distill boundary. It also does not implement the new
future Elaborate operation. Those changes require separate design and review
so a namespace migration cannot conceal behavioral changes.
