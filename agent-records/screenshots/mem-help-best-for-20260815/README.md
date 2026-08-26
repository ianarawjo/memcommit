# `mem help` use-case column verification

These captures verify that every public operation exposes its reviewed use case
before expansion. At `180×52`, the actual Help TUI splits each operation row
into equal-width summary and use-case columns. At `90×40`, it stacks the use
case directly below the summary instead of compressing either value beyond
readability. The repeated `BEST FOR ·` label is intentionally omitted from
collapsed rows.

The capture runs the installed `mem` executable in a color-capable `180×52`
PTY after removing `NO_COLOR`, setting `TERM=xterm-256color` and
`COLORTERM=truecolor`, and verifying the live `52 180` dimensions plus both
foreground and background ANSI styles. Direct macOS Terminal capture was not
available to Computer Use, so each PNG is rendered from the actual preserved
PTY byte stream; it is not a synthetic Help fixture.

Help does not consult a Profile or current Context. The capture suppresses the
otherwise unrelated command-attempt log, and every recorded state is
read-only.

## Ordered interaction log

| Capture | Exact command | PTY | Profile / current Context | Preceding input | Visible state | Durable mutation |
|---|---|---|---|---|---|---|
| `01-by-kind-entry` | `mem help` | `180×52` | not consulted / not consulted | none | BY KIND entry with summary and unlabeled use-case columns visible before expansion | none |
| `02-compare-best-for` | separate `mem help` | `180×52` | not consulted / not consulted | `Tab` ×3, `Down` ×3 | collapsed Compare row with both columns and no Form | none |
| `03-update-best-for` | separate `mem help` | `180×52` | not consulted / not consulted | `Tab` ×3, `Down` ×7 | collapsed Update row with both columns and no Form | none |
| `04-plain-read-only-verification` | `mem help </dev/null \| rg '^(compare\|update) '` | `180×52` | not consulted / not consulted | separate non-interactive invocation | stable Compare and Update summaries outside the TUI | none |
| `05-a-z-global-best-for` | separate `mem help` | `180×52` | not consulted / not consulted | `Shift-Tab`, `Right` | A–Z also uses the global summary and unlabeled use-case columns | none |
| `06-narrow-stacked-best-for` | separate `mem help` | `90×40` | not consulted / not consulted | none | narrow BY KIND entry stacks each unlabeled use case below its summary | none |

Every numbered state has a raw `.typescript`, terminal-text `.txt`, and
full-canvas `.png` artifact. The interactive process closes with `q` and exits
with status 0; no operation callback, provider, Context load, or mutation is
invoked.
