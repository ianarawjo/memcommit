# Study shared prewarm bundle design rationale

## Decision

Ordinary semantic caches remain owned by the Profile whose data, authority,
configuration, and interaction produced them. A participant Study Profile is
different: its prepared starting analyses were produced from one frozen Study
baseline and are identical for every run of that Study revision. Those
portable starting artifacts are therefore owned by the Study baseline bundle,
not by each participant Profile.

`init-study` now publishes the baseline's validated
`study-semantic-prewarm` tree once under the content-addressed
`~/.mem-profiles/study-semantic-prewarm-bundles/<bundle-digest>/` namespace.
The participant Store receives only
`study-semantic-prewarm-reference.json`, which pins the exact bundle digest and
baseline Profile UID.

The digest covers the strict registry. Every registry entry in turn covers its
artifact bytes by SHA-256, so changing, adding, or removing an artifact creates
a different bundle identity. An existing Study run never follows a mutable
"latest" pointer.

## Runtime ownership boundary

The shared bundle is portable, read-only semantic input. Operation lookup may
read an artifact only for an active participant Study Profile whose recorded
baseline UID matches the bundle. It must still validate the current task
description, Context and Memory identities and digests, provider contract,
model and reasoning configuration, authority, and operation-specific request.

Opening a prepared operation creates only the ordinary run-local state that
the participant actually requested. Compare, for example, reads one exact
shared artifact and publishes its granted comparison wrapper and session into
that participant Store. Responses, choices, later live provider results,
application state, checkpoints, and receipts remain participant-local and
never flow back into the shared bundle or another participant run.

Legacy Study runs that already contain a copied local registry remain readable.
A Store must not contain both a local registry and a shared reference; that
ambiguous ownership state fails closed. Shared-bundle garbage collection and
portable export are separate lifecycle work: a referenced bundle must not be
deleted merely because its baseline Profile was later changed or removed.

Summarize is deliberately asymmetric with saved-session operations. Its exact
shared artifact materializes a typed `SummarizeResult` only for the explicit
invocation because ordinary Summarize has no durable session or analysis
catalog. It does not create a participant-local Summary cache merely to imitate
Compare storage. Direct and recursive frames are separate exact requests; a
miss runs one ordinary whole-frame Summarize call.

## Compare exact-matrix boundary

Participant-facing Compare no longer uses a parent analysis to synthesize a
smaller report. The former projection preserved ledger coverage, but generic
replacement prose such as "a surviving part" was not a fresh interpretation
of the requested pair and could not truthfully support `WHAT MEM UNDERSTOOD`.

Every declared named Context pair must instead have its own artifact produced
by the ordinary Compare provider contract. The currently frozen Study graph
contains 718 such opposite-side pairs: 56 in Task 1, 289 in Task 2, and 373 in
Task 3. The 2026-08-13 preparation executed that entire matrix with 16
concurrent ordinary Compare calls: 5 rows reused an existing exact artifact,
713 were newly generated, 718 validated, and 0 failed. The prior sixth exact
artifact is the reverse-direction Task 1 parent request and remains a separate
valid row outside this manifest. An exact artifact may be re-rooted only when
the complete ordered provider-visible evidence is byte-identical. A missing
exact pair runs the ordinary live Compare path.

After the Summarize matrix was added, the resulting shared bundle has 921 total
entries: 719 Compare, 198 Summarize, and one each for Atomize, Sever, and
Update. It occupies 26.727 MiB on disk. The Summarize artifacts contribute
1.322 MiB. Participant bundle references remain below 512 bytes and no
artifact bytes are copied into a participant Store.

Symmetric Meld follows the same exact Compare prerequisite rule. Directional
Meld retains its distinct operation-owned action contract until its declared
matrix is separately revised; it must not be presented as ordinary Compare.

## Sever exact whole-request boundary

Sever uses the same shared-bundle and participant-overlay ownership, but its
cache unit is one ordinary whole request: a complete frozen Source frame plus
a complete frozen Criteria frame evaluated together in one normal Sever
provider turn. The artifact is eligible only for that exact binding, scope,
output name, description, provider contract, model, and reasoning setting.

Sever neither projects a parent artifact downward nor composes child cells
upward. If the Study protocol intends only the full personal-memory × full
guardrails request, one actually executed whole-frame artifact is sufficient.
If it names several requests, each request is executed whole-frame and stored
separately; aliases may share an artifact only when their complete frozen
provider-visible evidence and exact binding are identical. A miss runs the
ordinary one-turn Sever path and creates no partial participant state.

## Rejected alternatives

- Copying the bundle into every Study run makes storage scale with participant
  count even though the prepared bytes are identical.
- Referencing the mutable baseline directory lets a later edit silently change
  an already-started Study.
- Symlinks make ownership and deletion depend on filesystem topology and do
  not provide a digest-checked immutable revision boundary.
- Parent-to-child Compare projection is compact but does not produce a report
  from an actual Compare of the requested pair.
- Splitting Sever into Context cells changes the semantic neighborhood seen by
  the provider and makes an upward-composed overview look like a whole-frame
  judgment that never occurred.
