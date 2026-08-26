# `mem profile create` picker capture log

These images replay the actual color-preserving PTY streams produced while an
empty managed Profile is created, explicitly selected, initialized with its
first Context, and verified read-only.

## Reproduction frame

- Working directory: `/Users/KimMunyeong/Github/memcommit`
- PTY: `180` columns × `52` rows, set before every launch and verified by the
  child as `52 180`
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` removed
- Initial Profile/current Context: disposable `authoring` / `authoring-notes`
- New Profile/current Context: `capture-empty` / initially none, then `inbox`
- Renderer: actual cumulative ANSI streams replayed with `pyte`, with matching
  `.typescript` and `.txt` evidence beside every PNG
- Durable scope: one temporary HOME removed after capture; the real Profile
  registry and stores were not touched

The capture command is:

```bash
python agent-records/screenshots/profile-create-picker-20260822/capture_profile_create.py
```

The driver rejects an incorrect PTY size, missing ANSI styling, absence of the
shared blue CREATE foreground, absence of the focused-row reverse background,
or any mismatch in the final Profile and Context state.

## Ordered interaction

| Image | Command and exact input since preceding image | Visible state | Durable mutation in disposable HOME |
| --- | --- | --- | --- |
| `01-profile-picker-entry.png` | `mem profile` | Current `authoring` row and blue `N new Profile` action | None |
| `02-empty-profile-name-input.png` | `N` | Shared exact one-line field, blank and `NOT CREATED` | None |
| `03-invalid-profile-name-refused.png` | `capture/invalid`, `Enter` | Portable one-segment validation error; exact input retained and no review opened | None |
| `04-exact-profile-name-entered.png` | `Ctrl-U`, `capture-empty` | Corrected exact Profile name and cleared validation error; still not created | None |
| `05-exact-create-review.png` | `Enter` | Frozen `mem profile create capture-empty`, empty-store effects, and unchanged-active boundary | None |
| `06-create-success-new-row-focused.png` | `A` | Success status, zero inventory, and new row focused but not current | Empty managed Profile and registry entry created atomically |
| `07-new-profile-selected.png` | `Enter` | Profile selection receipt and `(none)` current Context | Active Profile changed to `capture-empty` |
| `08-empty-profile-read-only-verification.png` | `mem profile current` | New Profile owns zero Contexts and has no current Context | None |
| `09-first-context-created.png` | `mem init inbox` | First Context initialization receipt | `inbox` created and selected inside `capture-empty` |
| `10-final-read-only-verification.png` | `mem profile current` | `capture-empty`, one owned Context, current `inbox` | None |
