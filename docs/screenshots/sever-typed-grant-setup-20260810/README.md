# Sever typed-Grant setup capture log

These images record the repaired `mem sever` New-session path in the existing
active Study Profile. The path deliberately stops at the non-publishing setup
boundary: it selects readable Grant sources process-locally, leaves the
suggested Output visibly `NOT CREATED`, and cancels before provider connection,
session persistence, or Context creation.

## Reproduction frame

- Command: `mem sever`, then `N` for `Add new Sever session`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Profile: `study-alt-20260810-t3-find-additive`
- Store: `/Users/KimMunyeong/.mem-profiles/stores/c8651b54-005b-471e-aa24-579dff2ee3a1`
- Current Context before and after: `task-3/local/personal-memory`
- PTY: `180` columns × `52` rows; the raw stream begins with the live
  `stty size` result `52 180`
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Renderer: cumulative real PTY ANSI streams replayed with `pyte`, then drawn
  at the complete `1832×1124` terminal canvas with Menlo. Matching raw
  `.typescript` and plain terminal `.txt` evidence is retained beside each PNG.

The interactive streams contain application-emitted 256-color foreground and
background sequences (`38;5` and `48;5`). The renderer preserves those styles;
it does not infer colors from text. Menlo Regular supplies box-drawing fallback
for focused bold frame chrome because Menlo Bold itself omits those glyphs.

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-saved-session-launcher.png` | Launch `mem sever` | Three existing saved Sever sessions and `Add new Sever session` | None |
| `02-new-setup-current.png` | `N` | New setup opens successfully on the unchanged current Context; typed QUERY/READ Grant annotations render instead of failing validation | None |
| `03-source-read-grant-selected.png` | `Up` ×8, `Right`, `Down` ×3, `Enter` | Source is process-locally checked as `task-2/advisor1`; its READ Grant permissions render as typed tokens | None |
| `04-criteria-read-grant-selected.png` | `Up` ×8, `Right`, `Down` ×4, `Enter` | Criteria is process-locally checked as `task-2/advisor2`; Output is `task-2/severed · NOT CREATED` | None |
| `05-cancel-receipt.png` | `Escape` | `Sever setup cancelled. No session created.` | None |
| `06-read-only-verification.png` | Separate PTY: `mem profile current`; `mem status`; non-TTY `mem sever --sessions`; `mem show --context task-2/severed` | Same Profile/current Context, the same three saved sessions, and expected absence of `task-2/severed` | None |

## Verified boundary

- Saved Sever sessions: `3` before, `3` after.
- Suggested Output `task-2/severed`: absent before, absent after.
- Current Context: unchanged.
- No provider call, Source/Criteria mutation, checkpoint, semantic review, or
  Apply approval occurred. Those later stages are intentionally outside this
  regression: the defect was the typed annotation handoff before New setup
  could open.

The capture helper asserts all three invariants after the interactive command
and fails rather than publishing screenshots when any one changes.
