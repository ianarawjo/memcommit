# Complete DUN application boundary

## Name and purpose

`dedup` and broader redundancy used to share the word “duplicate,” which made
one command appear to have two incompatible meanings. MemCommit now uses a
deliberate compositional vocabulary:

```text
dup = same-role exact duplicate
semantic dun = differently stored direct-Memory surface or semantic redundancy
dun = dup + semantic dun
```

Accordingly, `mem dedup` proves role-specific exact identity in program logic
and applies only exact cleanup. `mem dedun` resolves the complete redundancy
set: every same-role exact-DUP group plus conservative direct-Memory surface
equivalence and semantic provider equivalence. “De-redundancy” was rejected as
an awkward command spelling, while “consolidate” was rejected because it
suggests rewriting or combining content. Dedun is short, symmetrical with
Dedup, and names the broader product-specific safety contract after Help
teaches the equation once.

## Shared analysis, Dedun-owned Apply

The semantic analysis is also a complete public read-only operation, while
Dedun owns the later applying stages:

```text
mem find-redundancies
  -> find EXACT + SURFACE_EQUIVALENT + SEMANTIC_EQUIVALENT evidence
  -> inspect or annotate evidence without changing a Source

mem dedun
  -> reuse the same analysis and evidence report
  -> accept every eligible typed Memory evidence link
  -> include every same-role exact Embed and Reference group
  -> form role-bounded redundancy groups
  -> retain the earliest unchanged existing UID per group
  -> apply one atomic checkpoint
  -> print a compact receipt
```

The default invocation and `-d/--direct` use the current exact Context and
express immediate Apply intent in both TTY and non-TTY environments.
`--context NAME` chooses another exact Context without changing the global
current Context. `-r/--recursive` freezes that local lexical subtree and keeps
every Context as an independent DUN frame; it never forms a cleanup group
across Contexts or follows embedded Contexts. The survivor rule
matches exact Dedup's stored-order rule: retain the earliest existing UID in
each connected group. The detailed provider evidence, members, selections,
and reasons are stored inside the same checkpoint and reopen through
`mem review dedun --receipt UID`; ordinary execution prints only a short
receipt. The read-only `mem find-redundancies` route remains available when a
person wants to inspect evidence without accepting Apply intent.

`find-duplicates` is the separate provider-free exact-DUP report, while
`find-redundancies` reports the complete exact-plus-semantic DUN relation. There
is no separate singular operation: `find-redundancy` is an input alias for the
canonical `find-redundancies` identity. The exact-review `consolidate` spelling
is retired rather than retained as a second execution surface; the `dedun`
invocation itself is the console Apply boundary.

## Canonical ownership

The public split is reflected in the implementation layout. Provider-free
exact cleanup is owned by `memcommit.application.operations.dedup`, while the
complete DUN request and typed effect contract are owned by
`memcommit.application.operations.dedun.application`, confirmed relations are
grouped in `analysis` through the shared semantic-execution relation capability,
and `runtime` owns both direct and recursive Store publication. The console
package contains only the immediate command adapter; the old operation-specific
`interfaces/cli/dedup.py` and `interfaces/tui/operations/dedup` paths are
removed without facades. Public Python assembly follows the same split through
`_operations.dedup` and `_operations.dedun`.

The checkpoint contracts, evidence wire values, receipts, authority checks, and
survivor behavior remain unchanged. The obsolete console replay arguments are
retired rather than preserved as a second execution surface. In particular, the
historical `dedup-component-*` prefix is retained because those component UIDs
remain embedded in durable checkpoints and public plan results. The established
public Python `Dedup*Result`, `plan_dedup`, and `apply_dedup` compatibility
aliases remain thin projections onto canonical Dedun types and functions.

## Invariants

- Every provider-free same-role exact group is part of DUN. Direct Memory
  `EXACT` content remains a typed DUN edge; live Embeds and immutable
  References use their role-specific Source/binding or snapshot identity.
- Cross-role pairs never form DUN edges. In particular, Memory–Embed,
  Memory–Reference, and Embed–Reference equality cannot authorize removal.
- The complete stored content of each direct Memory is one indivisible judgment
  unit. Dedun does not split a Memory, extract a matching substring, or delete
  only one proposition inside it.
- Shared wording or a shared proper part is `OVERLAP`, not redundancy. For
  example, `abc` and `bcd` do not become redundant because both contain `bc`.
  If a multi-claim Memory contains one otherwise redundant claim, run Atomize
  first so that claim becomes a separately reviewable Memory, then run Dedun.
- Public complete-DUN evidence uses `redundancy-evidence-v2` and says
  `kind=REDUNDANCY` and `route=DEDUN`; the former semantic-only v1 wire form
  remains decode-only compatibility evidence.
- Every semantic evidence edge names two directly owned Memories in one frozen
  frame. Exact Embed and Reference groups remain deterministic typed groups and
  are never fabricated as Memory evidence.
- Connected edges form groups; edge order never chooses a survivor.
- The stored-order rule chooses exactly one existing occurrence UID per group.
  Dedun never rewrites content, retargets a live link, or converts one role to
  another.
- Source identity, direct-Memory digest, Context record digest, evidence UIDs,
  group identities, Grant binding, and reviewed revision are checked at Apply.
- Granted Apply requires `READ + DERIVE + DELETE`.
- Inbound References to absorbed owned Memory UIDs block the complete Apply.
- Direct deletions publish in one `dedun` / `dedun-v3` checkpoint. Recursive
  deletions publish one evidence checkpoint per changed Context, all carrying
  one validated operation UID and membership list so Undo/Redo treats them as
  one command unit. Otherwise nothing is published. Recovery is `mem undo`.

## Recursive application boundary

Recursive Dedun is broader in namespace reach, not in semantic relation. The
command freezes the local Context catalog before any provider turn, analyzes
each lexical Context separately, and prepares every deterministic survivor
projection before the first mutation. It then scans the complete local Context
graph for inbound Memory References and publishes all changed Context records
with `save_context_command_batch`. Unchanged graph records and the catalog are
bound through the locked batch so a new child, new Reference, or unrelated
record change cannot race the safety scan. Expected Context digests protect
each write, and exception rollback removes provisional records and checkpoints.

Version 1 rejects granted roots and granted descendants before provider
connection. A cross-Store or authority-domain Apply would need a durable
transaction and a joint recovery receipt; sequentially applying each Grant was
rejected because a later revocation or write failure could leave a half-Dedun
tree. Read-only Find Redundancies may still enumerate readable granted lexical
names because it has no publication boundary.

## Presentation boundary and limits

Dedup and Dedun both return short execution receipts. Dedup proves equality in
program logic; Dedun combines that proof with any non-exact provider judgment
as part of the applying command. A user who needs inspection first runs the
corresponding read-only finder. Review later uses “redundancy group,” never
“duplicate component.”

Public Help exposes the indivisible-unit rule as the typed `partial-overlap`
semantic-boundary note. This makes the Atomize-before-Dedun route discoverable
when only one claim or a shared proper part overlaps, instead of implying that
Dedun may remove a fragment from a stored Memory.

The current Dedun contract does not synthesize canonical wording, migrate
inbound references, deduplicate query-only views, atomize compound Memories,
or apply one group across multiple Contexts. Recursive reach applies multiple
independent groups, never one cross-Context group. Rewriting belongs to Normalize,
Meld, Update, or Fit Resolve; claim-boundary decomposition belongs to Atomize;
reference migration needs its own reviewed identity contract.

## 2026-08-21 direct execution-receipt migration

Dedun no longer opens target setup, a process-local evidence Viewer, or a
survivor-choice workbench during ordinary execution. It analyzes the exact
current or explicit Context, applies the deterministic earliest-existing-UID
rule, and stores groups, selections, contents, and reasons in the checkpoint.
Success is compact; `mem review dedun --receipt UID` renders the immutable
terminal evidence. Public Python and agent adapters may still submit typed
survivor mappings through the application contract, without a hidden CLI.

The direct route additionally stores deterministic `exact_item_groups` for
same-role Embed and Reference occurrences. These groups need no semantic
survivor choice: the first direct occurrence survives. They join Memory DUN
groups in the same revision and checkpoint, and Review labels each retained or
absorbed occurrence with its exact item role and Source/snapshot summary.

Within each reviewed resolved group, the surviving UID and its retained
content appear once on the `SURVIVOR` row. Removed members remain separate
`ABSORB` rows. A second `KEEP` row would repeat the same durable identity and
is intentionally omitted. The immutable applied Review carries the same typed
disposition tokens as the one-shot Find reports: `SURVIVOR` uses shared ADD
blue and `ABSORB` uses shared REMOVE red. The stored checkpoint and ANSI-free
snapshot remain plain text with identical labels; Review never infers colors by
parsing its rendered report.

## 2026-08-21 inclusive DUN composition

Find Duplicates and Find Redundancies are independent public operations, so
their command-attempt and Read Report identities must match exactly; no alias
canonicalization is permitted. Find Duplicates is provider-free and complete
only for exact stored identity. Find Redundancies deliberately includes those
exact edges in the broader DUN report instead of suppressing them and printing
an `EXACT -> DEDUP` redirect.

Human-facing counts distinguish evidence from application topology:

```text
DUN evidence links = DUP / EXACT links + semantic-DUN links
cleanup groups = connected components across all DUN evidence links
```

These values cannot always be added as group counts because one exact edge and
one semantic edge may belong to the same connected cleanup group. Keeping the
link equation and connected-group count separate makes the report complete
without presenting contradictory arithmetic.

## 2026-08-30 console replay and ownership cleanup

The hidden `consolidate` command, hidden Dedun evidence/survivor/revision flags,
and the unreachable survivor workbench were retired. They preserved a
pre-immediate-Apply interaction that no public console flow still used and made
Dedun appear to have a choice boundary absent from its actual command. The
direct command now has the same visible lifecycle as exact Dedup: analyze,
apply the deterministic earliest existing UID, print a receipt, and retain full
evidence for post-application Review.

The former `planning` module was renamed `analysis` because it classifies no
future user choice: it turns confirmed relation edges into stable cleanup
components and a Source-bound revision. Its local union-find was replaced by
the shared semantic-execution connected-component capability. Recursive scope
publication moved into `runtime`, where its Store, authority, graph-freshness,
and atomic batch responsibilities belong; the separate `scope` module no
longer implied another application phase.
