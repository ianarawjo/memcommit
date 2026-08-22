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
primary outcome of `mem atomize`, `mem dedun`, `mem distill`, `mem elaborate`,
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

## Compact judgment surface

An execution command with unresolved judgments uses a report-free decision
surface rather than embedding the complete Impact document above its controls.
The surface shows one issue's kind, title, question, and operation-authored
choices at a time. `Left`/`Right` wraps across issues, so the person may answer
them in any order; it is not a forced one-item wizard. `Up`/`Down` moves the
visible keyboard target, `Enter` stages that row, and `1` through `9` are direct
choice accelerators. The blue target makes arrow movement visible, while `✓`
is the complete non-color channel for a staged value.

Staging is process-local or saved through the operation's existing draft port.
It does not call a provider or mutate a Context. One Continue action may submit
all staged required choices together. `D` remains a first-class Defer action,
and a consequential semantic turn still receives the adjacent exact-command
review required by its operation. The compact surface may mark
`(Recommended)` only when the operation's typed option identity or label says
so; choice order alone is not a recommendation.

The complete report remains durable. Execution receipts name the exact Impact
or Review route that opens it, but execution itself does not render the report
before every choice or reopen it after terminal success.

## Evidence ownership

Distill, Elaborate, Forget, Dedun, and Resolve use immutable checkpoint-backed
Review records. Their checkpoint payloads retain the exact applied content,
pre/post image, selected survivor, or verified candidate reasoning needed by
the operation's report. Update, Meld, Sever, and Atomize already have durable
operation-owned session/analysis identities; Review opens only their terminal
application projection.

The compact receipt is not reconstructed by parsing rendered text. It is
projected from the typed application/session receipt. Likewise, Review reads
typed persisted evidence and never treats the receipt's display label as
authority to mutate.

## Intentional variants

- Audit, Compare, Impact, Find, Query, Rationale, Trace, and other read/report
  operations still produce reports and retain Viewer behavior. Reporting is
  their job.
- An execution operation may expose an explicit Impact route for preflight
  inspection. Impact remains non-mutating and is not silently inserted into
  the execution lifecycle.
- Required ambiguity/conflict decisions use the compact Resolution projection
  by default. Explicit Impact and Review retain the source-linked report and
  the full shared Viewer when inspection is requested.
- Ground-owned Distill/Elaborate proposal adapters remain read-only where their
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
must not expose them as terminal evidence.
