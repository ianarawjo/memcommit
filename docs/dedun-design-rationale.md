# Complete DUN application boundary

## Name and purpose

`dedup` and broader redundancy used to share the word “duplicate,” which made
one command appear to have two incompatible meanings. MemCommit now uses a
deliberate compositional vocabulary:

```text
dup = exact stored duplicate
semantic dun = differently stored surface or semantic redundancy
dun = dup + semantic dun
```

Accordingly, `mem dedup` proves byte-identical content in program logic and
applies only exact cleanup. `mem dedun` resolves the complete redundancy set:
the same exact-DUP edges plus conservative surface equivalence and semantic
provider equivalence. “De-redundancy” was rejected as an awkward command
spelling, while “consolidate” was rejected because it suggests rewriting or
combining content. Dedun is short, symmetrical with Dedup, and names the
broader product-specific safety contract after Help teaches the equation once.

## Shared analysis, Dedun-owned Apply

The semantic analysis is also a complete public read-only operation, while
Dedun owns the later applying stages:

```text
mem find-redundancies
  -> find EXACT + SURFACE_EQUIVALENT + SEMANTIC_EQUIVALENT evidence
  -> inspect or annotate evidence without changing a Source

mem dedun
  -> reuse the same analysis and evidence report
  -> accept every eligible typed evidence link
  -> form connected redundancy groups
  -> retain the earliest unchanged existing UID per group
  -> apply one atomic checkpoint
  -> print a compact receipt
```

The default invocation uses the current Context and expresses immediate Apply
intent in both TTY and non-TTY environments. `--context NAME` chooses another
exact Context without changing the global current Context. The survivor rule
matches exact Dedup's stored-order rule: retain the earliest existing UID in
each connected group. The detailed provider evidence, members, selections,
and reasons are stored inside the same checkpoint and reopen through
`mem review dedun --receipt UID`; ordinary execution prints only a short
receipt. The read-only `mem find-redundancies` route remains available when a
person wants to inspect evidence without accepting Apply intent.

`find-duplicates` is the separate provider-free exact-DUP report, while
`find-redundancies` reports the complete exact-plus-semantic DUN relation. There
is no singular `find-redundancy` command. The exact-review `consolidate`
spelling remains hidden for existing stateless receipts; it is a Dedun Apply
adapter, not another discovery operation.

## Invariants

- `EXACT` content remains a typed DUN edge and is eligible for immediate
  Dedun Apply; `mem dedup` is the provider-free exact-only alternative.
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
- Every evidence edge names two directly owned Memories in one frozen frame.
- Connected edges form groups; edge order never chooses a survivor.
- The stored-order rule chooses exactly one existing UID per group. Dedun never
  rewrites or integrates Memory content.
- Source identity, direct-Memory digest, Context record digest, evidence UIDs,
  group identities, Grant binding, and reviewed revision are checked at Apply.
- Granted Apply requires `READ + DERIVE + DELETE`.
- Inbound references to absorbed UIDs block the complete Apply.
- All deletions publish in one `dedun` / `dedun-v2` checkpoint, or
  nothing is published. Recovery is `mem undo`.

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
inbound references, atomize compound Memories, or apply one group across
multiple Contexts. Rewriting belongs to Normalize, Meld, Update, or Fit Resolve;
claim-boundary decomposition belongs to Atomize; reference migration needs its
own reviewed identity contract.

## 2026-08-21 direct execution-receipt migration

Dedun no longer opens target setup, a process-local evidence Viewer, or a
survivor-choice workbench during ordinary execution. It analyzes the exact
current or explicit Context, applies the deterministic earliest-existing-UID
rule, and stores groups, selections, contents, and reasons in the checkpoint.
Success is compact; `mem review dedun --receipt UID` renders the immutable
terminal evidence. The hidden exact replay remains for compatibility and for
external adapters that already possess a separately reviewed survivor set.

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
