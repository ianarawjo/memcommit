# Semantic Dedun application boundary

## Name and purpose

`dedup` and semantic redundancy used to share the word “duplicate,” which made
one command appear to have two incompatible meanings. MemCommit now uses a
deliberate product term:

```text
dup = exact stored duplicate
dun = semantic redundancy
```

Accordingly, `mem dedup` proves byte-identical content in program logic and
applies immediately. `mem dedun` finds and resolves differently stored wording
that a semantic provider judges redundant. “De-redundancy” was rejected as an
awkward command spelling, while “consolidate” was rejected because it suggests
rewriting or combining content. Dedun is short, symmetrical with Dedup, and
names the product-specific safety contract precisely after Help teaches the
`dup`/`dun` distinction once.

## Shared analysis, Dedun-owned Apply

The semantic analysis is also a complete public read-only operation, while
Dedun owns the later applying stages:

```text
mem find-redundancies
  -> find SURFACE_EQUIVALENT / SEMANTIC_EQUIVALENT evidence
  -> inspect or annotate evidence without changing a Source

mem dedun
  -> reuse the same analysis and evidence report
  -> confirm eligible evidence links
  -> form connected redundancy groups
  -> choose one unchanged existing survivor per group
  -> review one exact command
  -> apply one atomic checkpoint
```

In a TTY, the default invocation carries the reviewer through this whole flow.
Outside a TTY, discovery prints a read-only report and never guesses survivor
choices. The final review emits a stateless `mem dedun` replay containing
canonical semantic redundancy evidence, selections, and the frozen revision;
those mechanical fields stay hidden from ordinary command Help.

`find-duplicates` remains a hidden exact callback alias of the canonical
read-only `find-redundancies` command and is folded into that Help row. There
is no singular `find-redundancy` command. The exact-review `consolidate`
spelling remains hidden for existing stateless receipts; it is a Dedun Apply
adapter, not another discovery operation.

## Invariants

- `EXACT` content is excluded and belongs to provider-free `mem dedup`.
- The complete stored content of each direct Memory is one indivisible judgment
  unit. Dedun does not split a Memory, extract a matching substring, or delete
  only one proposition inside it.
- Shared wording or a shared proper part is `OVERLAP`, not redundancy. For
  example, `abc` and `bcd` do not become redundant because both contain `bc`.
  If a multi-claim Memory contains one otherwise redundant claim, run Atomize
  first so that claim becomes a separately reviewable Memory, then run Dedun.
- Public semantic evidence says `kind=REDUNDANCY` and `route=DEDUN`; internal
  version-1 duplicate/handoff values are compatibility details only.
- Every evidence edge names two directly owned Memories in one frozen frame.
- Connected edges form groups; edge order never chooses a survivor.
- Review chooses exactly one existing UID per group. Dedun never rewrites or
  integrates Memory content.
- Source identity, direct-Memory digest, Context record digest, evidence UIDs,
  group identities, Grant binding, and reviewed revision are checked at Apply.
- Granted Apply requires `READ + DERIVE + DELETE`.
- Inbound references to absorbed UIDs block the complete Apply.
- All deletions publish in one `dedun` / `semantic-dedun-v1` checkpoint, or
  nothing is published. Recovery is `mem undo`.

## Presentation boundary and limits

Dedup returns a short deterministic receipt because equality and the survivor
rule are complete in program logic. Dedun shows semantic evidence and an
existing-survivor review because model judgment can be wrong. The semantic
screen uses “redundancy group,” never “duplicate component.”

Public Help exposes the indivisible-unit rule as the typed `partial-overlap`
semantic-boundary note. This makes the Atomize-before-Dedun route discoverable
when only one claim or a shared proper part overlaps, instead of implying that
Dedun may remove a fragment from a stored Memory.

Dedun version 1 does not synthesize canonical wording, migrate inbound
references, atomize compound Memories, or apply one group across multiple
Contexts. Rewriting belongs to Normalize, Meld, Update, or Fit Resolve;
claim-boundary decomposition belongs to Atomize; reference migration needs its
own reviewed identity contract.
