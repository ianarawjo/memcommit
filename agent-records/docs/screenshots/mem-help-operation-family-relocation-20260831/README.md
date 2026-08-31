# `mem help` operation-family relocation verification

This ordered capture set verifies that the catalog taxonomy is projected by
the interactive Help browser after the application and console operation
packages adopt the same physical topology. All captures are read-only.

The capture command is:

```text
python agent-records/docs/screenshots/mem-help-operation-family-relocation-20260831/capture.py
```

Every image comes from the actual `mem help` process in a color-capable
`180×52` PTY with `NO_COLOR` removed, `TERM=xterm-256color`, and
`COLORTERM=truecolor`. Help does not consult a Profile or current Context.

## Ordered interaction log

| Capture | Exact command | PTY | Profile / current Context | Preceding input | Visible state | Durable mutation |
|---|---|---|---|---|---|---|
| `01-search-explain` | `mem help` | `180×52` | not consulted / not consulted | `Tab` ×2, `Down` ×3 | Search & Explain with Retrieve & Answer and Synthesize | none |
| `02-direct-changes` | separate `mem help` | `180×52` | not consulted / not consulted | `Tab` ×3, `Down` ×6 | Direct Changes | none |
| `03-semantic-updates` | separate `mem help` | `180×52` | not consulted / not consulted | `Tab` ×4, `Down` ×5 | Semantic Updates with Foundation, Derive, and Curate & Integrate | none |
| `04-translation` | separate `mem help` | `180×52` | not consulted / not consulted | `Tab` ×5 | Translation as an independent family | none |
| `05-quality-resolution` | separate `mem help` | `180×52` | not consulted / not consulted | `Tab` ×6, `Down` ×8 | Quality & Resolution with Diagnose, Repair, and Validate | none |
| `06-operation-lifecycle` | separate `mem help` | `180×52` | not consulted / not consulted | `Tab` ×7 | unsplit Impact and Review lifecycle family | none |
| `07-history-recovery` | separate `mem help` | `180×52` | not consulted / not consulted | `Tab` ×9, `Down` ×4 | History & Recovery with Inspection and Recovery | none |
| `08-a-z-flat` | separate `mem help` | `180×52` | not consulted / not consulted | `Shift-Tab`, `Right` | flat A–Z projection without family dividers | none |

Every numbered state has a raw `.typescript`, terminal-text `.txt`, and
full-canvas `.png` artifact beside this log.
