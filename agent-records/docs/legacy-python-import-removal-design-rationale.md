# Legacy Python import removal design rationale

## Problem

The physical relocation work had removed flat implementation files while one
runtime finder continued to recognize 240 historical root modules, 89 flat
command-support modules, and eight `semantic_execution` package paths. That
second vocabulary no longer served an external consumer or an intended public
contract, but it still ran at every `memcommit` package import and allowed
repository tests, tools, and capture scripts to keep depending on obsolete
ownership names.

## Decision

Remove `memcommit.compatibility`, its generated maps, and the `sys.meta_path`
finder as one change. Every repository-owned executable import now names the
canonical module. The root and command layout generators retain the historical
inventory, but they no longer emit executable alias catalogs; their checks
instead reject internal historical imports and prove in isolated interpreters
that removed names raise `ModuleNotFoundError`.

The four root paths already retired without aliases (`_architecture_catalog`,
`cli`, `ops`, and `provenance`) are checked by the same canonical-only rule so
there is one verification boundary rather than a separate exception list.

## Compatibility boundary

This intentionally breaks direct imports, monkeypatch targets, reload calls,
and Python pickles whose global references name the removed modules. Tests that
existed only to preserve those identities are removed rather than rewritten as
trivial canonical-to-canonical comparisons.

The installed `mem` entry point, command names and options, canonical Python
modules, public operation behavior, and durable memcommit data schemas are not
changed. Command entry packages such as `memcommit.commands.add` also remain;
only their former flat support-module siblings are removed.

## Alternatives

- Keeping the finder would preserve unsupported paths and continue hiding
  stale internal dependencies.
- Adding deprecation facades would restore the same second vocabulary without
  a consumer or an agreed removal window.
- Removing only root aliases would leave command and semantic-execution imports
  governed by a different rule and retain the startup hook.

The canonical-only boundary is selected because it is smaller, explicit, and
mechanically enforceable.

## Verification

- Generated root and command layout checks validate canonical targets, reject
  historical imports, and assert that removed names cannot be imported.
- Package tests verify the absence of the compatibility directory and runtime
  finder while importing representative canonical owners.
- The callable catalog and operation evidence registries remain generated from
  canonical source paths.
