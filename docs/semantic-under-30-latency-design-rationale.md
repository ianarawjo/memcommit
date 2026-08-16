# Semantic execution under 30 seconds: design rationale

## Status

This note records an exploratory latency direction. It does not enable staged
execution, change a provider or model, relax an existing semantic contract, or
authorize hidden provider calls. The evaluation-only experiments below retain
their raw responses and publish no production Compare result.

The initial design workload is the existing 300-Memory Compare case. The
discussion starts with Compare because it exposes the largest combination of
global reasoning, exhaustive disposition, relation reconstruction, and verbose
structured output. Any transfer to another operation must preserve that
operation's own invariants rather than copying Compare's defaults.

## Goal and measurement boundary

The target is an actionable semantic result within 30 seconds for a 300-item
workload. For the first benchmark, "actionable" means that:

- the provider result has arrived;
- the host has decoded and validated it;
- all 300 frozen input items have an explicit or contract-defined disposition;
- required reconciliation has completed; and
- the first reviewable report can be displayed without publishing a partial
  result.

Human review time is outside the 30-second boundary. Optional narrative,
expanded explanations, and follow-up investigation may occur after the first
actionable result only when they are visible, separately initiated work. They
must not be hidden calls required to make an apparently complete result true.

Each experiment should report at least two latency measures:

1. **Critical-path wall time**: time from semantic execution start to the first
   actionable result.
2. **Total provider work**: number of provider calls and the sum of their
   durations. Parallel calls may reduce wall time while increasing total work,
   rate-limit pressure, and cost.

The strict gate is the slowest of three repeated runs at or below 30 seconds,
not merely a favorable median. Cold-start inclusion must be stated with every
result.

## Research premise: one Context is interpreted together

The paper's semantic unit is a Context, not an independently routed sequence
of Memories or criteria. When an operation claims to interpret one Context,
every frozen Memory in that Context must remain available in the same semantic
frame so neighboring items can qualify, disambiguate, or constrain one
another. An optimization must not silently replace that premise with
item-at-a-time or criterion-at-a-time inference merely because those calls are
smaller.

Background preparation is compatible with this premise. A complete
Context-bound analysis may be computed before the foreground command, cached
by exact Context revision, and projected immediately when the revision still
matches. Add, remove, Sever, or Forget maintenance may invalidate and repair a
derived artifact internally, but an artifact presented as complete must still
mean that the whole current Context was interpreted together. Candidate-only,
incremental, or projected results are distinct experimental approximations
unless a later whole-Context reconciliation restores that invariant.

User-study fixtures may therefore start with prewarmed exact-revision
artifacts. Such a condition measures foreground interaction latency, not a
claim that the hidden precomputation completed within 30 seconds. Reports must
record foreground latency and precomputation or convergence work separately.

## Deferred Forget and Sever prewarm plan

Forget and Sever remain future work while Compare establishes the cache and
projection method. Their eventual optimization must retain the one-Context
premise above.

For Forget, 300 independent `1:1` provider calls are not an authoritative fast
path. They could overlap and lower foreground wall time in a synthetic test,
but each call would lose neighboring Memory context, repeat the same
instruction, multiply total provider work, and require a new reconciliation
contract. The failed full-context Compare parallel experiment also shows that
overlap alone is not evidence of a valid semantic speedup. Per-Memory calls may
later serve as a diagnostic approximation, but not as the operation whose
result is described as interpreting the Context together.

The leading Forget experiment keeps the complete Source and one
instruction in one turn while requesting only a fixed-length action vector
(`KEEP`, `TRANSFORM`, or `DROP`) plus replacement text for the sparse
`TRANSFORM` positions. An exact Source-revision plus exact-instruction artifact
may be prewarmed for a fixed study fixture. Arbitrary future instructions
cannot be fully predicted, so a product implementation may precompute only
Context-internal semantic state and must still perform instruction-specific
work. A lower reasoning effort is a separate axis, not part of the cache or
output-representation claim. The evaluation-only implementation and its
fail-closed host reconstruction are specified in
[`forget-compact-output-design-rationale.md`](forget-compact-output-design-rationale.md).

For Sever, cache the complete whole-frame decision artifact by exact Source
revision, exact Criteria revision, semantic ruleset, model identity, and
reasoning setting. An unchanged request is a direct cache hit. Removing Source
members may support a provider-free projection of surviving decisions for an
explicit fast study condition; transformed content, changed Criteria, or an
artifact advertised as newly complete still requires whole-Context refresh or
an explicitly named approximate status. Add is not a timed user-study path.
In a later product path it should invalidate the artifact and schedule a
debounced whole-Context refresh rather than treating an item-at-a-time decision
as authoritative.

This section authorizes only the separate compact-output Forget evaluation
runner. It does not change production Forget, apply a benchmark result, enable
staged Forget, or authorize a Sever provider run.

## Existing evidence

The following figures were observed in earlier local study sessions. They are
historical baselines, not controlled measurements from a single benchmark run.

| Operation and observed frame | Provider time | End-to-end time or output |
| --- | ---: | --- |
| Provider connection, 52 observations | 0.024 s median | 0.036 s maximum |
| Query, recent small result | 5.6-9.5 s | — |
| Find, about 64 KB input and a very small answer | 12.2-44.5 s | about 188 output characters in one observation |
| Update, 84,658 input characters | 118.1 s | 219.4 s end to end |
| Compare, about 87.4 KB input | 229.5-304.3 s | 42.6-58.2 KB provider output |
| Compare, 113,198 input characters | 608.6 s | first attempt timed out at 600 s |
| Meld | 113-529 s | response incorporation about 455-459 s |
| Forget, larger frames | 126-308 s | — |
| Sever, 66,553 input characters | 296.8 s | 1,082.4 s end to end |
| Impact/Atomize, 25,064 input characters | 60.2 s | 657.3 s end to end |

The Task 3 incremental-Forget run gives the retained Forget range a concrete
whole-Context interpretation. Four successive one-Context turns processed
`300`, `251`, `231`, and `187` Source Memories in 308, 271, 230, and 126
provider seconds. Their responses contained 71,681, 68,155, 59,150, and 34,282
characters. Even the smallest retained turn was therefore not a 20-30-second
operation; short per-Memory semantic-gate cases are not representative of this
complete-coverage command.

The later compact-output corpus matrix kept the full 300-Memory input and one
whole-frame call while removing repeated Source text and per-Memory prose from
the response. Thirty-five of 64 model/reasoning-by-instruction cells completed
within 30 provider seconds; Luna none did so in 8/8, Terra none and Sol none in
7/8 each. This is direct evidence that output obligation can be a dominant
latency factor for classification-heavy Forget requests. It is not a complete
solution: model outputs ranged from keep-all to delete-all for `SENSITIVE`, and
the sparse EDIT field required 324 conservative cross-field repairs across 25
cells. Full tables and interpretation boundaries are in
[`outputs/forget-latency/compact-corpus-matrix-v1/`](../outputs/forget-latency/compact-corpus-matrix-v1/README.md).

The prototype subsequently adopted `gpt-5.6-sol` reasoning `none` as the
Forget-only provider policy. It was the least obviously collapsed compromise
in that unlabelled matrix: seven of eight compact cells met 30 seconds with a
19.9-second median, while Luna none kept all `SENSITIVE` items and Terra none
deleted all of them. The selection does not change other operations, skip
Forget review, establish semantic accuracy, or promote the compact evaluation
contract into production. It only fixes the model/reasoning axis for current
Forget work while those separate boundaries remain.

These observations support three limited conclusions:

- Provider connection setup is not the material bottleneck in the measured
  runs.
- Output obligation is a credible latency factor: recent Compare runs returned
  tens of thousands of characters, while Find sometimes processed a large
  input with a very small output in under 45 seconds.
- Output size alone does not explain the result. Compare also performs global
  grouping and relation classification, so the observations do not establish
  that compact output by itself can meet 30 seconds.

The stored 300-item Compare result contains 109 relations and five issues. Its
persisted relation JSON is about 65 KB. Even a reduced
`{kind, members}` representation is about 35 KB. Removing DISTINCT relations
still leaves 66 relations covering 249 of 300 members, so a sparse-positive
relation list is not especially sparse for this workload. A positional or
indexed decision representation is therefore a more promising compression
candidate than merely omitting DISTINCT records.

The later controlled medium baseline gives a more exact relation-shape view.
Its production exhaustive analysis returned 101 primary groups: 34 one-sided
DISTINCT groups and 67 cross-source groups. The cross-source shapes were 37
`1:1`, two `1:N`, five `N:1`, and 23 true `N:M` groups. The `N:M` groups were
nine `2:2`, five `3:3`, two `4:4`, and one each of `2:3`, `3:2`, `5:4`, `5:7`,
`6:6`, `7:7`, and `9:8`. There was no very large `50:50`-style group, and the
largest contained 17 members, but the 23 `N:M` groups collectively covered 156
of the 300 source memberships. They are therefore locally bounded in shape but
not negligible as a maintenance surface. The compact same-input condition
returned a similar 26 `N:M` groups, while differing semantically in individual
placements.

## Is one-shot execution the bottleneck?

Not yet proven. One-shot execution is both an advantage and a constraint.

Its advantages are important:

- every source item is visible in the same semantic frame;
- cross-block relations cannot be lost because there are no blocks;
- candidate generation cannot silently reduce recall;
- one response is validated against one complete contract; and
- no secondary reconciliation semantics are needed.

Its costs are also important:

- the entire workload sits on one serial critical path;
- one response must satisfy a large, coupled, exhaustive output contract;
- one slow or failed call loses all progress; and
- independent subproblems cannot use provider concurrency.

The working conclusion is therefore narrower: the current exhaustive one-shot
contract is a likely contributor to latency, but it is not yet identified as
the sole bottleneck. The experiments must isolate representation cost from
reasoning topology and model choice.

## Keep three changes separate

The following changes must be evaluated independently before they are
combined:

1. **Lossless representation compression** changes how the same semantic
   decision is encoded. It must reconstruct the existing typed result without
   dropping information.
2. **Semantic approximation** changes what the provider is required to notice
   or explain. Candidate filtering, default dispositions, and deferred
   narrative belong here and may change recall or review quality.
3. **Staged or parallel execution** changes how work is scheduled. It requires
   an operation-owned reconciler and cannot be justified merely because a
   one-shot frame exceeded a size or time budget.

This separation prevents a fast result from being attributed to "parallelism"
when it actually came from weaker coverage, or to "compact JSON" when it
actually came from a faster model.

## Candidate A: exhaustive one-shot control

The current full Compare request and response remain the control. It preserves
the existing behavior and supplies the frozen quality reference for subsequent
experiments. Historical runs are useful orientation, but a controlled series
must use the same frozen 300 inputs, prompt contract, model identity, and host
validation.

This candidate is not expected to reach 30 seconds. It remains necessary to
measure which relations, issues, and explanations faster candidates omit or
change.

## Candidate B: compact one-shot decision plane

The first implementation experiment should keep the complete input and one
provider call while replacing repeated identifiers and prose-heavy relation
objects with a compact, exact decision plane. This is the cleanest way to test
whether output obligation is a primary cause.

A possible Compare wire representation is:

```json
{
  "left_groups": [1, 0, 5, 5],
  "right_groups": [0, 1, 5, 0],
  "group_kinds": ["E", "C", "S", "E", "C"]
}
```

The actual contract would use the frozen canonical order of both input frames.
`0` means DISTINCT. A positive integer identifies a cross-frame relation group,
and `group_kinds[group_id - 1]` supplies its type. The host, not the provider,
would reconstruct durable relation identifiers, member objects, ordering, and
report presentation.

Before such a format is usable, local validation must prove:

- both vectors have exactly the expected length;
- every position corresponds to exactly one frozen input item;
- all group identifiers are valid and contiguous, or the contract explicitly
  defines another canonical rule;
- every nonzero group satisfies the allowed cross-frame membership shape;
- every kind code is recognized;
- reconstructed source coverage is exactly 300 of 300;
- no unknown or duplicate source identity can be introduced; and
- issues that cannot be represented by the vectors remain explicit in a
  bounded issue plane.

Positional encoding has a specific risk: a shifted or truncated vector can
misassign every later decision. Exact length validation catches truncation but
does not by itself prove semantic alignment. The prompt and decoder therefore
need stable, visible ordinals, and this representation should first be treated
as an experimental fast contract rather than a transparent replacement for
identifier-bearing rows.

Compact one-shot execution intentionally does not test concurrency. If it
misses the latency target, that result is still useful because it separates
large-output cost from the cost of global reasoning.

## Candidate C: layered parallel Instant execution

A faster model may be used as a mesh of concurrent judges rather than as one
large call. "Layered" here means a small number of dependency stages; calls
inside a stage overlap. Sequentially stacking many fast calls would add their
latencies and is unlikely to meet the target.

The candidate pipeline is:

1. **Freeze and index locally.** Freeze all source identities, canonical
   ordinals, model identity, and operation contract before any provider call.
2. **Generate complete candidate exposure locally.** Build shards, candidate
   pairs, or a complete block matrix. This step schedules exposure; it does not
   prove that the final semantics are complete.
3. **Run compact judgments concurrently.** Each provider call returns only the
   decision and sparse evidence required by its assigned exposure.
4. **Build relation components locally.** Merge compatible edges and identify
   incompatible, overlapping, or underdetermined components without publishing
   a partial Compare result.
5. **Reconcile ambiguous components concurrently.** Only components that
   cannot be resolved by deterministic invariants receive a second provider
   turn.
6. **Validate and publish once.** Reconstruct the full typed Compare result,
   validate exhaustive disposition and issues, then expose the first actionable
   report.
7. **Produce optional narrative separately.** Expanded prose is explicit and
   outside the required critical path.

Its approximate critical path is:

```text
T_actionable ~= T_host_prepare
             + max(T_parallel_judgment_calls)
             + T_host_component_build
             + max(T_parallel_reconciliation_calls)
             + T_host_validate
```

The formula does not include the sum of all provider durations. That sum is a
separate cost and capacity measure.

The central unresolved problem is candidate completeness. Naively partitioning
300 items can miss a relation whose members land in different blocks. A
complete block matrix preserves exposure but may create too much duplicated
input and too many calls. Retrieval-based pruning is faster but lowers recall
unless the operation can justify and measure its candidate generator. Because
Compare promises exhaustive disposition and cross-frame relations, the current
production strategy must remain disabled until an operation-owned reconciler
preserves those properties.

## Candidate D: hybrid proposal and audit

An Instant-class model could produce the first compact proposal while a slower,
stronger model audits only ambiguous or high-risk components. This is useful
only if the stronger audit is either:

- narrow enough to remain inside the same 30-second critical path; or
- explicitly presented as post-result verification rather than silently
  required completion work.

A full sequential strong-model audit would likely reproduce the existing
latency problem. It is therefore not the default fast path.

## Model terminology and access boundary

OpenAI documents `chat-latest` as the API alias for the latest ChatGPT Instant
model and lists Structured Outputs support. The alias changes as the underlying
snapshot changes, and the same documentation recommends GPT-5.6 for production
API use. See the official
[Chat Latest model documentation](https://developers.openai.com/api/docs/models/chat-latest).

OpenAI describes GPT-5.6 Luna as a cost-sensitive, high-volume model with
reasoning support. Luna and ChatGPT Instant are not interchangeable names or
necessarily equivalent latency profiles. See the official
[GPT-5.6 Luna documentation](https://developers.openai.com/api/docs/models/gpt-5.6-luna).

The current memcommit provider path uses the installed Codex CLI rather than a
direct API adapter. API documentation does not establish that this provider can
select `chat-latest`, preserve a stable underlying snapshot, or sustain the
desired concurrency. Model availability, exact resolved identity, rate limits,
and structured-output behavior must be verified before an Instant experiment.
That verification is intentionally deferred; it was not performed for this
note.

Any result using a moving alias is exploratory unless the resolved model
identity can be recorded. Model selection must be an explicit experiment axis,
not silently combined with a schema or scheduling change.

## A transferable output architecture

The useful common method is not "remove JSON." It is to retain strict machine
validation while separating four output planes:

1. **Decision plane**: one compact disposition per frozen item, or the smallest
   exact structure that can reconstruct it.
2. **Sparse payload plane**: replacement text, relation-specific evidence, or
   other content only where the decision requires it.
3. **Issue plane**: ambiguity, conflict, or missing-information records that
   require review.
4. **Narrative plane**: overview, explanatory prose, and expanded rationale,
   generated locally when derivable or requested explicitly when semantic
   explanation is required.

This removes repeated field names, identifiers, and prose from the critical
path without abandoning a typed result. Each operation owns its default
disposition and reconstruction rules.

| Operation | Possible compact default | Transfer boundary |
| --- | --- | --- |
| Compare | DISTINCT | Cross-frame groups and issues still require exact reconciliation. |
| Meld | PRESERVE | Application-ready merged content and cross-source relations must survive. |
| Update | UNCHANGED | Every target needs an exact final disposition and provenance. |
| Atomize | KEEP original | Hierarchical or cross-item reductions need operation-owned reconciliation. |
| Forget | KEEP | The complete Source and instruction must remain one frame under current semantics. |
| Sever | DROP may be privacy-safe | It can destroy utility and does not authorize partitioning the whole frame. |
| Quality finders | NO FINDING | Global-quality checks need a defined reconciliation rule. |

Forget and Sever are deliberately not candidates for naive layered splitting.
Their present contract requires the complete frozen Source and criterion frame
in one provider turn because neighboring Memories may change a keep,
transform, or drop decision. Compact one-shot output may transfer to them, but
partitioning would be a semantic change.

Find already has retrieval-shaped behavior and is not evidence that relation
operations can use the same batching unchanged. Summarize and Rationale are
holistic reductions; their fast forms need operation-specific quality criteria
rather than an item-disposition vector.

## Safety and compatibility boundaries

- Existing production semantic behavior remains unchanged while this is an
  experiment design.
- `provider.complete()` remains one bounded provider-call primitive. Planning
  and reconciliation belong under `memcommit.semantic_execution`.
- No over-budget frame may be silently truncated.
- No failed or incomplete batch may publish a partial result.
- Frozen inputs must be exposed according to the declared strategy, and the
  operation must validate its final whole result.
- Compression must be lossless relative to the declared contract. Any quality
  concession must be named and measured as approximation.
- Defaults are operation-owned. An omitted row must never acquire a generic
  cross-operation meaning.
- Provider calls, model changes, follow-up explanation calls, and fallbacks
  must remain visible in execution records.
- Compare, Meld, Update, Conflict, and Atomize remain ineligible for staged
  execution until their adapters preserve exhaustive disposition,
  cross-block relations, issues, provenance, and application readiness.
- Forget and Sever remain `WHOLE_FRAME_ONLY` under their current semantics.

## Experiment ladder

The ladder separates the causal axes. E0 and the first one-run A/B diagnostic
are now implemented; repeated acceptance runs and later model or scheduling
conditions remain future work:

1. **E0 — local representation round trip.** Encode and decode the stored
   300-item result without a provider. Prove exact reconstruction, measure byte
   size, and fuzz vector length, ordering, group, and issue validation.
2. **E1 — frozen exhaustive control.** Record three runs of the unchanged
   300-item Compare contract with an exact model identity where possible.
3. **E2 — compact one-shot, same model.** Change only the response contract and
   repeat three times. This tests output obligation.
4. **E3 — compact one-shot, Instant candidate.** Change only the model after
   access and identity are verified. This tests model latency and quality.
5. **E4 — layered parallel Instant candidate.** Introduce staged exposure and
   reconciliation. Test bounded concurrency levels such as 4, 8, and 16 while
   recording both critical-path time and total provider work.
6. **E5 — operation transfer.** Move only the independently successful method
   to another operation whose invariants and default disposition are already
   specified.

The order matters. Jumping directly from the current exhaustive contract to a
parallel Instant mesh would make it impossible to tell whether improvement
came from model choice, output compression, approximation, or concurrency.

## Implemented one-run A/B diagnostic

`memcommit.eval.compare_latency_ab` provides an evaluation-only runner for the
canonical English Task 2 `advisor1` versus `advisor2` frame. It constructs the
same frozen 150+150 `ComparisonInput` for both calls and defaults to the
configured Codex model with explicit `medium` reasoning. A normal invocation
is:

```console
python -m memcommit.eval.compare_latency_ab \
  --model gpt-5.6-sol \
  --reasoning medium \
  --output outputs/compare-latency-ab/RUN.json
```

Condition A calls the production `analyze_comparison()` function unchanged.
Condition B remains one-shot and includes the same complete provider-visible
Memory payload. It changes only the prompt and response contract to require:

- one fixed-length positional group-ID vector per side;
- one ordered `{kind, note}` row per used group;
- an empty note for straightforward EQUIVALENT, COMPATIBLE, and DISTINCT
  groups;
- one concise note for every SCOPED, CONFLICT, and UNCLEAR group; and
- the existing issue detail, except that compact integer group IDs replace
  repeated relation keys.

The host rejects a vector of the wrong length, a missing or unused group, an
out-of-range group ID, an invalid one-side/cross-side shape, a missing required
note, or an unresolved group without a REQUIRED issue. It then derives status,
relation UIDs, member objects, source coverage, summaries, reasons, overview,
and category-report placeholders and reconstructs a validated
`ComparisonAnalysis`. These generated prose fields exist only to prove current
typed compatibility; they are not presented as provider-authored semantic
explanation and the compact result is not saved to a production comparison
store.

The final atomic ledger retains the raw responses, prompt/schema/response
digests and sizes, provider and validation durations, normalized relation
ledgers, and provider identity. The baseline prompt suffix must match the
compact semantic payload byte for byte for the experiment to be valid. Quality
is reported as agreement rather than accuracy because the one-run production
result is not ground truth: source relation-kind agreement, exact source group
and kind agreement, exact relation-signature overlap, and pairwise same-group
precision/recall/F1 are all recorded.

One A/B pair is only a feasibility and causal-direction diagnostic. It does not
satisfy the three-run acceptance gate below and cannot by itself authorize a
production contract change.

## First medium A/B result — 2026-08-10

One baseline-first diagnostic completed with `codex_chatgpt:gpt-5.6-sol`,
reasoning `medium`, and a 900-second per-call safety timeout. Both calls were
contract-valid and the baseline prompt suffix matched the compact semantic
payload byte for byte. The common provider-visible payload contained all
150+150 Memories and was 75,590 characters. The complete raw responses and
normalized ledgers are retained in
`outputs/compare-latency-ab/20260810-gpt-5.6-sol-medium-a-then-b.json`.

| Measure | A — exhaustive | B — compact vector | Change |
| --- | ---: | ---: | ---: |
| Prompt characters | 79,240 | 78,585 | -0.8% |
| Output-schema characters | 7,139 | 1,389 | -80.5% |
| Response characters | 55,392 | 11,285 | -79.6% |
| Provider completion | 341.945 s | 170.046 s | -50.3% |
| Validated relation groups | 101 | 105 | +4 |
| Required issues | 5 | 6 | +1 |

The compact call was 2.01 times faster, demonstrating that output obligation
is a material latency contributor. It still took 170 seconds, however, so
lossless host reconstruction and shorter model output alone do not approach
the 30-second target. The remaining time is consistent with substantial
full-frame ingestion and global grouping work, although this non-streaming
provider does not expose time-to-first-token or hidden reasoning-token timing
to separate them precisely.

The output composition shows where the direct reduction occurred. In A, the
serialized relation array used 29,369 characters and the repeated 300-row
`source_assignments` ledger used 21,452; issues used 3,274 and overview plus
category reports only about 1,228. In B, both fixed vectors together used 876
characters, 105 `{kind, note}` groups used 7,014, and six issues used 3,329.
Thirty-one compact groups carried a nonempty note. This indicates that removing
repeated assignments and per-relation summary/reason prose mattered much more
than removing the five top-level report paragraphs alone.

The two results were structurally valid but not semantically identical:

- source relation-kind agreement was 76.3%;
- exact source group-and-kind agreement was 55.0%;
- 57 exact relation signatures overlapped;
- pairwise same-group precision was 0.884, recall was 0.765, and F1 was 0.820;
- A returned 13 COMPATIBLE, 5 CONFLICT, 34 DISTINCT, 20 EQUIVALENT, and 29
  SCOPED groups; B returned 23, 6, 34, 17, and 25 respectively.

A is a stochastic comparison result, not reviewed ground truth, so these are
agreement measures rather than compact-output accuracy. Nevertheless, the
difference proves that a representation can be losslessly decoded while still
changing the model's inference behavior: removing required explanations and
changing the response topology altered some grouping and kind decisions. The
compact contract therefore cannot yet replace production Compare as a purely
mechanical optimization.

The result supports two next hypotheses without selecting either one yet:

1. repeat A/B to estimate ordinary same-contract variance before attributing
   all disagreement to compact output; and
2. evaluate full-context responsibility splitting or a faster model because
   compact one-shot latency remains more than five times the 30-second target.

## Minimal-I/O medium result — 2026-08-10

A third evaluation-only condition tested the smallest useful one-shot envelope
before changing reasoning effort or model. C preserved every ordered content
string from both 150-Memory frames but represented provider input as only two
arrays, `a` and `b`. It omitted aliases, positions, content digests, frame
metadata, relation notes, and provider-authored issues. Its output contained
only fixed group-ID vectors and one-letter kind codes. The host reconstructed
the current typed analysis and generic unresolved review markers.

The raw C response and its comparisons with the retained A/B normalized
ledgers are stored in
`outputs/compare-latency-ab/20260810-gpt-5.6-sol-medium-minimal-io.json`.

| Measure | A — exhaustive | B — compact output | C — minimal I/O |
| --- | ---: | ---: | ---: |
| Complete content items | 300 | 300 | 300 |
| Provider payload characters | 75,590 | 75,590 | 35,005 |
| Prompt characters | 79,240 | 78,585 | 36,482 |
| Output-schema characters | 7,139 | 1,389 | 350 |
| Response characters | 55,392 | 11,285 | 1,637 |
| Provider completion | 341.945 s | 170.046 s | 140.225 s |
| Relation groups | 101 | 105 | 156 |

C reduced prompt size by 53.6% and response size by 85.5% relative to B, but
provider completion improved by only 17.5%. Relative to A, C was 2.44 times
faster and returned 97.0% fewer response characters, yet it remained 4.67
times slower than the 30-second target. Local reconstruction and validation
took about 0.014 seconds, so host decoding is immaterial at this scale.

This is the strongest evidence so far that medium-effort global grouping, not
JSON serialization alone, dominates the remaining critical path. The provider
interface is non-streaming and does not expose hidden reasoning duration, so
the experiment cannot prove an exact time allocation. It does show that
removing another 40,585 prompt characters and 9,648 response characters saved
only about 30 seconds after B.

C was structurally valid and covered 300 of 300 inputs. It produced 156 groups:
60 COMPATIBLE, 18 CONFLICT, 33 DISTINCT, 30 EQUIVALENT, and 15 SCOPED. Its
agreement with A and B was lower than their mutual agreement. This does not
establish that C is less accurate because none of the stochastic runs is
reviewed ground truth, but it does show that a very terse task representation
changes grouping behavior. The current conclusion concerns latency causality,
not semantic acceptance.

## Reasoning-axis result — 2026-08-10

The controlled condition preserved C's exact input, prompt, schema, and output
contract and changed only the Codex reasoning-effort setting. Current OpenAI
GPT-5.6 documentation names `none` as the lowest-latency baseline and `low` as
the latency-sensitive reasoning setting; it does not name `minimal` as a
GPT-5.6 effort. The local memcommit adapter therefore exposes `none` for this
documented GPT-5.6 setting while retaining `minimal` only for older configured
models.

This fixture is `150:150`, or 300 total Memories. It is not a `300:300`
600-Memory fixture. Duplicating the existing inputs merely to reach 600 would
change the semantic workload and produce a misleading latency result, so that
larger condition remains unmeasured.

| Effort | Provider time | Contract | Observation |
| --- | ---: | --- | --- |
| `medium` | 140.225 s | Valid | Retained C control |
| `none`, diagnostic 1 | 23.342 s | Invalid | Call completed, but a mistaken reference-ledger path prevented retaining the response ledger |
| `none`, diagnostic 2 | 23.563 s | Invalid | `b` referenced a group ID not represented by `k` |
| `low` | 149.947 s | Invalid | `b` ended with group ID `670000000000`, outside the 86-entry `k` vector |

Both `none` calls met the 30-second wall-time target and failed the same typed
reconstruction boundary. They therefore produced no actionable Compare
result. The retained `none` run sent all 300 Memories in order in a
36,482-character prompt and returned 1,668 characters, but the host could not
assign a valid relation kind to every referenced group. `low` missed both
gates: it was 9.722 seconds slower than the valid `medium` control and was also
structurally invalid.

This rejects reasoning-effort reduction alone as the next Compare strategy.
The effort-to-latency relationship was not monotonic on this workload, and the
only setting below 30 seconds twice failed complete disposition. Do not spend
more study-preparation calls repeating this axis unless the output contract or
model changes and receives its own explicit evaluation condition. Semantic
agreement remains descriptive rather than a gate until reviewed ground truth
or an explicit acceptable-loss threshold exists, but structural completeness
is non-negotiable.

## Full-context parallel medium result — 2026-08-10

The next evaluation kept `gpt-5.6-sol` and reasoning `medium` unchanged and
tested responsibility splitting without reducing provider visibility. Six
workers each received the same complete ordered 150+150 content arrays. Their
only difference was a frozen, disjoint 50-position ownership range. Each
worker returned two fixed 50-row vectors: the canonical global anchor for each
owned position and a relation kind only when the position was itself that
anchor. The host allowed no retry or provider reconciliation and attempted one
deterministic merge only after all six calls completed.

The invocation was:

```console
python -m memcommit.eval.compare_parallel_anchor \
  --model gpt-5.6-sol \
  --reasoning medium \
  --batch-size 50 \
  --max-workers 6 \
  --reference-ledger \
    outputs/compare-latency-ab/20260810-gpt-5.6-sol-medium-minimal-io.json \
  --output \
    outputs/compare-latency-ab/20260810-gpt-5.6-sol-medium-parallel-anchor-batch50.json
```

The raw worker vectors, timings, and failed merge receipt are retained in the
named output ledger. All six provider calls completed without a provider or
local vector-schema error, but the global merge was invalid. Therefore this
run produced no actionable Compare result and its actionable latency is
recorded as `null`; 135.609 seconds is the observed time to discover the failed
global state.

| Measure | C — one-shot minimal I/O | P — 6 × 50 parallel | Change |
| --- | ---: | ---: | ---: |
| Complete content items visible per call | 300 | 300 | unchanged |
| Provider calls | 1 | 6 | +5 |
| Prompt characters per call | 36,482 | 36,746–36,749 | approximately unchanged |
| Prompt characters, total | 36,482 | 220,490 | 6.04× |
| Output-schema characters, total | 350 | 1,620 | 4.63× |
| Response characters, total | 1,637 | 2,262 | +38.2% |
| Provider seconds, sum | 140.225 | 533.822 | 3.81× |
| Observed parallel-stage wall time | 140.225 | 135.609 | -3.3% |
| Actionable result | valid | none | merge rejected |

Individual calls ranged from 61.948 to 135.608 seconds, with a median of
85.046 seconds. Their sum divided by stage wall time was 3.94, so provider work
did overlap materially. The slowest worker nevertheless controlled the
critical path and nearly equalled the one-shot C latency. This one run cannot
separate ordinary latency variance from shared-capacity or concurrency effects,
and current official model documentation does not establish an account-specific
Codex CLI concurrency guarantee. It does establish that simply making six
simultaneous calls did not approach 30 seconds in this environment.

The semantic failure was cross-worker asymmetry rather than malformed local
output. Seven positions were referenced as canonical anchors even though the
worker owning those positions had attached them to an earlier anchor; those
seven missing anchors received eight references. Following those references
transitively produced no cycle, but still left 25 groups with an invalid side
shape: a cross-source kind with members from only one source or a DISTINCT
anchor later used by both sources. Deterministically chasing anchor chains is
therefore insufficient reconciliation.

This exposes the deeper task-shape problem. Although a worker emitted decisions
for only 50 positions, finding each canonical anchor still required it to form
a view of the global grouping. The experiment repeated most of the global
reasoning six times and then asked stochastic calls to agree on one clustering
without communication. Smaller ownership batches would duplicate the same
complete input and global search more often; this result supplies no basis for
expecting that batch size alone will fix either tail latency or consistency.

The method remains evaluation-only. Production Compare is unchanged, no
partial worker result is published, and the incomplete record is retained
because it rejects this exact scheduling contract. A subsequent parallel
experiment should change the semantic unit of work, not merely use smaller
source-position slices. The strongest next candidate is candidate-edge
judgment: generate a frozen, measurable set of possible cross-source edges,
assign each edge to exactly one compact parallel judge, construct components
locally, and send only contradictory or overlapping components to an explicit
reconciliation stage. That design introduces a candidate-recall dependency and
cannot claim exhaustive Compare semantics until its generator and reconciler
are evaluated.

### Explicit parallelization conclusion

The measured condition did **not** improve actionable Compare latency. The
calls overlapped, but overlap is not itself a product speedup: the parallel run
produced no valid global result. Its 135.609-second terminal observation must
not be compared with the valid 140.225-second C result as though both were
actionable completions. The experiment therefore supplies no evidence of an
actionable latency improvement, and its 3.3% observed wall difference may not
be credited to the design.

The rejected mechanism is specifically full-context source-position ownership.
It divided response rows while leaving the global clustering problem inside
every call. This repeated most of the reasoning, increased total provider work,
and introduced stochastic disagreement between workers. Parallel execution may
still help after the semantic work is made genuinely local, but concurrency
alone and smaller batches of the same ownership contract are not accepted next
steps.

## Low-loss candidate-graph algorithm

Compare is closer to unordered bipartite record linkage and typed relation-graph
construction than to a sequential text diff. It is also not Meld itself:
Compare classifies relationships without materializing a merged result, while
Meld must later preserve provenance and produce application-ready content. A
one-to-one matching algorithm such as Hungarian assignment is therefore a poor
fit because Compare permits 1:N, N:1, and N:M groups.

For 150 by 150 Memories there are 22,500 possible cross-source pairs. Scoring
that complete pair plane with cheap host algorithms is practical; asking a
reasoning model to semantically judge every pair is the expensive part. The
leading low-loss design is:

1. **Freeze complete coverage.** Freeze both Contexts, all 300 identities,
   canonical ordering, content digests, and the model contract before routing.
   Every Memory must appear in the final disposition even if it has no judged
   relation edge.
2. **Generate a recall-first candidate union locally.** Score all 22,500 pairs
   with multiple independent signals such as exact-content equality, token or
   character n-gram similarity, BM25-style retrieval, and semantic embeddings
   when an approved local or separately measured embedding path exists. Keep
   the union of bidirectional top-k results and a deliberately broad threshold
   band. Exact equality is a safe candidate signal, not automatically proof of
   equal scope.
3. **Judge candidate edges exactly once.** Partition candidate pairs rather
   than source rows. Each compact provider row classifies one assigned pair as
   EQUIVALENT, COMPATIBLE, SCOPED, CONFLICT, NONE, or UNCLEAR. Its request
   contains the two endpoints and a bounded neighborhood needed to interpret
   them; it does not ask the worker to rediscover the global clustering.
4. **Construct the typed graph locally.** Use EQUIVALENT edges to propose
   components only after checking incompatible constraints. Retain COMPATIBLE,
   SCOPED, and CONFLICT as typed edges between or within components rather than
   assuming every relation is transitively mergeable. This preserves N:M
   structure without forcing a one-to-one match.
5. **Reconcile only coupled components.** Send overlapping anchors,
   contradictory edge labels, UNCLEAR edges, and components with incompatible
   scope or conflict structure to an explicit second-stage judge. Independent
   components need no global provider turn. Publish only after reconciliation
   and complete 300-item disposition validation.
6. **Audit the candidate boundary.** Judge a frozen sample of rejected pairs
   plus pairs immediately below each retrieval threshold. If the audit finds a
   missed relation, widen k or the thresholds and rerun before publication.
   Record candidate recall against reviewed fixtures and retained Compare runs;
   the retained stochastic runs are orientation, not ground truth.

This algorithm can reduce provider reasoning from one global clustering problem
to a sparse set of local edge decisions. Its principal possible loss is not
output compression but candidate recall: a true relation omitted by every host
signal may be defaulted to DISTINCT. Random negative auditing estimates this
risk but cannot prove exhaustive recall. A production fast mode must therefore
name this as approximation, select an explicit acceptable-loss threshold, and
retain a broader or one-shot fallback for frames that fail the audit.

Both complete Contexts remain the operation input and every Memory remains in
the final coverage ledger. They would no longer both be copied verbatim into
every provider call. If provider-visible full raw Contexts are required on every
turn, the measured 61.948–135.608-second worker range indicates that a
sub-30-second result is unlikely through batching alone; the product would need
a provider mechanism for reusable cached context, a faster measured model, or a
relaxed visibility requirement.

Reasoning can also be reduced structurally, but those changes must remain
separate from the effort-knob experiment:

- **Ontology reduction:** collapse six relation kinds into a smaller product
  decision such as SAME, RELATED/CONFLICTING, and DISTINCT. This removes
  distinctions and therefore requires an explicit product decision.
- **Frozen easy anchors:** deterministically pre-assign exact textual matches
  or other proof-level relations, expose those anchors with both complete
  content arrays, and ask the provider only for the remaining ownership. A
  heuristic near-match is not proof and cannot be silently frozen.
- **Full-context responsibility splitting:** give every parallel call both
  complete content arrays but assign a disjoint canonical anchor range. This
  trades repeated input work and reconciliation for shorter per-call reasoning
  and wall-clock overlap.
- **Candidate-guided verification:** provide host-generated candidate hints
  while retaining all content. This may reduce search but creates a measurable
  recall dependency and is an approximation unless the provider remains
  responsible for correcting missing candidates.

The measured six-worker full-context responsibility split did not approach 30
seconds and failed global reconstruction. Further JSON shortening or smaller
ownership batches are therefore weak next candidates by themselves. A future
reasoning-effort experiment may still isolate the effort axis, while a future
parallel experiment must change the semantic unit of work and add explicit
reconciliation.

## Next Compare experiment: prewarmed full-to-full

The next implementation should test precomputation before another provider
optimization. Freeze the complete Task 2 `advisor1` and `advisor2` frames at
150 Memories each and retain the production exhaustive `ComparisonAnalysis`
for that exact ordered pair and exact pair of revisions. In this experiment,
`full-to-full` means the complete `150:150` Context pair was analyzed before
the foreground timer; it does not mean every possible pair in the repository
was precomputed.

Run three separate lanes so a trivial cache hit is not mistaken for a new
semantic algorithm:

1. **W0 — exact warm `150:150`.** Seed or reuse the exact production artifact,
   invoke Compare with unchanged revisions, and verify zero provider calls,
   exact artifact identity, valid 300-item coverage, and foreground display
   latency. This validates the intended user-study experience.
2. **W1 — deletion projection.** Starting from the same retained artifact,
   remove a deterministic subset from one side, such as the `75:150` case, and
   project surviving members locally. Record projection time, untouched and
   cut relation groups, empty groups, orphaned members, changed side shapes,
   and especially touched `N:M` groups. Publish this only as an
   evaluation-only projected artifact because the present primary partition
   may hide secondary relations that become relevant after deletion.
3. **W2 — fresh whole-Context audit.** Outside the foreground latency path,
   compare the projection with a newly computed exhaustive result for the
   surviving full frames. This measures semantic drift and determines whether
   bounded group repair can ever be promoted beyond an approximation. It is
   intentionally deferred until W0 and W1 prove the host-side mechanics.

The first implementation should be an evaluation runner and fixture artifact,
not a new global relationship store or a production cache migration. The
existing exact ordered-pair Compare cache already supplies W0's basic reuse
mechanism. Reusing it avoids inventing a second cache before the experiment
shows what deletion metadata is actually missing. Study setup should prewarm
only the exact Context pairs participants can invoke; universal precomputation
would grow quadratically with the number of Contexts and is not required by
the foreground-latency hypothesis.

## First prewarm, projection, and fresh audit — 2026-08-10

`memcommit.eval.compare_prewarm_projection` implemented the three lanes above
without changing production Compare. It replayed the retained production
exhaustive response only to reconstruct and seed the existing exact cache;
the replay did not contact a provider. The new W2 audit used
`codex_chatgpt:gpt-5.6-sol` with reasoning `medium`, matching the retained
baseline's requested model and effort. The invocation was:

```console
python -m memcommit.eval.compare_prewarm_projection \
  --model gpt-5.6-sol \
  --reasoning medium \
  --timeout 900 \
  --output \
    outputs/compare-latency-ab/20260810-gpt-5.6-sol-medium-prewarm-projection-audit.json
```

W1 kept the odd one-based REFERENCE positions `1, 3, ..., 149`, yielding the
deterministic `75:150` surviving frame. This distributed deletion through the
ordered fixture rather than removing one contiguous half.

| Condition | Provider calls | Critical wall time | Result |
| --- | ---: | ---: | --- |
| W0 exact warm `150:150` | 0 | 5.11-5.18 ms across three reads | Exact saved analysis UID reused |
| W1 primary-ledger projection `75:150` | 0 | 0.225-0.269 ms across three runs | 225/225 coverage, but structurally invalid |
| W2 fresh whole-Context `75:150` | 1 | 241.869 s | Valid 225-item production analysis |

W0's isolated seed write took 11.10 ms, then every measured foreground lookup
reused the exact artifact without invoking the analyzer. This confirms the
narrow foreground hypothesis: an unchanged prewarmed full-to-full Compare can
be effectively immediate. It does not reduce or erase the retained 341.945
provider seconds used to create that exhaustive artifact.

W1 projected the 101 retained primary groups to 92 nonempty groups. Nine groups
became empty, 60 were cut, and only 41 were untouched. Coverage remained exact
with no missing, duplicate, or unknown source. All 23 original true `N:M`
groups were touched, but `N:M` was not the only repair surface: 23 projected
relations lost one complete side and became structurally invalid, and only one
of those 23 came from a true `N:M` group. Twenty came from `1:1`, one from
`1:2`, one from `2:1`, and one from `2:2`. Reconsidering only `N:M` groups is
therefore insufficient even for structural validity under this deletion.

A deterministic shape repair changed each one-sided cross-source remnant to
DISTINCT. This made the partition decodable but did not make it semantically
equivalent to W2:

| Agreement with fresh W2 | Raw projection | Shape-repaired projection |
| --- | ---: | ---: |
| Source relation-kind agreement | 49.3% | 52.4% |
| Exact source group-and-kind agreement | 34.2% | 37.3% |
| Exact relation-signature overlap | 28 of 92/72 | 35 of 92/72 |
| Pairwise same-group precision / recall / F1 | 0.815 / 0.755 / 0.784 | 0.815 / 0.755 / 0.784 |

Pairwise membership does not change when only a group kind is relabeled, which
is why the shape repair leaves pairwise scores unchanged. As in the earlier
A/B runs, these figures measure agreement with one stochastic fresh result,
not reviewed semantic accuracy. They nevertheless reject the claim that the
retained primary partition can simply be filtered and relabeled after a large
deletion while preserving current Compare behavior.

W2 returned 72 relations and four required issues from a 60,437-character
prompt and a 43,648-character response. Its provider completion was 241.857
seconds and local validation added about 0.011 seconds. Relative to the
retained `150:150` production completion of 341.945 seconds, removing half of
one side reduced provider time by only 29.3%; the fresh audit remained more
than eight times the 30-second target.

The evidence selects an asymmetric design boundary. Exact-revision prewarming
is useful for the controlled study and any unchanged pair. Large-deletion
projection is useful as an immediate preview or invalidation diagnostic, but
not as a complete Compare result. A product path must either refresh the whole
surviving pair in the background or introduce a wider candidate and
reconciliation method whose scope includes affected non-`N:M` groups and
possible secondary relations absent from the old primary partition.

### Production Study-run full-to-full prewarm — 2026-08-10

The earlier W0 condition used an isolated temporary store. A later run tested
the actual participant path in active Study Profile
`study-20260810T180141Z-641b669e`. Both sources were granted Contexts with
`RETAINED` analysis authority. `task-2/advisor1` contributed 16 Memories from
its selected root and 134 from descendants; `task-2/advisor2` likewise
contributed 16 root and 134 descendant Memories. Compare loaded each selected
root plus all descendants as one 150-Memory recursive projection and sent one
complete `150:150` provider turn with `gpt-5.6-sol` reasoning `medium`.

That first production run prepared only the study's expected root-to-root
operation. A later task-local graph experiment broadens preparation to every
root, intermediate, and leaf view pair inside each task. Each view still
includes its complete requested descendant scope in one provider turn; the
graph does not split one selected Context across calls. The broadened cache is
documented separately in
`docs/study-compare-graph-prewarm-design-rationale.md`.

`memcommit.eval.study_compare_prewarm` resolves the same local or granted
accesses as production Compare, uses the same recursive source projection and
atomic execution boundary, and keeps the semantic artifact inside the active
Profile's authorized store. Its repository receipt is content-free. The first
actual preparation produced analysis `6bbd2ff9-3b5f-4a09-b333-7669224ed5f0`:

| Measure | Cold prewarm | Exact reuse |
| --- | ---: | ---: |
| Provider calls | 1 | 0 |
| Provider completion | 256.097 s | 0 s |
| Host work | 0.103 s | 0.00578 s |
| Total setup/lookup | 256.200 s | 0.00578 s |
| Saved state | `RETAINED` | Same analysis UID reused |

The participant-facing production command then rendered
`REUSED · SAVED · RETAINED` without a provider call. It reported 150+150
Memories, 98 relations, and five potential conflicts. This confirms the actual
Study hierarchy and grant path rather than only an evaluation fixture.

The production follow-up separates declared Study preparation from ordinary
run-local caches. A content-free registry in the editable baseline names the
exact portable semantic seed, while `init-study` regenerates its granted
artifact wrapper from each new run's current Profile and Grant identities.
It never copies the old wrapper, sessions, checkpoints, logs, or ad-hoc
caches. A changed Source, task description, scope, provider contract, model,
or reasoning setting fails the exact installation and leaves the ordinary live
path available. The original content-free preparation receipts remain under
`outputs/compare-prewarm/`.

One new run, `study-prewarm-proof-20260810`, installed the declared Task 2
seed with zero provider calls. Its two saved binding records use the new
participant UID `683468b8-6310-4e46-8f85-6eff5823bb47`, new authority UID
`c694f340-80ec-494c-b277-c4be6056ecc4`, and new Grant UIDs rather than the
source run's identities. The participant-facing snapshot command completed in
`0.44` wall-clock seconds including process startup and printed
`EXACT PREWARM · SAVED · RETAINED` for the same 150+150 Memories, 98 relations,
and five issues.

A separate audit projected this actual retained analysis to 75+150 Memories.
Host projection remained essentially free at a `0.234` ms median and retained
225/225 source coverage, but agreement with the existing fresh partial result
was only 27.1% by source relation kind, 7.1% by exact group and kind, and 0.166
pairwise F1. This does not establish accuracy for either stochastic run. The
study accepts that semantic-loss tradeoff for speed, but production does not
present the current projection as an exact or freshly interpreted result. It
renders `PROJECTED · NOT SAVED · PREVIEW`, keeps the result out of durable
sessions and Meld, and sends additions, edits, same-side pairs, cross-task
pairs, ambiguity, and `--refresh` through the live path. An actual 13+13 Task 2
descendant projection completed in `0.46` wall-clock seconds with five groups,
zero provider calls, and complete input coverage.

### HCI study scope and out-of-scope NLP research discussion

Semantic equality with one fresh stochastic provider run is not the primary
outcome of the present qualitative study. The study asks whether prepared
relationship artifacts can remove foreground waiting and which user-visible
or background actions are required when the underlying Context changes. The
W1/W2 agreement figures are diagnostic observations, not accuracy scores and
not an acceptance threshold for this study. Deleted Memories were excluded
from the agreement denominator; the 52.4% shape-repaired kind agreement means
118 of the same 225 surviving Memories received the same primary relation kind
in one projection and one fresh run.

For the current study, the useful result is the action inventory exposed by a
deletion: remove deleted members, discard empty groups, detect groups that lose
one side, mark the retained artifact as projected or stale, keep the foreground
interaction immediate, and offer or schedule refresh. A projected view need
not reproduce one fresh run exactly to support observation of those actions.
It must still avoid claiming that a mechanically updated artifact is a newly
complete whole-Context interpretation.

The scope boundary should be carried into the paper explicitly:

| Current HCI study scope | Paper Discussion: out-of-scope NLP research opportunity |
| --- | --- |
| Foreground latency and waiting | Semantic accuracy for hundreds-versus-hundreds comparison |
| Prewarmed artifact interaction | Fresh-to-fresh stochastic consistency |
| Actions after Context change | Human-reviewed relation and regrouping ground truth |
| Projected/stale status communication | Recovery of secondary relations hidden by a primary partition |
| Background or person-requested refresh flow | Candidate recall and local-repair quality |
| Qualitative response to these mechanics | Criteria for choosing local repair versus whole-Context reconciliation |

The right column is not a current implementation TODO, a blocker, or an
acceptance gate for the qualitative study. It is a Discussion contribution:
the experiment exposes that reliable semantic regrouping at
hundreds-versus-hundreds scale remains limited and identifies concrete NLP
research opportunities for later work. The current project need not solve
those problems before studying latency, state, interaction mechanics, and the
actions people require. The present single fresh run must therefore not be
used to claim 52.4% semantic accuracy; its disagreement is evidence motivating
the out-of-scope discussion.

## Deferred provider-path benchmark record

This record applies only if later work resumes approximate or faster-provider
semantic execution. It is not an acceptance gate or current work list for the
HCI qualitative study.

Each run should record:

- frozen input digest and exact item count;
- input characters and estimated schema/output obligation;
- provider adapter, requested model, and resolved model identity if available;
- reasoning mode or equivalent control;
- number of calls, concurrency cap, retry count, and fallback count;
- time to first provider byte if available, provider completion times,
  reconciliation time, validation time, and actionable wall time;
- total provider seconds and response characters;
- decision coverage, unknown identities, duplicates, invalid groups, and
  unpublished partial attempts;
- relation and issue precision/recall or a clearly defined comparison against
  the frozen exhaustive baseline; and
- whether optional narrative was excluded from or included in the 30-second
  boundary.

The minimum validity gate is three of three contract-valid runs, 300 of 300
complete disposition, zero unknown or duplicate identities, and no partial
publication. The latency gate is all three actionable results at or below 30
seconds. A quality-loss threshold is intentionally not invented here; it must
be selected explicitly before an approximate method can be accepted.

## Current HCI implementation questions

The task-local cache eligibility and fallback policy is recorded in
[`study-semantic-prewarm-registry-design-rationale.md`](study-semantic-prewarm-registry-design-rationale.md).

- Which exact Context pairs can appear in the study and must be prewarmed?
- Where does study setup record hidden precomputation separately from
  foreground waiting?
- How should the interface distinguish exact, projected, stale, and refreshing
  artifacts without interrupting the person's current action?
- Which Context changes schedule background refresh, and which expose a
  person-requested refresh action?

## Deferred provider and NLP engineering questions

The questions below belong to the paper Discussion or later systems work. They
are not blockers or current implementation TODOs for the qualitative study.

- Can the current Codex-CLI-backed provider select an Instant model, and can it
  record a stable resolved identity?
- What concurrency and rate limits apply to the actual provider path?
- Does the 30-second product target include cold start and optional narrative?
- How much total provider work or cost may increase to reduce wall time?
- Can a candidate generator demonstrate sufficient cross-block relation
  recall on the 300-item frame?
- Can a compact positional contract detect semantic misalignment strongly
  enough, or should it retain periodic identity anchors?
- Which explanations are required for the first review decision, and which can
  safely be generated or requested afterward?

## Current decision

Continue using the 300-item Compare frame as the design benchmark. Compact
output materially reduced one-shot latency, but minimal I/O remained at
140.225 seconds. Reject the tested six-worker source-position ownership split:
it increased total provider work 3.81 times, reduced observed wall time only
3.3%, and could not reconstruct a globally consistent result. Do not try to
recover this contract merely by shrinking batches. Also reject reasoning
effort as the remaining shortcut: `none` completed twice in about 23.5 seconds
but produced invalid group vectors both times, while `low` took 149.947 seconds
and was also invalid. A fast non-actionable response does not meet the
foreground latency target.

The W0/W1/W2 experiment now establishes both sides of the cache boundary. An
unchanged exact `150:150` artifact was reused in at most 5.18 ms with zero
provider calls. The `75:150` deletion projection ran in at most 0.269 ms and
retained exact source coverage, but it broke 23 relation side shapes and agreed
poorly with the fresh whole-Context grouping. The corresponding fresh medium
analysis took 241.857 provider seconds. Therefore prewarm exact study pairs,
but do not present a large-deletion projection as a refreshed complete
Compare result.

The next foreground design question is how to surface artifact freshness and
background refresh without delaying an unchanged user-study path. If cache
preparation or refresh itself must meet 30 seconds, candidate-edge judgment
remains the leading later provider-time hypothesis. Its candidate-recall and
whole-Context reconciliation boundaries are unchanged. Forget and Sever retain
the deferred plan above; they may reuse the exact-revision prewarm pattern, but
this experiment gives no basis for transferring primary-ledger deletion
projection as complete semantics. Exact fresh equivalence and projection
accuracy belong in the paper's out-of-scope NLP research Discussion described
above. They are not current implementation TODOs or gates for the qualitative
study.
