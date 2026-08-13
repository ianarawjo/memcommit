# Permanent Profile deletion TUI captures

These snapshots record the focusable Study-header and child-Profile deletion
boundaries. Every run uses the repository CLI in a real color-capable PTY with
an isolated temporary `HOME`; no configured user Profile was read or changed.

## Environment

- Capture date: 2026-08-13
- Command: `python docs/screenshots/profile-soft-removal-20260813/capture_profile_soft_removal.py`
- CLI under test: `python -m memcommit.cli profile`
- PTY: `180` columns by `52` rows, set before launch and verified as `52 180`
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`,
  `PROMPT_TOOLKIT_COLOR_DEPTH=DEPTH_24_BIT`; `NO_COLOR` removed
- Evidence: each state has a raw ANSI `.typescript`, visible-canvas `.txt`, and
  full `1832 × 1124` `.png` rendered from that stream
- Fixture: every store contains a real checkpoint; `capture-workspace` is
  current for successful paths and `capture-participant` is current for the
  refusal path

The harness fails if an interactive raw stream lacks ANSI styling, if the PTY
size is wrong, if an exact command or irreversible warning is missing, if a
success receipt is absent, or if a deleted UID store remains on disk. The
single-Profile path additionally verifies that the sibling UID store remains.

## Ordered interaction log

| Capture | Command | Preceding input | Visible state | Durable mutation |
| --- | --- | --- | --- | --- |
| `01-study-entry` | `mem profile` equivalent | terminal CPR only | Entry with current workspace, focusable Study heading, participant, and granted-memory child | None |
| `02-study-header-target` | same | `Down` | `STUDY capture-study` owns focus; footer says `D remove Study` | None |
| `03-study-exact-removal-review` | same | `D` | Exact `mem profile remove-study capture-study --force`; Memories, sessions, checkpoints, and connected Grants are listed as unrecoverable deletions | None |
| `04-study-removal-receipt` | same | `Enter` | Green permanent-deletion receipt; both stores and checkpoint histories deleted | Both Study UID paths destroyed; both identity tombstones published; incident Grant removed |
| `05-study-read-only-verification` | `mem profile list` equivalent | None | Only authoring/workspace remain visible; two deletion tombstones reported | None; read-only |
| `06-fixed-authoring-removal-blocked` | `mem profile` equivalent | `Up`, `D` | Fixed authoring row refuses deletion before review | None |
| `07-profile-child-target` | same | `Down` × 3 | Participant child owns focus; footer says `D remove Profile` | None |
| `08-profile-exact-removal-review` | same | `D` | Exact `mem profile remove capture-participant --force`; permanent store/checkpoint deletion warning; sibling Study row retained | None |
| `09-profile-removal-receipt` | same | `A` | Green permanent-deletion receipt and `1 active · 1 removed` | Participant UID path destroyed; identity tombstone published; incident Grant removed; sibling store retained |
| `10-profile-read-only-verification` | `mem profile list` equivalent | None | Study header remains with granted-memory child and `1 removed` annotation | None; read-only |
| `11-active-profile-removal-blocked` | `mem profile` equivalent | `D` on current participant | Current Profile refuses deletion and instructs a prior switch | None |
| `12-active-study-removal-blocked` | same | `Up`, `D` | Parent Study refuses deletion because it contains current Profile | None |
| `13-blocked-read-only-verification` | `mem profile list` equivalent | `q`, then read-only command | Both Study children remain and participant is still current | None; read-only |

Study and Profile success paths use separate isolated registries. The blocked
path uses a third registry so refusal evidence cannot be confused with state
left by a prior successful deletion.
