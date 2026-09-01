# Makemore automatic Distill pipeline terminal captures

This ordered set records the read-only `mem impact makemore` path when no
explicit Goal or Rules are supplied. The current Context is Distilled into
transient evidence-linked Rules, those Rules feed the unchanged
Rules-to-Cases Makemore contract, and the viewer exposes both stages without
publishing a Memory or checkpoint.

## Capture environment

- Command: `python agent-records/docs/screenshots/makemore-auto-distill-20260831/capture.py`
- Exact operation command: `mem impact makemore --number 3`
- PTY: `180` columns × `52` rows, verified inside the child process
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`, prompt-toolkit 24-bit
  depth, and `NO_COLOR` removed
- Profile: isolated temporary Store; no external profile or provider
- Current Source and Target: `capture/makemore-auto`
- Initial direct Memories, in order: `reviewed`, `keep current`, `concurrent`,
  `reviewed`
- Provider: deterministic in-process provider; one Distill session followed by
  one Makemore session
- ANSI check: the combined raw `.typescript` streams contain true-color
  foreground or background sequences

Each PNG is rendered from its corresponding real color-preserving PTY byte
stream. The `.txt` file preserves the final `180×52` text canvas and the
`.typescript` file preserves the raw ANSI and cursor-control bytes.

## Ordered interaction log

| Image | Exact preceding input | Visible state | Durable mutation |
|---|---|---|---|
| `01-distilling-source-rules.png` | Launch `mem impact makemore --number 3` | Stage 1 is visibly Distilling the exact current Source | None |
| `02-generating-cases.png` | Distill returns two evidence-linked Rules | Stage 2 is visibly generating exactly three Cases from those Rules | None |
| `03-impact-entry-transient-rules.png` | Makemore returns the complete Case set | Initial read-only Impact report shows Context→Rules→Cases direction, Source/Rule/proposal counts, and transient Rule evidence | None |
| `04-proposed-cases-focused.png` | `Tab` | Focus moves from the complete Viewer to the proposed Case catalog without changing staged content | None |
| `05-first-case-detail.png` | `Down`, then `Enter` | The first proposed Case opens with its complete Rule coverage and expected outcome | None |
| `06-read-only-verification.png` | `q` | After closing Impact, verification shows four unchanged Memories, unchanged digest, zero checkpoints, and provider order `distill_context → makemore` | None |
