# Init-study prewarm regeneration design rationale

## Motivation

This regeneration path belongs to the preserved `legacy-v1` scenario. The
default built-in `coffee-v1` scenario contains participant-authored semantic
inputs and therefore skips compatibility checks and shared prewarm attachment;
see `agent-records/init-study-scenario-versioning-design-rationale.md`.

Study runs pin an immutable semantic-prewarm bundle. That isolation worked as
intended, but setup previously checked only registry shape and artifact hashes.
It could therefore attach readable artifacts that the current operation runtime
would reject later. The observed bundle contained 719 Compare artifacts with
`peer-relations-v3` while runtime Compare required `peer-relations-v4`, plus one
Update artifact declaring schema 6 while runtime Update required schema 7.
Every later exact lookup failed before checking whether its input matched.

`init-study` is now the generation boundary for a new run: it validates the
baseline's declared artifacts against the current operation contracts and does
not advertise the participant Profile until any supported obsolete generation
has been replaced.

## Compatibility states

Setup distinguishes three states.

- A current artifact must pass its operation's complete semantic validator as
  well as the registry SHA-256 check.
- A supported older Compare ruleset or Update wrapper schema is readable only
  through an explicitly versioned validator. It is a regeneration input, never
  a participant result.
- Unknown generations, malformed payloads, unsafe paths, missing bytes, and
  digest mismatches remain fail-closed. Regeneration must not turn corruption
  into a cache miss.

Disabled legacy Compare entries remain in the authored baseline registry as
digest-bound declaration anchors. Operations skip them. Setup can use their
exact pair coordinates to prove that the current active matrix is complete and
to repair a missing current row on a later run.

Compare compatibility includes both the relation ruleset and the provider
contract. A supported older provider contract is treated like a supported
older ruleset: its complete artifact remains digest- and semantics-validated
as a declaration anchor, but it is never callable as a current result.

## Compare regeneration

The older semantic analysis is not projected into v4. Setup reloads each
declared pair from the newly staged participant/authority topology and sends
that current `ComparisonInput` through production `analyze_comparison`.
Reversed declarations collapse to one deterministic symmetric coordinate.
Outputs are resumable under the Profile control directory and the plan key
includes the current ruleset, provider contract, provider, model, and reasoning
identity. An older ruleset, contract, or reasoning output therefore cannot
occupy a current row.

The current baseline declares 718 unique symmetric coordinates after collapsing
one reversed Task 1 parent artifact. The actual fresh staged participant and
authority topology resolves all 718 coordinates as ordinary Compare inputs:

- Task 1: 56
- Task 2: 289
- Task 3: 373
- Total: 718

An earlier read-only audit against an already-used Study Profile predicted that
seven Task 1 coordinates would be rejected for duplicate local-plus-Grant
evidence. That topology was not representative of a fresh init. The actual
staged init manifest is authoritative for generation breadth; input-invalid
coordinates would still be skipped only when production Compare rejects the
fresh staged input before provider connection.

The first real 718-row regeneration used provider contract
`one-shot-exhaustive-v1` with the frozen Study reasoning `none`. It retained
711 valid rows, while seven rows repeatedly returned a non-`DISTINCT` relation
whose source assignments came from only one PEER side. All seven failed six
provider attempts across three resumable init runs. No participant or registry
generation was published. Compare contract
`exhaustive-validation-repair-v2` separates paired and one-sided relation
records, explicitly states the side invariant, and permits one complete
validation-repair response before failing closed.

`init-study` defaults to 96 parallel workers and exposes
`--prewarm-workers` for the available provider capacity. Pair files are written
as they complete, but none become declared in the baseline registry until the
entire executable matrix succeeds. A retrying init can reuse validated pair
files and current active artifacts.

Offline Compare generation defaults to Codex reasoning `xhigh` and exposes
`--prewarm-reasoning`. The participant's frozen live route remains `none`;
the shared conservative quality ordering proves that an `xhigh` cache from the
same provider and model satisfies that lower request. Future init runs use the
same xhigh generation identity and therefore validate and reuse the immutable
bundle without provider calls. Choosing a generation quality below the frozen
participant request fails before provider connection.

The first production v2/xhigh setup completed on 2026-08-23 with 96 concurrent
workers. It generated and published all 718 rows (`56` Task 1, `289` Task 2,
`373` Task 3), reused no v1 row, and reported zero final failures. The resulting
Study `study-20260823T203237Z-e1dd61a6` pins bundle
`bd1d4b351af2b58b7633ece069d13d51975894c1af39219a8a198a9690744063`.
A post-publication audit SHA- and semantic-validated every enabled Compare
artifact as `peer-relations-v4`, `exhaustive-validation-repair-v2`,
`gpt-5.6-sol`, and `xhigh`; all 719 older Compare declarations were disabled.
A second preparation check with provider generation replaced by a failing
sentinel returned `READY 924` and `regenerated=0`, proving that the published
matrix is reusable without another provider turn.

## Update regeneration

Update schema 6 remains readable by `UpdateSession.from_dict`, and the observed
74-operation plan passes its complete legacy validation. The semantic plan does
not require another provider turn. Setup recomputes the prewarm key and wrapper
under Update schema 7 while preserving the validated operations and provider
evidence. This is deliberately narrower than accepting schema 6 at runtime:
participants receive only a current-generation artifact.

## Publication and rollback

The participant and authority stores are first composed in staging. After their
grants are materialized, both stores move to their final private paths so the
staged registry snapshot can resolve ordinary and granted Contexts exactly as a
real participant would. Cache validation and generation then run before the
Profile registry transaction advertises either Profile.

Regenerated operation families are published with one atomic registry-file
switch. New artifact files may exist unreferenced before that switch; they are
not callable. Old enabled entries in a replaced family become disabled, and the
new current entries become enabled together. Only after this succeeds does
setup publish a new content-addressed shared bundle and attach its digest to the
participant.

If validation, a provider row, matrix coverage, or bundle attachment fails, the
new participant and authority stores are rolled back and the Profile registry
remains unchanged. Cancellation follows the same rollback path, which matters
because first-generation provider work can run for several minutes. A
completed baseline refresh may remain available after a
later Profile-registry durability failure; it is a valid immutable generation
and does not make a partial participant visible. Existing Study runs retain
their previously pinned bundle digest and are never rewritten.

The Profile registry lock remains held during first-time regeneration. This
prevents another setup or Profile mutation from changing the baseline and grant
topology during the long provider phase, at the cost of temporarily serializing
Profile-control commands. Ordinary operations on already selected stores do not
use this publication lock.

## Boundary and non-goals

A baseline with no authored prewarm registry has no finite declaration to
reconstruct, so setup attaches no bundle and does not guess a cache scope. The
automatic path repairs declared current or supported-obsolete caches, including
missing current Compare rows when retained legacy anchors define them. Adding a
new operation or a new cache coordinate still requires an authored declaration
or generator policy.

This change does not make legacy artifacts reusable by participant operations,
does not mutate old shared bundles, and does not weaken malformed-artifact
failure behavior.
