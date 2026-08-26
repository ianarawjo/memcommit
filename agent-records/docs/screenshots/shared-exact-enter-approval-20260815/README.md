# Shared exact-command `Enter` approval capture log

This ordered set records the actual blank and named Ground TUI paths and the
standalone Import final review after exact-command approval adopted the shared
`Enter` gesture.  It also records the safety boundary: `Enter` on a different
read-only Ground pane does not apply the frozen command; the visible Chat
receipt must own focus.  Case-insensitive `A` remains a compatibility alias but
is deliberately not used by this replay.

## Reproduction frame

- Command: deterministic adapters around the real `run_ground_shell` and
  `run_named_ground_shell` applications
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- PTY: `180` columns × `52` rows, fixed by `pexpect` before launch
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Provider: local deterministic proposal fixture; no endpoint connection
- Durable scope: process-local Ground values only; no Profile, Context,
  checkpoint, or repository data is changed
- Renderer: the cumulative color PTY stream is replayed with `pyte` and saved
  as full-size PNG, plain text, and raw `.typescript` evidence

The capture command was:

```bash
python agent-records/docs/screenshots/shared-exact-enter-approval-20260815/capture.py
```

## Ordered interaction

| Image | Exact input since preceding image | Visible state | Mutation |
| --- | --- | --- | --- |
| `01-blank-entry.png` | Launch blank Ground | Unsaved five-pane Ground entry with Chat composer focused | None |
| `02-blank-exact-review.png` | Type request, `Enter` | Frozen creation argv and effects; Chat advertises `Enter apply` | None |
| `03-blank-other-pane-enter-no-op.png` | `Tab`, `Enter` | Another pane owns focus; the same receipt remains pending | None |
| `04-blank-success-verification.png` | `Shift-Tab`, `Enter` | Adapter receipt and exact-once read-only verification | One process-local apply callback |
| `05-named-entry.png` | Launch named Ground | Existing revision-zero Ground with Chat composer focused | None |
| `06-named-exact-review.png` | Type request, `Enter` | Frozen Rule proposal argv and effects; Chat advertises `Enter apply` | None |
| `07-named-other-pane-enter-no-op.png` | `Tab`, `Enter` | Another pane owns focus; the exact proposal is still pending | None |
| `08-named-success.png` | `Shift-Tab`, `Enter` | Named Ground reports the applied command and refreshed revision | One process-local typed session revision |
| `09-named-read-only-verification.png` | `Ctrl-C` | Exit receipt confirms one apply and revision `1` | None after apply |
| `10-import-exact-review.png` | Launch standalone Import review | Frozen Import argv and effects; footer advertises canonical `Enter` and compatibility `A` | None |
| `11-import-approval-verification.png` | `Enter` | Review returns approval exactly once; the capture intentionally does not invoke the operation-owned import callback | None |
