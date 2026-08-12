# Study prewarm hidden-receipt design rationale

## Decision

`mem init-study` validates every declared semantic prewarm against the new
participant run, but it does not create an ordinary Atomize, Compare, Update,
Meld, or Sever session. It writes one operation-neutral hidden receipt per
validated registry entry under `study-prewarm-installations/`.

The registry artifact remains the semantic cache. The receipt proves only that
setup validated this exact artifact, task, provider configuration, and
operation-owned evidence against this run. The first explicit matching command
loads the artifact, revalidates current Context and Grant state, and publishes
ordinary operation state through that operation's existing save/CAS boundary.
Bare session launchers and saved-session review commands therefore start empty.

## Motivation

The fixed Study analysis must be available without a foreground provider call,
but a prepared result is not participant history. Publishing it during
`init-study` previously made Atomize appear already open and made Compare and
Update artifacts look like participant-created sessions. That differed from
Directional Meld and Sever, which already retained hidden lookup receipts.

Separating cache availability from visible session materialization preserves
both requirements:

- the first exact or permitted projected request is provider-free; and
- the visible session catalog records operations the participant actually
  started.

## Receipt contract

Every declared operation uses the same strict envelope:

- kind and schema version;
- operation and Study task;
- registry entry key and artifact file digest;
- installation timestamp; and
- an operation-owned `evidence` map of semantic digests and stable identities.

The filename is derived from the operation and registry entry key, not from a
future session UID. The envelope contains no workbench response, application
state, Context mutation, or ordinary session identity. Symlinks, malformed
JSON, unexpected fields, and mismatched evidence are rejected.

Operation-specific evidence remains narrow. Atomize binds the analysis,
Source, and tutorial description. Compare binds the exhaustive analysis and
task description. Update binds the operation ledger, Source, target, and task
description. Directional Meld binds both frames and its Compare seed. Sever
binds its Source and Criteria frames.

## First-use materialization

Atomize installs the exact prepared `AtomizeAnalysisSession` and creates a new
blank run-local workbench only after `mem atomize --context ...` or
`mem impact atomize ...` identifies a matching hidden receipt. The declared
Output plan is restored, but no review response or application state crosses
runs.

Compare passes an exact or transparent re-rooted artifact through the ordinary
Compare execution boundary. Exact requests retain the prepared semantic UID.
Equivalent re-roots receive the current request identity, and subset requests
remain explicitly projected. Ordinary Compare may keep a projected result
ephemeral; a symmetric Meld prerequisite may retain it through its existing
durable boundary.

Update materializes an Impact plan from `mem impact --from ... --to ...` or a
staged plan from `mem update ...`. Exact, equivalent-scope, and projected
origins remain distinct. Current Source, target, Grant, owner, provenance, and
operation completeness checks run before the plan is published.

Directional Meld and Sever retain their existing first-use behavior. Their
legacy operation-specific receipt readers remain as compatibility fallbacks
for Study runs created before the common envelope; new initialization writes
only the common hidden receipt.

## Invariants

- Setup may validate ordinary and granted content, but must not publish a
  participant-visible session.
- A receipt is unusable without its digest-verified registry artifact.
- A registry artifact is unusable in a participant run without a matching
  installed receipt.
- Provider/model/reasoning drift, description drift, edited or added evidence,
  lost authority, and ambiguous matching all miss or fail before publication.
- A cache hit does not bypass the operation's authorization, revalidation,
  save, CAS, review, or apply boundary.
- Projection remains labeled and never claims to be a fresh semantic judgment.
- First materialization publishes atomically; a failed Atomize workbench save,
  Compare CAS, or Update publication leaves no partial visible session.

## Alternatives considered

Keeping prewarmed sessions visible after initialization was rejected because it
mixes setup state with participant history. Copying only a blank session row
was also rejected: the row would still imply that the operation had started and
would require operation-specific cleanup rules.

Deleting all receipts and consulting any artifact found in the registry was
rejected because registry presence alone does not prove that the new run's
fixtures, Grants, and configuration passed setup validation. Re-running that
entire initialization proof on every lookup would also obscure whether a cache
was deliberately installed.

## Compatibility and limitations

Previously materialized Atomize, Compare, and Update sessions remain readable
and resumable. Legacy Directional Meld and Sever receipts remain recognized.
The change does not erase existing visible sessions from already-created Study
runs; it changes new initialization and first use.

The registry currently declares fixed operation artifacts rather than a
general-purpose semantic memoization system. Parent/subset projection is
allowed only where an operation adapter can preserve exhaustive disposition,
provenance, authority, and application readiness. A live refresh remains the
explicit escape hatch when those proofs do not hold.
