# Complete compact semantic Rule rows · 2026-08-20

This ordered set records Distill and Goal-to-Rules Elaborate after their
proposal catalogs adopted the content-first `[N] CONTENT — METADATA` grammar.
The deterministic providers deliberately return a Rule whose safety
qualification appears at its end. Every capture retains that ending instead
of replacing it with an ellipsis. `PROPOSED RULES` is the only default result
catalog: the same generated Memory is not repeated in an `IMPACT`/`[ADD]`
ledger underneath it.

## Reproduction frame

- Working directory: `/Users/KimMunyeong/Github/memcommit`
- PTY: `180` columns × `52` rows, verified inside each child process
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, 24-bit color,
  `NO_COLOR` unset
- Store: one disposable isolated store per operation
- Profile/current Context: the empty Target is current; Source and Target are
  also supplied explicitly
- Provider: deterministic local provider; no network request
- Renderer: cumulative ANSI PTY bytes replayed through `pyte`; every PNG has
  matching `.typescript` and `.txt` evidence

Reproduce with:

```bash
python agent-records/screenshots/semantic-rule-rows-20260820/capture.py
```

## Ordered interaction

| Image | Exact command / preceding input | Visible boundary | Durable mutation |
|---|---|---|---|
| `01-distill-impact-entry.png` | `mem impact distill --from capture/distill-source --to capture/distill-target` | Exact Source and existing Target are frozen before inference | None |
| `02-distill-complete-rule-row.png` | Provider returns one long evidence-bound Rule | One logical `[1] … — SUPPORT 1 · BOUNDARY 1` row; the final text remains present and no duplicate `IMPACT`/`[ADD]` block follows | None |
| `03-distill-rule-detail.png` | `Tab`, `Down`, `Enter` | Full rationale plus exact SUPPORT/BOUNDARY UID prefixes remain available in detail | None |
| `04-distill-close-verification.png` | `Q` | Both endpoint digests are unchanged; Target has zero checkpoints; complete Rule tail is reasserted | None |
| `05-elaborate-impact-entry.png` | `mem impact elaborate --from capture/elaborate-source --to capture/elaborate-target --as goal` | The single direct Source Memory is explicitly interpreted as a Goal | None |
| `06-elaborate-complete-rule-row.png` | Provider returns one long unverified Rule | `PROPOSED RULES` contains one logical `[1] … — SUGGESTED · UNVERIFIED` row; no duplicate `IMPACT`/`[ADD]` block follows | None |
| `07-elaborate-rule-detail.png` | `Tab`, `Down`, `Enter` | The unverified rationale remains available under `WHY THIS NEEDS REVIEW` | None |
| `08-elaborate-close-verification.png` | `Q` | Both endpoint digests are unchanged; Target has zero checkpoints; complete Rule tail is reasserted | None |

Physical line wrapping in the PNG is viewport behavior. The `.txt` capture and
typed tests prove that each Rule remains one complete logical row with no
content-limit or ellipsis transformation.
