# Endpoint Setup focused Memory rationale

## Status

Implemented in the rebuilt operation-neutral Endpoint Setup component.  This
change establishes the reusable typed and interaction contract; it does not
migrate Compare, Update, Meld, Atomize, or another legacy semantic operation.

## Motivating scenario

A directional operation may act on one exact Memory in endpoint A while using
the whole exact Context in endpoint B.  Either endpoint may also use its whole
lexical subtree.  Context reach and Memory focus are therefore independent per
role, but one focused Memory is valid only while that role remains on the exact
Context that owns it.

If the person selects Memory `m` in Context `A` and then changes A to include
descendants, retaining `m` would create an invisible executable constraint.
The screen would describe a subtree while the draft still targeted one item.
Changing the selected Context presents the same stale-identity risk.

## Contract

`EndpointSetupMemory` is a frozen presentation projection containing the
public Context name, exact UID, and preview text.  The component receives these
values through an injected role-and-Context loader.  It does not import a
Store, resolve authority, traverse descendants, construct a provider, or write
durable state.

The loader is lazy and exact:

- the initially selected exact Context is loaded because its Memory choices
  are visible, while an initially descendant role loads no Memory projection;
- moving a Context-tree cursor does not load content;
- explicitly selecting a different available Context loads and validates only
  that exact Context;
- results are cached process-locally for the life of the setup; and
- every returned projection must name the requested Context and have a unique
  UID.

The calling operation must authorize and freeze readable input before exposing
it through this loader.  The UI component's validation is not an authority
grant.

Each Memory Focus surface contains one explicit `WHOLE CONTEXT` choice followed
by the selected Context's direct Memory projections.  The keyboard cursor and
the retained choice remain separate.  The completed `EndpointSetupValue`
contains the exact Context root, its independent descendant flag, and an
optional exact Memory UID.

## Safety invariants

- A Memory UID and `include_descendants=True` cannot coexist in a role or a
  completed value.
- Switching a role from exact to descendants clears that role's retained UID
  immediately and renders the Memory surface as whole-subtree only.
- Explicitly choosing a Context clears the role's previous Memory UID, even
  when the chosen name is unchanged.
- Clearing one role never clears another role's exact Memory selection.
- An initial Memory UID must occur in the loader result for the role's initial
  selected Context or setup fails before opening.
- Invalid owner names and duplicate loader UIDs fail closed.
- Cancellation returns no draft; setup performs no provider call or durable
  mutation.

## Alternatives considered

Preloading Memories for every selectable Context would keep the screen model
simple, but it would read and retain potentially large or granted catalogs that
the person never selected.  The exact lazy loader preserves the legacy
location-first behavior without importing storage into the component.

Embedding Memory rows inside the Context tree would more closely reproduce the
legacy shell.  A separate role-local surface was chosen because Context choice,
lexical reach, and exact Memory focus are distinct semantic axes.  It also makes
the range-clears-focus transition visible and keeps the Context selector free
of operation content.

The existing command-hosted endpoint shell was not moved wholesale because it
also owns new-Context editing, mode-dependent roles, and legacy rendering.  The
rebuilt component adds only the characterized capability needed by a future
directional consumer.

## Verification and remaining boundary

Focused tests cover exact selection, initial selection, Context-change and
descendant-range clearing, two-role independence, lazy loading, invalid loader
output, typed-value rejection, validator-compatible drafts, and unchanged
Merge/Audit consumers.  Ordered 180×52 color PTY evidence records exact focus,
whole-subtree clearing, typed receipts, cancellation, and byte-preserving Store
verification.

Compare or Update should be the next consumer.  Its adapter must map its
already-authorized direct Memories into `EndpointSetupMemory`, preserve its
existing CLI and session schema, and prove plain/TUI parity before the matching
legacy path can retire.  Require-new Context naming, parent location, and
mode-dependent active roles remain separate capabilities.
