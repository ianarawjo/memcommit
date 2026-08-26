# task-2 CORE audit findings

The CORE phase completed 105 counted `mem` invocations: 21 operations, five
materially distinct attempts each, all through the pinned `task-2` launcher and
one cumulative Store. There were 103 successful exits, one expected QUERY-only
Embed authorization rejection, one safe semantic-authority boundary failure,
and no provider infrastructure failures.

## T2V2-CONTEXTS-01 — Whole-Profile Context inventory obscures the active world

- Expected: Narrow Context discovery to the task-2 owned and granted subtree
  while retaining access annotations.
- Actual: All five invocations printed 112 non-empty lines spanning every Study
  world. The task-2 slice had to be found manually each time.
- Workaround: Search the output for the `task-2` prefix, then use explicit
  Context operands.
- Severity: Medium.
- Classification: Usability / information overload.
- Evidence: `core:contexts:1` through `core:contexts:5`.

## T2V2-RECURSIVE-VOLUME-01 — Recursive reads bury the synthesis target

- Expected: Recursive views reveal source balance and the next useful synthesis
  action without requiring a full-corpus reread.
- Actual: Recursive List produced 696 non-empty lines; recursive Show produced
  527 lines and traversed 37 Contexts and 301 Memories after live Embeds.
- Workaround: After one completeness check, use exact category reads, pairwise
  Compare, and targeted Find/Search.
- Severity: Medium.
- Classification: Usability / information overload.
- Evidence: `core:list:4`, `core:show:4`.

## T2V2-CHUNK-UIDS-01 — Chunk receipts omit created Memory UIDs

- Expected: The mutating receipt identifies every created Memory so later Edit,
  Move, Reference, and review operations can consume the result directly.
- Actual: All five receipts reported only the number added and clipped previews;
  none mapped the removed UID to the new UIDs.
- Workaround: Run a scoped List/Show/Find and recover each UID from its content
  and order.
- Severity: Medium.
- Classification: Workflow / provenance handoff.
- Evidence: `core:chunk:1` through `core:chunk:5`.

## T2V2-CHUNK-SEMANTICS-01 — Chunk creates dependent policy fragments

- Expected: Stored chunks remain independently actionable policies or retain a
  typed relationship understood by downstream quality checks.
- Actual: Compound policies became headings, conditions, and continuations such
  as `Final neutral policy:` and `Recruitment reconciliation:`. Ambiguity was
  0 through 15 Memories, but the final check flagged 11 of 19, primarily the
  Chunk-created fragments.
- Workaround: Keep conditional policies whole or immediately reconstruct every
  dependent fragment. Missing created UIDs make recovery manual.
- Severity: High.
- Classification: Semantic safety / workflow.
- Evidence: `core:chunk:1` through `core:chunk:5`,
  `core:find-ambiguities:5`.

## T2V2-SEARCH-DRIFT-01 — Search fallback broadens the ethics question

- Expected: Preserve the requested duplicate/conditional/conflict
  classification, or clearly stop before substituting a different task.
- Actual: Attempt 4 visibly broadened the query to `ethics policies for user
  studies` and returned `RELATED` items. The label was honest, but the results
  did not answer the requested classification.
- Workaround: Treat `RELATED` as a suggestion only; use exact Show/Compare/Query
  on both ethics categories.
- Severity: Medium.
- Classification: Semantic retrieval / usability.
- Evidence: `core:search:4`, with `core:compare:4` and `core:query:4` as the
  successful recovery path.

## Positive safety and regression evidence

- Query attempts 1–5 cited only the two explicitly requested advisor category
  frames. The prior wrong-source Query behavior did not reproduce.
- QUERY-only `proposal-submission-guidelines` was rejected before Embed mutation.
- Recursive Summarize refused to disclose a granted live Embed through its local
  owner and explained that the grant must be selected through an
  operation-aware authority route. No partial Summary was published.
- Pairwise Fit returned `NO` for the real budget-placement and recruitment-count
  incompatibilities, and `YES` for style, ethics, and evaluation where the
  policies can coexist conditionally.
- Exact duplicate discovery went from zero groups to one deliberate group and
  remained stable as unrelated synthesis accumulated.

# task-2 TRANSFORM audit findings

The TRANSFORM phase completed 120 more counted invocations: 24 operations,
five materially distinct attempts each, through the same pinned launcher and
cumulative Store. There were 88 successful exits, 32 safe nonzero exits, no
provider-infrastructure failures, no Store reset, and no external Share or
unsupported Apply. The raw files retain world order 106–225; the ledger uses
the verifier-required phase-local sequence 1–120.

## T2V2-MELD-PREWARM-SCOPE-01 — Explicit Meld inspects an unrelated Embed

- Expected: A direct symmetric Meld evaluates only its two explicit advisor
  peers and fresh Result, then stops at equal-authority decision gates.
- Actual: All five advisor-pair Melds failed because `task-2/description`
  contains an unrelated `advisor1/budget` Embed, even when neither that Context
  nor description was an endpoint.
- Workaround: Use explicit pairwise Compare/Query evidence and leave the
  synthesis unapplied; removing the Embed would mutate the study fixture.
- Severity: High.
- Classification: Semantic operation / authority scope.
- Evidence: `transform:meld:1` through `transform:meld:5`.

## T2V2-RATIONALE-LANGUAGE-01 — Rationale silently switches to Chinese

- Expected: Preserve the command/session language unless translation is
  requested.
- Actual: Attempt 3 rendered the English Memory normally but synthesized its
  entire 80-character provenance sentence in Chinese.
- Workaround: Use Trace JSON for retained evidence and ignore the synthesized
  prose.
- Severity: Medium.
- Classification: Semantic presentation / language drift.
- Evidence: `transform:rationale:3`.

## T2V2-UPDATE-TRACE-METADATA-01 — Trace cannot correlate an applied Update

- Expected: An applied cross-Context Update writes valid command-unit metadata
  so Trace can correlate its Memory changes and recovery point.
- Actual: Update attempt 1 applied one addition and created checkpoint
  `e8f7aaa4`, but Trace attempts 3 and 5 warned that this checkpoint has invalid
  Update command-unit metadata and its changes cannot be correlated across
  Contexts.
- Workaround: Correlate Update receipt `f451a277` and checkpoint `e8f7aaa4`
  manually; do not treat the later Trace as complete cross-Context lineage.
- Severity: High.
- Classification: Provenance / command-unit metadata.
- Evidence: `transform:update:1`, `transform:trace:3`,
  `transform:trace:5`.

## T2V2-HARNESS-CHECKPOINT-SELECTOR-01 — Harness missed short checkpoint IDs

- Expected: Carry each successful checkpoint selector into the later Diff and
  Revert commands.
- Actual: Checkpoint printed accepted eight-character selectors in brackets,
  but the study harness looked only for a full UID in a recovery command. It
  sent `00000000` to five Diffs and four intended Reverts; all failed safely.
- Workaround: Parse the bracketed selector. The five recovery checkpoints still
  exist in the isolated Store.
- Severity: Medium.
- Classification: Study instrumentation / not a product defect.
- Evidence: `transform:diff:1` through `transform:diff:5`, and
  `transform:revert:2` through `transform:revert:5`.

## TRANSFORM safety and decision-gate evidence

- Five checkpoints were created before scratch mutation. Delete and Clear
  stayed inside `task-2/participant/proposal-workspace`; round-1 Dedup removed
  only the deliberately seeded exact duplicate in `task-2`.
- Granted-source Distill and live-reference Sever routes rejected unsupported
  retained/derived work before provider disclosure or Result creation.
- Ground printed five unsaved frames and created no Ground, Context, Memory, or
  checkpoint. Impact remained read-only. Review reopened exact saved Audits
  provider-free.
- Resolve never required an ambiguous choice; Meld and Sever created no Result
  because their safety boundaries stopped execution. No equal-authority tie was
  chosen for the person.
- Rationale's over-limit complete narrative was rejected rather than silently
  truncated. One invalid Atomize selector grammar and one missing Delete target
  also failed before mutation.

# task-2 ADMIN audit findings

ADMIN completed 105 counted invocations: 21 operations, five materially
distinct attempts each, through the same pinned launcher and cumulative Store.
There were 70 successful exits and 35 safe nonzero exits, including eight
actual fail-closed Undo/Redo negative controls. All 105 post-call Profile/Store
identity reads matched. Share delivery and init-study success both stayed zero;
there was no Store reset, replay, supplemental call, or deletion-based repair.

## T2V2-BRANCH-NESTED-HISTORY-01 — Rename leaves Branch membership stale

- Expected: Rename preserves recoverable Branch history, and a later recursive
  Branch produces an exact command unit whose UID and complete member set can
  be host-verified before Undo.
- Actual: Rename M1 changed Branch1's owner from `b1` to `renamed-1` without
  rebasing its retained Branch creation membership. Branch M2 copied that
  invalid history into its seven-Context subtree. The counted inverse Rename
  M2 restored the original Branch1 UID/name, but the cloned checkpoint still
  belonged to UID `5f68e09b...` at `b2-tree/.../renamed-1` while its retained
  membership named UID `a111c808...` at `b1`. `build_command_stacks()` still
  failed with `Branch checkpoint owner is outside its creation membership.`
  All eight remaining counted Undo/Redo attempts reproduced that error before
  Context mutation; every complete scratch Context-tree/state digest was
  unchanged.
- Workaround: There is no safe in-phase recovery. Preserve this malformed
  history for diagnosis and avoid recursive Branch over renamed Branch history
  until Rename rebases recovery metadata or Branch rejects/isolates it before
  mutation.
- Severity: Critical.
- Classification: Recovery safety / Branch command history.
- Evidence: `admin:rename:1`, `admin:branch:2`, `admin:rename:2`,
  `admin:undo:2-5`, `admin:redo:2-5`, the eight fail-closed host reads, the
  final sequence-105 builder read, and `admin-stack-blocker.json`.

## T2V2-IMPORT-CONTEXT-UID-COLLISION-01 — Import blocks later Rename

- Expected: A successful Context Import into a new local name leaves a
  consistent identity graph that later world-local Rename can update, or it
  rejects the collision before mutation.
- Actual: Import M1 stored `advisor1/style` as `import-direct` with source UID
  `a759f597...`, while the active Profile already had a granted Context
  reference with that UID and source name `task-2/advisor1/style`. Rename M3
  then failed with `Context reference identity and stored target name
  disagree`. Rename M5's planned cancel target consequently did not exist, so
  its confirmation prompt was never reached.
- Workaround: Do not rename a Context imported under a new name when the active
  Profile already contains a reference with the source UID. Inspect the
  UID/name graph first and keep the imported Context at its initial name.
- Severity: High.
- Classification: Import / reference identity integrity.
- Evidence: `admin:import:1`, `admin:rename:3`, `admin:rename:5`, and
  `admin-host:imported-context-uid-reference-collision-host-read`.

## ADMIN safety and continuity evidence

- The protocol adjacency is preserved: `switch --previous` was phase sequence
  21 and `switch --next` was sequence 22, with no intervening `mem` call.
- Every counted command used the pinned `run_world_mem.py task-2` launcher.
  Raw world evidence spans 226–330, following unchanged CORE/TRANSFORM evidence
  1–225; the ADMIN ledger itself uses phase-local sequence 1–105.
- All five Share routes failed before delivery and left the Context-tree digest
  unchanged. All five init-study routes failed validation; M5 used the
  slash-invalid name `admin/v2/task-2/again`, returned `Study Profile name is
  invalid`, and left its registry digest unchanged.
- Eval wrote only under the task-2 lane-local admin ledger. The exact full M2
  run ID was host-read and consumed by M3 check. Shell output was byte-compared,
  syntax-checked, and sourced only in disposable shells.
- The malformed command history remains intentionally preserved as the final
  negative control. No product code, checkpoint metadata, Context JSON, or
  copied record was edited by the audit harness.
