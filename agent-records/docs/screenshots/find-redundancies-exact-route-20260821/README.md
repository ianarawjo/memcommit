# Direct exact-DUP and complete-DUN reports

This ordered set records the current direct-execution contract for
`mem find-duplicates` and `mem find-redundancies`. Both commands immediately
analyze the command-start current Context; neither opens an initial target
selector. The exact edge remains a first-class `DUP / EXACT` part of the
complete DUN report. No provider connects for this exact-only frame and no
Source mutation occurs.

## Reproduction frame

- Command: `python agent-records/docs/screenshots/find-redundancies-exact-route-20260821/capture.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Profile: isolated temporary default Profile
- Current Context: `quality/exact-route`
- Source: two directly owned byte-identical Memories; no embeds or descendants
- PTY: live and verified `180` columns × `52` rows
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Rendering: actual cumulative ANSI PTY streams replayed at full canvas; every
  PNG retains a matching `.typescript` and plain `.txt`
- Color verification: foreground ANSI styles are required before the script
  succeeds

## Ordered interaction log

| Capture | Exact command | Input since preceding capture | Visible state | Durable mutation |
| --- | --- | --- | --- | --- |
| `01-find-duplicates-direct` | `mem find-duplicates` | launch | provider-free exact-DUP report appears immediately, with no setup screen | none; provider not connected |
| `02-find-redundancies-direct` | `mem find-redundancies` | `Enter` after the first isolated command | complete DUN report appears immediately and states one exact link plus zero semantic links | none; provider not connected |
| `03-read-only-verification` | same isolated process | `Enter` | two Memories, zero checkpoints, unchanged current Context, and zero provider calls are verified | none |

The former selector capture was intentionally replaced because an explicit
`find-redundancies --select` path is not part of the current command contract.
Broader target composition remains operation-specific rather than implicit in
these two relation reports.
