# Init Study description Memory split

This ordered capture runs the checked-in Study packages through the real
`mem` CLI in an isolated Profile root. It first imports the editable baseline,
creates one Study run, and then reads Practice and Task 1–3 descriptions. The
capture verifies that each task description renders one `SITUATION` Memory and
one independent `TASK` Memory. Practice retains its separate overview Memory
before those two role rows.

## Reproduction frame

- Command: `python docs/screenshots/init-study-description-split-20260821/capture.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- PTY: `180` columns × `52` rows; `TERM=xterm-256color`,
  `COLORTERM=truecolor`, and `NO_COLOR` unset
- Profile root: a fresh `/tmp/memcommit-init-study-description-split-*`
  directory recorded exactly in `interaction.log`; the real user Profile and
  authoring store are never opened or changed
- Package source: checked-in `outputs/study-fixtures/task-1` through `task-3`
- Result Profile: `description-split-check`, current Context `practice`
- Provider boundary: no semantic provider is connected

## Ordered interaction

| Image | Exact command | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-baseline-imported.png` | `mem profile import-study` | Editable `study-baseline` import receipt | Creates the isolated baseline only |
| `02-study-run-created.png` | `mem init-study description-split-check` | New Study Profile receipt and current `practice` Context | Creates and selects the isolated run |
| `03-practice-description.png` | `mem ls practice/description --direct` | Overview, `SITUATION`, then independent `TASK` | None |
| `04-task-1-description.png` | `mem ls task-1/description --direct` | Task 1 `SITUATION` and `TASK` | None |
| `05-task-2-description.png` | `mem ls task-2/description --direct` | Task 2 `SITUATION` and `TASK` | None |
| `06-task-3-description.png` | `mem ls task-3/description --direct` | Task 3 `SITUATION` and `TASK` | None |
