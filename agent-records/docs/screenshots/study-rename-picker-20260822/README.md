# Study rename picker captures

These snapshots record a current two-Profile Study heading being renamed from
the Profile TUI. The participant and granted-memory Profile display names are
intentionally different from the Study label so the unchanged-child boundary
is visible.

## Environment

- Capture date: 2026-08-22
- Commands: `python -m memcommit.cli profile` and `python -m memcommit.cli profile list`
- Harness: `python agent-records/docs/screenshots/study-rename-picker-20260822/capture.py`
- PTY: `180` columns by `52` rows, set before launch and verified as `52 180`
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`, and `PROMPT_TOOLKIT_COLOR_DEPTH=DEPTH_24_BIT`; `NO_COLOR` removed
- Fixture: isolated temporary `HOME`; current Profile `authoring`; Study UID `11111111-1111-4111-8111-111111111111`; member Profiles `participant-one` and `participant-one-granted-memory`
- Evidence: every state has raw ANSI `.typescript`, visible-canvas `.txt`, and full-canvas `.png` artifacts

The harness fails unless the raw interactive stream contains ANSI styling, the
PTY reports the required size, the exact `mem profile rename-study` command is
reviewed, both Profile names remain visible after Apply, the Study/Profile UIDs
and stable store paths are unchanged, and no member-store byte changes.

## Ordered interaction log

| Capture | Exact command | Profile / current Context | Preceding input | Visible state | Durable mutation |
|---|---|---|---|---|---|
| `01-picker-entry` | `mem profile` | `authoring` / `authoring-notes` | none | Profile selector entry shows the Study heading and both child Profiles | none |
| `02-study-header-target` | same | same | `Down` | Study heading is the keyboard target; footer exposes `R rename` and `D remove Study` | none |
| `03-study-name-input` | same | same | `R`, `Ctrl-U`, `capture-renamed` | Exact one-line `NEW STUDY NAME` field contains the proposed label | none |
| `04-exact-rename-review` | same | same | `Enter` | Exact `mem profile rename-study capture-study capture-renamed` review states that member Profile names and all stable identities/data remain unchanged | none |
| `05-rename-success-receipt` | same | same | `A` | Fresh picker catalog shows `STUDY capture-renamed`, both original child names, and the success receipt | one Profile-registry generation; shared Study display metadata only |
| `06-read-only-verification` | `mem profile list` | `authoring` / `authoring-notes` | `Q`, then separate command | Stable list shows the new Study heading and unchanged participant/granted-memory Profile names | none; read-only |
