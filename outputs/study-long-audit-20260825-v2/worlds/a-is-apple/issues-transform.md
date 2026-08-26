# a-is-apple v2 · TRANSFORM phase issues

TRANSFORM completion: **120/120 counted commands** across 24 operations, five
interleaved methods each, continuing directly from the CORE digest with no
reset. There were 86 successful exits and 34 nonzero exits. Twenty-two nonzero
exits were deliberate or documented safety/availability boundaries; twelve
belong to the defects below. All 120 continuity checks passed.

Every destructive round used an explicit Checkpoint before Clear. The round's
Distill, Elaborate, Resolve, Dedup/Dedun, Forget, and Merge trials then ran only
inside that recovery window. All five Reverts restored the exact whole
Context-tree digest recorded immediately after the checkpoint:
`74d63d4b9b73d79428a4578c95dd937496a8977e60c535dfca644246c3d31e46`.
No generated output was accepted through Meld, Sever, or Update, and all five
Ground requests remained unsaved.

## AIA-V2-T-ATOMIZE-WHOLE-01 — Whole-Context Atomize loses the report when final repair stalls

- Expected: a dirty whole Context yields a saved review session containing its
  atomic, composite, uncertain, and unresolved items, as focused Atomize does.
- Actual: both whole-frame controls failed after 43.7s and 61.6s because three
  items remained `UNCERTAIN`/`COMPOSITE`; no analysis was saved. All three
  focused controls completed, including one with two unresolved review items.
- Workaround: Atomize one Memory at a time and aggregate sessions manually.
- Severity/classification: **High · functional reliability / whole frame**.
- Evidence: [whole practice](raw/transform/001-atomize-1.txt),
  [focused control](raw/transform/049-atomize-3.txt),
  [whole source](raw/transform/073-atomize-4.txt), and
  [focused control](raw/transform/097-atomize-5.txt).

## AIA-V2-T-AUDIT-AMBIG-DECODE-01 — Audit inherits the ambiguity decoder failure

- Expected: all configured finders complete over the same frozen snapshot, or
  Audit retains an explicit failed-check section without losing completed work.
- Actual: four Audits failed wholesale with `Codex find_ambiguities returned a
  question for NONE`; no artifact remained for Review. One full four-check
  Audit succeeded as the control.
- Workaround: run component finders separately and retain their outputs.
- Severity/classification: **High · composed provider-contract reliability**.
- Reproduction: **4/5**.
- Evidence: [round 1](raw/transform/002-audit-1.txt),
  [round 2](raw/transform/026-audit-2.txt),
  [round 3](raw/transform/050-audit-3.txt),
  [successful control](raw/transform/074-audit-4.txt), and
  [round 5](raw/transform/098-audit-5.txt).

## AIA-V2-T-CONFORMANCE-COVERAGE-01 — Check Conformance discards incomplete provider coverage

- Expected: every frozen target Memory receives a disposition, or the bounded
  response is repaired into a complete evidence report.
- Actual: the round-4 cross-Context call spent 10.2s and failed because the
  provider did not account for every target Memory. No partial report survived.
- Workaround: retry on smaller exact frames and reconcile the reports manually.
- Severity/classification: **High · functional reliability / coverage**.
- Evidence: [failed call](raw/transform/076-check-conformance-4.txt) and
  [later complete control](raw/transform/100-check-conformance-5.txt).

## AIA-V2-T-DIFF-CURRENT-01 — Checkpoint Diff hides post-checkpoint destructive changes

- Expected: after Checkpoint then Clear, Diff against that checkpoint shows the
  current empty target as removals from the recoverable snapshot.
- Actual: all five exact `diff CHECKPOINT --context CONTEXT` calls rendered
  `THIS CHECKPOINT VS PREVIOUS`, not checkpoint versus current. Rounds 1 and 2
  reported every item kept and zero removed immediately after Clear; later
  rounds compared the checkpoint to older recovery history.
- Workaround: create a second checkpoint after the destructive action merely to
  inspect it, or use separate exact List/Show commands.
- Severity/classification: **High · safety / recovery observability**.
- Reproduction: **5/5** post-Clear Diffs.
- Evidence: [Clear 1](raw/transform/005-clear-1.txt) and
  [Diff 1](raw/transform/007-diff-1.txt),
  [Clear 2](raw/transform/029-clear-2.txt) and
  [Diff 2](raw/transform/031-diff-2.txt), plus
  [Diff 3](raw/transform/055-diff-3.txt),
  [Diff 4](raw/transform/079-diff-4.txt), and
  [Diff 5](raw/transform/103-diff-5.txt).

## AIA-V2-T-FORGET-LOSS-01 — Forget removes a supported alternative and leaves malformed text

- Expected: `remove examples that introduce a word absent from the Source
  evidence` keeps both banana and blueberry because both occur in the frozen
  rule, or leaves the rule unchanged if the criterion is ambiguous.
- Actual: Forget changed `Treat b as unresolved between the alternatives banana
  and blueberry` to `Treat b as unresolved as blueberry`, deleting banana and
  producing awkward, materially different text. Revert recovered it.
- Workaround: compare every Forget receipt to the frozen Source and Revert on
  any unsupported loss.
- Severity/classification: **High · semantic safety / content loss**.
- Evidence: [Source rule](raw/transform/032-distill-2.txt),
  [Forget receipt](raw/transform/037-forget-2.txt),
  [recovery](raw/transform/043-revert-2.txt), and
  [immutable review](raw/transform/044-review-2.txt).

## AIA-V2-T-MELD-NESTED-RESULT-01 — Nested Result placement appears to invalidate Meld's own peer snapshot

- Expected: reject a Result below a peer before provider work, or bind it
  without invalidating the frozen peer graph.
- Actual: three calls used a fresh `practice/aia-meld-rN` Result while
  `practice` was a peer. After 18.7–38.9s they failed with `A source Context
  changed while Compare was analyzing it`. The lane was strictly sequential,
  no other writer touched this Store, and pre/post durable digests matched;
  command-local Result creation is therefore the likely invalidator.
- Workaround: place the fresh Result outside both peer namespaces.
- Severity/classification: **High · topology / self-invalidation**.
- Evidence: [round 1](raw/transform/016-meld-1.txt),
  [round 3](raw/transform/064-meld-3.txt), and
  [round 5](raw/transform/112-meld-5.txt).

## AIA-V2-T-MELD-PEER-01 — Meld loses the session after invalid PEER repair

- Expected: return a valid exhaustive relation set or a stable failure artifact
  bound to the frozen peers.
- Actual: round 2 spent 55.2s, then failed because a repaired `DISTINCT`
  relation still had invalid PEER sides. No session was saved.
- Workaround: preserve the peer snapshots and rerun the whole provider turn.
- Severity/classification: **High · provider relation-schema reliability**.
- Evidence: [round 2](raw/transform/040-meld-2.txt).

## AIA-V2-T-RATIONALE-LIMIT-01 — Rationale loses a complete trace after one length repair

- Expected: return a complete narrative within 40 words or fall back to a
  deterministic trace-based explanation.
- Actual: round 3 failed because the provider still exceeded 40 words after one
  whole-Trace repair. Four controls succeeded, including later longer lineages.
- Workaround: use Trace directly or retry Rationale.
- Severity/classification: **Medium · output-bound reliability**.
- Evidence: [failure](raw/transform/066-rationale-3.txt),
  [round 4 control](raw/transform/090-rationale-4.txt), and
  [round 5 control](raw/transform/114-rationale-5.txt).

## Positive safety and recovery controls

- Checkpoint/Revert restored all five destructive windows exactly; see
  [phase-transform.json](phase-transform.json) `recovery_verification`.
- Ground printed the same stable unsaved frame in all five non-TTY routes and
  created no Ground, Context Memory, or checkpoint.
- Translate created five `UNREVIEWED` views anchored to the original Memory UIDs
  and made no Context changes.
- Resolve stopped at `NEEDS INPUT · NO CHANGE` rather than applying its
  assumption in the one uncertain case.
- Sever rejected live Memory References before inference, and Update rejected
  same/overlapping Context graphs; those 10 safety failures are boundaries, not
  defects in this ledger.

Machine-readable issues are in [issues-transform.json](issues-transform.json).
