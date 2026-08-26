# Edit fixed-operation command capture log

This ordered set records the consequential states of bare interactive
`mem edit` through the real Typer root and an isolated Store. The exact
operation prefix is presentation outside the writable argument buffer; no
capture touches the host Profile or Context state.

## Reproduction frame

- Exact command under review: `mem edit`
- Working directory: repository root
- Profile/current Context: isolated local fixture; current `notes`
- PTY: `180` columns × `52` rows, verified by the child
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Renderer: cumulative real ANSI PTY bytes replayed through `pyte`; matching
  `.typescript` and `.txt` evidence accompanies each PNG

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `09-edit-entry.png` | Launch bare `mem edit` | UPDATE-authorized direct-Memory selector, empty replacement, and red invalid command because no Memory is selected | None |
| `10-edit-memory-selected.png` | `Down`, `Enter` | Exact Memory checked, old multiline content prefilled, command runnable | None |
| `11-edit-multiline-content.png` | `Tab`, replace the two-line content | Content editor owns focus and immediately rebuilds command arguments | None |
| `12-edit-exact-command.png` | `Tab` | `mem edit` remains a fixed prompt; full UID, escaped content, and Context are editable arguments | None |
| `13-edit-command-invalid.png` | `Ctrl-U`, type `mem delete target` | `Ctrl-U` clears only arguments, yielding visible `mem edit mem delete target`; red validation blocks Apply and upper controls remain unchanged | None |
| `14-edit-command-updates-content.png` | `Ctrl-U`, type valid Memory/content/Context arguments | Runnable blue frame and both command-authored lines synchronized into the multiline editor | None |
| `15-edit-success.png` | `Enter` | Compact receipt shows the reviewed before/after replacement | One Memory replacement and one Edit checkpoint |
| `16-edit-read-only-verification.png` | Capture-only `V`, `Enter` | Direct Store read confirms command-authored content and one checkpoint | None |
| `17-edit-cancel-verification.png` | Separate launch, `Escape` | Cancellation receipt followed by original content and zero checkpoints | None |

Edit freezes UPDATE authority, canonical Context UID/digest, the full Memory
UID, and original content. Invalid text, cancellation, or later drift publishes
no partial content or checkpoint.
