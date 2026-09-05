# Add: Context, ten-row Viewer, single-line input

Agent-produced captures of the actual CLI in a color PTY, rendered from its
recorded byte stream. Every PNG preserves the complete 180×52 terminal canvas.
The PTY size is set before launch and printed by `stty size`. `NO_COLOR` is
removed; `TERM=xterm-256color`, `COLORTERM=truecolor`, and the recorder-only
`PROMPT_TOOLKIT_NO_CPR=1` are set. Foreground and background ANSI styles are
asserted in the raw stream. This replaces the Add portion of the 2026-09-04
compact Add/Init record; Init itself is unchanged.
The ordered set is refreshed for the neutral `MEM ADD` title and now records
the screen-only multiline-paste rejection. Every visible title is checked to
use the same foreground style for `MEM` and `ADD`.

All commands run from the repository root using its `src` on PYTHONPATH and
an isolated temporary HOME, profile `authoring`. Initial Contexts are empty
`notes` (current) and `project` containing fifteen numbered Memories. The
Viewer contains ten rows of content; its frame occupies twelve terminal rows.

| Image | Command / preceding keys | Visible state | Durable effects since previous image |
| --- | --- | --- | --- |
| 01-entry | `mem add` | `notes`, empty Viewer, focused single-line ADD | None |
| 02-context-browser | Tab, Enter | Common Context tree opened in place | None |
| 03-context-selected | Down, Enter | `project` committed; first ten Memories visible | None; global current remains `notes` |
| 04-viewer-scrolled | Tab, Page Down | Viewer focused and scrolled to later Memories | None |
| 05-input-ready | Tab, `A new single-line Memory.` | Exact input before Enter | None |
| 05a-multiline-paste-rejected | Bracketed paste `Rejected first line.\nRejected second line.` | Paste rejected; original input unchanged; guidance visible | None |
| 06-added-ready-for-next | Enter | Newly appended Memory visible at end; ADD blank and focused; success notice | One Memory and Add checkpoint in `project` |
| 07-close-receipt | Escape | Ordinary Add receipt, including Context and checkpoint | None; saved Memory retained |
| 08-read-only-verification | `mem show project --direct` | Sixteen ordered Memories including the exact new one | None |
| 09-failure-path-entry | Fixture: `mem init temporary`, `mem add 'Existing temporary Memory.'`; then `mem add` | Current `temporary` and its existing Memory | Fixture creates `temporary` and one Memory before launching Add |
| 10-failure-path-input | `Keep this input after failure.` | Exact unsaved input | None |
| 11-failed-add-input-retained | External fixture calls `MemoryStore().delete('temporary')`, then Enter in Add | Target lookup fails, input retained, stale Viewer cleared | External deletion only; Add publishes no Memory/checkpoint |
| 12-failure-path-close | Escape | Cancellation receipt; no Add succeeded | None |
| 13-failure-read-only-verification | `mem show temporary --direct` | Target absent, exit 1; failed Add did not recreate it | None |

The failure path deliberately deletes the selected Context in another process
using the production Store lifecycle API, inside the isolated fixture only.
The running Add retains its original canonical target and does not retarget to
another Context. No test data touches the user's normal Profile.

The `.typescript` files contain raw PTY streams and `.txt` files their decoded
terminal canvases. Reproduce the entire ordered set with:

```sh
PYTHONPATH=src python agent-records/docs/screenshots/add-context-viewer-input-20260905/capture.py
```

The paste payload is enclosed in `ESC [ 200 ~` and `ESC [ 201 ~`; `\n` above
denotes one LF character. Screen paste accepts only one line. This differs from
`mem add --paste`, which reads the system clipboard and adds each nonblank
trimmed line as a separate Memory; the CLI contract is covered by
`tests/test_add_paste.py`.
