# Merge lineage UID handoff PTY trace

This ordered capture records the exact task-1 failure after the fix. Both the
retained Source UID `cd518767` and fresh Target UID `423582d8` open the same
receipt-connected lineage, including Move, Replace, and the `604759a1` Merge
checkpoint, without adding a new UID-map mode or mutating the Store.

## Reproduction frame

- Command: `python agent-records/docs/screenshots/mem-merge-lineage-trace-20260823/capture.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Profile/current Context: the active task-1 participant Profile and its
  unchanged current Context, printed in every PTY stream
- PTY: `180` columns × `52` rows, set before launch and verified as `52 180`
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Data: existing task-1 checkpoints; every command in this capture is read-only
- Renderer: each PNG is rendered from its matching real ANSI PTY stream at the
  complete terminal canvas; `.typescript` and plain `.txt` evidence are kept
  beside it

## Ordered interaction

| Image | Exact command and preceding input | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-source-uid-connected-trace.png` | `mem trace cd518767 --all --tui` | Source-selected Trace shows the earlier Move and Replace plus recorded downstream Merge Source/Target occurrences | None |
| `02-source-history-origin.png` | `End` in the Source Viewer | The bottom of the same frozen Trace exposes the complete Replace and Move origin detail | None |
| `03-target-uid-connected-trace.png` | `q` closes the first Viewer; separate PTY runs `mem trace 423582d8 --all --tui` | Target-selected Trace continues backward through the same Merge into the Source history | None |
| `04-read-only-verification.png` | `q` closes the second Viewer; separate PTY runs `mem trace cd518767 --plain --all` | Plain output retains the same operation grammar and the harness verifies the current Context is unchanged | None |

The harness rejects an incorrect PTY size, absent ANSI styling, a missing
Move/Replace/Merge chain, missing Source or Target UID, or any current-Context
change.
