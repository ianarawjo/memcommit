# Python API adapter container rationale

## Problem

The public Python client lived in a root-level `memcommit.api` package. The
name described a broad kind of boundary but did not identify either its
audience or its architectural role. Its client, public DTOs, public errors,
and operation wrappers all translate Python calls into application use cases
and project their outcomes back into a stable programmatic contract.

## Decision

Relocate the complete package without internal refactoring to
`memcommit.adapters.python_api`. The explicit `python_api` name distinguishes
this public programmatic surface from console, agent, and MCP adapters while
avoiding the ambiguity of `adapters.python`, since the entire implementation
is written in Python.

The relocation changes canonical import paths and physical ownership only.
`MemCommitClient`, public result and error types, operation method signatures,
provider injection, and runtime behavior remain unchanged. No
`memcommit.api` compatibility package is retained.

## Boundary and limitation

The private `_operations` modules currently contain substantial assembly code.
They remain inside the Python API adapter when their responsibility is public
request conversion, provider selection, application invocation, error
translation, or public result projection. Any business rule discovered there
should later move to the corresponding `application.operations` owner, but
that classification is deliberately excluded from this mechanical move.

The package-level `memcommit` exports remain supported by resolving their
public values from the new canonical adapter. This preserves the documented
top-level Python contract without restoring the removed `memcommit.api`
submodule path.

## Invariants

- Public client behavior, signatures, DTOs, and error categories do not
  change.
- Internal callers use `memcommit.adapters.python_api` as the canonical path.
- Console, agent, and MCP adapters consume the Python API adapter without
  becoming its implementation owners.
- The adapter does not become the canonical owner of application rules.
- The package initializer retains lazy public-name loading.
