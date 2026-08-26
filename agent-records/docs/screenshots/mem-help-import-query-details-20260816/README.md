# `mem help` Import and Query detail verification

This ordered capture set verifies that Import keeps its ordinary collapsed
Summary and `USE WHEN` while showing `import [PARTIAL]`, then explains the
current implementation boundary only after expansion. It also verifies the
reviewed Find/Search/Query/Summarize wording and Query's expanded
`QUERY-ONLY ACCESS` boundary.

Every image comes from the actual installed `mem` executable in a
color-capable PTY with `NO_COLOR` removed, `TERM=xterm-256color`, and
`COLORTERM=truecolor`. The wide sequence uses `180×52`; the compact sequence
uses `100×30`. Help does not consult a Profile or current Context, and every
state is read-only.

## Ordered interaction log

| Capture | Exact command | PTY | Profile / current Context | Preceding input | Visible state | Durable mutation |
|---|---|---|---|---|---|---|
| `01-wide-import-partial` | `mem help` | `180×52` | not consulted / not consulted | `Tab`, `Down` ×3 | collapsed Import row with `[PARTIAL]`; no limitation body | none |
| `02-wide-import-expanded` | same process | `180×52` | not consulted / not consulted | `Right` | expanded Import contract, `CURRENT LIMITATION`, and forms | none |
| `03-wide-search-explain` | same process | `180×52` | not consulted / not consulted | `Left` ×2, `Tab`, `Down` ×3 | collapsed Search & Explain category with exact and LLM-based routes | none |
| `04-wide-query-access` | same process | `180×52` | not consulted / not consulted | `Up`, `Right` | expanded Query contract and `QUERY-ONLY ACCESS` | none |
| `01-compact-import-partial` | separate `mem help` | `100×30` | not consulted / not consulted | `Tab`, `Down` ×3 | compact collapsed Import row with `[PARTIAL]` | none |
| `02-compact-import-expanded` | same compact process | `100×30` | not consulted / not consulted | `Right` | compact expanded Import contract and limitation | none |
| `03-compact-search-explain` | same compact process | `100×30` | not consulted / not consulted | `Left` ×2, `Tab`, `Down` ×3 | compact Search & Explain category | none |
| `04-compact-query-access` | same compact process | `100×30` | not consulted / not consulted | `Up`, `Right` | compact expanded Query access boundary | none |

Every numbered state has a raw `.typescript`, terminal-text `.txt`, and
full-canvas `.png` artifact beside this log. `capture.py` records the actual
PTY byte stream and renders that stream; the images are not synthetic Help
fixtures.
