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

## Interaction classification

START, TURN, RECEIPT, and NONE are vocabulary for describing the interaction
boundary, not a parallel runtime registry. The concrete operation command
builders and the screens that consume them are the authored implementation.
Their tests must verify the displayed argv, revision binding, approval path,
and commandless Apply boundary directly.

The shared console boundary lives at
`memcommit.adapters.console.terminal.components.command_editor`. Its `model`
owns the immutable `CommandReview`; operation-local Meld, Update, and Sever
codecs project START and TURN state through the same `build_start_review` and
`build_turn_review` names. Rendering and input remain neutral presentation
mechanics outside those projections.

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

These interaction roles are not an operation route-state ledger and do not
replace operation evidence. Draft persistence, provider batching, response
schema, destination changes, authority, cache reuse, final materialization,
and Undo remain operation-owned. A receipt describes an already-submitted
action and is not used to relabel final Apply.

## 2026-08-28 disconnected registry retirement

The standalone `interactive_command` registry was removed. No production
screen or execution route read it, and its tests checked only the registry's
own declarations, so it could remain green while the concrete builders or
screens diverged. The role vocabulary above remains useful design language,
while executable evidence now belongs beside the real operation-specific
command projection and its consuming interaction surface.

## 2026-08-20 lifecycle clarification

START and TURN still bind semantic decisions to exact saved revisions. The
final commandless Apply is now described as consuming a DECIDED execution
session, and success returns a compact receipt. Public Review is not a TURN or
final-Apply host; nonterminal Update, Meld, and Sever sessions resume through
their owning command.

## 2026-08-25 closed terminal execution

The ordinary attached-terminal paths for Meld and Update no longer enter the
START → TURN → Apply sequence described above. The command invocation is the
submitted operation: once its initial semantic result is complete, a local
Target advances directly through the existing freshness and application
boundary. A provider wait may remain visible, but it is progress for that one
command rather than a viewer or an invitation to submit another opinion.

For symmetric Meld, the imported Compare analysis is already the exhaustive
relation ledger. The default terminal path therefore performs no second
provider turn. It coalesces an `EQUIVALENT` relation into one exact
source-supported claim and preserves every member of every other relation as
an independently revisable Memory. This is deliberately a small structural
meld: it neither invents a synthesis nor chooses a winner for a conflict. The
conservative materialization replaces turn zero in the same saved revision,
then a local Result is applied and the command prints its receipt. Directional
Meld applies an already decision-complete analysis; an unresolved directional
analysis ends with an incomplete receipt rather than opening Responses.

For Update, the first complete provider plan is the operation result. A local
Target or a local Target derived from a granted read-only Source applies
without opening the staged Impact/comment workbench. A mutating granted
Target retains one narrow exact-plan ownership approval in a TTY, because the
invocation alone must not silently authorize a write to another owner; that
surface exposes Accept/close but not comment-driven revision. A zero-operation
plan needs no approval because it publishes no Context mutation.

The old TURN grammar remains callable for explicit compatibility routes such
as `--comment`, `--choice`, `--preserve-all`, saved Review, and non-interactive
Meld scripting. It is no longer the default attached-terminal experience.
Ground remains conversational by design, and Sever retains its reviewed
selection semantics. Resolve, Dedun, Distill, Forget, and Atomize already had
closed ordinary CLI execution, so this change does not add a second execution
mode to them.
