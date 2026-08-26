# Distill/Elaborate generative reduction · 2026-08-20

This ordered set records live configured-provider runs of the café calibration
fixture through the actual process-local `mem impact distill` and
`mem impact elaborate` routes. The disposable Store contains the full three
Example Memories or seven Rule Memories; the active Profile is not mutated.

## Reproduction frame

- Working directory: `/Users/KimMunyeong/Github/memcommit`
- PTY: `180` columns × `52` rows
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, 24-bit color,
  `NO_COLOR` unset
- Store: one isolated temporary Store per operation; Target current; endpoints
  explicit; Elaborate Target starts with one reviewed café Example as ambient
  destination context
- Provider: the configured live semantic provider, not a deterministic stub
- Input: `memcommit/eval/fixtures/distill_elaborate.json`
- Elaborate count: no `--number` flag; provider contract version 7 normalizes
  the omitted value to exactly three proposals
- Prompt reference: every call quotes the complete café, lost-property, and
  Cloze Rule/Example families from the same fixture
- Renderer: cumulative ANSI PTY bytes replayed through `pyte`; every PNG has a
  matching `.typescript` and `.txt`

Reproduce with:

```bash
python agent-records/screenshots/distill-elaborate-generative-reduction-20260820/capture.py
```

## Ordered interaction

| Image | Exact command / preceding input | Visible boundary | Durable mutation |
|---|---|---|---|
| `01-distill-live-result.png` | `mem impact distill --from calibration/cafe/examples --to calibration/cafe/distilled-rules --direct` | Three complete Examples produce evidence-bound proposed Rules | None |
| `02-distill-read-only-verification.png` | `Q` | Source and Target digests remain unchanged; Target has no checkpoint | None |
| `03-elaborate-live-result.png` | `mem impact elaborate --from calibration/cafe/rules --to calibration/cafe/generated-examples --as rules` | The omitted number defaults to exactly three suggested, unverified Examples in one compact proposal catalog; the header retains the Target ambient count while the repeated ambient body and `[ADD]` ledger stay off the default canvas | None |
| `04-elaborate-first-proposal-detail.png` | `Tab`, Down Arrow, `Enter` on the first proposed Case | One compact `RULE COVERAGE · ALL 7` boundary retains the expected result and exact Target alias without replaying seven provider-authored check explanations | None |
| `05-elaborate-read-only-verification.png` | `Q` | Seven Source Rules and one pre-existing Target Example remain unchanged; Target has no checkpoint | None |

The refreshed capture uses the English café family as the current Source. The
provider wording is not expected to be byte-stable. The contract under test is
structural: Distill may choose a different equivalent Rule decomposition,
while every Elaborate Case must carry one ordered coverage check for every
input Rule before it can be displayed. Elaborate also has to distinguish the
one run-specific Target Example from both current Rule evidence and the fixed
three-family prompt-reference corpus, and report any `target_context_refs` it
materially used. Focused tests separately verify that
all nine reference Examples and all seventeen reference Rules are quoted in
the actual Distill and both Elaborate prompt directions.

The renderer uses Menlo for terminal geometry and Apple SD Gothic Neo only as a
Hangul fallback. This preserves the real 180-column PTY grid without replacing
Korean text with unsupported-glyph boxes.
