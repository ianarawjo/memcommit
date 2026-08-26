# Context picker semantic clipboard capture log

This ordered set records focused `y` item copy and uppercase `Y` visible-branch
copy in the common Context picker. It also demonstrates that both keys produce
the same atomic result while a Memory owns focus.

## Reproduction frame

- Command: `python agent-records/docs/screenshots/context-picker-clipboard-20260813/capture.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Profile/current Context: no store or Profile is consulted; the child uses a
  synthetic Task 1-shaped tree and keeps `task-1` as its process-local current
  marker
- PTY: `180` columns × `52` rows; the child prints and verifies the live size
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Renderer: cumulative real PTY ANSI streams replayed through `pyte` and drawn
  at the full `1832×1124` Menlo canvas. Raw `.typescript` and plain `.txt`
  evidence are retained beside every PNG.
- Color verification: the capture helper requires ANSI foreground styling and
  the reverse-video focus style before succeeding.
- Clipboard provenance: the full picker and real key bindings run unchanged,
  while a capture-local text writer records each exact clipboard payload in
  memory so the evidence run cannot overwrite the person's macOS clipboard.
  The production writer remains the existing `/usr/bin/pbcopy` adapter covered
  by `tests/test_list_clipboard.py`.

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-context-entry.png` | Launch picker | `task-1` owns focus; direct children and Description Memory are visible | None |
| `02-context-item-copied.png` | `y` | Footer confirms that only focused Context `task-1` was copied | None |
| `03-context-visible-branch-copied.png` | `Y` | Footer confirms the currently visible Task 1 branch, including one Memory, was copied | None |
| `04-memory-focused.png` | `Down`, `Down` | Description Memory owns focus; the prior receipt is cleared | None |
| `05-memory-y-copied.png` | `y` | Footer confirms one focused Memory was copied | None |
| `06-memory-uppercase-y-copied.png` | `Y` | Uppercase `Y` confirms the same focused Memory copy | None |
| `07-read-only-copy-verification.png` | `q` | Four captured payloads report physical line counts; Memory `y` and `Y` are byte-identical; no switch receipt or store mutation exists | None |
| `08-copy-failed.png` | Launch failure picker, `y` | A clipboard adapter failure stays inside the picker as a visible `COPY FAILED` receipt | None |
| `09-failure-read-only-verification.png` | `q` | The failed write did not replace clipboard text, select a Context, or mutate a store | None |

The visible-branch payload includes a collapsed participant row and granted
campus-wiki row because both are visible. Their hidden descendants are absent.
The long Memory is one physical clipboard line even though the terminal may
soft-wrap that line when displaying the verification receipt.
