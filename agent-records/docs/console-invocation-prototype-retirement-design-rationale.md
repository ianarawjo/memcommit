# Console invocation prototype retirement

## Decision

Remove `memcommit.adapters.interfaces.cli.invocation` and its isolated test
fixture. From its introduction through retirement, the module's
`classify_click_invocation` and `select_console_route` functions were called
only by `tests/test_console_invocation.py`; no shipped command imported them.
The module therefore described a proposed routing contract rather than the
console's executable routing boundary.

## Intended behavior that remains

Console commands continue to select presentation through
`memcommit.adapters.console.router` and inspect terminal eligibility through
`memcommit.adapters.console.terminal`. Operation-owned command adapters retain
their existing distinctions among bare setup, explicit operands, `--plain`,
`--tui`, result presentation, and non-interactive execution. Removing the
prototype must not change any command signature, route predicate, terminal
output, or TUI state.

## Why removal was selected

Moving the module into `adapters.console` would preserve two parallel routing
models and a second, incompatible `TerminalCapabilities` representation. Its
single `BARE`/`EXPLICIT` rule is also too broad for commands whose explicit
`--tui` route, setup workbench, or result viewer has operation-specific
meaning. Keeping an unused facade would make those competing contracts appear
equally canonical.

If a real command later needs Click parameter-source classification, add that
narrow mechanism to the canonical console router when the consumer and its
route invariant are known. Do not restore the retired module merely as a
speculative abstraction.
