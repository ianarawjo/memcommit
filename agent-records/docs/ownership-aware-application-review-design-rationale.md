# Ownership-aware application review design rationale

## Motivation and revised reasoning

The first simplification treated review as a property of the operation:
Atomize and Update often had no unanswered decision, so their workbenches could
start at final approval. That removed a redundant report traversal but retained
an approval screen for every mutation.

The more useful boundary is not the command name. It is **who owns the Context
that the exact proposal will mutate, whether a semantic decision remains, and
whether the complete local mutation has an Undo receipt**. A local reversible
change does not need a confirmation screen merely to repeat an already exact
proposal. A write through a Grant changes an authority Profile's Context and
retains explicit final review even when the proposal has no unresolved choice.

This distinction also explains why the ownership of an input is insufficient.
A granted Source can feed a new local draft without being mutated. Sever is the
clearest example: Source and Criteria remain unchanged, the Output is a new
local Context, and its creation checkpoint is reversed by `mem undo`. Conversely,
a granted Update Target, directional Meld Baseline, or Forget Source is the
actual authority object being changed and must not be silently crossed.

## Application-layer owner

`memcommit.application_review_policy` owns the terminal-independent policy
value and classifier. It imports no CLI, TUI, Store, provider, or operation
module. Command and workbench adapters may consume the classification, but
they continue to own presentation and must not reimplement the ownership/Undo
truth table. The classifier accepts exact booleans only; ambiguous truthy
metadata fails before it can authorize automatic application.

## Decision-free behavior

One semantic mutation may bypass all review surfaces and return its existing
exact Accept action only when every condition below holds:

1. The operation adapter declares the current proposal applicable.
2. No `REQUIRED` item is unanswered.
3. The derived To Do action is exactly `APPLY` or `APPLY AS IS`; a pending
   response, incorporation turn, destination correction, or whole-set semantic
   strategy prevents the bypass.
4. Every published mutation is local to the active Profile. Merely reading a
   granted Source does not change this classification.
5. The operation records one complete checkpoint or creation receipt that
   `mem undo` can reverse.

A validated zero-change completion may also bypass review because it publishes
no Context mutation and therefore needs no recovery unit.

The bypass is provider-free and does not weaken freshness checks, CAS,
permissions, Grant revalidation, source traceability, application idempotency,
or checkpoint creation. It chooses the already-authorized exact Accept action;
the owning command still performs its normal application path.

Direct TTY Update and changed-batch Forget deliberately use a report-plus-Apply
boundary instead of consuming this optional auto-accept policy. Their operation
adapters decide when the report is shown; authority and recovery remain exactly
as classified here. Forget's empty/all-KEEP completion still skips approval.

## Operation rollout matrix

| Operation | Mutation target | Decision-free behavior | Rollout evidence |
| --- | --- | --- | --- |
| Merge, local Target | Local direct or recursive Target graph | Apply directly when no conflict remains; a verified no-op still records a command checkpoint; recover with operation-unit Undo | `VERIFIED` first vertical slice |
| Merge, granted Target | Authority Target graph | Retain final review; exact noninteractive argv remains the explicit action | `VERIFIED` policy routing and runtime authority metadata |
| Update, local Target | Local Target owner graph | TTY report plus Apply/Esc; recover with operation-unit Undo | `VERIFIED` policy, application, failure, and recovery tests |
| Update, granted Source and local Target | Local Target owner graph | TTY report plus Apply/Esc; granted input remains read-only | `VERIFIED` ownership routing test |
| Update, granted Target | Authority Target owner graph | TTY report plus Apply/Esc; a zero-change application still has mutation boundary `NONE` | `VERIFIED` routing tests and Task 1 granted-target replay |
| Atomize in place or planned local Output | Local Input or new local Output | Apply directly; retain unresolved-at-apply audit | `NOT VERIFIED HERE` |
| Meld, local Result/Baseline | Local target | Apply directly once required issues are resolved | `NOT VERIFIED HERE` |
| Meld, granted Incoming and local Baseline | Local Baseline | Apply directly; granted input remains read-only | `NOT VERIFIED HERE` |
| Directional Meld, granted Baseline | Authority Baseline | Require final review | `NOT VERIFIED HERE` |
| Sever with direct local Source | Same Source for SELF-SAVE or new local Result for OTHER-SAVE | Apply directly; Undo restores the exact Source preimage or removes/restores the creation receipt | `VERIFIED` by the Sever boundary slice |
| Sever with granted Source | New local Result only; authority Source unchanged | OTHER-SAVE applies directly; SELF-SAVE fails before provider until authority-side mutation receipts exist | `VERIFIED` by the Sever boundary slice |
| Forget, local Source | Local Source | TTY Impact plus Apply/Esc for a changed batch; recover with operation-unit Undo/Redo | `VERIFIED` policy, CAS, checkpoint, and recovery tests plus PTY replay |
| Forget, granted Source | Authority Source | TTY Impact plus Apply/Esc for a changed batch; all-KEEP completes without a screen or Context checkpoint | `VERIFIED` routing tests and granted change/no-op PTY replay |

## Deliberate boundaries

- “Grant present” is not itself the rule. Only a Grant on the mutation target
  creates the authority-write boundary.
- Read-only review commands never auto-accept.
- An unanswered required conflict or decision always remains interactive.
- A user-authored response that requires provider incorporation is not treated
  as decision-free.
- Undo is recovery for a completed local mutation, not permission to publish a
  partial result. Application validation and atomicity requirements are
  unchanged.
- This policy does not make remote or authority mutations reversible enough to
  skip consent merely because a coordinated Undo implementation exists.
