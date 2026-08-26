# Provider PARTIAL Help evidence

These ordered captures record the intentionally shelved Provider surface in
the canonical Help TUI. They were produced from the real `mem help` process in
a color-capable `180`-column by `52`-row PTY with `TERM=xterm-256color`,
`COLORTERM=truecolor`, and `NO_COLOR` removed.

The command is read-only. Neither step contacted a provider or mutated durable
state. Profile and current Context do not affect the Help catalog.

1. `01-provider-partial-row.png`
   - Command: `mem help`
   - Preceding keys: `Tab` × 10, `Down` × 5, `Up` × 4
   - Visible state: Provider is selected in `SYSTEM & STUDY TOOLS` and carries
     the `[PARTIAL]` maturity label.
   - Durable mutation: none.
2. `02-provider-partial-expanded.png`
   - Command: same live `mem help` process
   - Preceding key from step 1: `Right`
   - Visible state: Provider details are expanded; the overview guidance says
     the bare command prints routes without opening an editor.
   - Durable mutation: none.

Run `python docs/screenshots/provider-partial-help-20260823/capture.py` from the
repository root to refresh the set.
