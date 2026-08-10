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

## Next reasoning-axis experiments

The next controlled condition should preserve C's exact input, prompt, schema,
and output contract and change only the Codex reasoning-effort setting. The
local provider adapter accepts `low` and `minimal` in addition to the measured
`medium`; current official account-specific latency and availability are not
assumed by this note.

1. **R0 — C at medium:** the retained 140.225-second control.
2. **R1 — C at low:** one diagnostic run, then three repetitions only if it is
   contract-valid and materially closer to 30 seconds.
3. **R2 — C at minimal:** run only if low remains above the target or if the
   difference between low and medium is too small to explain the remaining
   latency.

Each condition must retain exact 300/300 coverage, valid group side shape, no
unused group, and local typed reconstruction. Semantic agreement remains a
descriptive measure rather than a gate until reviewed ground truth or an
explicit acceptable-loss threshold exists.

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

## Acceptance record for each 300-item run

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

## Open questions

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
- What measured quality loss is acceptable for a fast mode?

## Current decision

Continue using the 300-item Compare frame as the design benchmark. Compact
output materially reduced one-shot latency, but minimal I/O remained at
140.225 seconds. Reject the tested six-worker source-position ownership split:
it increased total provider work 3.81 times, reduced observed wall time only
3.3%, and could not reconstruct a globally consistent result. Do not try to
recover this contract merely by shrinking batches. The next scheduling design
must partition genuinely local semantic judgments and include an explicit
operation-owned reconciler; candidate-edge judgment is the current leading
hypothesis, with candidate recall named as an approximation boundary. Do not
transfer parallel staging to another operation until Compare's reconstruction
and reconciliation invariants are demonstrated.
