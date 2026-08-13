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
Both success paths fail if deletion exits the TUI instead of reopening the
refreshed selector. The same harness also runs the direct Profile and Study CLI
commands with `--force` in two additional isolated homes and verifies their
full receipts and deleted UID paths. Those subprocesses redirect output, so the
TTY-only transient cadence is intentionally absent from their stable receipt
evidence.
The interactive capture process delays the approved deletion by `1.4` seconds
without changing the deletion implementation. It requires the raw PTY stream
to show the shared `.`, `..`, `…` cadence before the refreshed selector.

## Ordered interaction log

| Capture | Command | Preceding input | Visible state | Durable mutation |
| --- | --- | --- | --- | --- |
| `01-study-entry` | `mem profile` equivalent | terminal CPR only | Entry with current workspace, focusable Study heading, participant, and granted-memory child | None |
| `02-study-header-target` | same | `Down` | `STUDY capture-study` owns focus; footer says `D remove Study` | None |
| `03-study-exact-removal-review` | same | `D` | Exact `mem profile remove-study capture-study --force`; Memories, sessions, checkpoints, and connected Grants are listed as unrecoverable deletions | None |
| `04-study-deletion-in-progress` | same | `Enter`; shared cadence reaches `…` | Reviewed Study remains frozen while header and footer show permanent store/checkpoint deletion in progress | Deletion running; no second action accepted |
| `05-study-removal-receipt` | same | background deletion completes | Refreshed selector stays open; the removed last group resolves to its preceding workspace row and a green permanent-deletion receipt is visible | Both Study UID paths destroyed; both identity tombstones published; incident Grant removed |
| `06-study-read-only-verification` | `mem profile list` equivalent | `q`, then read-only command | Only authoring/workspace remain visible; two deletion tombstones reported | None; read-only |
| `07-fixed-authoring-removal-blocked` | `mem profile` equivalent | `Up`, `D` | Fixed authoring row refuses deletion before review | None |
| `08-profile-child-target` | same | `Down` × 3 | Participant child owns focus; footer says `D remove Profile` | None |
| `09-profile-exact-removal-review` | same | `D` | Exact `mem profile remove capture-participant --force`; permanent store/checkpoint deletion warning; sibling Study row retained | None |
| `10-profile-deletion-in-progress` | same | `A`; shared cadence reaches `…` | Reviewed child remains frozen while header and footer show permanent store/checkpoint deletion in progress | Deletion running; no second action accepted |
| `11-profile-removal-receipt` | same | background deletion completes | Refreshed selector stays open with the surviving Study sibling focused at the removed child's former row, `1 removed`, and a green receipt | Participant UID path destroyed; identity tombstone published; incident Grant removed; sibling store retained |
| `12-profile-read-only-verification` | `mem profile list` equivalent | `q`, then read-only command | Study header remains with granted-memory child and `1 removed` annotation | None; read-only |
| `13-active-profile-removal-blocked` | `mem profile` equivalent | `D` on current participant | Current Profile refuses deletion and instructs a prior switch | None |
| `14-active-study-removal-blocked` | same | `Up`, `D` | Parent Study refuses deletion because it contains current Profile | None |
| `15-blocked-read-only-verification` | `mem profile list` equivalent | `q`, then read-only command | Both Study children remain and participant is still current | None; read-only |

Study and Profile success paths use separate isolated registries. The blocked
path uses a third registry so refusal evidence cannot be confused with state
left by a prior successful deletion.
