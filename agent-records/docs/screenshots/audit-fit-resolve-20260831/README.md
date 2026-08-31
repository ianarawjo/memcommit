# Audit Fit and Resolve evidence

This ordered set records the new whole-Context Fit section and its projection
as one Resolve item. The harness runs the real prompt-toolkit Audit Viewer and
Resolve command/decision surface in a color-capable `180 × 52` PTY with
`TERM=xterm-256color`, `COLORTERM=truecolor`, and `NO_COLOR` removed. It uses a
deterministic typed Audit for Review and a deterministic provider for the
isolated end-to-end Resolve run; it never opens the user's durable profile.

Reproduce from the repository root:

```text
python agent-records/docs/screenshots/audit-fit-resolve-20260831/capture.py
```

The capture harness verifies true-color ANSI in the raw PTY streams. Each PNG
is rendered from its matching `.typescript`; the `.txt` file is the ANSI-free
terminal canvas.

## Ordered interaction log

| # | Image | Exact visible command and state | Input since prior capture | Durable mutation |
| --- | --- | --- | --- | --- |
| 1 | `01-audit-fit-overview.png` | `mem review audit --session cccccccc-0000-4000-8000-000000000103`; isolated profile; current `study/audit-fit`; saved `4/4` report focused at entry | none | none |
| 2 | `02-audit-fit-may-section.png` | Same Audit Viewer; typed set-level `FIT · MAY`, two material Memories, and both ordinary readings focused | Down ×4 | none |
| 3 | `03-audit-close-no-write.png` | Audit Review closed; record digest unchanged; zero provider calls, Context writes, and checkpoints | `q` | none |
| 4 | `04-resolve-single-fit-item.png` | `mem resolve study/audit-fit`; isolated profile; current `study/audit-fit`; exactly one required `FIT` item at entry | none | none |
| 5 | `05-resolve-fit-force-selected.png` | The ordinary `LEAVE UNRESOLVED` choice is selected for the Fit item; `1/1 READY` | Down ×2, Enter | none; process-local decision only |
| 6 | `06-resolve-fit-finalize-ready.png` | Exact Finalize action focused after the one required decision | Down | none; process-local decision only |
| 7 | `07-resolve-post-image-fit-audit.png` | Finalized `FORCE` enters the complete detached post-image Audit; its second whole-Context Fit call is held at the visible verification gate | Enter | none yet |
| 8 | `08-resolve-fit-force-receipt.png` | Actual Resolve receipt: no Memory changes, one remaining Audit issue, one forced unresolved item, and one Resolve checkpoint | `c`, Enter | one checkpoint; Context content unchanged |
| 9 | `09-resolve-fit-read-only-verification.png` | Context digest unchanged; checkpoint command `resolve`; one unresolved issue; Fit called once initially and once for the post-image | `v`, Enter | read-only verification |

The force path deliberately supplies no semantic Update input, so the ordinary
Resolve transaction publishes a reviewed no-Memory-change checkpoint. The
post-image Audit still reruns Fit and permits only the exact forced Fit key.
This isolates the new semantic boundary: one Audit Fit judgment becomes one
ordinary solve target, not a separate hard gate or multiple pairwise findings.
