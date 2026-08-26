# Task-1 core audit issues

Study: `study-long-audit-20260823`  
World goal: apply the campus-construction change across the relevant campus-wiki areas.  
Evidence: `phase-core.json` contains five interleaved trials for each of the 21 parallel-safe operations (105 trials total). `status` is excluded because it has no explicit-Context route and must be exercised later under serialized current-Context control.

## Confirmed defects (reproduced at least twice)

### T1-GRANTED-ORDINARY-QUERY-MISROUTE — Critical — 2/2 relevant trials

- Expected: an ordinary Query with an explicit, readable granted Context should ground the answer in that exact Context.
- Actual: both `--context task-1/campus-wiki/temporary-parking --context-only` and the equivalent facility-updates trial reported `task-1/participant/construction-updates (no grounded answer found)` instead of the selected public target.
- Workaround: use `list`, `find`, and `show` on the granted Context, or use its canonical QUERY-only route when one is available. The ordinary explicit-grant route is not trustworthy for a grounded answer.
- User impact: the command succeeds while silently answering from the wrong workspace, so the failure can be mistaken for absence of evidence.

### T1-GRANTED-EXPORT-HANDOFF — High — 2/2 transfer trials

- Expected: a granted source displayed as readable/exportable should be usable by `copy` and `reference` when the local destination is explicit.
- Actual: both operations rejected the granted Memory UID as if it "does not exist locally."
- Workaround: embed the granted Context for a read-only working view, or manually re-add the fact locally (which loses original provenance).
- User impact: discovery and contribution cannot form a continuous workflow even though the catalog advertises the needed source capability.

### T1-CHUNK-NO-UID-HANDOFF — High — 4/4 split trials (plus 2 recovery trials)

- Expected: the receipt should identify every created chunk UID and explicitly state what happened to the original UID so the next operation can consume the result.
- Actual: receipts reported only counts. Later `list`/`find` calls were required to recover and manually disambiguate the new Memories.
- Workaround: immediately run an exact `list` or phrase `find`, then manually associate returned UIDs with each chunk.
- User impact: every successful split inserts at least one extra discovery step and makes automated output-to-input chaining fragile.

### T1-QUALITY-DESCRIPTIVE-AS-NORMATIVE — High — 2 scopes

- Expected: conflict analysis should distinguish a description of a likely user mistake (for example, visitors may expect a route to be open) from an asserted permission or policy.
- Actual: building and parking scans treated those expectation statements as normative claims and reported conflicts against the corrective guidance.
- Workaround: inspect every conflict reason and manually discard items whose evidence only describes a misconception.
- User impact: the quality scan directs attention toward false conflicts precisely where contributor text explains why an update is needed.

### T1-QUALITY-CONTEXT-ISOLATION — High — 3 scopes

- Expected: a contribution-oriented ambiguity scan should offer an explicit related/sibling evidence scope, or clearly state that it is judging one Context in isolation.
- Actual: event, parking, and route scans marked drafts as missing dates, locations, or rules that already existed in sibling construction-update Contexts.
- Workaround: manually reconcile results with sibling Contexts. `-a` is substantially broader than the task-local related set and is not a safe substitute.
- User impact: a goal distributed across several wiki areas produces systematic false positives and repeated rereading.

### T1-QUALITY-SCOPE-GRAMMAR — Medium — 2 operations

- Expected: related `find-*` quality commands should share understandable names for exact versus descendant scope.
- Actual: `find-ambiguities` rejected `--direct`, while `find-duplicates` rejected `--context-only`; neighboring commands use those terms for similar boundaries.
- Workaround: consult each command's help and memorize its operation-specific spelling.
- User impact: otherwise reasonable commands fail before work begins and are difficult to generate reliably across the suite.

### T1-SEARCH-INVERSE-MISS — Medium — 2 inverse queries

- Expected: semantic searches phrased as the obsolete or opposite guidance should rank the explicit normal/open-state facts needed to discover a contradiction.
- Actual: both trials returned no primary matches and only generic related items, missing the explicit open-garage evidence.
- Workaround: search for exact likely phrases, then use `query` or `compare` after discovering candidate UIDs.
- User impact: discovery depends on already knowing the vocabulary of the fact being sought.

### T1-QUERY-REFERENCE-OVERLOAD — Medium — 2 broad queries

- Expected: the concise answer and the most decision-relevant citations should remain immediately visible, with full evidence available on demand.
- Actual: useful answers were followed by 56 and 62 fully rendered Reference rows (roughly 4,000+ output tokens), burying the next action.
- Workaround: use narrower Contexts or switch to `summarize`/`compare`; otherwise manually scan or post-process the output.
- User impact: correct evidence becomes costly to review and difficult to reuse as the next command's input.

### T1-CTX-OVERLOAD — Medium — 5/5 trials

- Expected: task-local discovery should support a filter or focused subtree view.
- Actual: `contexts` always printed every world and grant (about eight terminal screens), even when the user only needed task-1.
- Workaround: terminal-search the full catalog and manually extract task-1 names.
- User impact: the same broad catalog must be reread throughout early, middle, and late work.

### T1-TRANSFER-DISCOVERABILITY — Medium — 3 operations

- Expected: when a plausible `SOURCE TARGET` form is rejected, the error should show the accepted `--from`/`--into` form for the invoked transfer operation.
- Actual: `copy`, `reference`, and `embed` produced generic positional-argument errors without the corrected route.
- Workaround: open help separately and re-enter the command with operation-specific options.
- User impact: simple source-to-target actions require repeated help lookup and full command re-entry.

### T1-PERMISSION-CONTRADICTION — Medium — 2 presentation surfaces

- Expected: readable granted-Context views should present one consistent effective capability set.
- Actual: the Context catalog showed READ/QUERY/EDIT/DELETE/EXPORT, while `list` combined broad CREATE/UPDATE/DELETE text with a `READ ONLY` label.
- Workaround: assume least privilege and rely on each operation's final authorization check.
- User impact: the user cannot decide from the discovery screen which contribution action is actually allowed.

## Single-observation candidates

These need a second independent reproduction before being treated as confirmed.

### T1-RECURSIVE-LIST-OVERLOAD — High candidate — 1 trial

- Expected: a recursive local list should make embedded/granted traversal explicit and keep the requested task-local result reviewable.
- Actual: it emitted about 786 lines, traversed into embedded granted material, and exceeded the capture limit.
- Workaround: list exact children individually and track them outside the command.

### T1-QUERY-SCOPE-BLEED-CANDIDATE — High candidate — 1 trial

- Expected: `-c task-1/campus-wiki -r` should cite evidence inside that selected public subtree.
- Actual: the Reference set also contained a Memory from `task-1/participant`.
- Workaround: inspect every Reference Context and rerun against exact leaves.

### T1-COMPARE-SAME-CONTEXT-MEMORY — Medium candidate — 1 trial

- Expected: two distinct Memory selectors in the same Context should be comparable.
- Actual: Compare rejected them because their Context names were not distinct.
- Workaround: move/copy one Memory to a temporary local Context, or compare larger Context frames.

### T1-ONE-TO-MANY-REDUNDANCY-CANDIDATE — Medium candidate — 1 trial

- Expected: redundancy analysis should recognize a copied whole plan whose claims are collectively covered by its three chunks.
- Actual: no redundancy group was returned.
- Workaround: compare the whole Memory and chunks manually.

### T1-OVERLAPPING-REACH-CANDIDATE — Medium candidate — 1 trial

- Expected: embedding a lexical descendant into its ancestor should warn that recursive and embedded reach overlap.
- Actual: the embed succeeded without explaining duplicate traversal risk.
- Workaround: avoid embedding a Context already reachable through the local name hierarchy.

### T1-LIST-COUNT-LABEL — Low candidate — 1 trial

- Expected: the header should distinguish owned Memories, Memory References, Context References, and embedded Contexts.
- Actual: it said `3 memories` while the body mixed one Memory, two Memory References, a Context Reference, and embedded Contexts.
- Workaround: count typed rows rather than trusting the header noun.

### T1-QUALITY-REPORT-OVERLOAD — Medium candidate — 1 trial

- Expected: a 14-item ambiguity review should prioritize actionable items and allow compact drill-down.
- Actual: all 14/14 items were expanded into more than 3,000 tokens, with many isolation-driven false positives.
- Workaround: capture the report externally and review one item at a time.

## Excluded parallel probe

### T1-STATUS-NO-EXPLICIT-TARGET — workflow boundary — 2 syntax probes

- Expected for parallel auditability: `status` would accept a canonical explicit Context without changing shared current state.
- Actual: both a positional Context and `--context` were rejected with exit 2.
- Workaround: the root audit must serialize Profile current-Context ownership and run the five valid status trials separately.
- Coverage note: these probes are evidence only and are not counted among the 105 successful core-audit trials.
