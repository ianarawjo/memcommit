# Python build artifact boundary design rationale

Last verified: 2026-08-26.

## Problem

The repository tracked 164 paths under `build/`, including a complete copied
`build/lib/memcommit` package. Setuptools may reuse that directory during an
incremental wheel build instead of recopying a source file whose timestamp does
not appear newer. A wheel built from commit `b8cae0bd` consequently contained
the stale copied `context.py`; its digest matched `build/lib`, not the canonical
`src/memcommit/context.py`, and `mem-mcp` failed during import.

This is not only unused duplication. It makes artifact content depend on old
local build history, so a successful source checkout and its wheel can execute
different Python modules.

## Chosen boundary

`src/memcommit/` is the sole canonical Python package input. Root `build/` and
`dist/` directories and `*.egg-info/` metadata are derived products and must
not be tracked. The existing `build/` working directory is left physically in
place during this change so unrelated local generated output is not destroyed;
removing it from Git's index and ignoring it is sufficient to keep it out of a
fresh clone or `git archive`.

A normal wheel build must start from a source tree that contains no tracked
derived tree. Verification therefore builds an unmodified `git archive` with
ordinary `uv build --wheel`; it must not move or delete `build/` as a special
preparatory workaround.

## Alternatives

- Running a cleanup command before every release was rejected because one
  missed cleanup silently restores the same nondeterministic artifact.
- Teaching MCP imports to tolerate the stale module was rejected because the
  wheel would still contain inconsistent implementations.
- Keeping selected files under `build/` was rejected because the directory is
  owned by the build backend and is not a source or evidence location.

Research evidence remains under `agent-records/` and `outputs/`; this boundary applies
only to generated Python packaging directories.

## Verification contract

The focused distribution check must prove all of the following:

1. `git ls-files build` is empty.
2. An ordinary wheel built from a new `git archive` imports MemCommit from the
   installed environment rather than the checkout.
3. The installed wheel contains the canonical `GrantedContextLink` definition
   that the earlier stale copy omitted.
4. The official MCP client can initialize installed `mem-mcp`, discover Query
   and Add, perform one Add, and verify its single durable checkpoint.

The ordinary archive/wheel/install/MCP check passed without pre-build cleanup.
The separate Profile-at-import coupling was then addressed independently in
`store-root-resolution-design-rationale.md`.
