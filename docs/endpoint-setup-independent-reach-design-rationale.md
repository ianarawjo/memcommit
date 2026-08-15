# Endpoint setup independent descendant reach

## Status

Implemented in the rebuilt endpoint setup component.  No legacy semantic
operation has been migrated by this change; Merge and Audit preserve their
existing setup contracts.

## Problem

An operation mode such as Merge's global `DIRECT` or `RECURSIVE` shape cannot
represent every directional setup.  Compare and Update can independently ask
whether A and B mean one exact Context root or that root plus its lexical
descendants.  The four valid combinations are therefore:

| A | B |
| --- | --- |
| exact | exact |
| descendants | exact |
| exact | descendants |
| descendants | descendants |

Coupling these controls would silently change Source or Target disclosure and
execution scope when one endpoint is edited.

## Decision

`EndpointSetupRole` owns two explicit booleans:

- `allow_descendants` declares whether the role exposes a range control;
- `include_descendants` supplies that control's frozen initial value.

Every enabled role receives its own `ContextReachState` and focus surface
immediately after its Context selector.  Left and Right change only that
role's range.  Tab and boundary-aware Up/Down traverse the visible sequence as
`role Context → role range → next role Context`.  Roles without the capability
retain the previous screen and focus order.

`EndpointSetupValue` returns the exact selected root name and one
`include_descendants` boolean.  The setup does not expand the root into names,
load descendants, or infer authorization.  The operation adapter must expand
against its already frozen readable/local catalog and apply its own authority,
provider-disclosure, and freshness rules.

An initial descendants value without a visible range control fails closed.
This prevents a hidden execution scope from entering the receipt.  The To Do
projection prints `THIS CONTEXT ONLY` or `INCLUDE DESCENDANTS` only for roles
that actually expose the range control, preserving existing Merge and Audit
presentation.

## Memory-focus boundary

Context reach and focused Memory selection remain separate axes.  The rebuilt
component now accepts a caller-authorized, lazy direct-Memory projection for
each role's selected exact Context and returns an optional exact Memory UID in
the same typed endpoint value.  Changing that role from exact to descendants
clears its retained UID immediately; a single Memory cannot remain invisibly
selected under a subtree range.  Changing the selected Context also clears the
old UID.  Another role's independently selected Memory is unaffected.

This capability does not migrate Compare or Update by itself.  Their adapters
must still freeze authority before constructing the projection loader and
translate the completed typed draft into their existing operation request.

## Verification

Tests exercise all four A/B combinations, an explicitly recursive initial
role, rejection of hidden descendant state, exact range delivery to an
operation validator, and unchanged Merge/Audit defaults.  A subsequent focused
suite covers exact Memory selection, Context-change clearing, range clearing,
role independence, lazy projection loading, and invalid loader output.  The
ordered 180×52 color PTY traces under
`docs/screenshots/endpoint-setup-independent-reach-20260815/` records A range
selection, B remaining exact, the complete To Do projection, the typed
process-local receipt, read-only Store verification, and cancellation; the
Memory-focus trace is recorded separately under
`docs/screenshots/endpoint-setup-memory-focus-20260815/`.

## Remaining work

The rebuilt component still lacks require-new Context naming, parent location,
and mode-dependent active roles.  The legacy endpoint shell remains
authoritative for operations requiring those capabilities.  Compare or Update
is the next directional consumer candidate now that independent range and
focused direct-Memory selection are represented together.
