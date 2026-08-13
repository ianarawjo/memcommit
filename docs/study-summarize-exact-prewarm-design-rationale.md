# Study Summarize exact prewarm design rationale

## Decision

Study Summarize uses the same baseline-owned, content-addressed immutable
bundle as other prepared Study semantics. `init-study` records only the bundle
digest. After an explicit participant invocation freezes and authorizes its
source, the runtime may read one exact Summarize artifact and materialize the
ordinary typed `SummarizeResult` without opening a provider.

The cache unit is the ordinary whole Summarize request. `mem summarize NAME`
and `mem summarize -r NAME` are distinct because recursive mode changes both
lexical descendant reach and embedded-Context traversal. The exact key binds:

- Study task and selected Context UID/name;
- direct/recursive traversal flags;
- the complete frozen frame digest and ordered Context/Memory identities;
- Summarize provider-contract version; and
- configured provider, model, and reasoning effort.

An edit, addition, scope change, configuration change, missing entry, or
authority failure is a miss. The runtime never projects a parent summary down,
combines child summaries upward, or treats equal-looking prose as evidence
equivalence. It revalidates the source frame and every Grant binding before
returning either a prepared or live result.

## Ownership and materialization

The artifact stores only the source-linked understanding and its exact input
identity. It remains in the shared immutable bundle. Ordinary Summarize has no
saved analysis/session catalog, review lifecycle, or Apply operation, so an
exact hit does not invent one. The participant receives the same process-local
typed result that a live invocation would have returned. Clipboard export
remains an explicit post-result action.

Existing Study runs remain pinned to the digest chosen at their initialization.
Publishing a revised baseline bundle does not move those references. A later
`init-study` receives the new digest; this preserves reproducibility across
participants.

Empty frames use the existing deterministic message and receive no artifact.
This avoids representing a provider run that never occurred.

## Exhaustive preparation and measurement

On 2026-08-13 the active Study exposed 109 readable Context names: 4 practice,
17 Task 1, 38 Task 2, and 50 Task 3. Freezing both direct and recursive command
forms produced 218 rows. Twenty were empty and provider-free; the remaining
198 were executed through production `summarize_frame` with
`codex_chatgpt / gpt-5.6-sol / medium`.

The resumable runner used 16 workers. It completed 198/198 provider rows with
no publication until every row validated. Aggregate provider time was
2,885.641 seconds; parallel wall time was about three minutes. One recursive
practice row exposed a pre-existing decoder boundary: two Context aliases
carried the same durable Memory UID, and citing both aliases violated the
portable summary's UID uniqueness. The decoder now preserves that durable UID
once in first-seen order; no different Memory identities or content are
merged. The failed row alone was rerun before publication.

The 198 artifacts occupy 1,385,892 bytes (1.322 MiB). The complete revised
bundle digest is
`35b712cda207b6bf8c2dc4b69557a28b7e7715b84a8df25def627dec28460757`;
it contains 921 entries and occupies 28,025,321 bytes (26.727 MiB). The
resumable manifest and outputs are under
`outputs/study-summarize-exact-matrix/20260813-exact-all-contexts/`.

## Concurrency and failure boundary

Parallelism applies only across independent ordinary requests. No single
Summarize frame is split into concurrent provider calls. Each validated row is
written to its own resumable output file. A failed or interrupted run may reuse
completed exact rows, but no baseline registry entries are published until all
198 nonempty rows and all 20 deterministic empty rows match the frozen
manifest. Registry publication remains serialized.

## Rejected alternatives

- Caching only recursive parents is smaller but cannot truthfully answer a
  direct child request as if that request had been summarized.
- Composing recursive results from direct child summaries changes the semantic
  neighborhood and never executes the ordinary whole-frame request.
- Copying 198 artifacts into every participant Profile duplicates immutable
  bytes and makes participant count determine storage.
- Adding a saved Summary session solely for cache symmetry changes the ordinary
  command's ownership and lifecycle without a user-visible need.
- Caching empty results invents an artifact where the production command is
  already deterministic and provider-free.
