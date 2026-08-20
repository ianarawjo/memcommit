# Process-local Impact registry · 2026-08-20

This ordered capture set records the three new registry-backed Impact routes.
Every route enters through the public `mem impact OPERATION` CLI, uses its
operation-owned application/runtime and a deterministic provider, then opens
the shared read-only Resolution/Impact host. The capture child verifies the
live PTY dimensions before execution.

## Reproduction frame

- Working directory: `/Users/KimMunyeong/Github/memcommit`
- PTY: `180` columns × `52` rows
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, 24-bit color,
  `NO_COLOR` unset
- Profile/current Context: one disposable local store per route; the exact
  `capture/impact-OPERATION` Source is also current
- Providers: deterministic local test providers; no network request
- Renderer: cumulative ANSI PTY bytes replayed through `pyte`; every PNG has a
  matching `.typescript` and `.txt`

Reproduce with:

```bash
python docs/screenshots/impact-process-local-registry-20260820/capture.py
```

## Ordered interaction

| Image | Exact command / preceding input | Visible boundary | Durable mutation |
|---|---|---|---|
| `01-forget-analysis.png` | `mem impact forget "Forget the old desk location." --context capture/impact-forget` | Complete Source was frozen before the one Forget provider turn | None |
| `02-forget-impact.png` | Provider returns complete KEEP/DROP coverage | Exact in-place Source diff; no Apply handoff | None |
| `03-forget-verification.png` | `Q` | Source digest and checkpoint count unchanged; Apply handoff absent | None |
| `04-distill-analysis.png` | `mem impact distill capture/impact-distill --save-as capture/impact-distill-result` | Complete Distill Source was frozen before provider inference | None |
| `05-distill-impact.png` | Provider returns one evidence-bound Rule | Proposed Result Memory is visible; Result is labelled `NOT CREATED`; Source unchanged | None |
| `06-distill-verification.png` | `Q` | Source digest/checkpoints unchanged, Result absent, Apply handoff absent | None |
| `07-resolve-analysis.png` | `mem impact resolve --context capture/impact-resolve` | Complete Resolve frame is being judged, generated, and independently verified | None |
| `08-resolve-impact.png` | Provider returns one verified minimum-change candidate | Exact before/after UPDATE in the same Source; no Apply handoff | None |
| `09-resolve-verification.png` | `Q` | Source digest and checkpoint count unchanged; Apply handoff absent | None |

The report entry begins in the complete Viewer, so no synthetic candidate or
Memory selection is required in these one-candidate fixtures. Multiple Resolve
candidates use a separate read-only candidate-set projection and require an
exact `--candidate` on a later invocation before Impact claims one effect set;
that branch is covered by automated tests rather than flattened into this
representative path.
