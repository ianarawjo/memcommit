# Operation package layout rationale

## Problem

The operation catalog and interactive Help classify the public surface into
families and, where useful, sections. Mirroring that presentation taxonomy in
the application and console filesystem initially looked like a useful source
navigation aid. In practice it made the operation tree deeper, obscured the
operation as the actual behavior owner, and suggested executable coupling
between siblings that share only an affordance label.

The mismatch was most visible when reading the repository directly. Finding
`trace`, `update`, or `dedup` required remembering its current presentation
family and section before reaching the package. Moving an operation between
Help sections would also imply a source relocation even when no authority,
provider, transaction, receipt, or application boundary had changed.

## Decision

Keep catalog classification and physical ownership independent. The canonical
operation package shape is flat and symmetric:

```text
memcommit/application/operations/<operation>/
memcommit/adapters/console/commands/<operation>/
```

All 66 catalog operations have a direct package under each root. Because
`import` is a Python keyword, that operation uses the package name
`resource_import`; its catalog identity and CLI spelling remain `import`.
The console-only `remove` package remains a compatibility spelling for Delete
and does not create a second catalog or application operation.

Families and sections remain stable typed metadata in
`memcommit.operation_catalog`. Help uses them for ordering and visual grouping,
and other adapters may use them for discovery. They are not package owners,
base classes, execution policies, or dependency boundaries. Reclassifying an
operation therefore changes the affordance catalog without automatically
moving its implementation.

The operation package remains the unit of executable behavior. Impact owns its
typed lifecycle and route catalog in `application.operations.impact`; Checkout
owns route selection in `application.operations.checkout` while Branch and
Switch retain their concrete effects. Config and Provider keep their application
validation boundaries. These ownership improvements survive the flattening.

Cross-operation mechanisms do not move into an arbitrary operation merely to
keep the root flat. Copy and Move share
`application.capabilities.memory_transfer`; Find and Search share readable
selection-source resolution under
`application.capabilities.save_context_from_selection`; the Retrieve & Answer
SAVE control lives under
`adapters.console.terminal.components.retrieve_answer_save`. Hidden Dev remains
under `adapters.console.diagnostics` because it is not a catalog operation.

## Compatibility and safety boundary

This is an internal canonical relocation. CLI spellings, callbacks,
request/result contracts, authority checks, provider calls, sessions, Store
transactions, receipts, and visible presentation do not change. The former
family and section import paths are removed rather than retained as parallel
facades, so repository code has one physical answer for each operation.

Generated command and root-module plans resolve direct operation packages. The
callable catalog continues to derive family membership from the operation
catalog, not from path components. Structural tests require the catalog's
complete operation set to match the flat application and console roots and
keep shared capabilities and diagnostics outside those roots.

## Alternatives considered

Keeping the family hierarchy was rejected after repository inspection showed
that presentation adjacency did not help locate the executable owner enough to
justify the extra path depth and implied coupling. Adding a broader Workspace
super-family would deepen the same problem and force the remaining families
into arbitrary peers. Removing the catalog grouping as well was also rejected:
the taxonomy remains useful in Help and discovery even though it is not a good
filesystem topology.

The flat roots are longer directory listings. That is an intentional tradeoff:
operation names are the stable lookup key in code, while Catalog and Help are
the appropriate views for browsing by affordance.
