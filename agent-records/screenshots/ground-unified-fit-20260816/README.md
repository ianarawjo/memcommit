# Unified Ground Fit detection

This ordered set records the complete Ground Fit detector in a real
`180 × 52` color-capable PTY. It uses isolated temporary Stores and a delayed,
deterministic provider so the same frozen graph produces the same evidence.
`TERM=xterm-256color`, `COLORTERM=truecolor`, and 24-bit prompt-toolkit color
are enabled; `NO_COLOR` is removed. PNGs are rendered from the retained ANSI
streams rather than from a synthetic UI fixture.

The frozen example intentionally conflicts with its own scope: the Goal and
Context require real, source-grounded United States companies, while the only
Example is an unsupported synthetic ticker claim. The ordinary Rule–Example
proposition check returns `FIT`; the separate coherence detector reports the
Context support gap and Goal–Example drift. This demonstrates why the two
semantics remain distinct but share one receipt.

Command:

```bash
python agent-records/screenshots/ground-unified-fit-20260816/capture.py
```

All captures use an isolated temporary Profile/Store with current Context
unset. No Ground or Context mutation occurs after fixture creation.

| # | File | Exact command / preceding keys | Visible state | Durable mutation |
| --- | --- | --- | --- | --- |
| 01 | `01-cli-complete-detection` | `mem fit --ground ticker-context-fit --plain` | One stable line reports `4/6 checks`, `CONTEXT 1`, `VERTICAL 1`, `PEER 0`; verification shows the Ground unchanged | one immutable Fit receipt only |
| 02 | `02-viewer-complete-graph-running` | `mem fit --ground ticker-context-fit --tui` | Complete-graph provider progress before the Viewer exists | none yet |
| 03 | `03-viewer-summary` | both detector turns complete | Viewer enters at the unified Summary | one immutable Fit receipt only |
| 04 | `04-viewer-context-focused` | `Down` | frozen Context K section focused, including frame roles and names | none |
| 05 | `05-viewer-example-issue-focused` | `Down` ×3 | Example section shows its passing Rule relation beside Context and vertical issues | none |
| 06 | `06-ground-auto-fit-running` | `mem ground ticker-context-fit`; no key | process-local AUTO-FIT starts on entry and announces a read-only frozen turn | none yet |
| 07 | `07-ground-detection-projected` | provider completion; no key | Goal, Contexts, Rule, and Example panes project the combined receipt without a fifth Fit pane | one immutable Fit receipt only |
| 08 | `08-ground-close-verification` | `Ctrl-C` | one AUTO-FIT run made two bounded provider calls, left the Ground byte-semantically unchanged, and published one current receipt | none |

Fit stops at detection. These captures deliberately contain no repair proposal,
automatic edit, approval, or Apply path; the later user-decision grammar remains
outside this slice.
