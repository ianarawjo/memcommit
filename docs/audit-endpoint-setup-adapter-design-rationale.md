# Audit endpoint setup adapter

## Status

Implemented and verified as the second real consumer of the rebuilt endpoint
setup component, after Merge.

## Problem

The rebuilt `interfaces.tui.components.endpoint_setup` screen initially had one
real operation consumer: Merge.  The older
`commands.session_endpoint_setup` shell has a wider capability set, including
per-role descendant reach, focused Memory selection, and require-new Context
editing.  Migrating Compare, Update, Meld, Atomize, or Branch before those
capabilities exist in the rebuilt component would silently remove visible
operation behavior.

Audit needs only the capability intersection:

| Capability | Rebuilt component | Legacy shell | Audit requires |
| --- | --- | --- | --- |
| frozen readable Context catalog | yes | yes | yes |
| one selected existing Context | yes | yes | yes |
| operation-owned mode and labels | yes | yes | yes |
| validation and explicit continue/cancel | yes | yes | yes |
| independent descendant reach | no | yes | no |
| focused Memory selection | no | yes | no |
| require-new name and parent locator | no | yes | no |
| mode-dependent active roles | no | yes | no |

## Decision

Use Audit's explicit `--select` route as the second real operation adapter.
Flagless Audit now uses the command-start current Context directly. The adapter freezes the
readable public-name catalog, the selected current public name, and Grant-aware
annotations into one `EndpointSetupSpec`.  The setup returns only the selected
public Context name.  The Audit command remains responsible for resolving the
exact `ContextAccess`, checking retained-analysis authority, loading the frozen
Source, connecting the provider, and saving the Audit session.

The explicit common setup performs no Context load, provider call, or durable mutation.
It represents only process-local selection.  Cancellation returns no Source.
The operation still audits one direct Context; making setup opt-in and adopting the shared component
does not add descendant or Profile-wide execution.

## Why not migrate the legacy semantic operations yet

Visual similarity is not sufficient evidence of capability parity.  Compare
and Update currently expose independent range and Memory focus for both roles;
Meld additionally has mode-dependent roles and a require-new result; Atomize
has focused input Memory and existing-or-new output; Branch combines Source
reach with an exact new-name parent locator.  Those operations remain on the
legacy shell until the rebuilt component gains and tests the exact applicable
capability without weakening their receipts.

## Verification boundary

Focused tests cover the component's existing Merge contract, Audit spec
projection, changing the selected Source, cancellation, invalid catalog
orientation, and the command loading the exact name returned by the adapter.
The ordered PTY trace under
`docs/screenshots/audit-endpoint-setup-20260815/` records entry, Source change,
the explicit continue action, the process-local receipt with read-only
verification, and cancellation.

## Remaining work

The two endpoint shells are not yet interchangeable and must not be aliased.
The next migration should add one missing capability family with parity tests,
then move an operation that actually requires it.  Independent descendant
reach is the smallest broadly reused candidate, but Memory focus must remain
separate so a range change cannot retain a hidden Memory UID.
