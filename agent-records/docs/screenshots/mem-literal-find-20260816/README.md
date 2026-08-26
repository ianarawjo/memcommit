# `mem find` provider-free terminal verification

This ordered set records the actual deterministic Find route at `180×52` in a
color-capable PTY. `NO_COLOR` is removed, `TERM=xterm-256color`, and
`COLORTERM=truecolor`. The source is the real `mem` executable and current
`task-1/campus-wiki` Study data; no synthetic screen fixture is substituted.

Find is read-only. None of these states creates a provider request, cache,
session, checkpoint, Context, or Memory change.

## Interaction log

| Capture | Exact command | PTY | Profile / current Context | Preceding input | Visible state | Durable mutation |
| --- | --- | --- | --- | --- | --- | --- |
| `01-pattern-entry` | `mem find construction --context task-1/campus-wiki --ignore-case --tui` | `180×52` | active Study Profile / explicit target makes current irrelevant | command launch | exact pattern is staged; execution has not occurred | none |
| `02-readable-context-target` | same process | `180×52` | same | `Tab` | frozen `ALL READABLE CONTEXTS` tree and checked explicit target | none |
| `03-independent-scope-controls` | same process | `180×52` | same | `Tab` | target cardinality, lexical descendants, embedded reach, match mode, and case mode | none |
| `04-complete-results` | same process | `180×52` | same | `Enter` | one matched Memory, six exact spans, complete occurrence count | none |
| `05-focused-copy` | same process | `180×52` | same | `y` | focused-match clipboard receipt | none |
| `06-whole-result-copy` | same process | `180×52` | same | `Y` | complete-result clipboard receipt | none |
| `07-zero-width-regex-rejected` | `mem find --plain --regex '^|'` | `180×52` | active Profile/current Context, content not opened | command launch | regex is rejected before source matching because it consumes no characters | none |

Each numbered state has the raw `.typescript`, terminal-text `.txt`, and
full-canvas `.png` artifact beside this log.
