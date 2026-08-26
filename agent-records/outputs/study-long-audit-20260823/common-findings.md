# Cross-world findings · provisional

This file is updated during collection. Priority is provisional until all six
worlds and all 66 operations reach five attempts.

Integrated coverage: **1,350/1,980 attempts · 270/396 operation-world
units**. All core and transform phases are complete; the serialized admin
phase remains pending.

## CF-01 · Explicit granted Query target is not authoritative

- Provisional priority: **P1**
- Worlds: task-1, task-2, task-3
- Pattern: an ordinary Query names one or more exact readable granted Contexts,
  but the successful route reports or answers from a prior/local participant
  workspace instead. Exact QUERY-only public names also misidentify the target
  in task-3. A success exit therefore cannot prove that the requested source
  grounded the answer.
- User consequence: evidence can appear absent, or an answer can be accepted
  under the wrong source identity. This is especially unsafe in minimum-
  disclosure and equal-authority workflows.
- Current safe workaround: inspect exact `list`/`show`/`find` evidence and every
  Query Reference Context; do not trust the ordinary explicit-grant route.
- Evidence: `T1-GRANTED-ORDINARY-QUERY-MISROUTE`, `T2-QUERY-TARGET-01`,
  `T3-QUERY-TARGETING`.

## CF-02 · Readable EXPORT grants do not form a selective handoff

- Provisional priority: **P1/P2 high**
- Worlds: task-1, task-2, task-3
- Pattern: granted Memories are visible and advertise EXPORT, yet `copy` and
  `reference` reject their qualified UID as not local. Whole-Context `embed`
  may work, but it is not a substitute for selecting the minimum necessary
  Memories or preserving an immutable provenance snapshot.
- User consequence: the discovery-to-contribution path breaks exactly at the
  point where a user tries to preserve provenance or minimize disclosure.
- Current safe workaround: retain read-only views or manually re-add text,
  accepting that manual re-entry loses original provenance.
- Evidence: `T1-GRANTED-EXPORT-HANDOFF`, `T2-GRANT-TRANSFER-01`,
  `T3-GRANT-SELECTIVE-TRANSFER`.

## CF-03 · Chunk output is not a safe reusable handoff

- Provisional priority: **P1 for safety-framing splits; P2 for receipt reuse**
- Worlds: all six
- Pattern: successful mutation receipts give counts but omit created UIDs and
  the original UID's disposition. Clause or size splitting can also separate a
  fact/policy from its condition, non-sharing boundary, or verification rule.
- User consequence: an extra `list`/`find` recovery step is mandatory, and a
  downstream search may surface a fragment whose independent meaning is unsafe
  or false.
- Current safe workaround: immediately enumerate the exact owner and inspect
  all chunks together; avoid clause/size splitting of permission, condition,
  exception, and evidence statements.
- Evidence: `T1-CHUNK-NO-UID-HANDOFF`, `T2-CHUNK-01`, `T2-CHUNK-02`,
  `T3-CHUNK-TRACEABILITY`, `T3-CHUNK-SEMANTICS`,
  `TICK-CHUNK-NO-UID-HANDOFF`, `AIA-CHUNK-01`, `AIA-CHUNK-02`,
  `PS-CHUNK-CONTEXT-LOSS`, `PS-CHUNK-RECEIPT`.

## CF-04 · Whole-Profile discovery repeatedly hides the active world

- Provisional priority: **P2**
- Worlds: all six
- Pattern: `contexts` always prints the complete shared Study Profile and has
  no prefix/world filter. Each world needed about eight terminal screens even
  after exact working names were already known.
- User consequence: early discovery cost becomes repeated rereading in middle
  and late work, and unrelated Grants distract from the actual goal.
- Current safe workaround: external terminal search plus manual extraction of
  canonical names.
- Evidence: `T1-CTX-OVERLOAD`, `T2-CONTEXTS-01`, `T3-CONTEXTS-OVERLOAD`,
  `TICK-CTX-OVERLOAD`, `AIA-CONTEXTS-01`, `PS-CTX-OVERLOAD`.

## CF-05 · Related quality commands do not share a learnable scope grammar

- Provisional priority: **P2**
- Worlds: task-1, task-2, task-3, practice-source
- Pattern: sibling `find-*` operations reject different plausible combinations
  of `--direct`, `--context-only`, `--select`, and `--plain`. The errors do not
  consistently route the user to the accepted equivalent.
- User consequence: goal exploration is interrupted by command-specific help
  lookup and full re-entry before any quality judgment can run.
- Current safe workaround: reopen exact help for every sibling command.
- Evidence: `T1-QUALITY-SCOPE-GRAMMAR`, `T2-QUALITY-FLAGS-01`,
  `T3-OPTION-GRAMMAR`.

## CF-06 · Exhaustive recursive and saved-analysis reports scale as output, not decisions

- Provisional priority: **P2**
- Worlds: all six
- Pattern: recursive `show`, Query References, quality reports, and saved Audit
  viewers fully render very large source snapshots and findings, including many
  empty sections or isolation-driven false positives. One task-3 redundancy run
  took about 176 seconds; task-1 and task-2 Audits buried the next action behind
  18–21 serialized source Memories and complete finding groups.
- User consequence: the next meaningful decision is buried, and users must
  export/capture the report and manually construct a smaller review set.
- Current safe workaround: narrow to exact leaf/category Contexts and chain
  several commands outside the product.
- Evidence: `T1-RECURSIVE-LIST-OVERLOAD`, `T1-QUERY-REFERENCE-OVERLOAD`,
  `T1-QUALITY-REPORT-OVERLOAD`, `T1-XFORM-AUDIT-TUI-OVERLOAD-CANDIDATE`,
  `T2-SHOW-01`, `T2T-AUDIT-OVERLOAD-01`, `T3-RECURSIVE-OVERLOAD`,
  `T3T-AUDIT-CURATION`, `T3T-CONFORMANCE-OVERLOAD`, `T3T-TRACE-LIMIT`,
  `T3T-RESULT-OVERLOAD`, `TICK-XFORM-004`,
  `AIA-T-AUDIT-OVERLOAD-01`, `AIA-T-IMPACT-OVERLOAD-01`,
  `PS-T-TRACE-LIMIT`, `PS-T-REVERT-OVERLOAD`,
  `PS-T-RESULT-OVERLOAD`.

## CF-07 · Current-only orientation conflicts with parallel goal work

- Provisional priority: **P2 workflow limitation**
- Worlds: task-1, task-2, task-3; remaining worlds pending serialized evidence
- Pattern: `status` cannot inspect an explicit canonical Context, so an agent or
  user working on several independent worlds must mutate global current merely
  to read orientation.
- User consequence: otherwise independent work cannot safely execute in
  parallel, and a status check can change or depend on another worker's state.
- Current safe workaround: serialize current ownership and restore it after
  each world's five attempts.
- Evidence: `T1-STATUS-NO-EXPLICIT-TARGET`, `T2-STATUS-01`,
  `T3-STATUS-CURRENT-ONLY`.

## CF-08 · Semantic output can silently change the working language

- Provisional priority: **P2**
- Worlds: task-2, ticker, a-is-apple, practice-source
- Pattern: an English-only direct or recursive source produced a Chinese or
  Korean Summary or Rationale without an explicit language request. Later
  equivalent runs returned English, so the user cannot predict which language
  becomes the reusable output.
- User consequence: review and copy-forward work unexpectedly requires
  translation, and exact downstream wording is no longer stable across runs.
- Current safe workaround: state the desired output language in a separate
  operation when supported and manually reject language-drifted artifacts.
- Evidence: `T2T-RATIONALE-LANGUAGE-01`, `TICK-SUMMARY-LANGUAGE-DRIFT`,
  `AIA-SUMMARY-LANGUAGE-01`, `PS-SUMMARY-LANGUAGE`.

## CF-09 · Cross-Context quality meaning is narrower than recursive presentation

- Provisional priority: **P2 high**
- Worlds: task-1, ticker, practice-source
- Pattern: recursive or multi-Context-looking quality commands still judge
  isolated direct owners, miss duplicates copied across child Contexts, or flag
  a Memory as incomplete despite the needed condition existing in a sibling.
- User consequence: a distributed goal produces both false negatives and false
  positives while the command's broad presentation implies that related
  evidence was considered together.
- Current safe workaround: manually assemble related evidence into one bounded
  Context before analysis, at the cost of extra copies and provenance handling.
- Evidence: `T1-QUALITY-CONTEXT-ISOLATION`,
  `TICK-QUALITY-CROSS-CONTEXT-BLIND`, `PS-QUALITY-SCOPE-MISMATCH`.

## CF-10 · Positive Conformance/Fit/Resolve outcomes are not auditable proof of safety

- Provisional priority: **P1 safety / P2 explainability**
- Worlds: task-3, ticker, practice-source
- Pattern: repeated successful Conformance, Fit, or Resolve receipts state
  `CONFORM`, `YES`, or
  `FIT · YES · NO CHANGE` but expose no evidence mapping or per-Memory
  disposition. In two task-3 corrective trials, explicitly challenged
  unsupported healthcare claims remained unchanged behind that positive form;
  three ticker trials likewise declared visibly incomplete fragments fit.
  Practice-source first declared the unsplit frame conformant to an atomization
  rule, then later accepted an explicitly identified non-constraint meta-rule
  unchanged; narrower evidence contradicted both broad positive forms.
- User consequence: users cannot distinguish a well-supported YES from a broad
  semantic judgment, and can mistake a no-change receipt for proof that unsafe
  content was corrected.
- Current safe workaround: pair Fit with explicit Compare/Query evidence and
  exact post-operation content inspection; keep the user-authored disposition
  separately.
- Evidence: `T3-FIT-OPAQUE`, `PS-FIT-OPAQUE`, `T3T-RESOLVE-UNSUPPORTED`,
  `T3T-RESOLVE-OPAQUE`, `TICK-XFORM-008`,
  `PS-T-CONFORMANCE-FALSE-CONFIDENCE`, `PS-T-RESOLVE-NOCHANGE`.

## CF-11 · Semantic prewarm failures disable otherwise valid goal routes

- Provisional priority: **P1 reliability**
- Worlds: task-1, task-2, task-3; practice-source has related fail-closed
  snapshot/validation failures, not the same confirmed prewarm signature
- Pattern: explicit local frames repeatedly fail before analysis with either
  `Declared Update prewarm is invalid` (Update and Impact) or
  `Declared Compare prewarm is invalid` (Meld). The message names neither the
  rejected frozen input nor the invariant the user could repair.
- User consequence: central transformation operations remain unusable across
  accumulated states, while a generic internal-planning error gives no
  recoverable next action.
- Current safe workaround: preserve checkpoints and use smaller Compare,
  Merge, Distill, or exact-Memory operations; do not treat those substitutes as
  proof that the intended Update/Meld/Impact semantics ran.
- Evidence: `T1-XFORM-UPDATE-PREWARM-INVALID`,
  `T2T-MELD-PREWARM-01`, `T3T-MELD-RELIABILITY`. Related practice-source
  evidence: `PS-T-MELD-SNAPSHOT-RACE`, `PS-T-SEVER-VALIDATION`.

## CF-12 · Implicit saved-operation state bleeds across parallel worlds

- Provisional priority: **P1 correctness and isolation**
- Worlds: task-1→task-2 and ticker→task-3 confirmed; a-is-apple has a related
  stage-divergence symptom but no independently identified foreign-world payload
- Pattern: a world's Diff displayed an applied Update from another concurrently
  accumulated world, and its next Update judged that shared record as diverged.
  The same shape reproduced independently for task-1→task-2 and
  ticker→task-3 pairings.
- User consequence: a successful-looking inspection can expose unrelated
  content and drive a decision from the wrong goal's state. Parallel goal work
  is unsafe even when all Context operands are explicit.
- Current safe workaround: serialize operations that consult implicit saved
  state and require an explicit, fully callable session locator before reuse.
- Evidence: `T1-XFORM-SHARED-SESSION-BLEED`, `TICK-XFORM-002`.

## CF-13 · Successful receipts omit or advertise unusable handoff identities

- Provisional priority: **P2 high**
- Worlds: all six
- Pattern: Merge reports only aggregate created/updated counts and not the
  Source-to-Target UID mapping needed by Rationale, Trace, Translate, or exact
  Atomize. Review prints short saved-session IDs that its own `--session` route
  rejects, and a recursive Checkpoint prints a set UID that Revert cannot
  resolve.
- User consequence: output chaining fails after a successful operation, so the
  user must rediscover content by text and guess identities; this is slow and
  can select the wrong derived Memory.
- Current safe workaround: immediately enumerate the exact Target, match full
  content manually, and retain full session UUIDs only where a producer exposes
  them.
- Evidence: `T1-XFORM-MERGE-UID-HANDOFF`, `T2T-SESSION-ID-01`,
  `T3T-CHECKPOINT-SET-UID`, `T3T-REVIEW-ARTIFACT`, `T3T-DEDUN-RECEIPT`,
  `TICK-XFORM-003`, `AIA-T-CHECKPOINT-LOCATOR-01`,
  `PS-T-DEDUN-RECEIPT`.

## CF-14 · Generated semantic work can cross from example into asserted fact

- Provisional priority: **P1 factual integrity**
- Worlds: task-2, task-3, a-is-apple, practice-source
- Pattern: Elaborate generated domain cases absent from the selected evidence,
  and Distill generated a presentation-style meta-rule explicitly excluded by
  the goal.
  Task-2 received unrelated minors, audio, and recruitment examples; task-3
  received asserted clinic purpose, treatment, accessibility, stairs, and knee
  pain. Practice-source received a fabricated concrete title and excluded
  presentation-style rules. Provenance later described the operation that
  generated a claim or split but did not distinguish that history from
  evidentiary support, and corrective Resolve could accept unsupported or
  excluded output unchanged.
- User consequence: a speculative example can become an ordinary Memory and
  then survive subsequent review as if it were a grounded fact. In healthcare
  selection this can change what appears eligible for disclosure.
- Current safe workaround: isolate all generated expansions from evidence,
  label them unverified, compare every assertion to exact Source Memories, and
  block materialization or transfer until a human accepts the factual status.
- Evidence: `T2T-ELABORATE-FABRICATION-01`, `T3T-ELABORATE-HALLUCINATION`,
  `T3T-RATIONALE-SEMANTIC-WARNING`, `T3T-RESOLVE-UNSUPPORTED`,
  `AIA-T-ELABORATE-INVENTION-01`, `AIA-T-ELABORATE-SCOPE-01`,
  `PS-T-DISTILL-META`, `PS-T-ELABORATE-INVENTED-EXAMPLE`,
  `PS-T-RATIONALE-SCOPE-WARNING`.

## CF-15 · Natural-language Forget can remove the rule the user meant to preserve

- Provisional priority: **P1 destructive intent risk**
- Worlds: task-2, a-is-apple
- Pattern: a duplicate-focused task-2 instruction deleted the unique general
  merge rule and edited a related conditional rule. An a-is-apple instruction
  about missing provenance removed all three atomized canonical mappings,
  leaving an empty Source that caused Impact, Meld, and Sever to fail.
- User consequence: wording that sounds like cleanup can erase the canonical
  knowledge needed by the goal, and the damage becomes visible only after
  publication or when the next operation encounters an empty frame.
- Current safe workaround: use structural Dedup for exact duplicates, state
  concrete unwanted content for semantic Forget, create an exact checkpoint,
  and require a reviewed per-Memory disposition before Apply.
- Evidence: `T2T-FORGET-SEMANTIC-SCOPE-01`,
  `AIA-T-FORGET-PROVENANCE-01`.

## CF-16 · An applied Atomize split can lose protected meaning

- Provisional priority: **P1 meaning preservation**
- Worlds: practice-source; cross-world confirmation pending
- Pattern: an applied split detached the protected word `for` from its
  document-title trigger and exception scope; Audit, Conformance, Rationale,
  and Trace independently exposed the loss, and Revert restored the scratch
  input.
- User consequence: a user can approve an apparently atomic child whose
  independent meaning no longer matches the source.
- Current safe workaround: verify every proposed child against the complete
  source and reject any child that omits a trigger, exception, protected
  object, or companion safeguard.
- Evidence: `PS-T-ATOMIZE-SCOPE-LOSS`. The separate
  `PS-T-ATOMIZE-SCOPE-INCONSISTENCY` observation is closed as accepted
  semantic-provider variance.

## CF-17 · Missing Impact endpoint can silently become shared current

- Provisional priority: **P1 candidate for parallel targeting**
- Worlds: practice-source; one excluded unsafe-default probe plus one explicit
  correction
- Pattern: `impact distill` with an explicit Source but no Target selected the
  shared current Context `practice` as an existing Target. The fully explicit
  `--from SOURCE --to RESULT` replacement used the intended world-local frame.
- User consequence: an explicit-looking semantic preview can inspect or plan
  against state outside the worker's goal, and a later Apply could target the
  wrong Context if the hidden default is not noticed.
- Current safe workaround: require both Source and Target on every Impact route
  that has two endpoints; exclude current-defaulted evidence from parallel
  coverage and never Apply it.
- Evidence: `PS-T-IMPACT-DEFAULT-CURRENT`.

## CF-18 · Applied semantic evidence can disappear from later history/review

- Provisional priority: **P1 candidate for recovery evidence**
- Worlds: practice-source; one applied Atomize observed through two later
  evidence surfaces
- Pattern: Diff's real 180×52 history omitted the applied Atomize event that
  Trace still showed. A later read-only Atomize Impact then replaced the
  Context review route's visible state, so Review said execution was incomplete
  although Trace retained the applied split and checkpoint.
- User consequence: a user may conclude that a material mutation never
  happened or cannot independently review it before recovery, even though the
  durable history still contains the event.
- Current safe workaround: review and capture Apply evidence immediately,
  retain the printed checkpoint, and pair Diff/Review with exact Trace until
  every surface agrees.
- Evidence: `PS-T-DIFF-HISTORY-OMISSION`,
  `PS-T-REVIEW-ATOMIZE-CLOBBER`.

## CF-19 · Stale zero-coverage proposal still advertises Apply

- Provisional priority: **P2 candidate for decision presentation**
- Worlds: practice-source; one late saved Meld session
- Pattern: saved Meld Impact reported `0/33 SOURCE COVERAGE`, zero final
  Memories, and zero changes after substantial Target mutation, then still
  displayed `APPLY? Continue to Meld Apply` without an equally prominent
  stale/inapplicable state.
- User consequence: the primary visible next action encourages advancing a
  proposal that no longer represents any current Source item.
- Current safe workaround: do not Apply; restart against the current explicit
  endpoints and require nonzero exhaustive coverage before review.
- Evidence: `PS-T-IMPACT-COVERAGE`.
