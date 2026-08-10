# `mem forget` exact Source Impact capture log

This focused ordered set records the materially changed Forget review boundary.
It complements the existing end-to-end flagless setup capture: unaffected setup,
provider wait, item detail, checkpoint receipt, and read-only command verification
remain documented there, while this set proves that the complete result is now
one navigable, Source-aware diff entry per frozen Memory.

## Reproduction frame

- Command: production `_run_resolution_forget` review path with a deterministic
  complete-coverage provider response
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- PTY: `180` columns × `52` rows, verified inside each child
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Source: disposable in-memory Context `beta` with three fixed-UID direct Memories
- Decisions: one TRANSFORM, one DROP, and one KEEP
- Production path retained: curation provider schema and decoder, `ForgetReview`,
  `forget_memory_changes`, `ImpactController`, shared Resolution shell, and
  `apply_changes`
- Focused-harness boundary: the unrelated provider wait screen and durable store
  checkpoint are intentionally outside this capture; the existing flagless setup
  capture retains those states
- Renderer: actual cumulative ANSI PTY bytes replayed through `pyte`, drawn at
  `1980×1092`; matching `.typescript` and `.txt` evidence is stored with each PNG

Reproduce with:

```bash
python docs/screenshots/mem-forget-source-impact-20260810/capture_forget_source_impact.py
```

## Ordered interaction

| Image | Input since preceding image | Visible state | Mutation |
| --- | --- | --- | --- |
| `01-review-entry.png` | Launch focused review | Complete Forget report shows exact TRANSFORM, DROP, and KEEP Source transitions once | None |
| `02-edit-focused.png` | `Down` × 3 | First Memory owns focus; original and retained result are visible as `-`/`+` | None |
| `03-drop-focused.png` | `Down` | Focus advances one Memory; the exact obsolete-code original is visible as `-` | None |
| `04-keep-focused.png` | `Down` | Focus advances one Memory; the exact retained original is visible as `=` | None |
| `05-decision-detail.png` | `Tab`, `Down`, `Enter` | First decision confirms classification, instruction, exact Source, rationale, and proposed result | None |
| `06-final-review.png` | `A` | Reviewed choices and the explicit no-change-before-Apply boundary are visible | None |
| `07-exact-apply.png` | `End` | Exact Apply action is focused | None |
| `08-apply-verification.png` | `Enter` | In-memory verification shows one provider call, two reviewed changes, edited content retained, and obsolete code absent | In-memory Source updated; no durable store |
| `09-cancel-verification.png` | Separate launch, then `Q` | Review cancellation reports one completed analysis call and byte-semantic Source equality | None |
