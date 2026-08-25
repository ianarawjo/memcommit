# Sever shared Endpoint Setup PTY trace

This ordered trace records the migration of Sever's command-local stacked
screen to the common compact role-pane Endpoint Setup. The actual `mem sever`
CLI callback is exercised through its setup receipt boundary. A capture-only
guard then raises before provider construction so the exact reviewed setup can
be verified without publishing a semantic session or Context mutation.

- PTY: `180` columns × `52` rows, set by `pexpect` and reported by the child.
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`, and
  `PROMPT_TOOLKIT_COLOR_DEPTH=DEPTH_24_BIT`, with `NO_COLOR` removed. The raw
  stream is checked for true-color ANSI foreground/background styles.
  `PROMPT_TOOLKIT_NO_CPR=1` suppresses only the cursor-position probe that
  pexpect does not answer; it does not change the canvas or color stream.
- Profile: isolated explicit Store; host Grants are excluded.
- Current Context: `capture/reference`.
- Command: `mem sever`.
- Provider: the capture guard records the typed setup receipt, reports one
  crossed setup boundary, and permits zero actual provider calls.

| Image | Preceding keys/text | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-entry.png` | none | Source, Criteria, and Result compact role rows; both readable inputs initially include descendants | none |
| `02-source-exact-range.png` | `Tab`, `Tab`, `Space` | Source narrowed to exact while Criteria retains its independent descendant range | none |
| `03-source-memory-preview.png` | `Tab`, `Enter` | Source direct Memories loaded lazily as read-only evidence; no Memory UID can enter the receipt | none |
| `04-criteria-browse.png` | `Escape`, `Down`, `Tab`, `Enter` | Criteria's complete frozen allowed Context catalog | none |
| `05-exact-start-review.png` | `Enter`, `Down`, `Ctrl-U`, `capture/reference`, `Enter` | exact self-save `mem sever` START command rebuilt from Source, Criteria, ranges, and Result | none |
| `06-guarded-failure-receipt.png` | `Enter` | expected capture guard failure after the typed setup receipt crossed, before provider/session work | none |
| `07-read-only-verification.png` | `v` | unchanged complete Store digest, checkpoint count, Current, zero Sever sessions, and zero actual provider calls | none |

The failure is deliberate evidence of the setup boundary, not an application
failure: it proves focused Enter returned the reviewed typed receipt and that
the next external boundary remained closed. Existing Sever provider, saved
session, decision, Apply, Undo/Redo, and post-application Review flows retain
their separate application tests and capture sets.
