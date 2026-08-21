# Historical Find Redundancies and Dedun handoff

> Historical evidence: this set records the pre-2026-08-21 flagless setup and
> process-local Dedun handoff. Current direct execution is recorded under
> `docs/screenshots/dedun-find-audit-direct-20260821/`; the reviewed survivor
> route remains available only through the hidden exact compatibility replay.

This ordered set records the canonical flagless `mem find-redundancies` path
and the one behavior deliberately reserved for `mem dedun`. Both commands run
the production shared analyzer and Resolution workbench against an isolated
store. A deterministic process-local provider returns one
`SEMANTIC_EQUIVALENT` link between two differently worded garage rules.

## Reproduction frame

- Command: `python docs/screenshots/find-redundancies-shared-dedun-20260820/capture.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Profile: isolated temporary default Profile
- Current Context: `quality/redundancy-capture`
- Source: two directly owned Memories; no embeds or descendants
- PTY: live and verified `180` columns × `52` rows
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Rendering: actual cumulative ANSI PTY streams replayed at full canvas; every
  PNG retains a matching `.typescript` and plain `.txt`
- Color verification: foreground and focused-control background ANSI styles
  are required before the script succeeds

## Ordered interaction log

| Capture | Exact command | Input since preceding capture | Visible state | Durable mutation |
| --- | --- | --- | --- | --- |
| `01-find-setup-entry` | `mem find-redundancies` | launch | frozen readable target is checked | none; provider not connected |
| `02-find-source-scope` | same process | `Tab` | target cardinality and direct/descendant reach are reviewable | none; provider not connected |
| `03-find-run-approval` | same process | `Tab` | exact `RUN FIND REDUNDANCIES` action is focused | none; provider not connected |
| `04-find-read-only-report` | same process | `Enter` | complete `MEM FIND REDUNDANCIES` report states process-local/no-Apply boundary | none |
| `05-find-evidence-row` | same process | `Tab`, `Down` | exact emitted evidence item is focused | none |
| `06-find-evidence-detail` | same process | `Enter` | source-linked `SEMANTIC_EQUIVALENT` reason is open | none |
| `07-find-confirm-choice` | same process | `Tab` | `CONFIRM LINK` is the keyboard target, not yet selected | none |
| `08-find-confirmed-process-local` | same process | `Enter` | link is confirmed as a process-local review response | none |
| `09-find-close-without-handoff` | same process | `Tab`, `Tab` | To Do offers only report completion; no Dedun survivor/Apply handoff appears | none |
| `10-find-read-only-verification` | same process | `Q` | command exits with both Memories, zero checkpoints, unchanged current Context, and one finder provider call | none |
| `11-dedun-exclusive-handoff` | fresh `mem dedun` | setup `Tab`, `Tab`, `Enter`; report `Tab`, `Down`, `Enter`; Responses `Tab`, `Enter`; then `Tab`, `Tab` | the same confirmed evidence now exposes `Dedun 1 confirmed semantic redundancy link` | none; Apply not approved |
| `12-dedun-cancelled-verification` | same Dedun process | `Q` | cancellation exits with both Memories and zero checkpoints | none |

The distinction is adapter-owned: Find Redundancies passes no duplicate
handoff handler, while Dedun alone supplies one. Sharing the analyzer and view
therefore cannot silently grant the read-only command mutation behavior.
