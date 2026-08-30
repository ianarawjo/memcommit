# Find Duplicates callable boundary matrix

## Reviewed scope

Find Duplicates is the independent read-only exact-DUP operation. Direct reach
freezes one readable direct Context. Recursive reach freezes the readable
lexical subtree and keeps every Context as an independent direct identity
frame. It reports the first occurrence UID plus every later identical
occurrence within that frame. It neither aliases Find Redundancies nor enters
the applying Dedup boundary.

| Route | Public input | Application entry | Result/effect |
| --- | --- | --- | --- |
| CLI | `mem find-duplicates [--context CONTEXT] [-d\|-r]` | `operations.find_duplicates.application.find_duplicates` | complete Context-labelled exact groups; no mutation |
| Public Python | `MemCommitClient.find_duplicates(context_name, include_descendants=...)` | the same `FindDuplicatesRequest` and application callable | aggregate `ExactDuplicateFindResult` plus per-Context results; no mutation |

Both routes converge on the operation-aligned
`memcommit.application.operations.find_duplicates.application` boundary, which
owns the exact report and direct-or-lexical analysis while reusing the pure
`reviewing.direct_item_duplicates` detector. Applying Dedup consumes this same
frozen analysis once rather than rediscovering groups. Adapters do not construct a
provider, normalize content, open a semantic workbench, create a checkpoint,
or modify the global current Context. Recursive reach uses public lexical
names, may include READ-granted descendants, and never follows Embed edges.
Their Read Report
operation identity is exactly `find-duplicates`; metadata from
`find-redundancies` is rejected instead of canonicalized as an alias.

This shared analysis does not merge Find Duplicates with applying Dedup. Find
Duplicates exposes only the frozen provider-free report, while Dedup alone
invokes authority, freshness, reference, checkpoint, and atomic publication
over that report.

## Relationship to DUN

`mem find-redundancies` is a different operation with the inclusive contract:

```text
DUN evidence = DUP / EXACT evidence + semantic-DUN evidence
```

It may therefore contain the same same-role exact groups returned here plus
conservative direct-Memory surface-equivalence and provider-validated
semantic-equivalence edges. This
does not make the commands aliases: Find Duplicates is complete for exact
stored identity and provider-free; Find Redundancies is complete for the
broader DUN frame and may connect exact and non-exact edges into one cleanup
group.

## Limits

Memory content uses byte equality; live Memory Embeds use the complete Source
binding; Memory and Context References include their immutable snapshot
identity. Cross-role pairs never match. Query-only views remain excluded.
The current direct-item map prevents two exact Context Embed occurrences with
the same target UID from coexisting, while its role-aware key remains explicit.
Apply remains owned by `mem dedup` for exact-only cleanup or `mem dedun` for
complete DUN cleanup. Matching content in different Context frames is reported
and counted independently rather than forming a cross-Context group.
