# task-3 TRANSFORM issues

120 counted commands completed through the pinned runner. No external transfer occurred.

## T3V2-ELABORATE-UNVERIFIED-ORDINARY-MEMORY — Elaborate persists invented healthcare examples as ordinary factual-looking Memories

- Severity: P1 / high
- Classification: semantic safety / unsupported generation
- Expected: Generated Cases remain visibly hypothetical and unverified in their durable content, especially when the Source supplies no recipient, clinician, prescription, vendor, or employee facts.
- Actual: A one-Rule healthcare run invented Dr. Chen, a confirmed current prescription-adjustment purpose, and current medication name/dosage, then added the sentence as an ordinary Memory. A minimization run similarly added concrete benefits-vendor and employee incident stories. `VERIFICATION · UNVERIFIED` appeared only in the transient receipt; the first stored Memory did not label itself as a suggested example.
- Workaround: Checkpoint the Target first, inspect the full Elaborate receipt immediately, and undo/revert every output whose stored text is not self-labelled hypothetical and source-grounded.
- Reproduction: Yes — 2/5 materially different Elaborate attempts persisted invented concrete scenarios; strict round 4 improved this by including `Suggested Example Memory` in the content.

## T3V2-FORGET-SAFETY-GATE-LOSS — Forget removes or weakens the exact safety boundary it was told to preserve

- Severity: P1 / high
- Classification: semantic safety / destructive curation
- Expected: Whole-frame curation preserves explicit uncertainty and human decision gates while dropping only items that actually imply approval, unsupported currentness, or forbidden third-party disclosure.
- Actual: Round 1 deleted a Memory that explicitly said the candidate was `not yet approved` under an instruction to remove only items implying approval. Round 3 deleted both an uncertainty-preserving medication rule and a draft accommodation candidate that required verification. Round 5 rewrote the exact recipient/purpose/item/channel/retention checklist into the vague phrase `decision before any transfer` despite an explicit preserve-the-human-decision-gate instruction.
- Workaround: Always checkpoint before Forget, inspect the complete DIFF rather than trusting the instruction echo, and revert if a negative gate, uncertainty statement, or enumerated approval field is removed or generalized.
- Reproduction: Yes — harmful disposition drift appeared in 3/5 different curation frames and was recovered by same-round Revert.

## T3V2-UPDATE-AUTO-APPLY-OPAQUE — Update applies semantic edits before showing the changed text

- Severity: P1 / high
- Classification: semantic mutation / review safety
- Expected: A high-stakes semantic Update presents the exact ADD/EDIT/REMOVE proposal for review before materialization, or at minimum prints every changed Memory in its Apply receipt.
- Actual: Three Update attempts immediately printed `UPDATE APPLIED` and changed the local audit scratch with no `--accept` step. Receipts showed only aggregate counts. The final run edited five Memories, including appending possible recipient retention/internal-forwarding behavior to a minimization record, but none of the five before/after texts appeared in the receipt.
- Workaround: Checkpoint the Target, run Update only in disposable local scratch, open `mem review update --session RECEIPT` immediately, and undo if any exact edit was not already approved.
- Reproduction: Yes — 3 successful local Update routes auto-applied; two other attempts failed closed on an embedded Grant before mutation.

## T3V2-SEVER-OPAQUE-READY — Sever declares personal-Memory curation ready without showing kept, transformed, or dropped items

- Severity: P1 / high
- Classification: privacy review / output opacity
- Expected: Before a fresh Result can be accepted, the line-oriented receipt exposes the exact selected/excluded/transformed Memories and their reasons, with every unresolved healthcare meaning decision required.
- Actual: Four personal-history Sever runs returned `SEVER READY`, `JUDGMENTS · REQUIRED 0`, and `READY TO CREATE` with only Source/Result/session identifiers. No kept, dropped, transformed, third-party, stale, or unapproved items were visible in the receipt, so readiness could not be checked from the command that produced it.
- Workaround: Do not accept from the READY receipt. Open the exact saved session through Impact/Review, inspect every disposition, and require explicit human approval of the final item list.
- Reproduction: Yes — 4 successful Sever variants had the same opaque READY receipt; the fifth failed provider-result validation and changed nothing.

## T3V2-MELD-EAGER-EMPTY-RESULT — Meld creates an empty Result Context while semantic choices still need input

- Severity: P2 / medium
- Classification: workflow state / premature materialization
- Expected: A fresh symmetric Result remains a plan until required/optional meaning review is complete, or the receipt clearly identifies any intentionally materialized placeholder and its cleanup route.
- Actual: Rounds 1 and 5 returned `MELD NEEDS INPUT` with optional judgments and no `--accept`, but each invocation created a durable empty local Result Context. Source remained unchanged, yet the Result creation survived restoration of the separately checkpointed scratch Target.
- Workaround: Use directional Meld when possible; otherwise treat the fresh Result name as reserved scratch and remove the empty placeholder only through a separately authorized cleanup after the review is abandoned.
- Reproduction: Yes — both symmetric fresh-Result NEEDS INPUT attempts created zero-item Contexts; directional attempts did not.

## T3V2-GRANTED-TRANSFORM-ROUTE-INCONSISTENCY — Granted Context works in Audit, Meld, and Merge but is reported absent by Atomize and Impact Atomize

- Severity: P2 / medium-high
- Classification: authorization routing / operation consistency
- Expected: Every readable/DERIVE-authorized operation resolves the same public Context through the grant-aware catalog, or fails with the exact missing capability rather than claiming the Context is not local/not found.
- Actual: Atomize said the public guidance `does not exist locally`, and Impact Atomize said it was `not found`. In the same cumulative lane, Audit analyzed all 25 granted Memories, directional Meld accepted the public Source, and structural Merge copied all 25 into checkpointed local scratch. Distill separately gave a clear not-authorized boundary.
- Workaround: Use the operations that explicitly resolve readable Grants, or copy/merge only when inward EXPORT authority and local recovery are appropriate; do not interpret `not found` as evidence that the Grant disappeared.
- Reproduction: Yes across two failing Atomize adapters and three successful peer adapters over the identical public name.

## T3V2-RESOLVE-OPAQUE-NOCHANGE — Resolve reports FIT YES / NO CHANGE without evidence or candidate disposition

- Severity: P2 / medium
- Classification: usability / semantic explainability
- Expected: A no-change Resolve receipt explains what was examined, why no repair is needed, and how the stated guidance and Fit check support that result.
- Actual: All five varied Resolve invocations returned only the Context name and `FIT · YES · NO CHANGE`. No selected Memory, assessed issue, evidence, guidance effect, or reusable session was shown, including focused and allow-delete routes.
- Workaround: Treat NO CHANGE as an opaque model outcome, inspect the Source and saved quality findings separately, and do not interpret FIT YES as healthcare approval.
- Reproduction: Yes — 5/5 interleaved Resolve routes produced the same evidence-free shape.

## T3V2-ATOMIZE-PROVIDER-TIMEOUT — One whole-Context Atomize provider call exceeded the isolated 360-second audit bound

- Severity: P2 / medium campaign impact; not classified as a product semantic defect
- Classification: infrastructure / provider latency
- Expected: The bounded provider call finishes or fails with a native timeout before the audit's six-minute outer isolation limit, publishing no partial result.
- Actual: The first whole-Context Atomize call emitted no application output and was terminated by the world-local audit harness after 360 seconds. The task-3 tree digest was unchanged. Four later focused/smaller Atomize attempts returned in 7–9 seconds or failed immediately at a route boundary.
- Workaround: Use a focused Memory/Context frame, retain the outer timeout, and retry only in a new counted campaign rather than silently duplicating this invocation.
- Reproduction: 1/5 Atomize attempts; isolated as provider/infrastructure because later Atomize calls completed normally.

## T3V2-TRANSFORM-HARNESS-ARTIFACT-ROUTING — Audit harness failed to reuse saved artifact UIDs and used unsupported replay modifiers

- Severity: P2 / coverage limitation; not a product defect
- Classification: audit infrastructure / methodology limitation
- Expected: The audit extracts `SESSION [uid]` from snapshot receipts, binds round-local dynamic selectors eagerly, and uses only supported replay syntax so Review/Impact evidence exercises real saved artifacts.
- Actual: The harness initially recognized only `mem review audit --session uid`, not Audit snapshot's `SESSION [uid]`, so Review attempts 1, 2, 4, and 5 passed `deadbeef`. Review 3 used an unsupported Context-only saved-Audit route. Impact 5 requested the current round's Meld artifact before Meld 5 existed. All five Dedun attempts also combined hidden `--plain` replay state with exact discovery and were rejected. Late-bound source selectors caused Rationale/Trace/Translate and Update 3 to use the final round's approval Source; ledger routes are corrected to the actual argv rather than the intended Sources.
- Workaround: The harness source now recognizes bracketed Audit sessions. For a new campaign, bind every lambda default eagerly, use prior-round artifacts when Impact precedes creation, omit hidden `--plain` from exact Dedun discovery, and validate generated argv before the first counted call.
- Reproduction: Deterministic from the recorded argv/raw output; no extra mem calls were made because the 120-command contract forbids replacement attempts.

## T3V2-SEVER-PROVIDER-CONTRACT-FAILURE — One Sever result failed complete-output validation

- Severity: P2 / medium campaign impact; fail-closed
- Classification: provider output / infrastructure failure
- Expected: Sever returns exactly one validated disposition per Source Memory with an application summary citing only Criteria related to a change.
- Actual: Round 2 failed with `The application summary cites Criteria unrelated to a change.` No Source or Result Context was changed. Four other Sever variants produced saved READY sessions.
- Workaround: Keep the failure fail-closed, retain the exact Source/Criteria frame, and retry only as a separately counted operation while checking the full session contract.
- Reproduction: 1/5 Sever attempts; validation correctly prevented publication.

