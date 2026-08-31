# `mem pwd` design rationale

## Motivation

Agents, scripts, and people need a cheap way to discover MemCommit's current
Context without parsing `mem status`. Status opens and authorizes Context data,
collects counts, and may traverse a readable graph. Orientation should not pay
for or imply any of those operations.

## Command contract

`mem pwd` prints the active Profile Store's canonical current Context name and
one trailing newline:

```text
task-1/participant
```

It prints no label, Profile prefix, UID, counts, or terminal decoration. When
there is no current pointer, it writes an explanatory error to stderr and exits
with status 1. Inspecting an uninitialized Store must not create `~/.mem` or
`state.json`.

The result is orientation, not authority. It reports a locally retained public
name even when that name denotes a READ-granted virtual Context. It does not
load the Context, reconnect to its authority Profile, or promise that a later
operation is authorized. Every consuming operation must still resolve and
authorize the current pointer under its own rules. This preserves revocation
and operation-specific permission checks while keeping `pwd` deterministic.

## Layer boundary

- `operations/pwd/application.py` owns the terminal-independent reader
  protocol, typed result, and missing/invalid-state failures.
- `operations/pwd/runtime.py` adapts one explicit `MemoryStore` without
  creating the Store or loading Context contents.
- `commands/pwd/presentation.py` renders the typed result as one line.
- `commands/pwd/command.py` is the Typer error/exit-code and composition boundary.

The plain presenter is co-located with the command because it is specific to
the `mem pwd` console surface rather than a cross-interface adapter. The former
`interfaces/cli/pwd.py` path is removed without a compatibility facade. This is
an ownership-only relocation: the one-line text contract and the command's
error boundary remain unchanged.

The former top-level application and runtime paths remain true module aliases,
not copied re-export namespaces. This keeps existing imports, object identity,
and monkeypatch behavior intact while grouping the unchanged implementation by
operation. The relocation does not alter signatures, failures, Store access,
output, or the command's authority boundary.

No domain transform is introduced because `pwd` does not inspect or change a
Context. It has no provider, cache, receipt, TUI, clipboard, or durable effect.
The typed application result can later be projected by a Python or agent
adapter without parsing CLI output; this change does not yet declare a stable
public Python API or JSON schema.

## Alternatives and limits

Making `pwd` an alias for `status --short` was rejected because short Status
still loads and authorizes Context data and produces counts. Including the
Profile in the default output was also rejected: the returned Context name
should remain directly reusable as a canonical Context operand inside the
already active Profile. `mem status -b` remains the detailed Profile-and-lineage
view.

This small read-only slice validates the layer direction but does not replace
the planned second operation slice that must exercise cache, receipt, review,
or durable-effect boundaries.
