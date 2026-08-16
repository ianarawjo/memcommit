# Semantic evaluation harness design rationale

## Decision

memcommit will have a case-driven semantic evaluation and execution harness in
addition to the provider transport probe. Its long-term purpose is to make
complex semantic operations executable by smaller models without weakening
their result or safety contracts. The harness uses the strongest current Codex
model, Sol, as a **reference teacher** and incrementally optimizes observable,
bounded stages for Luna-low and local `qwen3.6:35b-a3b`.

```text
versioned corpus
  -> frozen campaign manifest
  -> small stage schema
  -> Luna-low / Qwen completion
  -> host-side validation and scoring
  -> immutable attempt record
  -> scoreboard and failure distribution
  -> pipeline revision
  -> complete regression rerun
```

A Sol result is not automatically true and does not replace a human-authored
expected result. Sol can propose an observable reference for a stage that does
not yet have one or help characterize a disagreement between models. A Luna or
Qwen failure is never silently replaced by Sol. A disagreement with Sol is
never automatically promoted to either an error or a new expected result. The
harness records schema-visible stage artifacts, not hidden chain of thought.

## Motivation and success criterion

Provider independence makes it possible to send the same completion contract
through Codex, Ollama, or OpenRouter. It does not establish that the selected
model can perform the operation. Current Context-wide one-shot operations may
combine candidate discovery, semantic judgment, explanation, reconciliation,
and result projection in one response. When such a call fails, it is difficult
to distinguish a model limitation from a prompt, schema, input-size, or
particular reasoning-stage problem.

The harness must make the following questions answerable from retained
evidence:

- Which exact corpus, pipeline, prompt, schema, provider, and model ran?
- Did a failure occur at transport, JSON parsing, schema validation, semantic
  labeling, reconciliation, or projection?
- Does the result remain stable over repeated attempts?
- Which cases newly pass, and which regress, after a pipeline revision?
- Did apparent improvement come from a hidden fallback, repair request, or
  relaxed safety contract?
- Can a new pilot case be steered into the next campaign without mutating the
  currently running campaign?

Success is not one syntactically valid JSON response. Within a frozen call
budget, every required stage must pass its local validator, reach the corpus's
semantic gate, and preserve any provider-free projection or application
boundary owned by the operation.

## Corpus roles

Corpus role is distinct from the review status of an expected result. The
harness uses three roles:

| Role | Purpose | Exposure to prompts | Official denominator |
| --- | --- | --- | --- |
| `CALIBRATION` | Explain boundaries and optimize the pipeline | Explicitly allowed | Reported only as a calibration score |
| `HOLDOUT` | Measure generalization after the pipeline is frozen | Never supplied as examples | Included in a separate holdout score |
| `PILOT` | Capture unreviewed cases from studies, steering, and observed failures | Isolated according to campaign policy | Excluded until reviewed |

A `PILOT` case moves into a later corpus version only after duplicate checking,
minimal reproduction, and review of its expected contract. It may then become
`CALIBRATION` or `HOLDOUT`. This prevents easy or redundant pilot cases from
inflating the denominator. Steering received during a live campaign does not
alter that campaign's manifest. The current campaign finishes against its
frozen corpus digest and case list; the new case enters a subsequent campaign.

Expected-result status is tracked separately. A case may have a human-reviewed
expectation, a provisional Sol reference, or an unresolved expectation. A case
with only a teacher-generated reference is not called Gold.

## Exact status of the current ambiguity fixture

The ten cases in `memcommit/eval/fixtures/ambiguity.json` are initial
calibration examples for the 3x3 `interpretation`-by-`clarification` boundary,
plus one Context-resolution contrast. The file itself states that these are
reviewed calibration contract examples rather than an independent held-out
evaluation set.

More importantly, the production `find-ambiguities` one-shot prompt includes
every complete case object from this file as calibration. Each object contains
the scenario and Memory as well as the exact expected interpretation,
clarification, readings, question, and rationale. Running those same ten cases
through the current production call would therefore test a prompt that already
contains the answer under evaluation. Such a result must not be called Gold,
`HOLDOUT`, or proof of operation portability.

V1 avoids this circularity with **leave-one-out calibration**. For one attempt,
the held case contributes only its scenario and Memory as input, and its entire
case object is removed from the calibration-example list. The remaining cases
may be supplied as calibration. The ledger and scoreboard always display this
boundary:

```text
CALIBRATION / IN-SAMPLE / LEAVE-ONE-OUT
NOT AN INDEPENDENT HOLDOUT
```

This removes exact-answer leakage for the held case, but it remains an
in-distribution measurement under the same draft ruleset.

The independent v1 holdout was later authored before its first provider
evaluation in `ambiguity_holdout.json`. Its separate lock manifest freezes:

- fixture SHA-256 `be722ce2316365844ed1f0c852d5812bea6b583a3a7d41c3386bcba911a7e853`;
- 12 reviewed case identities;
- calibration SHA-256
  `003654c092e03ea74f72e8f084624438085555e2cedad2c9abed985ae2b3c067`;
- the fixture and calibration filenames; and
- the pre-evaluation timestamp.

The runner verifies all of those fields and rejects ID or Memory-UID overlap
before connecting a scored case to the pipeline. A holdout target contributes
only its scenario and Memory. Calibration comes from all ten frozen
calibration cases; no holdout expectation or sibling holdout case enters the
prompt. The ledger records `HOLDOUT / FIXED_CALIBRATION / independent=true`
and the lock timestamp.

This holdout has now been consumed by the V2/V6 comparisons below. Its
failures may guide calibration or a later V7 design, but a revision informed
by them cannot be evaluated on this same corpus and still claim an independent
generalization test. A new holdout digest is required for that claim.

## V1 foundation: label-only ambiguity classification

The first vertical slice is `ambiguity-classify-v1`. For each case, the
provider returns one small object with only two labels:

```json
{
  "interpretation": "SINGLE | DOMINANT | COMPETING",
  "clarification": "NONE | HELPFUL | REQUIRED"
}
```

The host validates the exact key set, string types, enum membership, and
duplicate JSON keys. The existing ten cases contain human-authored expected
labels, so V1 can score this stage deterministically without an LLM judge.
`SINGLE/NONE` is returned explicitly at the classification stage. Classification
coverage and the production projection that omits a clean Memory from the
findings list are separate concerns.

V1 does not modify the production `find-ambiguities` prompt or implementation.
It measures only the first decomposed stage in a separate harness. A 10/10
result means that `ambiguity-classify-v1` passed its calibration gate. It does
not establish parity for ordinary readings, clarification questions, final
`AmbiguityReport` projection, Context-wide reconciliation, or the complete
production operation.

Label-only classification is the first slice because:

- both labels permit exact deterministic scoring;
- a failure can be localized to one semantic axis;
- fuzzy prose is not prematurely scored by exact-string comparison or an
  unversioned teacher judgment; and
- persistence, provenance, repetition, and the scoreboard can be validated
  with a small number of calls.

Later stages must not grow this object into one large schema. Pipeline state
may become richer, but each provider-facing stage remains small and
independently validated.

## Implemented pipeline revisions

The harness retains every implemented version as an explicit replay choice
through `--pipeline v1` to `--pipeline v6`. A later version is not silently
substituted for an earlier one, because the observed best pipeline differs by
model and inference mode.

| Version | Provider-facing calls per case | Stage contract | Host projection |
| --- | ---: | --- | --- |
| V1 `ambiguity-classify-v1` | 1 | Original exact two-label object | Strictly validate both labels |
| V2 `ambiguity-classify-v2` | 1 | Two labels plus a more explicit decision procedure | Strictly validate both labels |
| V3 `ambiguity-binary-v3` | 2--4 | Conditional `YES`/`NO` probes for multiple readings, clear leader, practical improvement, and ability to proceed | Compose the probe answers into the two public labels |
| V4 `ambiguity-census-v4` | 2 | Reading census and clarification census | Map census enums to the two public labels |
| V5 `ambiguity-census-v5` | 2 | V4 plus an explicit reading-contrast checklist | Map census enums to the two public labels |
| V6 `ambiguity-rules-v6` | 2 | V5 plus compact reviewed boundary rules for credentials/proof modes and missing location/contact routes | Map census enums to the two public labels |

V3 uses `MULTIPLE_READINGS` and `PRACTICAL_IMPROVEMENT` for every case,
calling `CLEAR_LEADER` and `CAN_PROCEED` only when the preceding answer makes
them relevant. V4--V6 instead externalize two compact evidence records:
`READING_CENSUS` returns a primary reading, possible alternative, and one of
`ONE`, `MULTIPLE_WITH_LEADER`, or `MULTIPLE_BALANCED`; `CLARIFICATION_CENSUS`
returns one missing detail and one of `NO_IMPROVEMENT`, `MINOR_FRICTION`, or
`BLOCKS_OR_MATERIAL_RISK`. The host, not another model call, projects those
enums to the public labels.

V6's boundary rules were compiled from failures in this ten-case calibration
set. They are useful optimization artifacts, not evidence of generalization.
The first independent holdout later confirmed that V6 fixes its credential
boundary while introducing other stable regressions, so it is not the current
general operation default.

## Campaign and atomic run ledger

One run is a campaign with a frozen provider/model snapshot, corpus snapshot,
pipeline version, selected cases, repetition count, and call budget. Those
values are frozen in the first persisted run snapshot. The implemented
harness uses one JSON file per run:

```text
semantic-eval/
  runs/
    <UTC-timestamp>-<random-suffix>.json
```

The first snapshot has status `RUNNING` and no attempts. After each attempt,
the complete run record is rewritten through a temporary UTF-8 JSON file in
the same directory, flushed and `fsync`ed, installed with `os.replace`, and
followed by a directory `fsync`. A process interruption therefore leaves
either the prior complete snapshot or the new complete snapshot, never a
partially written JSON document. The terminal snapshot is `COMPLETED` even
when semantic cases fail; `ABORTED` means an unexpected host failure stopped
the fixed campaign. A terminal file is treated as immutable by the harness.

This single-file snapshot design is the current bounded tradeoff. It preserves
the latest durable attempt boundary and makes status and replay simple, but it
does not preserve every intermediate version as an append-only audit log. A
future study requiring proof of each publication event can migrate to
immutable per-attempt files without changing the attempt schema. Unknown
schema versions, duplicate JSON keys, symlinks, and unexpected path types fail
closed.

Each attempt record contains at least:

- case ID, repetition ordinal, stage name, and pipeline version;
- expected labels and locally validated actual labels;
- PASS or FAIL, a primary failure category, and a short host-authored
  diagnostic;
- completion elapsed time and any provider-reported input/output token counts;
- response byte count and digest, plus the normalized parsed result when valid;
  and
- provider/model provenance and the parent run ID.

The ledger does not retain prompt text, credentials, API keys, environment
dumps, the Codex authentication directory, query-only sources, or ordinary
Context Memories. The current repository-owned ambiguity calibration scope,
including its V1--V6 pipeline revisions, does retain each bounded raw provider
response, its byte count, and its digest. This is acceptable here because the
input is public fixture text and every response has a small strict schema. It
is deliberately not a default for later campaigns over user data: those
operations must choose and document a narrower retention policy before reusing
the ledger writer. Each prompt can be reconstructed from its versioned fixture
and deterministic pipeline template, so prompt duplication is unnecessary.

## Timing measurements

The provider contract is non-streaming. The current harness therefore has no
trustworthy TTFT (time to first token). TTFT is omitted or explicitly marked
`not_available_nonstreaming`; it is not recorded as zero or inferred from total
latency.

The harness uses a monotonic clock for four boundaries:

| Metric | Start | End | Included work |
| --- | --- | --- | --- |
| `provider_connection_seconds` | Immediately before the provider factory call | After exact provider/model probes and instance creation | Configuration read, authentication, local runtime, model and capability probes |
| attempt `completion_seconds` | Immediately before the classification runner | After completion and local parsing/validation, or a classified error | One provider/model inference attempt plus its strict host validation |
| `campaign_seconds` | Before fixture loading | After the terminal run record is assembled, immediately before final publication | Fixture validation, ledger setup, completion, validation, scoring, and record assembly |
| `total_seconds` | Derived as connection plus campaign | Immediately before final publication | Connection and all measured campaign work |

`campaign_seconds` excludes provider connection; `total_seconds` includes it.
The final atomic JSON serialization, file and directory `fsync`, and terminal
rendering are excluded. They are persistence/UI overhead rather than model
performance, and including a file's own final publication time inside that
same immutable record would require a second rewrite. A provider error still
retains the elapsed time of its blocking completion attempt.

Within one campaign, attempt-completion samples have `mean`, `median`, `p95`,
and `max`. Connection, campaign, and total are each one elapsed value for that
campaign. P95 uses the deterministic nearest-rank definition: item
`ceil(0.95 * n)` in sorted order. An empty attempt sample set is `N/A`, not
zero. The current status view selects the latest comparable retained campaign;
it does not synthesize timing distributions across separate campaign files.

The run command renders each completed attempt's elapsed time in its live
progress line. Its terminal result, and the provider-free `semantic status`
view loaded later from the ledger, render provider connection time;
completion mean, median, p95, and max; campaign and total time; and stage mean
and p95 when a staged pipeline supplied stage samples. The ledger remains the
authority for these displays; status does not reconnect the provider or
recompute model timing.

## Pass gate

An ambiguity-classification attempt passes only if all of these conditions
hold:

1. Completion finishes against the allowlisted provider and frozen model
   snapshot.
2. Every required provider-facing stage returns a nonempty, untruncated exact
   JSON object.
3. Each stage contains no duplicate, unknown, or missing key and no invalid
   type, enum, or local invariant.
4. Both labels exactly match the human-authored expectation for the held case.
5. There is no hidden repair completion, provider fallback, schema relaxation,
   or call-budget overrun.

For repeated execution, a case passes only when every attempt is structurally
valid, label accuracy is at least 2/3, and majority stability of the label pair
is at least 2/3. With one repetition, that one attempt must be an exact match.
A campaign passes only when every selected case passes. Partial results remain
in the ledger and scoreboard but do not receive a successful exit status.

This gate applies only to the two-label ambiguity-classification slice across
V1--V6. A complete explanation or production-operation stage needs separately
versioned gates for reading quality, the relationship between labels and
questions, source/Context coverage, and reviewed semantic adjudication. Label
accuracy must not be reused as an explanation-quality score.

## Failure taxonomy

Each attempt records the first failure that makes the result unusable as one
primary category and one stage. A single error is not counted in several
buckets.

| Category | Meaning |
| --- | --- |
| `CONNECTION` | The provider/model snapshot or preflight probe could not be created |
| `TIMEOUT` | A connection or completion exceeded its frozen time budget |
| `PROVIDER` | Authentication, transport, runtime, or upstream-provider failure |
| `EMPTY_OR_TRUNCATED` | Empty response, confirmed output-budget exhaustion, or truncation |
| `INVALID_JSON` | The response is not exactly one strict JSON object |
| `SCHEMA` | Key, type, enum, or local-invariant violation |
| `LABEL_MISMATCH` | Structurally valid labels differ from the expected labels |
| `STABILITY` | Repeated results do not meet the majority threshold |
| `PERSISTENCE` | An attempt-bearing or terminal run snapshot could not be atomically published |
| `INTERNAL` | An uncategorized host defect that aborts the campaign |

A connection failure occurs before semantic input is sent and aborts the
campaign. A provider, JSON, schema, or label failure for one case does not
prevent later cases from running within the fixed budget. A persistence
failure aborts the campaign because an unrecorded result cannot be claimed as
durable evidence. Any later retry is a visible, budgeted attempt; it cannot
overwrite the original failure.

## Reproducibility identity and digests

Every comparable result freezes at least these axes:

- provider ID, requested model, and observed upstream model/provider;
- local model catalog digest, runtime/version, reasoning effort or thinking
  setting;
- host-controlled context/output budgets, timeout, temperature, and related
  generation settings;
- corpus schema/ruleset version, selected case IDs, and corpus-file SHA-256;
- pipeline ID/version and declared stage list;
- each attempt's exact prompt-byte SHA-256, canonical JSON Schema SHA-256,
  and response SHA-256; and
- ledger schema version.

The prompt digest is calculated from the exact UTF-8 bytes sent to the
provider. The schema digest uses canonical JSON bytes with deterministic key
ordering and whitespace. Retaining a digest does not authorize retaining the
prompt. Raw-response retention is the explicit public-calibration exception
described above. The current status grouping separates corpus digest, pipeline
ID/version, provider/model identity, repetition count, and reasoning/thinking
condition. Prompt or schema digest changes remain visible inside the ledger
and require manual comparison; the status view does not silently merge their
attempt evidence.

A mutable model tag is recorded with that limitation. When an exact artifact
identity such as an Ollama catalog digest is available, it is required.
OpenRouter provenance includes the requested slug and any observed upstream
route. A Codex-managed selection includes an observed upstream model when the
runtime exposes it; the harness does not invent unavailable identity data.

## Scoreboard

The scoreboard is a read-only projection of corpus and failure distributions,
not merely one headline success count. Reading status never connects a
provider or creates a completion.

The current terminal scoreboard shows:

- provider, model, model digest grouping, pipeline, reasoning/thinking mode,
  repetition count, campaign status, and selected/full corpus coverage;
- the calibration case-gate score and failure-category counts;
- exact and structurally valid attempt counts;
- the 3x3 `interpretation`-by-`clarification` case distribution;
- connection, campaign, and total elapsed time plus attempt-completion mean,
  median, p95, and max; and
- per-stage mean and p95 completion latency for staged pipelines.

The ledger additionally retains attempt-level exact matches, structural
validity, majority stability, stage failures, reported token/call metadata,
and corpus/prompt/schema digests. A later richer dashboard can project those
fields, comparisons, and language/difficulty distributions without rerunning
the provider; the current CLI does not claim to render them all.

The current ambiguity fixture has no reliable language or difficulty metadata,
so the scoreboard does not infer it. Scores with different corpus digests or
pipeline IDs/versions are not merged into one denominator. A calibration score
is never
rendered as a holdout score, and unreviewed PILOT cases remain outside the
official denominator.

## Observed calibration campaigns on 2026-08-03

The following results are retained observations from one development machine,
not portable throughput claims. `Mean attempt` includes all provider calls and
strict host validation inside one case attempt. `Total elapsed` includes
provider connection and the campaign. Every row uses the same ten reviewed
cases in leave-one-out calibration unless explicitly marked as a three-case
diagnostic subset.

| Provider condition | Pipeline and repetitions | Case gate | Exact attempts | Mean attempt | Total elapsed |
| --- | --- | ---: | ---: | ---: | ---: |
| Sol, high reasoning | V1, 1 | 9/10 | 9/10 | 5.274 s | 52.807 s |
| Sol, high reasoning | V2, 1 | 10/10 | 10/10 | 5.830 s | 58.369 s |
| Luna-low | V1, 1 | 7/10 | 7/10 | 4.663 s | 46.703 s |
| Luna-low | V2, 1 | 7/10 | 7/10 | 5.388 s | 53.949 s |
| Luna-low | V6, 1 | 10/10 | 10/10 | 10.192 s | 101.992 s |
| Luna-low | V6, 3 | **7/10** | **20/30** | 11.934 s | 358.142 s |
| Qwen, thinking `auto` | V1, 1 | 3/10 | 3/10 | 16.171 s | 161.748 s |
| Qwen, thinking `off` | V1, 1 | 8/10 | 8/10 | 0.723 s | 7.261 s |
| Qwen, thinking `off` | V2, 3 | **10/10** | **30/30** | 0.572 s | 17.237 s |
| Qwen, thinking `off` | V6, 1 | 9/10 | 9/10 | 3.083 s | 30.880 s |

The source ledgers are under `outputs/semantic-eval-v1/runs/`; representative
run IDs are `20260803T185425758124Z-97cd98e2` for Qwen V2 with three
repetitions and `20260803T191651654420Z-62294e9d` for Luna V6 with three
repetitions.

These measurements support four bounded conclusions:

- Qwen with thinking explicitly `off` and V2 is the strongest and fastest
  observed Qwen condition on this calibration set: all 30 attempts match.
  Thinking `auto` is both slower and substantially less accurate here, so
  thinking mode is part of the frozen operation condition rather than an
  assumed quality improvement.
- Luna V6's single 10/10 campaign is not a stability result. The complete
  three-repetition rerun passes only 7/10 case gates and 20/30 attempts. Its
  three failing gates are the Context-resolved-time, access-card, and hotel-216
  cases. The repetition gate prevented a misleading one-shot success claim.
- Luna V6 averages 6.098 seconds in `READING_CENSUS` and 5.835 seconds in
  `CLARIFICATION_CENSUS` during the three-repetition campaign. Its 11.934-second
  mean attempt is about 21 times the observed Qwen V2 mean, but that comparison
  includes a two-call staged pipeline versus a one-call pipeline as well as
  different provider runtimes. It must not be read as a pure model-speed ratio.
- V6 is not a universal replacement for V2. It repaired the earlier stable
  Luna V2 failure classes, while regressing or destabilizing other boundaries;
  Qwen also scores lower and takes longer on V6 than on V2.

The V3--V6 development sequence was also run against only the three stable
Luna V2 failures. This was a targeted diagnostic and is excluded from the
full-corpus denominator:

| Luna-low diagnostic | Cases passed | Mean attempt | Total elapsed |
| --- | ---: | ---: | ---: |
| V3 conditional binary probes | 1/3 | 11.413 s | 34.296 s |
| V4 evidence census | 1/3 | 10.711 s | 32.194 s |
| V5 contrast checklist | 1/3 | 9.949 s | 29.907 s |
| V6 compiled boundary rules | 3/3 | 10.305 s | 30.971 s |

That local 3/3 motivated the complete V6 rerun; the later 7/10 repeated result
demonstrates why optimizing only formerly failing cases is insufficient.

## First frozen holdout evaluation on 2026-08-03

The first holdout exposure used only pipelines already frozen before the
holdout was authored. No prompt or rule changed between lock publication and
these runs.

| Provider condition | Pipeline and repetitions | Case gate | Exact attempts | Mean / median / p95 / max | Total elapsed |
| --- | --- | ---: | ---: | ---: | ---: |
| Qwen, thinking `off` | V2, 3 | **12/12** | **36/36** | 0.810 / 0.502 / 0.866 / 8.436 s | 29.283 s |
| Sol, high reasoning | V2, 1 | **12/12** | **12/12** | 5.453 / 5.408 / 9.139 / 9.139 s | 65.514 s |
| Luna-low | V2, 3 | **11/12** | **34/36** | 4.534 / 3.886 / 7.555 / 8.704 s | 163.348 s |
| Luna-low | V6, 3 | **10/12** | **29/36** | 13.058 / 10.109 / 33.430 / 43.249 s | 470.268 s |

The representative ledgers are `20260803T201143832715Z-e1ea4bfb` (Qwen V2),
`20260803T201227441885Z-d83cb013` (Sol V2),
`20260803T201349202626Z-0e1e6619` (Luna V2), and
`20260803T201655110512Z-51c9ef3f` (Luna V6).

Qwen's first local attempt took 8.436 seconds while the median attempt was
0.502 seconds. The mean therefore includes a visible model/runtime cold-start
cost rather than hiding it. Luna V2 failed only the vaccination-certificate
case: clarification was consistently `REQUIRED`, but the reading structure
oscillated between `DOMINANT` and `COMPETING`. V6 made that case exact 3/3,
then introduced stable regressions:

- parking ticket became `SINGLE/NONE` rather than `DOMINANT/NONE` in 3/3;
- the LAB-labeled package became `COMPETING/HELPFUL` rather than
  `DOMINANT/HELPFUL` in 3/3; and
- one greenhouse-plant attempt also lost the secondary reading, although its
  case gate still passed 2/3.

V6's two-stage census was 2.88 times slower than Luna V2 by mean attempt and
had a 43.249-second maximum. This independent result supports profile-wide V2
selection for the current Qwen and Luna candidates. It does not justify a
case-aware V2/V6 router: such a router designed from these failures would be
tuned on a consumed holdout.

## Nine-operation gate pilot and Task scaling

The harness now includes `operation-gate-v1`, a common strict-label runner for
Conflict, Atomize, Translate, Compare, Update, Ground, Meld, Forget, and the
retired Integrate benchmark. This common runner does not make their complete
semantics generic or make every benchmark label a public command.
Each operation owns its label vocabulary and decision instruction, and later
candidate discovery, explanation, projection, review, and mutation stages
remain operation-specific. The shared component owns only strict JSON parsing,
leave-one-out example isolation, attempt persistence, scoring, and timing.

The reviewed pilot fixture currently contains 37 cases:

- 28 `SHORT` micro-cases that make one boundary independently reviewable;
- nine `LONG` cases, one per operation, drawn from the semantic structure of
  Task 1, Task 2, or Task 3; and
- explicit `task` and `length_tier` dimensions retained in every attempt and
  scoreboard comparison key.

The fixture declares a hard 200-case campaign ceiling. This is an intermediate
review and execution bound, not a claim that 200 cases cover the study. The
study loader already validates 1,306 bilingual fixture identities across thirteen
datasets: Task 1 has 454, Task 2 has 376, and Task 3 has 476. Expansion proceeds
through reviewed slices rather than copying all 1,306 Memories into prompts:

```text
37 reviewed gates
  -> balanced label and boundary additions
  -> 75-case Task-stratified slice
  -> 125-case bilingual/adversarial slice
  -> 200-case operation campaign
  -> micro-batched Task 1/2/3 operation coverage
  -> full 1,306-Memory workload and candidate-coverage evaluation
```

After the Conflict optimization described below, the 37-case calibration
baseline was frozen by `operation_gates.lock.json` at SHA-256
`ec580a4fe3ef8c158997930c413a813a2df790e58bb383d21fff62e92f865a91`.
The lock explicitly records `independent_holdout=false` and
`consumed_during_optimization=true`; freezing it makes later regression
comparison reproducible but does not retroactively turn it into unseen data.
Default campaigns reject a fixture, count, or 200-case-limit mismatch before
connecting a scored case to the provider.

The first Qwen thinking-off run exposed one useful failure. A direct Conflict
label prompt classified an underspecified entrance as `NO`. Adding prose to the
same one-shot label instruction did not fix it. Conflict was therefore split
into provider-visible `scope_relation` and `claim_relation` evidence, with the
host projecting those fields to `YES`, `MAY`, or `NO`. The first decomposed run
then recovered `MAY` but merged two explicitly different entrances. Because
the only `NO` case disappeared under leave-one-out, the calibration set had no
remaining explicit different-scope contrast. A second, non-duplicative
different-time `NO` case filled that distribution hole. The resulting Conflict
slice passed 4/4.

On 2026-08-03, local `qwen3.6:35b-a3b` with thinking off subsequently matched:

- 28/28 short cases and 84/84 repeated attempts, mean 0.466 seconds and p95
  0.703 seconds per attempt; and
- 9/9 long Task cases and 27/27 repeated attempts, mean 0.390 seconds and p95
  0.535 seconds per attempt in the warm run.

These are calibration results after observing and repairing the Conflict
failure. They do not constitute a frozen holdout, complete operation parity,
or evidence that one long case represents the length and interaction
distribution of an entire Task. The retained failed runs remain evidence of
why the stage split and distribution addition were selected.

The scoreboard comparison key includes operation, corpus digest, repetition
count, selected operations, Task slice, and length tier. Without the latter
dimensions, a later long-only run could hide an earlier short-only run even
though both ledgers remained intact.

### 75-case composite revision

The next iteration preserved the frozen 37-case file byte-for-byte and stored
38 additions in `operation_gates_v2.json`. The loader composes them only after
verifying the base filename and digest. The resulting 75-case corpus contains
57 `SHORT` and 18 `LONG` cases and fills labels absent from the first pilot,
including Translate/Meld `UNKNOWN`, Update `REMOVE` and `UNRESOLVED`, Ground
`FACT` and `MEMORY`, and retired Integrate `UNRESOLVED`. `--layer additions`
permits a
failure-driven run of only the new cases, while `--case` selects exact case
identities; neither changes the frozen campaign manifest after execution
starts.

The first additions run passed 36/38. Qwen mapped an unresolved Korean source
to Translate `CONTRADICTED` and an underspecified entrance to Meld
`COMPATIBLE`. Translate, Compare, and Meld were therefore changed from direct
labels to two-field evidence contracts: one resolution label plus the relation
under a resolved reading. The host projects unresolved meaning to `UNKNOWN`.
Translate passed immediately. Meld then exposed the same leave-one-out
distribution hole previously seen in Conflict: its only `UNKNOWN` case vanished
from its own calibration examples. A redundant compatible addition was replaced
by a second, semantically different underspecified-desk case while preserving
the 75-case count.

Both Meld cases then returned correct `scope_resolution=UNRESOLVED` evidence
but used `UNKNOWN` in the relation field. The initial schema rejected that
semantically correct sentinel. The schema now explicitly permits `UNKNOWN`
there only when scope is unresolved; the host rejects `UNKNOWN` paired with
resolved scope. This is a visible conditional contract, not a hidden repair or
fallback. The affected Translate/Compare/Meld regression passed 26/26, and the
revised additions passed 38/38.

Full local Qwen thinking-off results on the composite were:

- 75/75 cases and 75/75 attempts in the first complete replay, mean 0.866
  seconds, p95 1.143 seconds, and total 65.228 seconds; and
- 75/75 cases and 225/225 attempts in the three-run stability campaign, mean
  0.550 seconds, p95 1.081 seconds, and total 124.957 seconds.

The final consumed composite is frozen by `operation_gates_v2.lock.json`. It
binds base digest
`ec580a4fe3ef8c158997930c413a813a2df790e58bb383d21fff62e92f865a91`,
extension digest
`c1116cd7b3f3b0441d1eea8d47d2b653025a51d26c696e0b92e0865f628c3222`,
and composite digest
`241cf4c1f2224e35f5e886da3ef7b8d734f241aa962e17157c3f99ba660ab0dd`.
It explicitly remains `independent_holdout=false` and
`consumed_during_optimization=true`. New campaigns default to this latest
locked composite; the exact 37-case base remains replayable by explicit fixture
path.

## Task 2 end-to-end relation discovery

The operation-gate campaigns classify provider inputs already selected by the
host. They therefore cannot answer whether two providers find the same semantic
parts in a full Task. Task 2 now supplies the first end-to-end discovery target:
150 `advisor1` Memories, 150 `advisor2` Memories, and a reviewed sidecar that
partitions all 300 Memories into 138 cross-advisor relationship groups.

This sidecar is group-level Gold, not a 22,500-row atomic pair answer key. Nine
groups contain more than one member on at least one side, and the fixture design
explicitly says the group band does not independently label every Cartesian
left-right combination. The harness consequently reports exact hypergroup
recovery, per-Memory counterpart-set recovery, and within-group coassignment as
a partition diagnostic. It does not call the latter pairwise semantic accuracy.
The counterpart set is the opposite-side co-membership induced by a reviewed
hypergroup. It is not independently reviewed directed-edge Gold inside the nine
multi-member groups; only the 129 one-to-one groups also define an unambiguous
directed subset.
The corpus also has a counterpart for every Memory, so it cannot measure
one-sided `DISTINCT` discovery without a separately reviewed extension.

`task2-relation-discovery-v1` is a joint end-to-end baseline. Each provider sees
the same unordered left and right content sets plus their top-level topic. It
must return an exhaustive partition and one fixture-native relationship band
per group. Fixture IDs are replaced with independently salted opaque aliases,
and left and right order are independently digest-shuffled. The host rejects an
unknown, omitted, or repeated alias and never repairs a response with Gold or a
teacher output. Sol, Qwen, and the reviewed sidecar are three separate results:
Sol is a reference provider, not the source of truth.

Scores intentionally separate:

- exact group structure precision and recall;
- exact counterpart sets and their macro Jaccard across all selected Memories;
- band accuracy over the full Gold denominator;
- conditional band accuracy only where group structure was exactly recovered;
- structure-only, structure-plus-band, and coassignment agreement between two
  providers; and
- per-band counts, especially the eight `Conflict` and two
  `Compatible Complement` groups.

The first 26 complete reviewed groups form a consumed calibration slice with 29
left and 27 right Memories and all five bands. It is not a holdout. The scale
ladder is 26, 50, 100, and all 138 groups; the final rung is the required full
150-by-150 input. A one-shot full baseline is retained because the compact
payload fits the configured context and output budgets and directly measures
the desired joint behavior. Current production Compare and Meld still reject
this workload: their frames are direct-only and their provider contracts cap
the total source count at 200. The evaluation path does not silently raise
those production limits or claim persistence compatibility.

The consumed English ladder has explicit calibration revisions. The original
2026-08-04 identity is preserved verbatim as
`memcommit/eval/fixtures/task2_discovery.v1.lock.json`, binding corpus digest
`d98dd2bb55aa81efb692d9cd3e72aec4403d6ff5548437a17f81821c168f6ac9`
and sidecar digest
`0f6244e75fc739c752105ec02f9c5e9bee6eab8d883169644024f288676bff0c`.
The exact corpus bytes for that identity are no longer present in the
repository, so V1 is an archival provenance record and intentionally fails
replay against current fixtures. Recovering those exact inputs remains a
limitation; the V1 identity must not be silently rebound to new bytes.

The default `memcommit/eval/fixtures/task2_discovery.lock.json` is schema 2 and
names revision `task2-relation-discovery-calibration-v2`. It freezes the
currently checked-in 150-by-150, 138-group corpus at digest
`2e42279f3f78e4e033d0ba951b2d90ba0859e7564dea3ea8302a422f68beef8d`
and sidecar digest
`fb0f6652f665fd65fe3b3df2468d9e04a5115efe10e578c60a588825389b9642`,
including separate input, alias-map, Gold, count, and band-distribution
manifests for 26, 50, 100, and 138 groups. The full revision contains eight
Conflicts, two Compatible Complements, 65 Near Duplicates, and 37
Context-Dependent Variants. English campaigns replay V2 before inference.

Both revisions explicitly record `consumed_during_optimization=true` and
`independent_holdout=false`. V2 is a new consumed calibration baseline, not a
continuity claim for V1 results; existing V1 result ledgers must remain labelled
with their recorded lock provenance. The unreviewed Korean translation remains
a separate robustness condition rather than interchangeable Gold.

If one-shot discovery fails, V2 must localize the cause instead of adding a
larger monolithic prompt:

```text
same frozen 150 + 150 input
  -> discovery-only grouping
  -> host coverage reconciliation
  -> oracle-group band classification
  -> predicted-group band classification
  -> Sol / Qwen / reviewed-Gold three-way report
```

The bounded fallback is bidirectional retrieval in batches of 15 Memories
against all 150 on the opposite side, followed by reciprocal-candidate union,
global group reconciliation, and small classification batches. Batch routing
must be content/topology derived; using Gold groups to choose runtime batches
would leak the discovery answer. A global recovery pass is required because
three reviewed groups cross top-level topics. The harness first records a
one-shot failure before introducing this fallback so the reason for the
pipeline split remains reconstructable.

Task 2 timing is split into provider connection, corpus preparation, prompt
preparation, provider completion, response validation, scoring, campaign, and
total elapsed seconds. The completion interface remains non-streaming, so TTFT
is unavailable rather than guessed. Prompt, schema, input, alias-map, corpus,
and response digests make parity comparisons fail closed when two records did
not use the same frozen condition.

The first retained discovery ledgers used a last-observation counterpart
diagnostic for contract-invalid partitions with repeated members. Because that
made the diagnostic depend on provider output order, scorer version 2 unions
every observed opposite-side mate before comparison. Existing files are not
rewritten or silently rescored: a missing `scorer_version` is displayed as
`legacy-v1`, while new V1 and V2 records carry `scorer_version: 2`. Status also
shows `PRE-LOCK` versus `LOCKED`, keeps those provenance conditions in separate
latest-run rows, and V1 parity refuses to compare different scorer versions.

### First 26-group joint baseline

The first same-input comparison on 2026-08-03 established that V1 does not yet
provide Sol/Qwen parity:

| Provider | Partition contract | Exact structure | Exact structure + band | Group-induced co-membership | Provider completion |
| --- | --- | ---: | ---: | ---: | ---: |
| Sol, high reasoning | valid | 26/26 | 17/26 | 56/56 | 60.553 s |
| Qwen, thinking off | invalid | 23/26 | 14/26 | 44/56 | 22.741 s |

Qwen returned 28 draft groups, omitted two left and one right Memory, and
reused one left and two right Memories. The retained partial partition still
made the useful distinction between semantic quality and contract validity.
Against Sol, Qwen shared 23 exact structures but only 11 of those structures
also had the same band. The direct diagnostic Jaccards were 0.742 for exact
group structure, 0.256 for structure plus band, and 0.667 for within-group
coassignment. This diagnostic does not pass the parity gate because Qwen's
partition was invalid.

Sol's perfect structure recovery but 17/26 band score is separate evidence
that discovery and classification must not be optimized as one signal. It also
shows why Sol cannot replace the reviewed sidecar as Gold. The five fixture
bands contain fine distinctions that are not reproduced by a strong reference
model from the brief definitions alone. V2 therefore evaluates oracle-group
classification separately before deciding whether a better evidence contract,
additional reviewed rationale, or a revised label ontology is needed.

The retained ledgers are
`20260803T214750043669Z-ollama.json` and
`20260803T214757320576Z-codex_chatgpt.json`. The harness was changed after the
first unretained Qwen failure so any completed but contract-invalid response is
now written with its raw response, partial normalized groups, failure reason,
score, and stage timings rather than disappearing at the exception boundary.
Both runs are now labelled `PRE-LOCK`: their corpus and sidecar digests match
the later lock, but they ran before lock replay existed. New ledgers record the
lock and scorer revision rather than being mixed with these rows.

### Full 150-by-150 baseline and first decomposition

The same one-shot V1 was then run against all 138 reviewed groups. This is the
required 150-left by 150-right workload, not a sampled pair list.

| Provider | Partition contract | Exact structure | Exact structure + band | Group-induced co-membership | Provider completion |
| --- | --- | ---: | ---: | ---: | ---: |
| Sol, high reasoning | invalid | 85/138 | 33/138 | 190/300 | 364.512 s |
| Qwen, thinking off | invalid | 72/138 | 51/138 | 121/300 | 184.820 s |

Sol omitted one left and one right Memory without reusing another member. Qwen
used every left Memory once but omitted 55 right Memories and reused 36 right
Memories. Its 150 returned groups behaved mostly like one independently chosen
target per left item; it recovered none of the nine reviewed multi-member
groups. Sol recovered three of those nine. The direct Sol/Qwen diagnostic had
71 shared structures, structure Jaccard 0.345, structure-plus-band Jaccard
0.104, and coassignment Jaccard 0.306. Both records fail the parity gate.

The two invalid Qwen ledgers were initially written with a last-observation
counterpart diagnostic, which reported 46/56 and 135/300. Scorer V2 unions all
mates of a repeated member before comparison, making invalid-output diagnostics
independent of provider group order; the deterministic rescores shown above are
44/56 and 121/300. The immutable original ledgers are not rewritten.

Qwen's full-run band output also collapsed to 135 `Near Duplicate` and 15
`Compatible Complement` predictions. Sol used all five bands but still matched
only 33 exact structure-and-band groups. These failures rule out treating a
larger one-shot prompt as the portability strategy.

V2 first removed bands and made candidate grouping plus global reconciliation
two fixed, visible calls. On the 26-group slice Sol recovered 26/26 structures
with a valid partition in 54.227 seconds. Qwen's first stage mixed right aliases
into left-member arrays and its reconciliation over-merged topical groups; the
final partition was invalid and recovered 12/26 structures. Its immutable
legacy ledger stores 24/56 group-induced co-membership sets; deterministic
scorer V2 unions repeated-member observations and rescored it as 23/56 in
48.044 seconds. This regression is retained rather than
selected away. It motivates the next source-anchored, bidirectional microbatch
stage, where the host fixes which side and which source IDs each call must
answer instead of asking Qwen to manage a global partition.

The oracle-group evidence classifier separately supplied all 26 reviewed
structures and hid their bands. Qwen projected 14/26 correct bands in 20.733
seconds; Sol projected 13/26 in 37.371 seconds. They agreed on 19/26 projected
bands: 11 were jointly correct, eight were the same wrong band, three were
Qwen-only correct, two Sol-only correct, and two different wrong answers. The
evidence split therefore improves failure localization but not Gold accuracy.
It suggests that the fine reviewed band boundary needs either additional
reviewed rationale or an explicitly revised ontology; adding the first 26
answers as examples and rescoring those same 26 would only memorize consumed
calibration.

V3 then replaced global partitioning with fixed source-anchored, bidirectional
group-co-membership retrieval. Calls see at most 15 sources and the complete
opposite collection; the locked scale ladder requires 4, 8, 16, and 20 calls.
The contract asks for every opposite-side member of the same reviewed
hypergroup, not every atomic Cartesian pair. It separately reports the reviewed
one-to-one subset (48/56 sources on the first rung and 258/300 on the full
rung), and retains reciprocal and union components without choosing the better
one after Gold scoring. Campaign durability is currently final-atomic-write
only, so a process interruption before publication can lose completed calls.

The first Qwen V3 run was retained invalid. Its fourth call placed source-side
aliases in a target list; exact group co-membership was 19/56, the reviewed
one-to-one subset was 17/48, reciprocal components were 10/26, union components
were 2/26, and pipeline time was 69.001 seconds. A post-run ranked-candidate
diagnostic found complete reviewed co-members in 50/56 lists and at least one in
54/56. The next revision therefore freezes candidate generation and bounded
verification as separate stages instead of asking Qwen to retrieve and decide
cardinality in the same call. The full contract and promotion gates are in
`docs/task2-portable-semantic-harness-design-rationale.md`.

The same V3 schedule gave Sol a valid 55/56 co-membership result, 48/48 on the
reviewed one-to-one subset, and 26/26 reciprocal and union groups in 130.425
seconds. Luna-low was valid at 48/56, 44/48, 22/26 reciprocal groups, and 18/26
union groups in 74.933 seconds. Qwen/Sol co-membership agreement was 18/56,
Qwen/Luna 19/56, and Sol/Luna 47/56; only the last pair had two valid contracts.

V4 split every source batch into top-3 candidate retrieval followed by subset
verification. Its implementation review allowed a truthful empty verifier
answer, corrected the consumed-Gold provenance boundary, and added a dedicated
multi-member metric. The real 26-group runs were contract-valid but all failed:
Qwen retrieved 60/64 Gold co-members and finished at 36/56 exact source sets in
88.563 seconds; Sol retrieved 64/64 but finished at 37/56 in 317.249 seconds;
Luna-low retrieved 61/64 but finished at 35/56 in 121.218 seconds. Every model
recovered zero of two multi-member groups. Qwen retained only 41/60 Gold
members available to its verifier, while Sol retained 47/64, so the free
subset verifier is a shared bottleneck rather than evidence that Qwen matched
the reference teacher.

V4 end-to-end parity also remains candidate-confounded: Qwen/Sol agreed on
34/56 final sets, Qwen/Luna on 40/56, and Sol/Luna on 40/56, but each verifier
saw provider-specific candidates. The next fixed experiment is therefore a
verifier-only judge-isolation replay over one deterministic, Gold-blind union
of retained candidate sets. It requires one explicit relationship enum for
every identical candidate pair and reports raw label agreement separately from
group-induced membership Gold quality. Retrieval top-K is changed only after
that judge lane is calibrated.

That V5 replay has now run over one identical 249-pair, 11-call bundle with a
complete 64/64 group-co-member ceiling. Qwen/Sol/Luna were all contract-valid,
but their partition-proxy binary precision was .496/.376/.377 and accepted
source-set exact was 14/56, 6/56, and 8/56. Qwen/Sol agreed on only 174/249
binary decisions and 122/249 enums; even Sol/Luna reached only 220/249 and
182/249. Forty-six cross-hypergroup pairs were accepted by all three. Because
cross-group membership is not independently reviewed atomic negative Gold,
those cases now enter a read-only adjudication queue rather than being silently
used as negative training labels.

V6 changed only the prompt boundary on the same replay freeze. Its mandatory
relationship-unit test reduced the partition-induced FP proxy from 60 to 40
for Qwen, 106 to 22 for Sol, and 104 to 31 for Luna. Enum exact rose to
176/249, 206/249, and 199/249; source sets rose to 19/56, 35/56, and 32/56.
Qwen/Sol binary agreement rose to 199/249, but Sol multi-member recall fell
from 1.000 to .812. V6 is therefore a useful consumed-calibration ablation, not
a scale promotion. The next judge revision canonicalizes direction, projects
decomposed evidence, and separates component recovery from group-level band
classification. The full measurements and Gold boundaries are in
`docs/task2-portable-semantic-harness-design-rationale.md`.

V7-and-later optimization replays are Qwen-only. The retained Sol/Luna V5 and
V6 ledgers remain frozen references and are not repeatedly rerun for every red
local revision. A new Sol/Luna common-freeze confirmation is deferred until
Qwen passes the 26-group stability gate and the scale ladder.

The first Qwen V7 canonical-evidence run is itself retained red. It completed
all eight calls in 205.247 seconds and returned strict JSON plus exact IDs for
all 169 canonical pairs, but 38 of its five-field evidence vectors were not in
the frozen nine-vector projection table. V7's whole-call rejection rule then
marked five calls and 120 pairs missing, discarding 82 otherwise supported
peer vectors. This is a harness-contract failure, not a partial accuracy or
provider-parity result. V8 consequently splits the work into a coarse
relationship-unit gate, a relationship-family decision, and one
branch-specific evidence choice. The host alone projects a final relationship;
explicit uncertainty, item-local invalid evidence, and call-level missing data
remain separate outcomes. Sol and Luna were not called for V7 and remain
outside this optimization loop.

The one requested Qwen V8 run is contract-valid and strict-replay-valid. Its
three stages used 14 calls and 148.321 seconds for all 169 canonical pairs,
with no abstain, invalid evidence, missing pair, or call anomaly. It therefore
demonstrates that the lower-model staged execution contract works. Semantic
quality remains below the 26-group gate: the directed partition proxy is
`40/13/172/24` at precision `.755` and recall `.625`, reviewed one-to-one enum
is `20/48`, and multi-member recall is `.375`. Against the frozen Sol V6
ledger on the same 249 candidate occurrences, binary agreement is 198 and enum
agreement 190, but accepted-pair Jaccard is only `.452` because 156 common
rejections dominate the binary count. This is not Qwen/Sol parity. The detailed
stage choices, Gold boundary, and timings are recorded in
`docs/task2-portable-semantic-harness-design-rationale.md`. Work pauses at V8;
no V9, scale rung, Sol, or Luna run follows this result.

The full V1 ledgers are `20260803T215024486372Z-ollama.json` and
`20260803T215029469386Z-codex_chatgpt.json`. The V2 ledgers are
`20260803T215900622333Z-ollama.json` and
`20260803T215907303761Z-codex_chatgpt.json`. The oracle-classification ledgers
are `20260803T215700684839Z-ollama.json` and
`20260803T215707252795Z-codex_chatgpt.json`.

## Next optimization and staged expansion

The V1--V6 classification experiments, atomic ledger, replay, status view,
timing distributions, and first independent holdout are implemented. The next
iteration proceeds in this order:

1. **Keep profile-wide V2 selection:** Qwen thinking-off V2 is holdout-green.
   Luna V2 has one bounded reading-structure failure but is more accurate and
   much faster than V6. Do not hide either condition behind per-case switching.
2. **Move the observed failures into calibration/PILOT:** The consumed holdout
   remains immutable evidence. Any new guarded rule or V7 must be developed
   against a separate calibration revision.
3. **Freeze a new holdout before testing a revision:** A later V7 candidate is
   frozen first and receives one first exposure to a new untouched holdout.
   The current holdout cannot be reused for another generalization claim.
4. **Explain:** Given validated labels, generate readings, reason, and the
   clarification question under a small schema. Separate deterministic
   invariants from Sol-reference disagreement.
5. **Project:** Project validated stage state into the current
   `AmbiguityReport` without a provider call, including `SINGLE/NONE` omission
   and Context-order restoration.
6. **Full operation:** Evaluate multi-Memory Context framing, candidate
   coverage, reconciliation, and increasing micro-batch sizes, and compare the
   semantic result with the production one-shot operation.
7. **Adversarial steering:** Collect Korean/English, long-Context, competing
   antecedent, prompt-injection, correction/retraction, timeout, and truncation
   cases as PILOT material and promote them only after review.
8. **Other operations:** Duplicate relation classification and nine additional
   first-stage gates now have calibration pipelines. Add label-balanced short
   cases and diverse long cases, then replace each generic first gate with the
   operation-specific downstream stage graph and scorer needed for complete
   Task execution.

At each stage, Luna-low and Qwen failure locations are compared with the Sol
reference. Optimization should improve general stage contracts, host
validation, candidate coverage, micro-batch size, and budgets rather than make
the prompt memorize one case. After a change, the entire relevant corpus is
rerun instead of only the formerly failing example. A V7/router informed by
the consumed holdout requires a new frozen holdout before it can make an
independent generalization claim. Qwen V2 passed this first bounded holdout;
that does not yet establish full multi-Memory operation parity.

## Mutation boundary and intentional non-goals

Semantic evaluation is a read-only research workflow. It preserves these
boundaries:

- It does not create, edit, switch, checkpoint, bind, update, or apply a
  Context.
- Running an eval does not change global provider selection. A campaign only
  snapshots the selection present at its start.
- V1--V6 do not change the production `find-ambiguities` one-shot contract or
  user-visible result.
- Provider output cannot bypass an operation's review, exact-command approval,
  digest/CAS, lock, or provider-free apply boundary.
- Ordinary user Memories and query-only sources are not collected into the
  calibration ledger.
- A failure is not converted into success through Sol, OpenRouter fallback,
  hidden repair, or schema relaxation.
- A Sol reference or case steered during execution is not automatically
  promoted to Gold or `HOLDOUT`.
- The current harness does not establish full semantic-operation parity, an
  HTML dashboard, automatic prompt search, or cost optimization.

The current deliverable remains bounded to unary ambiguity, pairwise duplicate
classification, and the first reviewed gate of nine additional operations:
honest calibration labeling, ambiguity V1--V6 replay, host/provider
decomposition, interruption-safe evidence, timing analysis, and a scoreboard
that supports operation/provider/model/Task/length comparison.
Profile-wide selection is preferred over a case-adaptive router at this stage.
V7 remains a later experiment, not a promised default. The first holdout is
implemented and consumed; a new untouched holdout is future work before any
V7 generalization claim. Explanation, projection, and full-operation
evaluation also remain future work.
