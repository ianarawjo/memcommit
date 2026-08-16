# Mem Help review progress

Updated: 2026-08-16

This is the compact session ledger for the 62 public operations. The reviewed
English and Korean copy remains in
[`mem-help-content-review-20260815.md`](mem-help-content-review-20260815.md);
this file records only what has and has not completed the Help review.

An operation moves to **Reviewed** after its summary, `USE WHEN`, expanded
Flow/Execution/Effect/Range contract, meaningful CLI forms and examples, and
wide/compact rendering have been checked together. **In progress** means that
some of those surfaces were discussed or changed but the complete gate has not
closed.

| Category | Reviewed | In progress | Pending |
|---|---|---|---|
| Browse & Navigate | status | — | pwd, contexts, list, show, switch, checkout |
| Create, Copy & Connect | — | init, branch, import | add, reference, embed |
| Search & Explain | — | find, search, query, summarize | — |
| Deterministic Content Changes | merge | — | edit, chunk, delete, clear, dedup |
| Semantic Transformations | meld, update, distill, elaborate | — | atomize, translate, forget, resolve, sever |
| Check, Compare & Review | compare | — | find-duplicates, find-ambiguities, find-conflicts, audit, impact, review, fit, check-conformance |
| Ground Workbench | — | — | ground |
| History & Recovery | — | — | log, diff, trace, rationale, checkpoint, undo, redo, revert |
| Profiles | — | — | profile, rename |
| Sharing & Protection | — | — | share, lock, unlock |
| System & Study Tools | — | — | help, provider, shell-init, config, init-study, eval |

## Global Help UI

| Contract | Status |
|---|---|
| BY KIND and A–Z share the same operation copy | Reviewed |
| Every BY KIND box explains intent; execution-pure groups identify LLM use | Reviewed |
| Wide view uses equal summary/use-case columns | Reviewed |
| Compact view stacks the use case below the summary | Reviewed |
| `USE WHEN:` aligns with the summary body; only the label is bold; wrapped use-case text aligns after the label | Reviewed |
| Representative actual-color PTY evidence at `180×52` and `100×30` | Reviewed for Meld, Merge, Distill, Elaborate, and the Import/Query typed-detail presentation |

`replace` is now a public operation under Deterministic Content Changes; its
operation review is tracked with that category even though the implementation
was completed in a separate change series.

## Next review

Select the next operation from the pending rows above. If a review stops
mid-operation, keep it In progress and name the missing surface in a short note
here.

- `distill` semantic direction is now enforced in code: it derives Rules
  upward from Case/example propositions stored as Context Memories, while an
  optional Goal only focuses relevance. Every Rule requires Source support and
  an empty Source fails before provider connection.
- `distill` Summary is reviewed as: “Derive reusable Rules from Case or
  Example propositions in a selected Context scope, using an optional Goal to
  focus relevance.” Flow, `USE WHEN`, Forms, behavior, and wide/compact
  real-terminal rendering have now passed together.
- The top-down Goal-to-Rule / Rule-to-Case proposal operation is implemented as
  `elaborate`. Its typed behavior, Forms, and wide/compact rendering are
  verified. Its reviewed wording distinguishes candidate Rules from concrete
  Case propositions, avoids implying that the operation itself refines Rules,
  and presents the two use cases as starter Rule candidates or additional Cases
  for review. Suggested and unverified status remains in the Effect contract.
- `merge` is reviewed as the deterministic counterpart to semantic `meld`.
  Its Summary states the Source-only addition and Source/Target choice behavior,
  while its `USE WHEN` stays scenario-based rather than asking the user to
  understand stored-identity mechanics before choosing the operation.
- `status` is reviewed against its rebuilt typed behavior: inventory,
  first-five direct-Memory preview, conditional relationships, and latest-five
  checkpoint summaries. Summary, `USE WHEN`, expanded contracts, four command
  forms, and actual-color `180×52` and `100×30` rendering are verified.
- `init` and `branch` have reviewed initial wording and expanded contracts but
  still need their complete wide/compact operation gate before moving out of
  In progress.
- `import` preserves its ordinary Summary and `USE WHEN`, adds a collapsed
  `PARTIAL` maturity tag, and owns an expanded typed `CURRENT LIMITATION`
  detail for the current MemCommit-to-MemCommit boundary. The maturity tag is
  not an operation-route classification.
- `find`, `search`, `query`, and `summarize` now distinguish provider-free exact
  text lookup from LLM-based semantic retrieval, answering, and summarization.
  Query additionally owns a typed `QUERY-ONLY ACCESS` detail. Their shared
  collapsed layout and Query's expanded boundary now have wide/compact visual
  evidence; operation-specific forms and end-to-end behavior review remain
  before all four rows can be marked Reviewed.
