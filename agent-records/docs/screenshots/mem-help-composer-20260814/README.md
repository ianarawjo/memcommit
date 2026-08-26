# `mem help` operation composer verification

These captures verify that the small interface-neutral operation contract is
combined with the existing interactive and CLI Help projections. The
interactive path runs the installed `mem` executable in a color-capable
`180x52` PTY after removing `NO_COLOR`, setting `TERM=xterm-256color` and
`COLORTERM=truecolor`, and checking both the PTY dimensions and foreground and
background ANSI styles.

Help does not consult a Profile or current Context. The capture suppresses the
otherwise unrelated command-attempt log, so every state below is read-only.

## Ordered interaction log

| Capture | Exact command | Profile / current Context | Preceding input | Visible state | Durable mutation |
|---|---|---|---|---|---|
| `01-by-kind-entry` | `mem help` | not consulted / not consulted | none | existing BY KIND browser entry and shared navigation guidance | none |
| `02-update-composed-detail` | same | not consulted / not consulted | `Tab` x3, `Down` x6, `Right` | Update expanded with common Flow, Execution, Effect, and Range before its exact CLI Forms | none |
| `03-update-full-help` | same | not consulted / not consulted | `H` | the same composed overview and Forms followed by Typer's complete Update syntax and flags | none |
| `04-plain-read-only-verification` | `mem help </dev/null \| rg '^(branch\|checkout\|list\|ls\|switch) '` | not consulted / not consulted | separate non-interactive invocation | stable compact inventory remains available without a TUI | none |

Every numbered state has a raw `.typescript`, terminal-text `.txt`, and
full-canvas `.png` artifact. The final full-help state exits with status 0;
no operation callback, provider, Context load, or mutation is invoked.
