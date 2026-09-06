# Current Study lifecycle PTY captures

This ordered set records a current participant/authority Study after retirement
of split-Study administration. The images are renders of actual color-preserving
PTY output, not synthetic UI fixtures or GUI screenshots. The companion raw
`.typescript` streams and visible `.txt` canvases preserve the execution evidence.

## Reproduction and environment

- Run: `PYTHONPATH=src python agent-records/docs/screenshots/profile-study-lifecycle-20260906/capture.py`
- Runtime used: `/opt/anaconda3/bin/python` on 2026-09-06.
- Each command launches in a fresh PTY through `/bin/zsh -f -c` with
  `stty rows 52 cols 180; stty size; exec /opt/anaconda3/bin/python -m memcommit.adapters.console.entrypoint ...`.
- PTY dimensions are 180 columns × 52 rows, verified by the live `52 180` output.
- `TERM=xterm-256color`, `COLORTERM=truecolor`, and
  `PROMPT_TOOLKIT_COLOR_DEPTH=DEPTH_24_BIT`; `NO_COLOR` is removed.
- The harness requires foreground `38;2;` and background `48;2;` ANSI styles in
  both interactive streams. PNGs retain the full 1832 × 1124 terminal canvas.
- A disposable temporary home contains all fixture files. Current Profile is
  `authoring` and current Context is `authoring-notes` throughout.
- Study UID: `11111111-1111-4111-8111-111111111111`. Member Profiles are
  `participant-one` and `participant-one-granted-memory`, deliberately named
  independently of the Study heading. Each store has one Memory and a checkpoint.
- No semantic provider is contacted. Command-attempt logging is disabled for the
  isolated reproduction. The host's Profile registry and user stores are not used.

In the table, `profile` means the exact command
`/opt/anaconda3/bin/python -m memcommit.adapters.console.entrypoint profile`;
`profile list` appends `list` to that command. All rows use the same 180 × 52
viewport and `authoring` / `authoring-notes` Profile/Context.

## Ordered interaction log

| Image | Command | Preceding input | Visible state | Durable mutation since previous image |
|---|---|---|---|---|
| 01-picker-entry | `profile` | None | Current authoring row and complete Study pair | None |
| 02-study-header-target | Same process | Down | Study heading selected; rename/remove controls available | None |
| 03-study-name-entry | Same process | `r` | Exact name input opens with `capture-study` | None |
| 04-study-name-edited | Same process | Ctrl-U, `capture-renamed` | Edited proposed Study name | None |
| 05-exact-rename-review | Same process | Enter | Exact `mem profile rename-study capture-study capture-renamed`; member names stay unchanged | None |
| 06-rename-success-receipt | Same process | `a` | Refreshed Study heading and rename success receipt | One registry generation; shared Study label only |
| 07-rename-verification | `profile list` | `q` to close picker, then new command | Renamed Study with unchanged participant and authority names | None; read-only |
| 08-removal-target | New `profile` process | Down | Renamed Study heading selected for removal | None |
| 09-exact-removal-review | Same process | `d` | Exact `mem profile remove-study capture-renamed --force`; permanent deletion effects | None |
| 10-removal-success-receipt | Same process | `a` | Refreshed picker contains authoring and a deletion receipt | Both isolated member stores and checkpoint histories deleted; tombstones retained |
| 11-removal-verification | `profile list` | `q` to close picker, then new command | No visible Study pair; two deleted Profile tombstones reported | None; read-only |

The harness also verifies unchanged Study/member UIDs, unchanged store paths,
and byte-identical member stores after rename. After removal it verifies that
both stores are absent, both member tombstones remain, and authoring is still
active. The complete temporary environment is discarded after verification.
