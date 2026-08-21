# Interactive semantic command boundary

## Motivation

Meld, Update, and Sever each combine three different kinds of work in one
interactive experience: setup starts semantic analysis, review responses cause
another saved semantic/session turn, and final Apply publishes a reviewed
result. Treating every visible action as the same kind of exact command made
the TUI either hide executable identity or repeat a noisy command at final
Apply even though Apply already had a stronger frozen-state boundary.

The intended flow is therefore:

```text
setup -> START command -> saved session -> reviewed response
      -> TURN command -> rebuilt saved session -> final Apply
```

The final Apply is deliberately not another command line. It consumes the
already reviewed session snapshot through the operation's existing optimistic
concurrency and authority checks.

## Authored classification

`memcommit.interactive_command.INTERACTIVE_COMMAND_SURFACES` is the sole code
catalog for this interactive command policy. Each surface declares a role,
binding, approval mechanism, and rebuild triggers.

| Role | Binding | Rebuild rule | Approval |
| --- | --- | --- | --- |
| `START` | `PORTABLE` | every setup draft change | focused Enter |
| `TURN` | `SESSION_REVISION` | every response change and every saved-session revision | focused Enter |
| `RECEIPT` | operation-owned | none; the command already ran | none |
| `NONE` | none | none | none |

Meld, Update, and Sever register `setup` as `START`, `semantic-turn` as
`TURN`, and `final-apply` as `NONE`. Summarize, Distill, and Atomize register
their existing semantic-result surfaces as `NONE`; this rollout does not add
exact-command ceremony to those bounded transform/review flows.

## START commands

The setup UI continually derives a complete public argv from its typed draft.
Meld and Update use the shared Endpoint Setup command slot; Sever's older
stacked setup exposes the same compact `COMMAND · RUNNABLE` boundary. Enter on
the command is required after the endpoint fields have been validated.

The argv is portable: it contains canonical Context names, explicit range
flags, and exact Memory selectors where selected. It can be pasted into a
shell to start the same public operation. Executing from the TUI does not
recursively invoke Typer or a subprocess, however. The caller receives the
same typed setup receipt and enters the normal application boundary directly.
This avoids a second parser, nested terminal, and disagreement between the
displayed command and the data already validated by the setup controls.

START begins or resumes analysis and may save a review session. It never
performs final Apply. Its effect text states this limit explicitly.

## TURN commands

The common Resolution Session final-review layer accepts an operation-owned
builder from a typed `ResolutionWorkbenchAction`. It displays the complete
argv before the semantic/session action, freezes that review, then rebuilds it
again when Enter approves the final action. A mismatch returns to review
instead of executing stale intent.

Every generated TURN command includes `--expect-session DIGEST`. Meld hashes
the complete canonical session record, Update hashes the complete serialized
staged session, and Sever uses the opaque version token returned by its session
application boundary. The public command rejects the turn before provider or
session mutation when that token no longer matches. After a successful turn,
the operation reloads/reprojects the new saved session; the next command is
therefore rebuilt with the new revision.

TURN commands preserve the existing public grammar:

- Meld uses its endpoint shape plus `--issue`, `--choice`, `--comment`,
  `--preserve-all`, or `--defer-all` as applicable.
- Update uses its endpoint shape plus `--comment`.
- Sever uses `--resume`, `--candidate`, `--choice`, and optional custom
  `--comment`.

No displayed TURN command applies Context effects. Meld and Update rebuild a
staged semantic proposal; Sever records one reviewed candidate decision.

## Final Apply boundary

Meld, Update, and Sever keep the existing explicit final review and Apply
action without a command section. Apply is bound to the in-memory/saved
snapshot already shown, performs operation-owned authority and freshness
checks, and publishes through the existing atomic or require-new application
service. Closing the review publishes no Apply effect.

This asymmetry is intentional. A second argv at Apply would add visual weight
without strengthening identity, while inviting a parallel scripted grammar
for data already represented by a typed frozen snapshot. Existing explicit
CLI Apply options remain supported public interfaces; they are not the
identity shown by this TUI stage.

## Alternatives considered

- **Show only the launch command.** This leaves later provider/session turns
  untraceable and lets the TUI drift from the public command grammar.
- **Show a command for final Apply too.** This duplicates the frozen Apply
  boundary and makes long sessions end with the noisiest command even though
  no semantic draft remains to rebuild.
- **Execute the displayed argv through a nested shell/Typer invocation.** This
  would re-resolve mutable current state, open nested TTYs, and create a second
  error/receipt path. Typed in-process execution preserves the already frozen
  values.
- **Use only session UID for TURN.** A UID identifies the artifact but not its
  reviewed revision. The digest/version token is required to reject stale
  pasted commands.

## Remaining boundaries

The command catalog classifies interaction semantics; it is not an operation
route-state ledger and does not replace operation evidence. Draft persistence,
provider batching, response schema, destination changes, authority, cache
reuse, final materialization, and Undo remain operation-owned. `RECEIPT` is
available for future already-submitted read actions but is not used to relabel
final Apply.

## 2026-08-20 lifecycle clarification

START and TURN still bind semantic decisions to exact saved revisions. The
final commandless Apply is now described as consuming a DECIDED execution
session, and success returns a compact receipt. Public Review is not a TURN or
final-Apply host; nonterminal Update, Meld, and Sever sessions resume through
their owning command.
