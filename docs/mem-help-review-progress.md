# Mem Help review progress

Updated: 2026-08-15

This is the compact session ledger for the 58 public operations. The reviewed
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
| Contexts | — | — | status, pwd, contexts, list, show, switch, checkout, init, branch, import, embed |
| Memories | — | — | add, reference, edit, chunk, forget, delete, clear |
| Search & Explain | — | — | find, query, summarize, trace, rationale, find-duplicates, find-ambiguities, find-conflicts |
| Analyze & Transform | compare, meld, update, distill, elaborate, merge | — | audit, atomize, impact, review, sever, translate |
| History & Recovery | — | — | log, diff, checkpoint, undo, redo, revert |
| Ground & Evaluation | — | — | ground, fit, check-conformance, init-study, eval |
| Profile & Sharing | — | — | profile, rename, share, lock, unlock |
| System | — | — | help, provider, shell-init, config |

## Global Help UI

| Contract | Status |
|---|---|
| BY KIND and A–Z share the same operation copy | Reviewed |
| Wide view uses equal summary/use-case columns | Reviewed |
| Compact view stacks the use case below the summary | Reviewed |
| `USE WHEN:` aligns with the summary body; only the label is bold; wrapped use-case text aligns after the label | Reviewed |
| Representative actual-color PTY evidence at `180×52` and `100×30` | Reviewed for Meld, Merge, Distill, and Elaborate |

## Next review

Select the next operation from the remaining Analyze & Transform set. If a
review stops mid-operation, keep it In progress and name the missing surface in
a short note here.

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
