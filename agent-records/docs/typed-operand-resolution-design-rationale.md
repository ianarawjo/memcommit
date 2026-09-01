# Typed operand resolution design rationale

## Problem

Several CLI positions accept more than one semantic kind. A value such as
`2a4dc8ab` may be a displayed Context UID, a Memory UID prefix, a retained
artifact UID, or—only in explicitly text-bearing operations—literal prose.
Historically those decisions were made by command-local syntax checks. In the
motivating failure, `mem meld --from 2a4dc8ab` classified the value as inline
Memory content before checking the readable Context catalog, so Meld created a
Memory whose body was the Context UID. Similar storage-independent
classification existed in Compare, Goal/Fit/Conformance inputs, and several
Context-or-Memory commands.

The provider response that assigned `DISTINCT` to an invalid Meld source side
is a separate relation-decoding concern. This change deliberately does not
alter it; that behavior is being reconsidered with Compare.

## Ownership and dependency direction

Operand resolution is split by responsibility rather than by command:

| Owner | Responsibility |
| --- | --- |
| `memcommit.application.capabilities.context_locator` | Pure `.`/`..` lexical expansion against one captured current Context; no storage or authority |
| `memcommit.core.context_targeting.uid_locator` | UUID-prefix shape predicates and operation-neutral exact/unique matching |
| `memcommit.application.capabilities.durable_uid_resolution` | Exact/unique durable UID selection inside a caller-supplied authorized candidate frame |
| `memcommit.application.capabilities.operand_resolution` | Existing-Context name/relative/UID precedence and typed not-found/ambiguity results |
| `memcommit.application.context_access.operand_resolution` | Ordinary-local plus READ-granted public Context candidate freezing, exact permission re-resolution, and readable Context-versus-local-Memory composition |
| `memcommit.application.capabilities.local_target_lookup` | Ordinary-local Context/Memory/direct-item coordinates and local mixed-target completion |
| Operation adapters | Explicit grammar markers, allowed final fallback, loading mode, mutation permission, locks, receipts, and Apply |

`resolve_context_access` remains the name-based authority primitive. It does
not enumerate UIDs. The access-aware operand layer first selects a public name
or UID from the operation's frozen readable catalog, then calls
`resolve_context_access` again with the operation's exact permission. This
prevents a READ candidate from silently satisfying `UPDATE` or `DELETE`.
Local-only, READ-visible, and QUERY-only are therefore candidate-catalog
policies, not separate locator algorithms. The local helper freezes strict
ordinary Context records and feeds the same resolver without opening Grants;
the readable helper freezes local plus READ-granted public identities. Query
adds its QUERY-only View arm only in the positions whose grammar promises that
interface.

## Resolution contract

One command captures current Context once and freezes each candidate namespace
once. Resolution then follows this order:

1. An explicit semantic type wins, for example `CONTEXT:UID`, `--memory`, or
   `text:`.
2. An exact canonical or explicitly relative Context name wins.
3. A UID-shaped operand is compared across every semantic kind admitted by
   that position in the same candidate frame. One full identity and one usable
   coordinate are required.
4. Only a grammar that explicitly admits text may apply its operation-owned
   final fallback.

An unmatched UID never becomes prose or a new Context name. A UID that selects
both a Context and a Memory, different full identities, multiple public Context
routes, or multiple direct owner coordinates fails closed with disambiguation
coordinates. Bare Memory enumeration remains ordinary-local; Grant Memory
content requires an explicit public owner such as `CONTEXT:UID`. QUERY-only
routes never enter a readable Context UID catalog.

The resolved canonical public name and full UID—not the raw spelling—are used
for equality, loading, session/cache identity, persistence, revalidation, and
confirmation. New identifiers such as `init`, Branch/Checkout destinations,
Meld's symmetric new Result, Sever `--save-as`, and other require-new Save
Locations do not use this existing-Context resolver.

## Grammar families and rollout

The first implementation covers shared choke points rather than adding a UID
parser to every command:

- Existing Context: Switch, Checkpoint, Rename source, Clear, Context Delete,
  Add target, List, Show's explicit owner, Edit owner including batch input,
  Replace roots, Summarize, Search, Find, Audit, duplicate and redundancy
  discovery, Dedup, Diff, Log, Rationale, Trace, Lock/Unlock, and Revert.
- Directional Context endpoints: Meld, Update and directional Impact, and
  Compare `--from`/`--to` plus positional peers, and Merge's readable Source
  and CREATE-authorized Target.
- Context or local Memory: Atomize, Chunk, Translate, Impact Atomize,
  Reference, Embed, Delete's combined target, Resolve's one-Context target
  grammar, and every caller of
  `resolve_local_context_memory_target`.
- Context, local Memory, or text: Goal focus, Fit stored inputs, Conformance
  Rules, and Update's inline Source.
- Context, Memory, or retained history/artifact UID: Trace keeps its typed
  fall-through from Context UID to Memory/history selection; operation-owned
  artifact catalogs continue to use the durable UID primitive.
- Query's first positional compares readable Context and QUERY-only View UIDs
  before permitting question fallback. Its question position already compares
  Memory and retained-artifact UIDs through the same durable UID primitive.
  A single explicit `--context` uses the same two-arm classification so a
  QUERY-only public View does not fail prematurely under READ; repeated
  `--context` remains an ordinary readable-Context form.
- Distill and Makemore use a storage-aware semantic-result endpoint sibling:
  the Source catalog may include READ-granted public Contexts, while the
  memorization Target is resolved only from ordinary-local existing Contexts.
  Elaborate resolves its existing READ+UPDATE owner through the access-aware
  operand layer before selecting the direct Memory.
- Copy and Move resolve explicit Source owners and local Targets from frozen
  Context identity frames, including when the Context locator is nested in
  `CONTEXT:MEMORY`. Copy may add READ-granted Source frames; Move preserves its
  existing rejection of granted ownership transfer after identity resolution.
- Share and cross-Profile Context/Memory Import use the same resolver over an
  explicit ordinary-local Store. They do not inherit the active Profile's
  Grants. Profile Grant creation resolves its authority resource and grantee
  attachment independently in those Profiles' local stores, while the public
  view remains a new-name field.

The storage-aware endpoint resolvers replace their earlier lexical-only
counterparts. The old `resolve_semantic_result_endpoints`,
`resolve_memorization_target`, `resolve_update_endpoints`, and the latter's
`UpdateEndpoints` result type have no compatibility facade: retaining a second
public route would let new callers bypass existence, durable-identity, and
authority checks. Persisted session compatibility is preserved in operation
adapters and schemas instead of by keeping an unsafe operand-resolution API.

Show additionally compares a Context UID with its readable/local direct-item
routes before choosing Context. Diff compares its readable Context arm with
ordinary-local checkpoint identities, then performs checkpoint-read
authorization only after a Context or checkpoint coordinate is selected.
Trace, Rationale, and Log likewise resolve a readable Context identity before
their stronger retained-history policy is allowed to accept or reject it.
This rollout covers the identified overloaded and existing-Context choke
points; it is not permission to treat the operation catalog as permanently
closed. A later operation or adapter audit must route new existing-Context
operands through these layers and must not solve a gap by broadening a global
UID index or by making the pure Context locator enumerate storage.

## Alternatives and boundaries

A process-wide UID index was rejected because operation authority differs by
Profile, Grant, retained history window, and artifact repository. Making
`resolve_context_locator` storage-aware was rejected because lexical
canonicalization is useful for new-name and persisted-name code that must not
perform lookup. Making `resolve_context_access` guess every identifier kind was
rejected because it would mix authority with Memory/artifact grammar and create
dependency cycles. Treating every eight-character UUID shape as Memory was
rejected because Context UIDs are printed and expected to round-trip.

This layer does not choose recursive reach, follow embeds, mutation authority,
provider disclosure, semantic relation meaning, cache equivalence, or Apply.
It only converts one raw operand into an exact typed coordinate inside the
candidate namespaces the calling operation was already allowed to expose.
Grant selection still uses the most-specific public-name rule in
`resolve_granted_context_view`, and execution-time permission/revocation checks
remain in the authorization boundary. Checkpoint-read grants similarly remain
an operation policy rather than a locator candidate source.
