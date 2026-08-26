# Ticker world · transform-phase findings

## Internally reviewed non-defects

### TICK-XFORM-001 · NOT A DEFECT · intended complete-frame Audit behavior

- Observation retained: two independent saved Audits over the 13-Memory example frame reported `0/13` ambiguities and zero conflicts; CLI Review and the 180×52 Review TUI faithfully displayed the same frozen fragments and saved zero-finding result.
- Contract interpretation: Audit runs Find Ambiguities over the complete selected Context, where adjacent Chunk outputs supply one ordinary reading; a target is not ambiguous merely because it is not self-contained, so the contract requires clean `SINGLE/NONE` targets to be omitted.
- Disposition: `NOT A DEFECT`. The result does not certify standalone self-containment, and the visible coexistence of Source fragments and zero findings is an accurate presentation of the saved judgment rather than a Review contradiction.
- Reporting boundary: retain this note and the raw attempts as internal decision history, but exclude `TICK-XFORM-001` from external issue lists, priority counts, decision-boundary evidence, and repair work.

## TICK-XFORM-002 · Update/Diff can surface another world's saved applied state

- Expected: An explicit ticker Source/Target request, and Diff immediately following it, should be bound to those displayed endpoints or require an explicit saved-session selector.
- Actual: The first two ticker Update attempts and three Diff routes surfaced an already-applied `task-3` update. Verbose Diff increased the unrelated detail without making the ticker route current.
- Workaround: Start Update with `--replace-stage` and explicit ticker endpoints; retain the returned receipt and review that exact session instead of using implicit Diff state.
- Severity: high — a user can inspect or reason about the wrong world's operation while every visible command operand appears ticker-local.
- Reproduction: confirmed 5 times (2 Update, 3 Diff); the late `--replace-stage --direct` route recovered and returned ticker receipt `ea0fbe78`.

## TICK-XFORM-003 · Merge does not hand off remapped Memory UIDs

- Expected: When Merge copies Memories and assigns target-local UIDs, its receipt should expose a source-to-target UID map or a directly reusable typed result for Rationale, Trace, Translate, and Atomize.
- Actual: Merge reported only aggregate counts (`NEW 14`, later `NEW 9`). Exact follow-ups using the known source UID failed until another analysis/output revealed target UIDs such as `d1eb7878`.
- Workaround: Re-list/show the target or extract the remapped UID from a later Atomize snapshot before exact follow-up commands.
- Severity: medium — correctness is preserved, but the output cannot be directly chained and forces redundant discovery.
- Reproduction: confirmed after 2 Merge writes and by 3 failed exact consumers (Rationale, Trace, Translate).

## TICK-XFORM-004 · Impact buries a no-change outcome under full-frame evidence

- Expected: A no-change Impact should lead with a compact outcome and keep full source bodies/hashes behind an explicit detail route.
- Actual: Direct and recursive attempts both printed the entire large source frame plus hashes even though the result was no change.
- Workaround: Search/scroll to the outcome line or capture output and extract the summary manually.
- Severity: medium — no data loss, but the next action is buried and the same evidence must be reread.
- Reproduction: confirmed 2 times with materially different direct and recursive scopes.

## TICK-XFORM-005 · Combined Audit + Conformance can discard a long provider turn

- Expected: Every frozen target Memory should receive a decoded disposition, or the command should return a bounded retry/recovery artifact without publishing partial findings.
- Actual: After about 25 seconds, the combined run failed because Conformance did not account for every target Memory; no partial Audit was published or reusable.
- Workaround: Run quality Audit and Check Conformance separately; retry only the failed half.
- Severity: medium — safety is maintained, but provider time and the whole combined result are lost.
- Reproduction: observed once in this phase; not yet confirmed twice.

## TICK-XFORM-008 · Resolve reports fragmented source as already fit

- Expected: Resolve should propose reconstruction, mark uncertainty, or reject clearly incomplete standalone fragments when guidance asks for complete ticker claims.
- Actual: Whole-frame, exact-fragment-guided, and late `--allow-delete` attempts all returned `FIT · YES · NO CHANGE` on the same fragmented source.
- Workaround: Use Check Conformance/Atomize to expose the fragments and a reviewed Sever session to apply explicit KEEP/FORGET decisions.
- Severity: high — the primary repair operation gives a confident no-op for the defect the user is trying to repair.
- Reproduction: confirmed 3 times across early, mid, and late accumulated state.

## Decision boundary observed

The agent could safely execute empty, missing, stale, cached, checkpoint, and scratch-only destructive paths without user decisions. The only material judgment remained the reviewed Sever Apply: its exact session stated `KEEP 8 / FORGET 5`, affected only `audit/ticker/transform-scratch/source`, and had a prior subtree checkpoint. That is the appropriate pause point; discovery, evidence collection, and reversible recovery did not require user intervention.
