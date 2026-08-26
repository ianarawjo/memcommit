# Profile rename picker and unified Help captures

These snapshots record Profile rename as a target-local picker action and show
the concise and explicit CLI spellings together under Help's single Rename
entry. The Context picker is not involved.

## Environment

- Capture date: 2026-08-13
- Commands: `python -m memcommit.cli profile`, `python -m memcommit.cli profile list`, and `python -m memcommit.cli help`
- Harness: `python agent-records/docs/screenshots/profile-rename-picker-20260813/capture_profile_rename.py`
- PTY: `180` columns by `52` rows, set before launch and verified as `52 180`
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`, `PROMPT_TOOLKIT_COLOR_DEPTH=DEPTH_24_BIT`; `NO_COLOR` removed
- Fixture: isolated temporary `HOME`; current managed Profile `capture-workspace`, fixed `authoring`, and managed sibling `capture-sibling`
- Evidence: every state has raw ANSI `.typescript`, visible-canvas `.txt`, and full-canvas `.png` artifacts

The harness fails unless the interactive stream contains ANSI styling, the
review shows the exact explicit command, the Profile UID/current selection and
managed store path survive rename, the old name disappears from a fresh
read-only list, and the top-level `mem rename OLD NEW` spelling independently
renames the remaining managed sibling.

## Ordered interaction log

| Capture | Exact command | Profile / current Context | Preceding input | Visible state | Durable mutation |
|---|---|---|---|---|---|
| `01-profile-picker-entry` | `mem profile` | `capture-workspace` / `workspace/context` | none | Current Profile row is focused; footer exposes `Enter use  R rename  D remove Profile` | none |
| `02-rename-name-input` | same | same | `R` | Shared exact one-line field opens prefilled with `capture-workspace`; state is `NOT APPLIED` | none |
| `03-invalid-name-refused` | same | same | `Ctrl-U`, `capture/invalid`, `Enter` | Profile-segment validator refuses the slash-delimited name inside the picker | none |
| `04-corrected-exact-name` | same | same | `Ctrl-U`, `capture-renamed` | Corrected exact name is visible before review | none |
| `05-exact-rename-review` | same | same | `Enter` | Exact `mem profile rename capture-workspace capture-renamed` review states the UID/store/content/Grant invariants | none |
| `06-rename-success-receipt` | same | `capture-renamed` / `workspace/context` | `A` | Fresh picker catalog reopens on the renamed current row with a green success receipt | Profile registry display name only |
| `07-fixed-profile-rename-blocked` | same | `capture-renamed` / `workspace/context` | `Up`, `R` | Fixed `authoring` refuses rename before an input or review opens | none |
| `08-read-only-profile-verification` | `mem profile list` | `capture-renamed` / `workspace/context` | `Q`, then separate command | New name is current; old name is absent; Context and Memory counts remain | none; read-only |
| `09-combined-rename-help` | `mem help` | not consulted / not consulted | switch to A-Z, focus Rename, `Right` | One Rename detail contains both `mem rename` forms and both retained `mem profile rename` forms | none; read-only |

The capture script finally invokes `mem rename capture-sibling sibling-renamed`
in the same isolated home and verifies that this concise spelling performs the
same stable-identity Profile operation. That subprocess is an automated
contract check rather than an additional screenshot state.
