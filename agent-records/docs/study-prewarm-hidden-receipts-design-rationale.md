# Study prewarm lazy-reference design rationale

> Historical design: the prewarm implementation was removed on 2026-09-06.
> Scenario data and ordinary sessions remain; see [retirement rationale](study-prewarm-retirement-design-rationale.md).

## Decision

`mem init-study` does not copy declared semantic artifacts into the participant
and does not write per-entry hidden receipts. Before attaching a bundle it now
validates every declared artifact and regenerates supported obsolete cache
generations; it then records one small reference to the resulting
content-addressed immutable Study bundle: its digest and baseline Profile UID.
It creates no ordinary Atomize, Compare, Update, Meld, or Sever session.

The first explicit matching command reads only artifacts eligible for its
exact evidence and compatible cached quality,
checks its file digest and operation-owned evidence against the current frozen
request, revalidates Context and Grant authority, and publishes ordinary state
through that operation's existing save/CAS boundary. Bare session launchers
and saved-session review commands therefore start empty, while the shared
artifact bytes are stored once per Study revision rather than once per run.

## Motivation

The fixed Study analysis must be available without a foreground provider call,
but a prepared result is not participant history. Publishing it during
`init-study` previously made Atomize appear already open and made Compare and
Update artifacts look like participant-created sessions. That differed from
Directional Meld and Sever, which already retained hidden lookup receipts.

Separating shared cache ownership from participant-visible materialization
preserves all three requirements:

- the first matching request is provider-free under its operation's cache
  policy;
- the visible session catalog records operations the participant actually
  started; and
- participant count does not multiply the shared artifact bytes.

Successful setup is deliberately summarized as `Shared Study prewarm bundle
attached.` It does not enumerate operation names, task-to-operation mappings,
artifact counts, or prepared branches. Those are researcher diagnostics that
could prime a participant toward a measured command.

## Shared reference contract

Every new participant Store contains one strict reference envelope:

- kind and schema version;
- baseline Profile UID; and
- immutable bundle digest.

The digest covers the strict registry, whose entries cover every artifact file
digest. The reference contains no workbench response, application state,
Context mutation, operation name, or ordinary session identity. Symlinks,
malformed JSON, unexpected fields, a missing bundle, and a baseline mismatch
are rejected. Registry metadata is cheap to read; artifact bytes are read and
hashed only for the requested entry.

At first use, operation-specific evidence remains narrow. Atomize binds the analysis,
Source, and tutorial description. Compare binds the exhaustive analysis and
task description. Update binds the operation ledger, Source, target, and task
description. Directional Meld binds both frames and its Compare seed. Sever
binds its Source and Criteria frames.

## First-use materialization

Atomize installs the exact prepared `AtomizeAnalysisSession` and creates a new
blank run-local workbench only after `mem atomize --context ...` or
`mem impact atomize ...` identifies a matching shared artifact. The declared
Output plan is restored, but no review response or application state crosses
runs.

Compare passes an exact or evidence-identical re-rooted artifact through the
ordinary Compare execution boundary. Each declared named pair was actually
executed under the normal Compare provider contract. Participant-facing parent
projection is unavailable; an unprepared pair runs live. Symmetric Meld uses
the same exact Compare prerequisite.

Update materializes an Impact plan from `mem impact --from ... --to ...` or a
staged plan from `mem update ...`. Exact, equivalent-scope, and projected
origins remain distinct. Current Source, target, Grant, owner, provenance, and
operation completeness checks run before the plan is published.

Directional Meld retains its operation-owned action-ledger semantics. Sever
loads only an exact ordinary whole Source × whole Criteria request and never
projects a parent or composes child cells. Both create fresh participant-local
state only after the invoking command freezes and authorizes its request.
Legacy operation-specific receipt readers remain compatibility fallbacks for
older Study runs; new initialization writes no receipt directory.

Meld resolution bundles contain one or more researcher-reviewed **final**
whole-ledger reconciliations. The issue options already present in the frozen
initial assessment are provider-free local branches, so the bundle does not
store ten separate semantic outputs for five binary issues and does not
enumerate 32 vectors. The artifact binds each final outcome to the exact task
description, provider provenance, branch-set digest, and request-contract
version. It publishes no Meld row or selected choice. The first exact complete
choice vector uses an exact or component-wise higher compatible cached
identity, replays the response
through Meld's ordinary decoder and live Context/Grant checks, and copies that
outcome into the run-local cache. This makes prewarming an acceleration of an
actual complete participant action, not a preselected answer.

## Invariants

- Setup pins the immutable bundle but must not publish a participant-visible
  session or operation receipt.
- A shared artifact is usable only by the active participant Profile whose
  baseline UID matches the pinned registry.
- The requested artifact file digest and operation-owned exact evidence are
  revalidated at first use.
- A lower or incomparable cached provider/model/reasoning identity,
  description drift, edited or added evidence, lost authority, and ambiguous
  matching all miss or fail before publication. Artifact provider identity
  remains exact provenance even when its quality dominates the request.
- A cache hit does not bypass the operation's authorization, revalidation,
  save, CAS, review, or apply boundary.
- Compare and Sever do not project. Any projection retained by a different
  operation remains labeled and never claims to be a fresh semantic judgment.
- First materialization publishes atomically; a failed Atomize workbench save,
  Compare CAS, or Update publication leaves no partial visible session.

## Alternatives considered

Keeping prewarmed sessions visible after initialization was rejected because it
mixes setup state with participant history. Copying only a blank session row
was also rejected: the row would still imply that the operation had started and
would require operation-specific cleanup rules.

Copying the registry tree and writing one receipt per entry was rejected
because both setup work and storage scaled with entries × participants even
though every participant began from the same frozen bytes. Consulting a
mutable baseline directory was also rejected because a later baseline edit
could silently change an existing Study run. The pinned digest plus first-use
exact validation gives an immutable revision boundary without setup-time
per-entry work.

## Compatibility and limitations

Previously materialized Atomize, Compare, and Update sessions remain readable
and resumable. Copied local registries and legacy receipts remain recognized.
The change does not erase existing visible sessions from already-created Study
runs; it changes new initialization and first use. A Store containing both a
copied registry and a shared reference is ambiguous and fails closed.

The registry declares fixed operation artifacts and reviewed Meld branch
bundles rather than accepting arbitrary participant cache content. Run-local
Meld memoization remains separate and cannot update the baseline registry.
Parent/subset projection is
allowed only where an operation adapter can preserve exhaustive disposition,
provenance, authority, and application readiness. A live refresh remains the
explicit escape hatch when those proofs do not hold.
