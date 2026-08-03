# Federated query routing design rationale

## Problem

A parent query view and a more specific descendant grant intentionally remain
separate authority capabilities. That separation prevents ordinary parent
`READ`, `find`, or `ls` operations from exposing concealed descendant
Memories. It also previously meant that a question sent to the parent could
miss a useful descendant: asking `campus-wiki` about construction did not use
the separately granted `campus-wiki/construction-details` source.

## Command contract

For a one-shot whole-view question such as:

```text
mem query task-1/campus-wiki "QUESTION"
```

the command may federate explicitly granted descendant query views attached to
the same grantee Context. It first sends only the question and public candidate
view names to the authenticated query provider. The provider selects names
that are semantically relevant and likely to materially help, including across
languages. Only selected views are then opened and labelled alongside the
requested parent source in one final answer turn.

The route selector still determines the primary permission boundary. A
descendant participates only when it independently grants `QUERY`; federation
does not infer access from namespace shape and does not merge stores, grants,
or ordinary Context trees.

## Invariants

- Relevance routing receives public view names, never concealed source text.
- The routing result must be a structured subset of the offered names; invalid
  or invented names fail closed.
- Every selected descendant is resolved and loaded through its own grant.
- The parent and all selected descendant grant/source bindings are rechecked
  under the registry snapshot lock after the provider answers. A changed or
  revoked source prevents publication.
- `find`, `ls`, and ordinary Context switching remain unchanged and cannot use
  federation to reveal query-only content.
- Catalog browsing without a question remains exact to the requested view.
- A `#HANDLE` request remains exact to that one opaque Memory.
- Saved sessions remain exact to one grant. Federation is disabled whenever
  `--session` is present, so a transcript cannot silently acquire additional
  authority bindings.

## Alternatives and limitation

Always loading every descendant would be simpler, but it would open irrelevant
authority sources and make the experimental condition depend on all siblings.
Pure lexical matching would avoid a provider routing turn but fails for
cross-language pairs such as Korean `건설` and English
`construction-details`. The selected design uses a name-only semantic routing
turn and keeps source disclosure conditional.

Selection quality is limited by public view names. A poorly named descendant
may be missed even when its content would help. Adding trusted public
descriptions is a possible later extension; inspecting concealed content to
improve routing is an intentional non-goal.
