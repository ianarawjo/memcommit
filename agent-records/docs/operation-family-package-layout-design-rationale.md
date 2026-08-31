# Operation family package layout rationale

## Problem

The top-level operation catalog and interactive Help agreed on operation
families, but the application and console trees remained flat. A reader could
see `trace`, `update`, `impact`, and `dedup` as siblings without learning
whether the package represented history inspection, a semantic foundation,
an execution-lifecycle view, or quality repair. The console tree and
application tree also provided no shared physical answer to “where does this
operation live?”

## Decision

Use the catalog family as the first physical package component and a declared
family section as the second component. The canonical shape is:

```text
memcommit/application/operations/<family>/<section?>/<operation>/
memcommit/adapters/console/commands/<family>/<section?>/<operation>/
```

All thirteen public catalog families now have physical package boundaries:
`browse_navigate`, `create_copy_connect`,
`search_explain/{retrieve_answer,synthesize}`, `direct_changes`,
`semantic_updates/{foundation,derive,curate_integrate}`, `translation`,
`quality_resolution/{diagnose,repair,validate}`, `operation_lifecycle`,
`ground_workbench`, `history_recovery/{inspection,recovery}`, `profiles`,
`sharing_protection`, and `system_study_tools`. Operation Lifecycle and every
other sectionless family remain unsplit. Because `import` is a Python keyword,
its leaf is named `resource_import`; its catalog identity and CLI spelling
remain `import`.

The operation package remains the unit of behavior. Family and section
packages contain only package boundaries and affordance-level organization;
siblings do not gain shared authority, provider, transaction, receipt, or
materialization behavior merely because they share a directory. In
particular, Update is the Semantic Updates foundation but not a base class for
the derived or curation operations. Reusable execution mechanics continue to
belong in application capabilities.

Impact route metadata is application meaning, so
`application.operations.operation_lifecycle.impact` owns the typed lifecycle
and route catalog. `adapters.console.commands.operation_lifecycle.impact`
installs those routes into Typer and keeps console session and presentation
mechanics. The dependency direction is application to no adapter, then console
to application.

Checkout is a public composition operation rather than an independent Store
effect. Its application package validates Checkout-only flags and selects an
exact Branch or Switch route; those two operations retain their existing
authority and mutation contracts. Config similarly owns key-alias
normalization in its application package, while Provider owns provider-route
input validation and the separation between Profile route identity and
machine-local transport settings. Their console packages retain Typer parsing,
progress, and text rendering.

The Copy and Move operation packages belong to different public families, so
their shared typed values and Store kernel cannot truthfully live beneath
either family. They moved to
`application.capabilities.memory_transfer`; the two operation packages remain
the only public application entrypoints. The hidden Dev command is not a
catalog affordance and lives under `adapters.console.diagnostics`, outside the
public command-family tree. The parallel `application.operations.resource_import`
compatibility façade was removed after callers adopted the canonical Import
resource modules.

## Compatibility and safety boundary

This is an internal canonical relocation, not a new public command surface.
The CLI names, callback behavior, request/result contracts, authority checks,
provider calls, cache/session semantics, Store transactions, and receipts do
not change. No moved flat package remains as a compatibility facade because a
second import topology would make the physical classification non-authoritative
and allow internal callers to drift back to the flat layout.

Generated command and root-module plans resolve canonical family paths, the
callable catalog discovers an operation package by its exact path component
rather than assuming it is directly below `application.operations`, and tests
verify both module importability and absence of former flat packages. The
catalog's complete 66-operation key set must equal the authored path map, and
the top-level application and console operation roots may contain only the
thirteen catalog family packages.

## Alternatives considered

Keeping the taxonomy in Help alone would preserve behavior but leave source
navigation and non-console adapters without the same ownership signal. Moving
only the console packages would make the adapter look more structured than the
application meaning it projects. Creating one broad `semantic` or `history`
service was rejected because directory proximity is not evidence that the
operations share executable policy or one aggregate history authority.
Placing shared Copy/Move mechanics below Create, Copy & Connect was rejected
because Move would then depend on another operation family for its mutation
kernel. Treating Dev as a System & Study Tool was also rejected: hidden
diagnostics do not become a public affordance merely because they are launched
from the same executable.
