# Help handoff and init-study-owned shell

This ordered actual-terminal record covers both responsibilities formerly
hidden behind the public `shell-init` wrapper. The first path selects one Help
Form, edits only its arguments, closes Help, and runs the reviewed child argv.
The second initializes a Study, enters its disposable zsh, proves the parent
history entry is absent there, runs a Mem command, and returns to the unchanged
parent shell.

## Reproduction frame

- Command: `python agent-records/docs/screenshots/help-init-study-shell-responsibility-20260828/capture.py`
- Working directory: repository root
- PTY: `180` columns × `52` rows; `TERM=xterm-256color`,
  `COLORTERM=truecolor`, and `NO_COLOR` unset
- Profile roots: fresh temporary roots recorded in `interaction.log`; the real
  user Profile, Store, configuration, and history files are never opened
- Executable: a temporary `mem` shim invokes this checkout's real Typer entry
  point in every child process
- Provider boundary: no semantic provider is connected

## Ordered interaction

| Image | Command / preceding input | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-help-entry.png` | `mem help` | Initial Help browser | None |
| `02-status-form-selected.png` | A–Z, select Status Form 2 | `mem status --short` Form selected | None |
| `03-command-editor-prefilled.png` | Enter | Fixed `mem status` prefix and editable `--short` | None |
| `04-command-editor-edited.png` | Ctrl-U, then `--branch` | Valid reviewed `mem status --branch` | None |
| `05-child-command-result.png` | Enter | Help is closed; the child Status receipt is visible | None |
| `06-init-study-shell-entered.png` | `mem init-study shell-owned-study` | Published Study receipt followed by the isolated zsh prompt | Creates and selects the isolated participant/authority Profile pair |
| `07-study-history-isolated.png` | `fc -l -10` | The parent-only history marker is absent | None |
| `08-study-command-active.png` | `mem status --short` | The child shell uses the new Study Profile and `practice` Context | None |
| `09-parent-shell-returned.png` | `exit` | Study exit receipt, parent-resumed marker, and parent-only history marker | None |

The exact keys, temporary roots, color environment, and mutation classification
are preserved in `interaction.log`. The `.typescript` files retain the raw ANSI
streams used to render each PNG.
