# Task-1 transformation/evidence issues

Evidence: `phase-transform.json` contains 24 operations × 5 interleaved attempts = 120 actual frozen-launcher attempts. Destructive mutations were confined to checkpointed `task-1/participant/transform-scratch/...` Contexts.

## Confirmed

### T1-XFORM-UPDATE-PREWARM-INVALID — Critical — 5 reproductions

- Expected: explicit local Source/Target Update and Impact routes should either produce a scoped plan or a task-specific validation error.
- Actual: direct and replacement Update plus direct/recursive Impact repeatedly failed immediately with `Declared Update prewarm is invalid.`
- Workaround: Compare/Merge the explicit frames and preserve a checkpoint; Update/Impact cannot currently drive this task-1 route.

### T1-XFORM-SHARED-SESSION-BLEED — Critical — 3 reproductions

- Expected: task-1 Diff/Update should not consume another parallel world's saved session.
- Actual: `diff --raw` and `diff --verbose` displayed an applied `task-2/participant/transform-scratch/...` Update. A task-1 Update then reported that the shared applied record had diverged.
- Workaround: do not use implicit saved Update state during parallel worlds; serialize session-owning operations or require an explicit session locator.

### T1-XFORM-MERGE-UID-HANDOFF — High — 4 linked observations

- Expected: Merge should map each Source UID to its Target UID so Rationale, Trace, Translate, and exact Atomize can consume the result.
- Actual: Merge reported only aggregate counts. The original `cd518767` failed in all three consumers because copied Memories had new UIDs. The usable `b410d90f` became visible only in Atomize's validation error.
- Workaround: run a separate List/Find after Merge and manually match content to recover Target UIDs.

## Candidates

### T1-XFORM-AUDIT-TUI-OVERLOAD-CANDIDATE — High — 1 TUI path

- Expected: a saved Audit Viewer should lead with prioritized findings and allow compact section navigation.
- Actual: the 180×52 Viewer opened with all 18 snapshot Memories serialized inline before the findings; the action-relevant ambiguity/conflict detail required paging/End navigation. End then Escape were needed to inspect and close.
- Workaround: use `review audit --session ... --snapshot` and external text search, or retain the compact Audit receipt.

### T1-XFORM-MELD-INLINE-AUTOTYPE-CANDIDATE — Medium — 1 attempt

- Expected: the documented unambiguously non-Context sole sentence should be accepted as inline Memory content.
- Actual: `Verified campus-wiki contributions cite their source.` was treated as a Context name and rejected.
- Workaround: add the sentence to a scratch Context first, then Meld Context-to-Context.

### T1-XFORM-DEDUN-PLAIN-GRAMMAR-CANDIDATE — Medium — 1 attempt

- Expected: `--plain` should select line output for ordinary discovery.
- Actual: `dedun ... --direct --plain` said discovery options cannot be combined with an exact-review replay, although no replay evidence was supplied.
- Workaround: omit `--plain`; the same direct route then completed normally.

## Useful recovery behavior

- Checkpoint→Clear→Revert restored scratch result/archive states without touching the contribution workspace.
- Exact Atomize classified one focused Memory as ATOMIC/KEEP and resumed its saved analysis without another provider call; whole-frame uncertainty published no partial change.
- Conformance supported both a local Rules Context and forced `text:` literal rules.
- Sever staged a self-save, Impact exposed its decisions, and exact resume/accept applied 10 KEEP / 0 FORGET safely in scratch.
- Translate reused an exact cached view and refreshed it only when requested; Trace and Rationale preserved Merge provenance once the remapped UID was known.
