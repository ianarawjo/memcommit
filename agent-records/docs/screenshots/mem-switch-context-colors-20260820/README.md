# `mem switch` Context-category color capture log

This ordered color-PTY record verifies that `mem switch` limits category color
to three typed words: `GRANT` is green, `VIA EMBED` is yellow, and `QUERY ONLY`
is purple. Context names, selector UIDs, paths, capability summaries,
punctuation, and tree chrome remain white. The moving focus bar temporarily
replaces a token color with the shared reverse-focus treatment.

## Reproduction frame

- Command: `mem switch`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- PTY: `180` columns × `52` rows, set and verified before launch
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Profile: disposable `authoring` Profile plus one managed authority Profile
- Current Context: `workspace`
- Direct items: one opaque `QueryContextRef` and one embedded Context
- Public route: one recursive `READ` Grant at `granted/shared-source`
- Durable scope: cancellation only; the complete disposable Profile tree is
  byte-hashed before and after the picker

The capture command was:

```bash
env -u NO_COLOR TERM=xterm-256color COLORTERM=truecolor \
  python agent-records/docs/screenshots/mem-switch-context-colors-20260820/capture.py
```

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-switch-entry-grant-visible.png` | Launch `mem switch` | Current ordinary `workspace` row plus green `GRANT`; its public name and `READ` capability remain white | None |
| `02-three-context-colors-visible.png` | `m` | Purple `QUERY ONLY`, yellow `VIA EMBED`, and green `GRANT` are visible together; every sibling value remains white | None |
| `03-reference-context-focused.png` | `Down` | Query-only Context owns the common focus bar; embedded and granted category colors remain visible | None |
| `04-embedded-context-focused.png` | `Down` | Embedded Context owns the common focus bar; reference and granted category colors remain visible | None |
| `05-cancelled-and-verified.png` | `Escape` | Cancellation receipt, unchanged complete-Profile digest/current Context, and `mem show --context workspace` verification | None |

The driver also rejects a capture unless the raw PTY stream contains the exact
`xterm-256color` foregrounds emitted for the requested semantic colors: green
`#a6da95` → palette `150`, yellow `#eed49f` → `223`, and purple `#c6a0f6` →
`183`. `COLORTERM=truecolor` remains set, but prompt-toolkit quantizes this PTY
output; the log records that observed behavior instead of claiming 24-bit ANSI.
