# Execution, receipt, and post-application Review

## Decision

Memory-transforming operations are execution commands. Their public lifecycle
is:

```text
invocation (Apply intent)
  → operation-owned judgments
  → atomic Apply
  → compact Receipt
  → optional read-only Review
```

`Proposal` remains an internal value used to validate provider output, bind
choices, calculate an exact post-image, and revalidate freshness. It is not the
primary outcome of `mem atomize`, `mem dedun`, `mem distill`, `mem makemore`,
`mem forget`, `mem meld`, `mem resolve`, `mem sever`, or `mem update`.

## Motivation

The earlier shared workbench vocabulary made a generated proposal look like
the operation's product. That was misleading for Forget and Distill in
particular: their purpose is to perform a bounded transformation, not to create
a report that may later be applied. It also made a successful command reopen a
large Viewer even though no further decision could change that already-applied
result.

Merge's compact conflict route supplied the useful precedent. A mutation may
need visible judgments before publication without turning the entire report
into a precondition named Review or rendering it again after success.

## Invariants

1. Invocation of an execution operation expresses Apply intent. Interactive
   controls shown during that invocation are operation-owned judgments, not a
   separate Review operation.
2. Required judgments are resolved before publication. Local deterministic or
   decision-free defaults may advance automatically; authority-sensitive,
   ambiguous, or user-authored choices remain explicit.
3. Apply revalidates the exact decided value and publishes all effects or none.
   `PREPARED → DECIDED → APPLIED` is the shared phase vocabulary.
4. Success renders a compact receipt: outcome/effect counts, durable receipt
   or session identity, checkpoint identity where applicable, the exact
   `mem review …` route, and recovery availability.
5. Review consumes terminal application evidence. It cannot make execution
   decisions, call a provider, apply a staged proposal, or create a second
   checkpoint.
6. A one-checkpoint operation stores the facts needed for Review in the same
   checkpoint transaction as its Context effect. Saved-session operations keep
   their operation-owned terminal application receipt and expose only applied
   sessions through Review.
7. A no-change result is terminal and explicit even when it creates no Context
   checkpoint. It must not be presented as an unaccepted proposal.
8. Every saved artifact selector resolves an exact UID first and otherwise one
   unique prefix inside the operation's frozen catalog. A displayed compact
   UID is therefore callable; an ambiguous prefix asks for more characters
   instead of choosing the newest or current artifact.

## Compact judgment surface

An execution command with unresolved judgments uses a report-free decision
surface rather than embedding the complete Impact document above its controls.
The surface shows one issue's kind, title, question, and operation-authored
choices at a time. `Left`/`Right` wraps across issues, so the person may answer
them in any order; it is not a forced one-item wizard. `Up`/`Down` moves the
visible keyboard target, and `Enter` stages that row. Number keys are inert so
issue ordinals cannot be mistaken for a second choice grammar. The blue target
makes arrow movement visible, while `✓` is the complete non-color channel for
a selected value.

New compact staging is process-local and closing does not save it through an
operation draft port. It does not call a provider or mutate a Context. A blank
line separates the current issue's choices from one navigable
`APPLY ALL · n/n READY` row; Enter there consumes the complete selected set
without an `A` shortcut or a second exact-command confirmation. Defer and
Preserve-all remain compatible domain/CLI actions where an operation already
supports them, but they are not compact decision rows. The surface selects and
marks `· Recommended` only when the operation's typed option identity or label
says so; choice order alone is not a recommendation. Existing durable
responses may still seed a resumed operation, but compact edits remain
ephemeral until the operation consumes them.

The complete report remains durable. Execution receipts name the exact Impact
or Review route that opens it, but execution itself does not render the report
before every choice or reopen it after terminal success.

## Evidence ownership

Distill, Makemore, Forget, Dedun, and Resolve use immutable checkpoint-backed
Review records. Their checkpoint payloads retain the exact applied content,
pre/post image, selected survivor, or verified candidate reasoning needed by
the operation's report. Update, Meld, Sever, and Atomize already have durable
operation-owned session/analysis identities; Review opens only their terminal
application projection.

Update separates its mutable active slot from terminal evidence. The active
`staged-update.json` remains the one resumable plan or current command state.
On successful application, the validated terminal session is also written to
`update-receipts/FULL_UID.json`; a later plan may replace the active slot
without invalidating the receipt's advertised Review and Impact commands.
No-change applications are retained even though they create no Context
checkpoint. Existing terminal singletons are migrated into the ledger before
the next staged plan replaces them.

The first retained application projection is immutable. Undo and Redo may
change the active session's status, but they do not rewrite what the original
Update receipt proved at application time. Review is read-only and cannot use
a retained receipt to reactivate Apply. Publishing a terminal active session
and its receipt is exception-atomic: a failed receipt write restores the prior
active session so Context application rollback cannot leave a falsely terminal
singleton.

A plain or `--snapshot` Review projection must render every typed Memory row in
an operation-authored detail block, including its explicit `MEMORY n` identity
and complete content. It does not repeat supporting evidence spans by default;
those remain typed evidence available to interactive expansion rather than
looking like a second copy of the applied Memory. Compact execution receipts may
bound their immediate proof, but snapshot rendering cannot treat structured rows
as empty merely because the block's fallback text field is blank. Interactive
and noninteractive Review are projections of the same durable evidence with
different disclosure depth, not different stored evidence sets.

The compact receipt is not reconstructed by parsing rendered text. It is
projected from the typed application/session receipt. Likewise, Review reads
typed persisted evidence and never treats the receipt's display label as
authority to mutate.

## Intentional variants

- Audit, Compare, Impact, Find, Query, Rationale, Trace, and other read/report
  operations still produce reports and retain Viewer behavior. Reporting is
  their job.
- An execution operation may expose an explicit Impact route for preflight
  inspection. Direct TTY Update and changed-batch Forget also embed the
  Impact report beside their single Apply action. These are operation-owned
  approval boundaries, not the post-application Review command. Forget skips
  the screen for empty/all-KEEP batches; explicit non-TTY execution still
  advances directly to application. Impact projection itself remains non-mutating.
- Required ambiguity/conflict decisions use the compact Resolution projection
  by default. Explicit Impact and Review retain the source-linked report and
  the full shared Viewer when inspection is requested.
- Ground-owned Distill/Makemore proposal adapters remain read-only where their
  workspace application authority has not been implemented. This does not
  change the standalone Add lifecycle.
- Granted-authority receipts may not be discoverable from the participant's
  local checkpoint store. The command therefore does not advertise a local
  checkpoint Review route when that evidence is owned by the grant provider.

## Rejected alternatives

Keeping `Proposal → Review → Apply` as the universal public sequence was
rejected because it conflates semantic decoding with the operation outcome and
makes Review a mutation gate. Automatically opening the full Viewer after
Apply was rejected because it adds no decision capability and obscures the
receipt. Dropping detailed evidence entirely was also rejected: the evidence
is retained atomically and remains available through explicit post-application
Review.

## Current boundary

The lifecycle is shared; semantic judgments, authority, persistence, no-op
meaning, and recovery remain operation-owned. This change does not create one
universal proposal schema or one universal Review document model. A compact
execution surface does not replace custom free-form response routes when an
operation requires them; those remain operation-owned. Legacy staged artifacts
may still be resumed through their owning operation, but the Review launcher
must not expose them as terminal evidence. Receipts created before the ledger
existed remain reviewable while they occupy the active slot and are migrated on
its next normal replacement; already-replaced historical singletons cannot be
reconstructed without external evidence.
