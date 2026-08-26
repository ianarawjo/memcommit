# Context history and one-shot Diff capture log

This ordered set records the Context-wide Trace Viewer and the checkpoint-unit
Diff command after removing Diff's TTY-only target browser.

## Reproduction frame

- Command: `python agent-records/screenshots/context-history-one-shot-diff-20260825/capture.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Profile/current Context: isolated temporary HOME; `practice/rules`
- Fixture: ten alphabetic fruit Memories; the `c` Memory is later edited from
  `c is cherry` to `c is clementine`
- PTY: `180` columns × `52` rows, verified by live `stty size`
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Renderer: actual color-preserving PTY bytes replayed through `pyte` and drawn
  on the full Menlo terminal canvas; every PNG retains matching `.typescript`
  and `.txt` evidence
- Mutation boundary: fixture setup mutates only the temporary HOME before the
  ordered path begins; the capture script hashes that store before and after
  every recorded command and requires byte-identical durable state

## Ordered evidence

| Image | Exact command or keys | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-context-trace-viewer-entry.png` | `mem trace practice/rules --tui --all` | One Context-lineage document, latest operation first; no checkpoint picker | None |
| `02-context-trace-viewer-scrolled.png` | preceding state, then `PgDn` | Older complete Context operations inside the same read-only Viewer | None |
| `03-context-trace-viewer-closed.png` | preceding state, then `Esc` | Viewer closes; the capture harness prints the read-only close marker | None |
| `04-context-trace-plain-verification.png` | `mem trace practice/rules --plain --limit 3` | Text-only Context subject, bounded as three of the complete operation lineage | None |
| `05-diff-latest-checkpoint-result.png` | `mem diff practice/rules` | Newest checkpoint only, explicitly labelled as checkpoint versus previous | None |
| `06-diff-exact-checkpoint-result.png` | `mem diff EDIT_CHECKPOINT_UID` | The exact edit checkpoint, showing `c is cherry` → `c is clementine` | None |
| `07-diff-context-typo-suggestion.png` | `mem diff pracitce/rules --stat` | Exact failure followed by display-only `Did you mean 'practice/rules'?` | None |

The close and completion lines are capture-harness markers, not command
receipts. They make PTY completion and the independently verified read-only
boundary visible without changing the application's output contract.
