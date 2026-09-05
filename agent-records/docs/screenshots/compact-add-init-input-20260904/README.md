# Compact Add and Init input flow

The Add captures 01–05 record the earlier multiline intake, superseded on
2026-09-05 by [Context / Viewer / Add](../add-context-viewer-input-20260905/README.md).
The Init captures remain applicable. The original capture entry point records
the earlier key contract; its support functions are reused by the newer script.

These captures record the compact interactive `mem add`, `mem init`, and
`mem init --parents` flows after removing Add's draft list and Init's parent
browser. They were produced from the repository entry point in an isolated
temporary home with profile `authoring`, a 180-column by 52-row PTY,
`TERM=xterm-256color`, `COLORTERM=truecolor`, and `NO_COLOR` unset.
`PROMPT_TOOLKIT_NO_CPR=1` suppresses the recorder-only cursor-position warning.

The fixture begins with local Contexts `project` and `notes`, current Context
`notes`, and one existing Memory in `project`.

| Image | Command and preceding input | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-add-entry.png` | `mem add` | Initial `MEM ADD` screen; Memory input is focused and `notes` is the Target | No |
| `02-add-target-choice.png` | Shift-Tab, Up, Enter | Target focus with `project` selected | No |
| `03-add-memory-ready.png` | Tab, `A compact Memory.`, Enter, `Second line stays together.` | Exact two-line Memory immediately before Ctrl-S | No |
| `04-add-success-receipt.png` | Ctrl-S | Ordinary Add receipt for one Memory in `project` | Yes: one Memory appended to `project`; current remains `notes` |
| `05-add-read-only-verification.png` | `mem show project --direct` | Existing and newly added Memories in Target order | No |
| `06-init-entry.png` | `mem init` | Initial `MEM INIT` screen with the fresh suggestion focused | No |
| `07-init-name-ready.png` | Ctrl-U, `project/new-topic` | Exact new Context name immediately before Enter | No |
| `08-init-success-receipt.png` | Enter | Ordinary Init receipt | Yes: `project/new-topic` created and made current |
| `09-init-read-only-verification.png` | `mem show project/new-topic --direct` | The exact new Context exists and is empty | No |
| `10-init-parents-name-ready.png` | `mem init --parents`, Ctrl-U, `archive/2026/notes` | `CREATE MISSING PARENTS` state and exact name immediately before Enter | No |
| `11-init-parents-success-receipt.png` | Enter | Init hierarchy receipt naming every created Context | Yes: missing lexical parents and `archive/2026/notes` created; descendant made current |
| `12-init-parents-read-only-verification.png` | `mem show archive/2026/notes --direct` | The exact descendant exists and is empty | No |

The PNGs are rendered from the accompanying color-preserving PTY byte streams.
The `.txt` files contain the corresponding reconstructed terminal canvases.
Run `PYTHONPATH=src python agent-records/docs/screenshots/compact-add-init-input-20260904/capture.py`
with the earlier Add implementation to reproduce this historical set.
