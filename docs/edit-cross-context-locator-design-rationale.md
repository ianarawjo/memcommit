# Edit cross-Context locator design rationale

## Motivating case

`mem list` can show a live Memory Embed or immutable Reference owned by the
current Context while identifying its Source Memory in another Context. The
old `mem edit UID CONTENT` route searched only the current Context, so the
visible Source UID could not be used directly. Editing the link UID was also
correctly rejected because neither link form is a directly owned Memory.

## Locator contract

Single-Memory Edit accepts either a UID/prefix or `CONTEXT:UID`. The Context
half is an existing-Context operand and therefore uses the shared Context
locator resolver. Canonical `practice/3:ca562047` and explicit relative
`../3:ca562047` forms resolve against the one current-Context snapshot captured
at command start. `CONTEXT:UID` and `--context` cannot be combined because two
owners would make the request ambiguous.

A bare UID searches one strict snapshot of every ordinary local Context for a
directly owned Memory without preferring the current Context. One match freezes
that owner and canonical Memory UID for the existing mutation/checkpoint path.
No match fails directly; multiple matches list every canonical
`CONTEXT:FULL_UID` candidate with its JSON-quoted exact content and tell the
person to rerun with the chosen displayed `CONTEXT:UID` value. Both failures
occur before mutation. Embedded Contexts, MemoryRefs, and other non-Memory
direct items never enter the candidate set.

The search is intentionally local-only. It does not enumerate granted public
names, reinterpret attachment metadata as hierarchy, or infer write authority
from readable content. A granted owner remains available only through an
explicit qualified Context or `--context`, where the existing UPDATE Grant
resolution and mutation revalidation apply.

## Ownership and safety invariants

- A list row identifies the Source as `[CONTEXT][memory UID]`; it never makes
  the link object writable.
- Snapshot References and live Memory Embeds remain read-only direct items.
  Edit changes only the Source Context's ordinary directly owned Memory.
- Owner resolution completes before `ops.edit` changes the in-memory Context.
  Ambiguity and missing-target failures publish no checkpoint or partial state.
- Successful cross-Context Edit saves and checkpoints the resolved owner while
  leaving the global current Context unchanged.
- Batch `--input` retains its existing exact target selection through current
  Context or `--context`; it does not perform per-row cross-Context search.

## Alternatives and limitation

Write-through from the link UID was rejected because it would make a read-only
projection a mutation capability and blur snapshot versus live-link semantics.
Always scanning every readable Context was rejected because Grant enumeration
and authorization are separate boundaries, and current-local shorthand should
remain deterministic. Persisting a global UID index was unnecessary for the
prototype: the local catalog scan is bounded by the Profile's ordinary Context
store, but may become expensive with a very large catalog.
