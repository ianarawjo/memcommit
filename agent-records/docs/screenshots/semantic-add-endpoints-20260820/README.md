# Semantic Add endpoints · 2026-08-20

This ordered capture set records Distill and Elaborate's default existing-
Context Add routes and their explicit process-local Impact previews. Each path
uses an isolated store and a deterministic provider so the screenshots are
reproducible.

## Reproduction frame

- Working directory: `/Users/KimMunyeong/Github/memcommit`
- PTY: `180` columns × `52` rows
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, 24-bit color,
  `NO_COLOR` unset
- Profile/current Context: one disposable store per route; the Target is
  current while both `--from` and `--to` are explicit
- Providers: deterministic local providers; no network request
- Renderer: cumulative ANSI PTY bytes replayed through `pyte`; every PNG has a
  matching `.typescript` and `.txt`

Reproduce with:

```bash
python agent-records/docs/screenshots/semantic-add-endpoints-20260820/capture.py
```

## Ordered interaction

| Image | Exact command / preceding input | Visible boundary | Durable mutation |
|---|---|---|---|
| `01-distill-add-entry.png` | `mem distill --from capture/distill-source --to capture/distill-target` | Source and existing Target are frozen before provider inference | None yet |
| `02-distill-add-receipt.png` | Provider returns one evidence-bound Rule | Proposal plus exact Add/checkpoint/Undo receipt | One Rule added atomically |
| `03-distill-add-verification.png` | `V` | Target has one Memory and one Distill checkpoint; distinct Source digest is unchanged | Verification only |
| `04-elaborate-add-entry.png` | `mem elaborate --from capture/elaborate-source --to capture/elaborate-target` | Context Memories are interpreted as Rules by invocation role | None yet |
| `05-elaborate-add-receipt.png` | Provider returns FIT and BOUNDARY Cases | Both unverified proposals plus one Add/checkpoint/Undo receipt | Two Cases added atomically |
| `06-elaborate-add-verification.png` | `V` | Target has two Memories and one Elaborate checkpoint; distinct Source digest is unchanged | Verification only |
| `07-distill-impact-entry.png` | `mem impact distill --from capture/distill-source --to capture/distill-target` | Same preparation begins under explicit Impact | None |
| `08-distill-impact-result.png` | Provider returns one Rule | Existing Target is labelled unchanged; no Apply handoff | None |
| `09-distill-impact-verification.png` | `Q` | Both endpoint digests and Target checkpoint count remain unchanged | None |
| `10-elaborate-impact-entry.png` | `mem impact elaborate --from capture/elaborate-source --to capture/elaborate-target` | Same preparation begins under explicit Impact | None |
| `11-elaborate-impact-result.png` | Provider returns two Cases | Proposals remain suggested/unverified; no Apply handoff | None |
| `12-elaborate-impact-verification.png` | `Q` | Both endpoint digests and Target checkpoint count remain unchanged | None |

## Live ticker-provider verification

A separate isolated-store run used the configured real semantic provider on
the same date. Distill consumed three actual company/ticker observations
(`AAPL`, `MSFT`, and `GOOG`) and added one evidence-linked Rule to an existing
`ticker/rules` Context. Elaborate consumed that Rule and added three unverified
FIT/BOUNDARY/CONTRAST Cases to an existing `ticker/cases` Context. An
`impact elaborate --from ticker/rules --to ticker/cases` run left both endpoint
digests unchanged, and `mem undo` removed exactly the three Elaborate additions
while retaining the Distill Rule.
