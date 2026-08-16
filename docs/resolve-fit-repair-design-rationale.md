# Resolve Fit-repair design rationale

## Status

Resolve V1 is implemented as a public, direct-Memory, exact-Context operation
through CLI, TUI, Python, agent, and MCP projections. All interfaces call the
same application boundary. Analysis is process-local; only an approved Apply
creates one `resolve` checkpoint.

## Motivating scenario

A complete Context can contain propositions that Fit as `MAY` or `NO` without
showing which stored text may safely change. A conflict finder can identify a
problem but cannot authorize a rewrite, while generic Meld or Merge semantics
would change the operation: Merge chooses structural collision dispositions,
and Meld combines two Context frames. Resolve instead changes one frozen
Memory frame from non-Fit to independently verified Fit with the smallest
grounded effects it can defend.

The public flow is:

```text
freeze exact direct-Memory frame and authority
-> complete initial Fit judgment
-> generate grounded candidate effects
-> independently verify grounding, information preservation, and deletion basis
-> independently Fit each complete post-image
-> retain Pareto-minimum verified candidates
-> review one exact candidate
-> revalidate authority and Context digest
-> apply one checkpoint
```

The plain review/replay form is:

```text
mem resolve [MEMORY_UID_PREFIX ...] --context NAME [--allow-create]
  [--allow-delete --guidance TEXT] --plain

mem resolve [FULL_MEMORY_UID ...] --context CANONICAL_NAME [same effect flags]
  --candidate FULL_CANDIDATE_UID --expected-revision REVISION --apply --plain
```

The agent `apply` action uses the same stateless replay: it regenerates the
candidate under the expected revision, requires the exact candidate UID to be
present, and only then calls the typed Apply use case. Python callers may keep
the returned typed analysis object process-locally and pass it directly to
`apply_resolve`.

## Effect and authority contract

Resolve exposes primitive durable effects rather than a separate integration
permission:

- `UPDATE` is requested by default;
- `CREATE` is requested only with `--allow-create`;
- `DELETE` is requested only with `--allow-delete`, and that flag is invalid
  without nonblank guidance that states when retirement is justified; and
- an integration is represented by the exact combination of CREATE, UPDATE,
  and DELETE effects that produces its post-image.

For a local Context, requested effects are locally available. For a granted
Context, effective effects are the intersection of requested effect kinds and
the Grant's `CREATE`, `UPDATE`, and `DELETE` capabilities. Semantic use also
requires `READ` and `DERIVE`. Missing capability is reported before provider
construction when no requested effect remains or `DERIVE` is absent. A denied
optional effect does not prevent a candidate that uses only the remaining
capabilities.

V1 reads and mutates one authority resource, so it does not claim `COMBINE`,
`EXPORT`, or `ACCEPT_DERIVED`. Those permissions become relevant only if a
later version accepts multiple authority frames or materializes into a
different owner.

## Grounding and minimum-change invariants

The provider receives aliases such as `m1`, not durable Memory UIDs. Candidate
generation may cite only supplied Memory content and explicit guidance. The
separate verifier receives the complete original frame and exact effects, and
must accept grounding, information preservation, and deletion justification
for each candidate independently. A separate Fit call then judges the complete
post-image; only `YES` survives.

When no explicit Memory selectors are supplied, only Memories identified as
material by the initial Fit judgment may be updated or deleted. Explicit
selectors freeze the exact mutable UID set instead. CREATE may cite any direct
source Memory, but remains opt-in.

Minimum change is a transparent vector:

```text
(delete count, create count, update count, changed text units)
```

Resolve retains the Pareto frontier instead of collapsing unlike effects into
an arbitrary scalar. One minimum is a proposal; multiple incomparable minima
require a person or caller to choose. Neither case is automatic Apply.

## Exact identity and Apply

The revision hashes the contract version, Context identity and digest,
canonical display target, actionable Memory UIDs, requested effects, and
guidance. A candidate UID hashes that revision plus exact owner, Memory,
pre-image, post-image, and source identities for every effect. Explanatory
provider prose is deliberately outside mutation identity.

Apply validates the candidate through the operation-neutral Resolution
lifecycle, revalidates the Context and Grant, acquires the mutation boundary,
checks every pre-image, and writes one checkpoint. DELETE additionally scans
the direct Context graph under the command lock and fails if any inbound
`MemoryRef` still targets a deleted Memory. This is conservative: V1 does not
rewrite references or publish partial effects.

## Alternatives considered

A generic `reconcile` command was rejected because it would combine ambiguity
clarification, conflict repair, duplicate survival, and Context combination
under one name despite different evidence and Apply contracts. A generic
solver callback inside the shared Resolution lifecycle was also rejected: the
common layer validates frozen choices, while Resolve owns semantic generation,
verification, ranking, and mutation.

Treating permission to DELETE as a semantic reason to delete was rejected.
Fit can always be improved by removing propositions, so deletion requires an
independent guidance basis. Persisting provider candidates as a new session
schema was deferred because exact revision-and-candidate replay provides a
smaller V1 safety boundary without hidden durable drafts.

## Intentional limitations

- V1 handles only directly owned Memories in one exact Context. It has no
  lexical-descendant or embedded traversal mode.
- It does not discover duplicates, ambiguities, or conflicts and does not yet
  consume a typed finder handoff. Those commands remain read-only.
- It does not clarify an ungrounded reading; zero verified candidates returns
  `NEEDS_INPUT`. `NEEDS_AUTHORITY` is reserved for a deterministically missing
  `DERIVE` capability or for a request with no effective mutation kind; a
  denied optional effect alone is not proof that more authority would solve
  the semantic problem.
- DELETE never migrates inbound references.
- There is no hidden batching. Every Fit, generation, and verification stage
  is whole-frame and fails before publication when its budget is exceeded.
- The process-local proposal is not a claim of factual truth. Resolve proves
  only supplied-evidence grounding, information preservation, authorization,
  and complete-frame Fit under the operation's reviewed contract.
