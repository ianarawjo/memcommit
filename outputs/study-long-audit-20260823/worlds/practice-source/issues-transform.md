# practice-source transformation/evidence issues

Evidence: `phase-transform.json` contains 24 operations × 5 interleaved counted attempts = 120. One additional unsafe-default Impact probe is explicitly excluded and replaced by an explicit-source-and-target attempt. `practice/source` remained read-only; destructive work stayed in checkpointed `practice/audit-workspace/transform-scratch/...` Contexts.

## PS-T-ATOMIZE-NORMAL-FORM — Whole-frame Atomize cannot apply its own otherwise useful analysis

- Expected: A 12-Memory scratch copy either reaches semantic chunk normal form, exposes the exact unresolved items and a safe explicit resolution path, or applies only a validated complete plan without changing meaning.
- Actual: Whole-frame Atomize/Impact identified 4 useful splits and one unresolved opening `But`, but direct Atomize failed final validation with two COMPOSITE items and one UNCERTAIN item. No change was published. The report did not provide an explicit-context, non-session command that could apply only the validated subset.
- Workaround: Keep the failed full analysis as evidence, narrow a checkpointed scratch Context to one source Memory, apply there, Audit/Conformance the children, then Revert if scope is lost.
- Severity: **P2 / medium-high** workflow-completion and re-entry cost; fail-closed publication was correct.
- Reproduction: **One whole-frame Apply failure**, contrasted with a later narrow Context Apply.

## PS-T-ATOMIZE-SCOPE-INCONSISTENCY — Closed as accepted provider variance

- Status: **CLOSED / NOT A PRODUCT DEFECT** by user decision on 2026-08-23.
- Observation: Whole-frame Impact classified Memory `74fe914d` as `COMPOSITE · 2 CHILDREN`, while a later exact `--memory 74fe914d` call classified the same unchanged Memory as `ATOMIC · KEEP`.
- Decision: The two judgments came from separate semantic-provider turns, used different Atomize evidence roles, and were collected in different audit rounds. One disagreeing pair therefore does not isolate scope as the cause and is accepted as ordinary LLM judgment variance.
- Future triage: Preserve similar observations as provider-variance evidence, explain that independent semantic runs can disagree, and close them without a product issue. Reopen only if repeated paired runs over one frozen Context and identical provider configuration show a route-correlated bias; a published split that loses source meaning remains a separate defect.
- Historical evidence: The original attempt association remains in `phase-transform.json` so the decision can be revisited without reconstructing the run.

## PS-T-ATOMIZE-SCOPE-LOSS — Applied split detaches the protected word from document-title scope

- Expected: Splitting the document-title rule preserves the title scope, narrow capitalization override, literal protected word `for`, and approved-wording evidence in every independently reviewable child that needs them.
- Actual: Narrow scratch Atomize applied one split: the first child retained document-title sentence-case scope; the second became only `Always keep “for” whenever it is part of the intended wording.` Audit immediately flagged the child underspecified, and Conformance could not establish that either child preserved the original title-specific scope and exception boundary. The checkpointed Context was reverted.
- Workaround: Reject this split. Keep the title-capitalization/default/override/wording unit together, or restate the second child with explicit document-title scope and source provenance before review.
- Severity: **P1 / high** meaning-preservation defect.
- Reproduction: **One applied split, independently exposed by Audit, Conformance, Rationale, and Trace**.

## PS-T-ATOMIZE-EMPTY — Empty Atomize publishes an applied receipt and checkpoint

- Expected: An exact Context with zero direct Memories reports a no-op and creates no semantic Apply/checkpoint artifact.
- Actual: The empty late Result reported `ATOMIZE APPLIED`, `0/0`, and created receipt `7322e9fa` plus checkpoint `09e24a45`.
- Workaround: Preflight the exact Context and skip Atomize when it is empty.
- Severity: **P3 / low-medium** durable-history noise.
- Reproduction: **One intentional empty-boundary attempt**.

## PS-T-CONFORMANCE-FALSE-CONFIDENCE — Broad conformance says all source notes preserve an atomization rule before atomization

- Expected: Conformance distinguishes an unsplit source instruction from an independently reviewable atom and does not claim that a future transform property is already satisfied merely because the source contains the needed information.
- Actual: Round 1 reported all 12 source Memories conform to `Each atom must preserve its trigger, exception, protected object, companion safeguard, and source meaning`, even though Atomize had just failed normal-form validation and later applied splitting demonstrably lost scope.
- Workaround: Run Conformance on actual proposed children together with their original source frame, not on unsplit source Memories alone.
- Severity: **P2 / medium-high** false-confidence risk.
- Reproduction: **One broad all-conform result; later child-level Audit/Conformance provides the contradictory boundary evidence**.

## PS-T-DISTILL-META — Distill repeatedly invents a presentation-style rule excluded by the goal

- Expected: Goals saying constraint atoms only or exclude personal/presentation style omit corpus-shape observations that are not operative editing constraints.
- Actual: Three successful Distill runs added a final rule about concise English, first-person framing, conditional openings, present tense, or informal directive style. Rounds 3 and 5 explicitly excluded that class. Exact Resolve returned FIT/NO CHANGE for the late meta-rule; Forget then removed it successfully.
- Workaround: Treat Distill results as candidates, run an explicit source-grounding/constraint-only filter, and use checkpointed Forget to remove inferred family-style rules.
- Severity: **P1 / high** semantic scope drift in a reusable rule set.
- Reproduction: **Yes, 3/4 successful Distill executions**; round 1 was a parser failure before execution.

## PS-T-RESOLVE-NOCHANGE — Resolve does not remove explicitly identified non-constraint output

- Expected: Exact corrective guidance identifying a Memory as an inferred presentation-style meta-rule proposes removal/edit, or reports why the selected scope cannot change it.
- Actual: The late exact Resolve returned `FIT · YES · NO CHANGE`; the Memory remained. Earlier whole-result guidance to keep atomization separate from editing also returned the same terse no-change result. A following Forget with equivalent removal intent removed the meta-rule.
- Workaround: Verify the exact Memory after Resolve. For discard decisions use checkpointed Forget and Review its applied receipt.
- Severity: **P1 / high** correction-path reliability defect.
- Reproduction: **Yes, 3 FIT/NO CHANGE outcomes across different corrective scopes; 1 exact case has a successful Forget contrast**.

## PS-T-DIFF-DISCOVERY — Checkpoint output cannot be reused through an obvious noninteractive Diff command

- Expected: A displayed checkpoint UID and Context can be supplied to Diff in a documented line-oriented form, or `diff CONTEXT` supports a concise noninteractive summary.
- Actual: Three non-TTY Context attempts required an interactive terminal; `diff e9e83007 --context RESULT` was rejected because Diff has no `--context`. The error says to pass a checkpoint explicitly but does not show the exact grammar.
- Workaround: Use the exact Context in a real PTY and select history interactively; keep Revert's direct UID route as the reliable noninteractive recovery command.
- Severity: **P2 / medium-high** recovery discovery and repeated-input cost.
- Reproduction: **Yes, 4 CLI attempts across empty, changed, and checkpointed Contexts**.

## PS-T-DIFF-HISTORY-OMISSION — Diff TUI omits the applied Atomize event visible in Trace

- Expected: Diff's saved-history list includes every material operation affecting the selected Context, especially an applied Atomize split with its own receipt/checkpoint.
- Actual: The actual 180×52 truecolor Diff TUI on criteria showed only the scoped Update checkpoint (`14f5a95d`, one ADD). It did not list the subsequently applied Atomize split/checkpoint (`cdb793a7`), although Trace later showed both events. Tab and two Esc presses were needed to enter Viewer, return a layer, and close.
- Workaround: Pair Diff with Trace/Rationale and keep Atomize's printed checkpoint separately; do not infer complete history from the Diff Items list.
- Severity: **P1 / high** recovery/evidence omission.
- Reproduction: **One real PTY path**, independently confirmed by Trace.

## PS-T-ELABORATE-SOURCE-TYPE — Visible embedded evidence makes a Context unusable as Elaborate Source

- Expected: Elaborate either supports a clearly selected direct-Memory subset or explains before provider work which displayed item types prevent Context-backed execution.
- Actual: Criteria contained two ordinary candidate Memories and two embedded Contexts. Context-backed Elaborate rejected the Source because it was not composed only of directly owned ordinary Memories; the exact ordinary subset could not be selected in that route.
- Workaround: Use explicit inline `--rule` inputs, or copy the intended ordinary criteria into a clean scratch Context before Elaborate.
- Severity: **P2 / medium** source-selection and re-entry cost.
- Reproduction: **One mixed-item Source rejection; 3 inline routes succeeded**.

## PS-T-ELABORATE-INVENTED-EXAMPLE — Example introduces a concrete title that was not supplied

- Expected: An unverified boundary example remains parametrized or quotes only exact source wording; it must not turn required terms into a fabricated concrete title.
- Actual: Elaborate created `When revising the title “Interaction and management for AI agent memory,” ...`. The source requires those terms for a title about the topic but does not provide that exact title. A following Forget did not remove it outright; it staged an edit.
- Workaround: Keep the example explicitly hypothetical and source-linked, or avoid concrete title synthesis and express only the title-scope/`for` constraint.
- Severity: **P2 / medium-high** provenance and false-specificity risk.
- Reproduction: **One exact inline-rule example**.

## PS-T-DEDUN-RECEIPT — Dedun summary hides survivor and absorption mappings

- Expected: Multi-item semantic cleanup prints every survivor UID and absorbed-to-survivor link so output can feed Trace, Review, Merge, or Revert directly.
- Actual: Round 3 reported 6 absorbed / 6 kept and round 4 reported 11 absorbed / 11 kept without mappings. Only a later one-group Review exposed its survivor/absorbed pair. The large Result therefore required another command to learn what remained.
- Workaround: Checkpoint, then immediately use `review dedun --receipt ...` and exact List/Show before another mutation.
- Severity: **P2 / medium** output-reuse and independent-review cost.
- Reproduction: **Yes, 2 multi-group concise receipts**, plus one small receipt successfully reviewed.

## PS-T-GROUND-GRAMMAR — Binding requires several differently named options discovered through failure

- Expected: The Ground binding grammar uses learnable names aligned with surrounding commands or prints one exact corrective command when a required binding field is missing.
- Actual: `--publication-context` was rejected in favor of `--publication-target`; the next call then said binding also required `--description`. The third fully explicit form succeeded.
- Workaround: Supply name, goal, description, `--raw-context`, `--derived-context`, and `--publication-target` together.
- Severity: **P2 / medium** repeated-input and option-discovery cost.
- Reproduction: **Two sequential parser/validation failures followed by one success**.

## PS-T-GROUND-RESEARCH-NOISE — Atomization Ground foregrounds unrelated method readings

- Expected: A Ground focused on local constraint atomization foregrounds the Goal, frozen frame staleness, exact candidate, and next review decision; research suggestions appear only when relevant or requested.
- Actual: The successful Ground showed two `UNREAD · agent-suggested` papers on machine teaching/Ripple Down Rules beside a local editing-constraint candidate. They did not help decide its trigger/exception/provenance boundary and competed with the blocked/next-action information.
- Workaround: Ignore method readings and use the exact RAW/DERIVED/target frame plus local Audit/Trace evidence.
- Severity: **P3 / low-medium** information-overload and attention cost.
- Reproduction: **Yes, shown on fresh creation and again on the stale snapshot**.

## PS-T-IMPACT-DEFAULT-CURRENT — Explicit Distill Source silently defaults Impact Target to shared current

- Expected: In a parallel audit that supplies an explicit Source, Impact either requires an explicit Target or fails before reading shared current state.
- Actual: The excluded probe `impact distill SOURCE ...` displayed `TARGET · practice · EXISTING`, taking the shared current as Target. No mutation occurred, but its interpretation depended on state outside the world. The replacement with explicit `--from SOURCE --to RESULT` succeeded and was counted.
- Workaround: Always pass both `--from` and `--to` for Impact Distill; exclude any current-defaulted attempt from world coverage.
- Severity: **P1 / high** cross-world state/targeting risk.
- Reproduction: **One unsafe default plus one explicit-target correction**.

## PS-T-IMPACT-COVERAGE — Saved Meld Impact presents Apply despite zero source coverage

- Expected: If a saved proposal covers 0/33 current Source items and its Target has changed, Impact foregrounds staleness/inapplicability rather than an Apply affordance.
- Actual: Late saved Meld Impact reported `0/33 SOURCE COVERAGE`, zero final Memories and zero changes, then displayed `APPLY? Continue to Meld Apply` without an equally prominent stale-target warning.
- Workaround: Do not apply; restart Meld against the current explicit Target and re-check coverage.
- Severity: **P2 / medium-high** stale-proposal decision risk.
- Reproduction: **One late saved-session Impact after substantial Result mutation**.

## PS-T-MELD-SNAPSHOT-RACE — Sequential Meld reports that its Source changed during Compare

- Expected: A frozen explicit Source/Criteria pair remains stable within one sequential command, or a genuine concurrent revision is named with its before/after digest.
- Actual: Symmetric Meld ran for 25.62 seconds and failed that a Source Context changed while Compare was analyzing it. No other audit command was concurrently mutating those Contexts, and no new analysis was saved.
- Workaround: Preserve the failure, retry through a narrow inline Memory plus explicit baseline and `--restart`, which produced READY sessions.
- Severity: **P2 / medium-high** reliability and wasted semantic-turn cost.
- Reproduction: **One sequential snapshot-race failure; 3 directional inline routes provide the working contrast**.

## PS-T-RATIONALE-SCOPE-WARNING — Provenance narrates a split without warning that the result lost scope

- Expected: Rationale distinguishes recorded operation provenance from semantic sufficiency and surfaces an existing Audit warning about the selected derived child.
- Actual: Rationale accurately said Atomize produced standalone `Always keep “for”...`, but did not mention that its original document-title scope was absent. The Audit on the same unchanged child had already flagged it underspecified.
- Workaround: Pair Rationale with current Audit/Conformance; do not interpret a recorded split event as proof of meaning preservation.
- Severity: **P2 / medium-high** epistemic-clarity risk.
- Reproduction: **One exact applied child with independent Audit evidence**.

## PS-T-REVERT-OVERLOAD — Large recovery receipts abbreviate the evidence needed to verify restoration

- Expected: Revert remains compact while emitting a machine-reusable complete effect manifest or exact follow-up command.
- Actual: Round 2 removed 21 items and printed 12 plus 9 omitted. Round 5 restored 38 and removed 32, printing 12 plus `58 more affected direct items`. Verifying the recovery therefore requires another List/Diff/Trace pass.
- Workaround: Use the exact checkpoint UID, then inspect the restored Context with List/Trace; retain the receipt only as a high-level count.
- Severity: **P2 / medium** information-overload and verification cost.
- Reproduction: **Yes, 2 large recoveries**.

## PS-T-RESULT-OVERLOAD — One Result mixes rules, examples, copies, and cleanup survivors

- Expected: Accumulated work stays type-separated or provides a typed filter so a reviewer can distinguish exact evidence, proposed atoms, examples, and meta-rules.
- Actual: Result reached 38 direct items before round-5 Clear. Rebuilding then reverting produced 70 effects. Dedun/Forget helped, but receipts required extra Review and Merge later reintroduced exact source copies alongside generated rules.
- Workaround: Keep separate scratch children for exact source evidence, proposed constraint atoms, examples, and reviewed output; checkpoint each before cross-type transforms.
- Severity: **P2 / medium-high** information architecture and review-time issue.
- Reproduction: **Observed across Clear, Distill, Elaborate, Dedun, Forget, Merge, and Revert**.

## PS-T-REVIEW-ATOMIZE-CLOBBER — Read-only Impact replaces the applied Atomize review route

- Expected: After Atomize Apply prints an operation receipt and Review command, later read-only Impact analysis does not make the applied evidence unreachable.
- Actual: Narrow Atomize applied split receipt `bd86927e`. A subsequent `impact atomize CRITERIA` saved analysis `d884adfd`. `review atomize --context CRITERIA` then said execution was incomplete, even though Trace still showed the recorded applied split/checkpoint.
- Workaround: Review immediately after Apply and save its output before running a new Impact analysis; use Trace as fallback evidence.
- Severity: **P1 / high** applied-evidence accessibility defect.
- Reproduction: **One Apply→Impact→Review sequence, independently verified by Trace**.

## PS-T-SEVER-VALIDATION — Sever rejects a proposed summary for citing unchanged Source

- Expected: A valid whole-frame curation analysis may cite an unchanged Source Memory as evidence while separately requiring each output disposition to be complete and grounded.
- Actual: Two fresh Sever attempts failed with `The application summary cites an unchanged Source Memory`, including one after narrowing criteria through an applied Atomize frame. No partial Result was created. A saved earlier READY session later applied separately with `KEEP 4 · FORGET 8`, leaving Source unchanged.
- Workaround: Keep Source immutable, retain the failure evidence, and only Apply a separately reviewed READY session into a fresh scratch Result.
- Severity: **P2 / medium-high** completion/reliability issue; fail-closed publication was safe.
- Reproduction: **Yes, 2 fresh failures; one earlier saved-session Apply succeeded**.

## PS-T-TRACE-LIMIT — JSON Trace ignores the requested minimal limit

- Expected: `--json --limit 1` bounds the returned trace or documents precisely which array is limited.
- Actual: The applied `for` child returned the full three-Member component, Update and Atomize events, analysis, spans, and children. The output exceeded several terminal screens despite the minimal limit.
- Workaround: Parse only needed fields and carry exact UIDs; use plain Trace for a one-event human check.
- Severity: **P2 / medium** output-volume and chaining cost.
- Reproduction: **One direct minimal-limit case; other JSON traces were similarly verbose**.

## Safe transformation outcome

The original `practice/source` was never edited, cleared, deleted, forgotten, atomized in place, or otherwise destructively changed. The only successful Atomize Apply occurred in a one-Memory scratch Criteria Context; Audit and Conformance showed its scope loss, and direct checkpoint Revert restored the prior scratch state. All Clear/Delete/Forget/Dedun/Update/Merge/Revert work remained inside `practice/audit-workspace/transform-scratch`. No publication or external transfer occurred.
