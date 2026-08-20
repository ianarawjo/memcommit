# Exact command review consumer boundary

## Motivation

Several terminal flows show an exact `mem` command immediately before an
action.  Sharing that visual form is useful only if it preserves the operation
boundary: the displayed command must identify the same frozen work that is
later applied, cancellation must publish nothing, and a read-only receipt must
not be mistaken for a second approval step.

This note records the consumer audit that closes `TUI-04` and `TUI-C06` in the
operation consistency matrix.  It complements, rather than replaces, each
operation's application-boundary rationale.

## Shared contract

`interfaces.tui.components.exact_command_review` owns one immutable logical
`argv` plus effects value and its terminal-safe projection.  A consequential
review owns a focused `Enter` action.  Existing `A`/`a` bindings remain only as
compatibility aliases where they were already published.  Escape or the
operation's read-only back action cancels without applying the reviewed work.

The shared component does not execute commands, open stores, or decide whether
an action needs approval.  The operation adapter must keep the displayed
identity adjacent to a typed frozen request, plan, or action and must validate
that identity again at its mutation or dispatch boundary.

The optional editable proposed-command layer is an always-visible,
non-executing setup state. It owns one-line parsing and form presentation,
while an operation adapter owns the complete argv grammar and an all-or-none
mapping back to its visible process-local controls. Valid keystrokes
synchronize those controls live; invalid intermediate text makes the compact
box red and changes no checked value. A retained upper-control change projects
the canonical command back into the same field. An adopting operation may bind
Enter on that valid synchronized field to its existing explicit final approval;
typing or synchronization alone never applies work. See the
[editable proposed-command rationale](editable-proposed-command-design-rationale.md).

## Audited consumers

| Consumer | Consequential approval | Operation-owned execution boundary |
| --- | --- | --- |
| Import | Focused `Enter`; `A`/`a` retained | Applies the adjacent frozen import plan |
| Profile rename/removal | Focused `Enter`; `A`/`a` retained | Returns one typed Profile picker action for the caller to commit |
| Ground blank and named shells | Focused `Enter` only while the exact command receipt owns Chat focus; `A`/`a` retained as the wider modal alias | Dispatches only the operation allowlist and revalidates the displayed command |
| Embed | Focused `Enter` on the blue `COMMAND · RUNNABLE` box; typing only synchronizes checked setup values and a red `COMMAND · INVALID` box blocks Enter | Returns a `FrozenEmbedPlan`; the CLI applies that same plan through `run_embed` |
| Merge | Focused `Enter` through the plan review or common Resolution workbench | Applies the same `FrozenMergePlan` and, for conflicts, the reviewed resolution set |
| Find SHOW | None: this is a receipt for the read-only action authorized by the submitted Find turn | Immediately dispatches only `mem show UID --context NAME` without a shell and leaves Find results and durable Context state unchanged |

Find SHOW deliberately uses the same immutable value and renderer so the
person can trace what ran.  Labeling it as receipt-only is important: adding an
approval prompt would turn an already-submitted read request into a redundant
second confirmation, while treating it as a mutation approval would overstate
its effects.  The allowlist and actual-output receipt are its safety boundary.

## Verification invariants

- Embed's TUI freezes but does not mutate.  The returned plan applies once;
  reusing it after the target digest changes fails without another checkpoint.
- Cancelling Embed before the final action leaves both the target record and
  checkpoint history unchanged.
- An edited Embed command validates its whole frozen-catalog mapping before
  changing Link Type, Source/Child, Target, or gap controls. Invalid input
  leaves them unchanged; valid text updates them immediately, and durable work
  still requires the field's explicit Enter approval.
- Merge plan review applies the exact plan once, cancellation does not call the
  application callback, and conflict bulk review applies one reviewed whole-set
  resolution.
- A real isolated Study Task 1 replay confirmed that decision-free direct Merge
  applies immediately, its repeated no-op records an explicit no-target-change
  checkpoint, and Embed stores the reviewed Task 1 child at the displayed gap.
- A real Task 1 Find SHOW receipt ran the exact allowlisted `mem show` command;
  every Context record, checkpoint list, current Context, and Find result stayed
  unchanged.

## Boundaries and non-goals

Decision-free Merge auto-application and no-op checkpoint policy are application
policy, not exact-command component behavior.  Recursive Merge mapping,
conflict semantics, Ground allowlists, Profile lifecycle rules, and Import
validation remain operation-owned.  New consumers must be audited before being
added to the verified matrix rows; visual reuse alone is not evidence that the
execution boundary is correct.
