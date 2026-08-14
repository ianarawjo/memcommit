# Merge direct and recursive TUI capture log

This ordered set records the public `mem merge` TUI, the unchanged direct
contract, the path-aligned recursive contract, and cancellation. Every launch
uses the real Typer route and Store-backed application in an isolated temporary
Store.

## Reproduction frame

- Command: `python docs/screenshots/mem-merge-recursive-tui-20260814/capture.py`
- Command under capture: bare `mem merge`, invoked through the real Typer root
  with `standalone_mode=False` so the child can print post-close Store evidence
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Profile/current Context: isolated local fixture; current Target `target`,
  readable Source tree `source` and `source/child`, plus Target-only
  `target/preserved`; host Profiles and Grants are excluded
- PTY: `180` columns × `52` rows; each child prints the live size
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset,
  and command-attempt logging disabled
- Renderer: cumulative real PTY ANSI streams replayed through `pyte` and drawn
  at the full Menlo canvas; raw `.typescript` and plain `.txt` evidence remain
  beside every PNG

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-direct-entry.png` | Launch bare `mem merge` | Shared readable Source tree owns initial focus; Range is direct; the frozen current Target is marked but unavailable as Source | None |
| `02-direct-exact-command.png` | `Tab` | Exact review shows `mem merge source --direct`, exact-root scope, UID-new additions, and no deletion propagation | None |
| `03-direct-success.png` | `Enter` | Success receipt reports direct reach, one Context and one checkpoint | Source root Memory added to `target` |
| `04-direct-verification.png` | `Enter` | TUI closes; Store verification confirms root copied, no `target/child`, Target-only descendant preserved, and one root checkpoint | No additional mutation |
| `05-recursive-range.png` | Separate launch, `Shift-Tab`, `Right` | Range owns focus with descendants selected; Source selection remains independent | None |
| `06-recursive-exact-command.png` | `Tab`, `Tab` | Exact review shows `--recursive`, complete-relative-path alignment, and Source-only Target-path creation | None |
| `07-recursive-success.png` | `Enter` | Success receipt reports descendant reach, two Contexts, one created, and two checkpoints | Root updated and `target/child` created atomically |
| `08-recursive-verification.png` | `Enter` | Store verification confirms root and child copied, Target-only descendant preserved, and the root checkpoint present | No additional mutation |
| `09-cancel-verification.png` | Separate launch, `Q` | Post-close Store verification confirms neither root nor child was copied and no root checkpoint exists | None |

Direct and recursive execution share one typed application boundary. The TUI
only selects a readable Source, reach, and exact reviewed command; it neither
implements Store mutation nor calls the CLI as a subprocess.
