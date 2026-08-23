# Find Duplicates callable boundary matrix

## Reviewed scope

Find Duplicates is the independent read-only exact-DUP operation. It freezes
one readable direct Context, groups eligible items by same-role exact identity,
and reports the first occurrence UID plus every later identical occurrence.
It neither aliases Find Redundancies nor enters the applying Dedup boundary.

| Route | Public input | Application entry | Result/effect |
| --- | --- | --- | --- |
| CLI | `mem find-duplicates [--context CONTEXT]` | shared locator and readable-Context freeze, then `find_exact_duplicates` | complete typed exact groups with summaries and member UIDs; no mutation |
| Public Python | `MemCommitClient.find_duplicates(context_name)` | `api._operations.exact_duplicates.find_duplicates_exact`, then the same core | typed `ExactDuplicateFindResult`; no mutation |

Both routes converge on `memcommit.exact_dedup.find_exact_duplicates` and its
pure `memcommit.direct_item_duplicates` detector. They do
not construct a provider, normalize content, open a semantic workbench, create
a checkpoint, or modify the global current Context. Their Read Report
operation identity is exactly `find-duplicates`; metadata from
`find-redundancies` is rejected instead of canonicalized as an alias.

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
complete DUN cleanup.
