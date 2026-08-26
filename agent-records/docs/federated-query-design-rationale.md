# Federated query routing design rationale

## Problem

A parent query view and a more specific descendant grant intentionally remain
separate authority capabilities. That separation prevents ordinary parent
`READ`, `find`, or `ls` operations from exposing concealed descendant
Memories. It also previously meant that a question sent to the parent could
miss a useful descendant: asking `campus-wiki` about construction did not use
the separately granted `campus-wiki/construction-details` source.

The CLI also previously reused one `selected_name` for two different roles.
When an explicit public READ or QUERY-only name did not exist in the local
store, the command replaced it with the Grant's local attachment name so it
could inspect legacy query references. The ordinary fallback then treated that
attachment as the semantic Source. A successful command could therefore answer
from, cite, or report an unrelated local workspace instead of the explicitly
requested granted Context.

## Command contract

For a one-shot whole-view question such as:

```text
mem query task-1/campus-wiki "QUESTION"
```

The displayed public name is a complete Query target. The CLI resolves it
against the active Profile's public Grant metadata before consulting the
current ordinary Context, so the same canonical command addresses the same
query-only View from any current Context and does not require a repeated
`--context` attachment operand. Global public-name resolution validates only
the local attachment identity; it must not open concealed authority Context
data before provider connection.

The one-question `--context` form classifies its operand before opening any
legacy attachment:

```text
mem query "QUESTION" --context READABLE_PUBLIC_NAME
mem query "QUESTION" --context QUERY_ONLY_PUBLIC_NAME
mem query "QUESTION" --context LEFT --context RIGHT
```

A READ-capable public name remains an ordinary Query Source even when the same
Grant also has QUERY. A QUERY-only name selects the exact granted Query route.
Repeated operands form one exact ordinary Source set and require DERIVE for
every granted contributor plus COMBINE across ownership domains. Every relative
operand is resolved from the one current-Context snapshot captured at command
start. The legacy attachment-scoped form remains available only when SELECTOR
and QUESTION are both present; its local anchor is held in a separate value and
cannot become an ordinary Query Source.

The command may federate explicitly granted descendant query views attached to
the same grantee Context. It first sends only the question and public candidate
view names to the authenticated query provider. The provider selects names
that are semantically relevant and likely to materially help, including across
languages. Only selected views are then opened and labelled alongside the
requested parent source in one final answer turn.

The route selector still determines the primary permission boundary. A
descendant participates only when it independently grants `QUERY`; federation
does not infer access from namespace shape and does not merge stores, grants,
or ordinary Context trees.

The terminal Query workbench exposes the same distinction as an explicit
`EXACT VIEW` versus `FEDERATE DESCENDANTS` Scope choice. The exact choice skips
the name-only routing turn. Federation preserves the CLI behavior described
above. A saved session still forces one exact grant binding even if the visible
control had previously selected federation.

## Invariants

- Relevance routing receives public view names, never concealed source text.
- A canonical public Query name is callable independently of current Context
  state; current Context items cannot reinterpret that name as a Memory
  selector.
- An explicit readable public name is retained as the ordinary request target;
  its Grant attachment is authorization metadata, never a substitute Source.
- Repeated ordinary targets freeze exactly the distinct named set. Missing
  DERIVE or cross-domain COMBINE authority fails before provider construction.
- QUERY-only `--context` cannot fall through to the ordinary local attachment.
- Ordinary provider evidence and rendered References originate only from the
  frozen readable roots and the descendant/embed reach explicitly selected by
  the request.
- The routing result must be a structured subset of the offered names; invalid
  or invented names fail closed.
- Every selected descendant is resolved and loaded through its own grant.
- The parent and all selected descendant grant/source bindings are rechecked
  under the registry snapshot lock after the provider answers. A changed or
  revoked source prevents publication.
- `find`, `ls`, and ordinary Context switching remain unchanged and cannot use
  federation to reveal query-only content.
- A granted request always includes a nonblank question and the complete
  authorized root View frame; there is no per-Memory catalog or selector.

## Alternatives and limitation

Always loading every descendant would be simpler, but it would open irrelevant
authority sources and make the experimental condition depend on all siblings.
Pure lexical matching would avoid a provider routing turn but fails for
cross-language pairs such as Korean `건설` and English
`construction-details`. The selected design uses a name-only semantic routing
turn and keeps source disclosure conditional.

Treating the local Grant attachment as a convenient fallback was rejected. An
attachment explains where authorization is connected; it does not prove that
the local workspace is an allowed answer Source. Failing closed is preferable
to a plausible answer with the wrong identity.

Selection quality is limited by public view names. A poorly named descendant
may be missed even when its content would help. Adding trusted public
descriptions is a possible later extension; inspecting concealed content to
improve routing is an intentional non-goal.

Repeated `--context` combines readable ordinary Sources only. It does not
combine unrelated QUERY-only views; query-only federation remains limited to
independently authorized descendants of one selected public route.
