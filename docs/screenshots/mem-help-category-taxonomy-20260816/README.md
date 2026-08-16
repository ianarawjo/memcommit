# `mem help` intent-category verification

This ordered capture set verifies the intent-based BY KIND taxonomy, the
category-level execution descriptions, and the wide/compact wrapping behavior.
It also verifies that `SYSTEM & STUDY TOOLS` begins directly with its intent
description rather than a `MIXED` execution label.

Every image comes from the actual installed `mem` executable in a
color-capable PTY with `NO_COLOR` removed, `TERM=xterm-256color`, and
`COLORTERM=truecolor`. The wide sequence uses `180×52`; the compact sequence
uses `100×30`. Help does not consult a Profile or current Context, and every
state is read-only.

## Ordered interaction log

| Capture | Exact command | PTY | Profile / current Context | Preceding input | Visible state | Durable mutation |
|---|---|---|---|---|---|---|
| `01-wide-top` | `mem help` | `180×52` | not consulted / not consulted | none | Browse & Navigate and Create, Copy & Connect with category descriptions | none |
| `01a-wide-status-expanded` | same process | `180×52` | not consulted / not consulted | `Right` | expanded Status flow, execution, effect, range, and forms | none |
| `02-wide-middle` | same process | `180×52` | not consulted / not consulted | `Tab` ×4 | Semantic Transformations and its LLM-based intent description | none |
| `03-wide-bottom` | same process | `180×52` | not consulted / not consulted | `Tab` ×6 | Profiles, Sharing & Protection, and System & Study Tools | none |
| `01-compact-top` | separate `mem help` | `100×30` | not consulted / not consulted | none | compact Browse & Navigate category and wrapped description | none |
| `01a-compact-status-expanded` | same compact process | `100×30` | not consulted / not consulted | `Right` | compact expanded Status flow, execution, effect, range, and forms | none |
| `01aa-compact-status-forms` | same compact process | `100×30` | not consulted / not consulted | `Down` | remaining expanded Status forms, including recursive scope | none |
| `01b-compact-status` | same compact process | `100×30` | not consulted / not consulted | `Down` | complete wrapped Status Summary and `USE WHEN` copy | none |
| `02-compact-middle` | same compact process | `100×30` | not consulted / not consulted | `Tab` ×4 | compact Semantic Transformations category and wrapped description | none |
| `03-compact-bottom` | same compact process | `100×30` | not consulted / not consulted | `Tab` ×6 | compact Profile, protection, and system/study categories | none |

Every numbered state has a raw `.typescript`, terminal-text `.txt`, and
full-canvas `.png` artifact beside this log.
