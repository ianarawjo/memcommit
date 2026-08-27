# CLI dependency compatibility

## Motivating failure

The `mem` executable is installed as an isolated uv tool. Its environment is
populated from the project's declared dependencies rather than from the active
Conda environment. CLI modules directly import Click for command-context,
parameter-source, styling, and output-capability behavior, so relying on Click
to arrive transitively left a valid-looking tool installation unable to import
the console entry point, now owned by
`memcommit.adapters.console.entrypoint`.

## Supported contract

Click is a direct runtime dependency. The current CLI adapters also depend on
Typer's Click-backed context and `CliRunner` behavior, including the
`mix_stderr` constructor control used throughout the command tests. The
supported dependency range is therefore Typer 0.12.x with Click 8.1.x.

An isolated install must be able to import the complete CLI, render `mem help`,
and construct every registered operation's help path without borrowing
packages from another Python environment.

## Alternatives and boundary

Installing Click manually into one uv tool environment repairs only that
machine and fails again on reinstall. Leaving Typer unbounded also admits newer
releases whose testing and command-context APIs no longer implement the current
adapter contract.

Migrating the CLI and its tests to the newer Typer API is a separate project:
it must update the shared invocation classifier and command-test harness before
the upper bounds can be removed. This packaging fix intentionally preserves the
existing behavior instead of combining that migration with an import repair.
