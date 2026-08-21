# Find Duplicates callable boundary matrix

## Reviewed scope

Find Duplicates is the independent read-only exact-DUP operation. It freezes
one readable direct Context, groups stored Memory content by exact Python
string equality, and reports the first UID plus every later identical UID.
It neither aliases Find Redundancies nor enters the applying Dedup boundary.

| Route | Public input | Application entry | Result/effect |
| --- | --- | --- | --- |
| CLI | `mem find-duplicates [--context CONTEXT]` | shared locator and readable-Context freeze, then `find_exact_duplicates` | complete exact groups with content and member UIDs; no mutation |
| Public Python | `MemCommitClient.find_duplicates(context_name)` | `api._operations.exact_duplicates.find_duplicates_exact`, then the same core | typed `ExactDuplicateFindResult`; no mutation |

Both routes converge on `memcommit.exact_dedup.find_exact_duplicates`. They do
not construct a provider, normalize content, open a semantic workbench, create
a checkpoint, or modify the global current Context. Their Read Report
operation identity is exactly `find-duplicates`; metadata from
`find-redundancies` is rejected instead of canonicalized as an alias.

## Relationship to DUN

`mem find-redundancies` is a different operation with the inclusive contract:

```text
DUN evidence = DUP / EXACT evidence + semantic-DUN evidence
```

It may therefore contain the same exact edges returned here plus conservative
surface-equivalence and provider-validated semantic-equivalence edges. This
does not make the commands aliases: Find Duplicates is complete for exact
stored identity and provider-free; Find Redundancies is complete for the
broader DUN frame and may connect exact and non-exact edges into one cleanup
group.

## Limits

The operation examines directly owned ordinary Memories only. Different
whitespace, Unicode, punctuation, case, or line endings are not exact matches.
Embedded Contexts, references, and query-only items are excluded. Apply
remains owned by `mem dedup` for exact-only cleanup or `mem dedun` for complete
DUN cleanup.
