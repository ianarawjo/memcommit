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

The classified paths are `search_explain/{retrieve_answer,synthesize}`,
`direct_changes`,
`semantic_updates/{foundation,derive,curate_integrate}`, `translation`,
`quality_resolution/{diagnose,repair,validate}`, `operation_lifecycle`, and
`history_recovery/{inspection,recovery}`. Operation Lifecycle is unsplit.
Operations outside these catalog families keep their existing direct package
location; the relocation does not invent a miscellaneous family.

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
verify both module importability and absence of former flat packages.

## Alternatives considered

Keeping the taxonomy in Help alone would preserve behavior but leave source
navigation and non-console adapters without the same ownership signal. Moving
only the console packages would make the adapter look more structured than the
application meaning it projects. Creating one broad `semantic` or `history`
service was rejected because directory proximity is not evidence that the
operations share executable policy or one aggregate history authority.
