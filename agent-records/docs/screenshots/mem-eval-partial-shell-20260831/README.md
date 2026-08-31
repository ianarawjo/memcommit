# Reserved Eval shell capture log

These ordered captures record the complete visible boundary after Eval became
a reserved `PARTIAL` operation. Every command ran from the repository root in
a real color-capable `180`-column by `52`-row PTY with `TERM=xterm-256color`,
`COLORTERM=truecolor`, and `NO_COLOR` removed. The interactive Help stream is
checked for foreground and background ANSI styles. Help and Eval do not consult
a Profile or current Context in this flow, and no step mutates durable state.

| Image | Command / preceding input | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-help-entry.png` | `mem help` | Initial `BY KIND` Help entry | None |
| `02-eval-partial-focused.png` | same Help process; `End` | `mem eval [PARTIAL]` focused with its reserved use case | None |
| `03-eval-reserved-detail.png` | same Help process; `Right` | Expanded Eval form and `RESERVED SHELL` limitation | None |
| `04-reserved-shell-receipt.png` | `mem eval` | Successful reservation receipt and no evaluation execution | None |
| `05-reserved-shell-help.png` | `mem eval --help` | Empty command shell with no semantic campaign forms | None |
| `06-semantic-route-removed.png` | `mem eval semantic` | Exit 2 unknown-command failure proving the route is removed | None |

Each PNG is rendered from the adjacent color-preserving `.typescript`; the
matching `.txt` is the full terminal-canvas plain projection.
