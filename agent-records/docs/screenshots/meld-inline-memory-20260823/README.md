# Inline-Memory Meld terminal trace

This ordered 180×52 color-PTY set records the new one-Memory directional
intake without creating a temporary Context. It covers the natural positional
sentence, the configured Provider wait, the reversible local TTY success path,
an independently prepared exact review, provider-free `--accept`, and a fresh
read-only reload.

## Reproduction frame

- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Command: `mem meld --from 'all greetings need "."; keep "" and ! literal. ' --to capture/greeting-policy`
- Current Context and local BASELINE/Target: `capture/greeting-policy`
- Initial Target Memory: `Keep the existing greeting policy.`
- Provider: deterministic `InlineMemoryProvider`, delayed only for the wait capture
- PTY: `180` columns × `52` rows, verified in every child
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`, true-color prompt-toolkit depth, and `NO_COLOR` removed in every child; the interactive images 06–08 contain verified true-color foreground and background styles, while the line-oriented receipts 01–05 retain their ANSI-free text-equivalent output
- Renderer: actual cumulative PTY bytes replayed through `pyte`; each PNG has matching `.typescript` and `.txt` evidence
- Profile: none; all stores are isolated temporary stores deleted after capture

## Ordered interaction

| Image | Preceding input | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-inline-input-provider-pending` | launch the quoted `--from SENTENCE --to BASELINE` form | exact punctuation-bearing argv, verified 180×52 PTY, explicit BASELINE/Target, and real Meld Provider wait | fixture Context only |
| `02-tty-success-receipt` | Provider completes with no unresolved semantic decision | local Undo-backed policy applies the reviewed edit; schema 9 is saved, one checkpoint exists, retained text includes `"."`, `""`, `!`, and trailing space, and `INLINE MEMORY CONTEXT EXISTS · False` | exact Target edit |
| `03-exact-ready-review` | prepare the same input in a separate store without TTY auto-application | complete ready relation/proposal plus exact shell-safe `mem meld --memory ... --into ... --accept` gate; zero checkpoints and no temporary Context | saved review session only |
| `04-exact-accept-receipt` | execute the displayed `--accept` command | Provider calls remain zero, session is `APPLIED`, one checkpoint exists, and the exact input is both Target content and retained source evidence | exact Target edit |
| `05-read-only-result-verification` | reopen the store and reload the local Target | applied schema-9 session, exact punctuation/trailing-space representation, one Context name only, and no Provider call | none |
| `06-unresolved-session-entry` | alternate branch: open a saved inline-Memory session whose relation still needs a required decision | real true-color compact decision surface shows the required scoped issue, both supported choices, blank optional note, and `SUBMIT SELECTED · 0/1` | saved review session only |
| `07-unresolved-issue-detail` | `Tab`, `Down`, `Enter` | `Preserve scoped exceptions` is visibly checked and the exact `APPLY ALL · 1/1 READY` action becomes available | process-local selection only |
| `08-unresolved-review-close-verification` | `Q` | session remains `AWAITING_REPLY`, Target bytes are unchanged, no temporary Context exists, and opening the view called no Provider | none |

The TTY path has no unanswered choice or ambiguity, so the established local
Undo policy auto-accepts after the bounded report instead of fabricating a
selection screen. The separate images 03–04 preserve the explicit reviewed
command boundary for scripted or non-TTY use.

Reproduce from the repository root with:

```sh
python agent-records/docs/screenshots/meld-inline-memory-20260823/capture.py
```
