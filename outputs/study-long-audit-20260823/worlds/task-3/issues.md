# task-3 phase-core issues

## T3-QUERY-TARGETING — Exact QUERY-only public target resolves to the wrong local Context

- Expected: `mem query --context task-3/remote/government/healthcare-agent/info-request/questions-and-answers QUESTION` uses only the named authorized QUERY-only endpoint, labels that public name as the source, and returns the recipient, purpose, requested fields, prohibited fields, and retention behavior with its used References. If it cannot query that endpoint, it must fail closed before consulting unrelated local personal Memories.
- Actual: Three exact commands exited 0 but labeled the result `task-3/local/personal-memory`, printed `(no grounded answer found)`, and emitted no References. The requested public name was identical in all three commands. The observed answer did not quote local Memory text, so this run proves target misrouting and a potential disclosure boundary violation, not confirmed content disclosure. An alternate positional form failed by looking for the public name as a direct item under local `task-3`.
- Workaround: None found for the exact QUERY-only interface. The world therefore executed no transfer, inferred no approval, and recorded the failed specification in the local audit Context.
- Severity: **P1 / high** authorization and targeting risk. A QUERY-only recipient cannot be safely trusted if the route silently identifies a local personal corpus instead.
- Reproduction: **Yes, 3 exact reproductions** (rounds 1, 4, and 5), plus one alternate-route failure (round 2).

## T3-GRANT-SELECTIVE-TRANSFER — Readable/exportable Grant cannot be selectively copied or referenced

- Expected: A granted public Memory that is visible through `list` and `show`, and whose Context advertises the necessary read/export authority, can be selected with its public Context and transferred through the supported provenance-preserving route, or the CLI explains the specific missing capability.
- Actual: `reference dcf1b441 --from task-3/remote/government/healthcare-agent/public-guidance ...` and the analogous `copy` both said that the public Context “does not exist locally.” Whole-Context `embed` of that same public name succeeded. The error collapses “granted but not local” into “does not exist,” hiding the actual route/capability boundary.
- Workaround: Whole-Context embed makes all 25 guidance Memories readable, then a local review can use them. This is materially broader and noisier than selecting one warning, so it is not an equivalent safe-export workflow.
- Severity: **P1 / high** for selective, minimum-necessary disclosure workflows; no unauthorized mutation occurred.
- Reproduction: **Yes, 2 selective routes**: reference in round 4 and copy in round 5. The contrasting embed route succeeded once and rejected a duplicate safely.

## T3-CONTEXTS-OVERLOAD — Whole-Profile discovery repeatedly buries one world

- Expected: A person working on task-3 can narrow Context discovery to the task-3 local/public hierarchy while preserving ownership, Grant, and capability annotations.
- Actual: `mem contexts` printed roughly 112 lines covering every world. Task-3 local, SHARE, QUERY-only, and READ/EXPORT names were present, but each reorientation required a multi-screen prefix scan; two captured outputs were truncated by volume.
- Workaround: Manually scan for the `task-3` prefix once, then carry exact public/local names into later commands.
- Severity: **P2 / medium** repeated navigation and information-overload cost.
- Reproduction: **Yes, 5/5 rounds**.

## T3-SEARCH-CURATION — Relevance retrieval does not form a safe disclosure decision

- Expected: A healthcare-sharing workflow can retrieve candidates and policy exclusions without implying that semantically relevant third-party, stale, or unapproved facts are safe to send; multi-root results should make source coverage visible.
- Actual: The candidate search returned a brother’s transport detail alongside medication/access facts. A two-root, limit-5 search returned only the policy branch, with no signal that the personal branch had contributed nothing. The final staged search again returned the brother reference and clause fragments alongside valid review-state and candidate items. Exact regex enumeration also produced 43 third-party matches, requiring manual disposition.
- Workaround: Search each source Context independently, reconcile results against minimization/privacy/approval rules, then run ambiguity checks and require explicit human approval. Do not treat Search ranking as an inclusion decision.
- Severity: **P2 / medium-high** curation and privacy risk; the audit stayed fail-closed.
- Reproduction: **Yes, 3 semantic retrieval patterns plus one literal full enumeration**.

## T3-SUMMARY-CURATION — Narrative summaries blend facts that require different disclosure dispositions

- Expected: When a summary is used to prepare external sharing, relevant personal facts, third-party facts, uncertainty, and approval status remain separately inspectable so excluded information is not normalized into the candidate answer.
- Actual: The 2024/03 summary blended medication, clinic-standing, and brother-transport information in one narrative. The final recursive local summary was useful for orientation but still did not output an executable include/exclude/verify/approval disposition.
- Workaround: Use summaries only for orientation; return to exact Memories, Search/Find evidence, ambiguity reports, and explicit approval before any transfer.
- Severity: **P2 / medium-high** privacy-review risk.
- Reproduction: **Yes, 2 materially different summary scopes**.

## T3-CHUNK-TRACEABILITY — Chunk mutation receipt omits created Memory identifiers

- Expected: A successful split names every created UID so its output can be reused directly by `show`, `edit`, `move`, `reference`, and downstream quality checks.
- Actual: Clause chunking reported three outputs but did not provide their UIDs. A separate scoped `list` was required to discover `82272ee8`, `d98449a8`, and `bd30d689`.
- Workaround: Run `list` on the exact target Context and manually match generated text.
- Severity: **P2 / medium** output-reuse and auditability cost.
- Reproduction: **No, one actual multi-chunk mutation**; later sentence/paragraph attempts were intentional one-chunk no-ops.

## T3-CHUNK-SEMANTICS — Clause chunking destroys the safety frame of a disclosure candidate

- Expected: A split preserves enough statement context that “not shared,” the candidate fact, and all verification/approval conditions cannot be mistaken for independent approved facts.
- Actual: One withheld disclosure Memory became a label-only fragment, a medication fragment, and a verification fragment. A later `show` exposed the medication clause alone, and `find-ambiguities` flagged all three fragments as underspecified.
- Workaround: Do not clause-chunk safety-gated disclosure statements. Keep the status, fact, verification conditions, and approval boundary in one Memory or use a typed structure that preserves their relationship.
- Severity: **P1 / high** because downstream retrieval can surface the fact without its non-sharing boundary.
- Reproduction: **One mutation, independently observed by list, show, and all-three ambiguity results**; a second destructive mutation was not attempted.

## T3-RECURSIVE-OVERLOAD — Exhaustive quality checks bury sparse findings and impose extreme latency

- Expected: Recursive duplicate/redundancy analysis summarizes empty subtrees and foregrounds the few actionable groups, while preserving drill-down evidence.
- Actual: Recursive exact-duplicate analysis printed 46 mostly empty Context sections for zero groups. Recursive redundancy analysis took about 176 seconds, found one useful group in 2024/11, and surrounded it with 45 empty sections.
- Workaround: Use a broad pass only to identify a candidate child, then rerun on the exact child with direct scope. Round 4’s bounded 2024/11 check produced the useful group compactly.
- Severity: **P2 / medium** exploration-time and information-overload cost.
- Reproduction: **Yes, 2 sibling operations** on the same recursive workspace.

## T3-FIT-OPAQUE — Positive fit result has no evidence or next action

- Expected: A positive fit decision identifies which source facts fit which target rules, what was excluded or uncertain, and what review action follows—especially for a privacy-sensitive healthcare transfer.
- Actual: Every successful invocation printed only `FIT · YES` and the two target names. It exposed no supporting Memories, rationale, exclusions, uncertainty, or safe-transfer disposition.
- Workaround: Use Compare, Search, Find Ambiguities, and exact Memory review to reconstruct evidence. Never interpret YES as disclosure approval.
- Severity: **P2 / medium-high** decision-explainability and workflow risk.
- Reproduction: **Yes, 4 successful rounds**; round 1 separately failed because the chosen source root had no direct ordinary Memories.

## T3-OPTION-GRAMMAR — Related commands require repeated flag rediscovery

- Expected: Closely related search, semantic, and quality commands share learnable scope/output flag names or report deliberate differences in contextual help.
- Actual: `chunk --method sentence`, `compare --plain`, `find-redundancies --select`, `find --limit`, and `query --json` were all rejected. Recovery required operation-specific retries or abandoning the requested machine-readable/bounded output.
- Workaround: Use plural `sentences`; omit Compare/Query output flags; use `--direct` for redundancies; use `--all-results` or accept Find’s built-in display boundary.
- Severity: **P2 / medium** exploration and re-entry cost; all failures occurred before mutation.
- Reproduction: **Yes, 5 distinct entry-route failures**.

## T3-AMBIGUITY-PROVIDER — Valid ambiguity frame can fail on a provider NONE/question mismatch

- Expected: A valid 13-Memory direct frame either returns a complete ambiguity report or a stable typed provider error without wasting a full semantic turn.
- Actual: Round 4 took about 21 seconds, then failed because the provider “returned a question for NONE.” No partial result was published. The identical round-5 command succeeded and flagged 3/13, showing an intermittent provider/decoder boundary rather than invalid input.
- Workaround: Retry the exact frozen frame; if it succeeds, retain the successful full report and record the failed turn separately.
- Severity: **P2 / medium** reliability and latency cost; fail-closed publication behavior was correct.
- Reproduction: **No—1 failure followed by 1 successful identical retry**.

## T3-COMPARE-CLARITY — Comparison relationship language obscures source/target meaning

- Expected: A local-vs-granted comparison names each frame’s role and gives user-facing consequences for candidate selection.
- Actual: The round-4 output described one frame as an “exact specialization embedded within the reference,” language that was difficult to map back to the local workspace and public guidance. The final local-vs-local comparison was materially clearer.
- Workaround: Compare narrower, role-homogeneous local guardrail Contexts and keep the command’s left/right names visible while interpreting the prose.
- Severity: **P3 / low-medium** comprehension cost.
- Reproduction: **No, observed in 1 mixed local/granted comparison**.

## T3-STATUS-CURRENT-ONLY — Status cannot be audited safely in the parallel shared Profile

- Expected: A worker can inspect task-3 status with an explicit Context without changing the shared current selection.
- Actual: `mem status --context task-3` exited 2 because Status is current-only. Counting a successful Status attempt here would therefore report whichever world another worker left current.
- Workaround: Exclude Status from this 105-trial parallel phase. The root agent will serialize five task-3 Status attempts while it temporarily owns the shared current Context.
- Severity: **P2 / medium** parallel-audit and state-clarity limitation.
- Reproduction: **One parser probe here; deterministic CLI contract, repeated successful coverage delegated to root**.

## Safe world outcome

No healthcare disclosure was executed. The audit found useful candidate categories (current functional/access needs and possibly medication instructions) but also third-party transport, stale medication identity/currentness, missing recipient/purpose/retention scope, and no explicit approval. Because the recipient’s exact QUERY-only specification misrouted, the only safe result was to preserve candidates locally, record the failure, and stop before transfer.

