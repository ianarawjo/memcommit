# Semantic overview label capture log

This ordered set records the presentation-only boundary introduced by the
semantic overview wording audit. It uses the production typed Summarize,
Distill, Elaborate, and Resolution renderers with deterministic typed values.
No provider, Store, Profile, Context, Grant, session, or checkpoint is opened.

## Reproduction frame

- Command: `python agent-records/screenshots/semantic-overview-labels-20260822/capture.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- PTY: `180` columns × `52` rows, set before launch and verified by every child
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`,
  `PROMPT_TOOLKIT_COLOR_DEPTH=DEPTH_24_BIT`, and `NO_COLOR` unset
- Profile/current Context: not consulted
- Mutation: none in every step
- Provenance: real prompt-toolkit applications and production renderer code;
  operation data is deterministic typed capture data
- Evidence: each PNG has its color-preserving `.typescript` stream and a
  replayed `.txt` terminal canvas

## Ordered interaction

Each case starts its own production Viewer at the report result, is captured,
and then receives `q` to close. Setup, semantic execution, and Apply are outside
this presentation-only change and are deliberately not simulated.

| Image | Exact child route | Visible state | Input after capture | Durable mutation |
| --- | --- | --- | --- | --- |
| `01-summarize-single-artifact.png` | `capture.py --child-case summary-single` | One Summary body directly below title/status; no nested comprehension heading | `q` | None |
| `02-summarize-both-scopes.png` | `capture.py --child-case summary-both` | Independently labelled current and descendant Summary bodies | `q` | None |
| `03-distill-source-overview.png` | `capture.py --child-case distill` | `SOURCE OVERVIEW` followed by exact proposed Rule | `q` | None |
| `04-elaborate-proposal-overview.png` | `capture.py --child-case elaborate` | `PROPOSAL OVERVIEW` followed by suggested Rule | `q` | None |
| `05-audit-owned-sections.png` | `capture.py --child-case audit` | Audit Summary, Checks, Source, Provenance, and Boundary as peer sections | `q` | None |
| `06-find-owned-sections.png` | `capture.py --child-case find` | Scope, Findings, and Boundary as peer sections | `q` | None |
| `07-update-plan.png` | `capture.py --child-case update` | Update `PLAN` without a comprehension wrapper | `q` | None |
| `08-resolve-plan-verification.png` | `capture.py --child-case resolve` | Issue, Automatic Plan, and Fit Verification as peer sections | `q` | None |
| `09-forget-assessment.png` | `capture.py --child-case forget` | Forget `ASSESSMENT` as the operation-owned batch overview | `q` | None |
| `10-sever-source-overview.png` | `capture.py --child-case sever` | Sever `SOURCE OVERVIEW` | `q` | None |
| `11-atomize-three-part-overview.png` | `capture.py --child-case atomize` | Legitimate Understood, Changed, and Unresolved review dimensions | `q` | None |
| `12-meld-understood-accounting.png` | `capture.py --child-case meld` | Meld Understood and Accounting as peers, not one nested group | `q` | None |
| `13-review-neutral-overview.png` | `capture.py --child-case review` | Legacy untyped report receives neutral `OVERVIEW` | `q` | None |
| `14-read-only-verification.png` | `capture.py --child-verification RESULTS` | All 13 label surfaces pass; no generic group is present | process exit | None |

The harness asserts the expected operation-owned heading in each replayed
canvas, rejects `WHAT MEM UNDERSTOOD` from all thirteen surfaces, and verifies
that every raw PTY stream contains ANSI styling.
