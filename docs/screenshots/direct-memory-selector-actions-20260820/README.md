# Direct-Memory selector action capture log

This ordered set records the shared direct-Memory selection contract used by
interactive Reference and Edit. Both commands run through the real Typer root
and isolated Stores; the capture child prints read-only durable verification
after each success or cancellation.

## Reproduction frame

- Command: `python docs/screenshots/direct-memory-selector-actions-20260820/capture.py`
- Commands under capture: bare `mem reference` and bare `mem edit`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Profile/current Context: isolated local fixtures; Reference uses current
  `target` plus peer `source`, and Edit uses current `notes`; host Profiles and
  Grants are excluded
- PTY: `180` columns × `52` rows, verified by the child
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset,
  and command-attempt logging disabled
- Renderer: cumulative real PTY ANSI bytes replayed through `pyte` and rendered
  at the full Menlo canvas; `.typescript` and `.txt` evidence accompany every
  PNG

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-reference-entry.png` | Launch bare `mem reference`, `Right` | Explicit snapshot-unit control selects Memory; Context-only scope is absent and To Do is incomplete | None |
| `02-reference-source-open.png` | `Tab` | Direct-Memory selector owns focus with peer `source` expanded and Target separately checked at current `target` | None |
| `03-reference-memory-selected.png` | `Down`, `Enter` | Exact full-UID Source Memory is checked independently from the Context cursor | None |
| `04-reference-target.png` | `Tab` | Target selector owns focus and still checks `target`; Source and Target roles remain separate | None |
| `05-reference-exact-command.png` | `Tab` | Exact `mem reference MEMORY_SELECTOR --from source --into target` and immutable-snapshot effects are focused | None |
| `06-reference-success.png` | `Enter` | TUI closes and the durable typed receipt reports Source Memory, new snapshot UID, and Target | One read-only snapshot and one Reference checkpoint in `target` |
| `07-reference-read-only-verification.png` | `V`, `Enter` at the capture-only verification gate | Direct Store read confirms one retained snapshot with exact content while Source stays unchanged | No additional mutation |
| `08-reference-cancel-verification.png` | Separate launch, `Escape` | Root cancellation receipt followed by zero Target items and zero Reference checkpoints | None |
| `09-edit-entry.png` | Launch bare `mem edit` | UPDATE-authorized direct-Memory selector, empty replacement field, and red invalid Proposed Command because no exact Memory is selected | None |
| `10-edit-memory-selected.png` | `Down`, `Enter` | Exact Memory is checked, its existing multiline content prefills the replacement field, and the command becomes runnable | None |
| `11-edit-multiline-content.png` | `Tab`, delete the prefilled value, enter two revised lines | Writable replacement field owns focus; the editable command immediately reflects the two process-local lines | None |
| `12-edit-exact-command.png` | `Tab` | The compact editable `PROPOSED COMMAND` keeps `mem edit` as a fixed prompt and exposes only the full-UID, escaped-content, and Context arguments for editing | None |
| `13-edit-command-invalid.png` | `Ctrl-U`, type `mem delete target` into the argument buffer | `Ctrl-U` cannot erase the fixed `mem edit` prefix, so the visible line is `mem edit mem delete target`; the frame and validation reason turn red, Apply is blocked, and the upper fields retain their prior values | None |
| `14-edit-command-updates-content.png` | `Ctrl-U`, type valid `MEMORY … --context notes` arguments | The fixed prefix remains, the frame returns to runnable, and both command-authored lines appear in the multiline replacement field | None |
| `15-edit-success.png` | `Enter` | TUI closes and the plain receipt shows the original lines replaced by the command-authored lines | One Memory replacement and one Edit checkpoint in `notes` |
| `16-edit-read-only-verification.png` | `V`, `Enter` at the capture-only verification gate | Direct Store read confirms the exact command-authored replacement and one Edit checkpoint | No additional mutation |
| `17-edit-cancel-verification.png` | Separate launch, `Escape` | Root cancellation receipt followed by original content and zero Edit checkpoints | None |

Reference freezes Source content, Source/Target identities, and Target revision
at the exact-command action; later drift fails without publication. Edit freezes
UPDATE authority, the Context digest, full Memory UID, and original content;
drift while the editor is open fails before mutation. The selector itself owns
only Context navigation, Memory hover, and exact checked selection. Add remains
a content-intake operation and therefore uses a Target selector plus draft
editor instead of interpreting selector-shaped input as an existing Memory.
