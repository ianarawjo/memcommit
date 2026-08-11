# Study semantic prewarm registry design rationale

## Status

This note defines a study-design registry for moving known long semantic work
out of participant-facing time. It is a cache-hit eligibility list, never an
operation allowlist. The implemented production slices now install the
declared Compare, Tutorial Atomize, Task 1 Update, and Task 3 Sever artifacts
when `init-study` creates a run. Compare also projects declared opposite-side
descendant subsets from each exact seed. Symmetric Meld starts reuse the exact
Compare ledgers without a second semantic cache. Directional Meld remains live
after its current exact attempt failed its semantic quality gate. The registry
itself never runs a provider, and an unlisted operation remains available
through its ordinary live path.

## Implemented first slice and measured boundary

`memcommit.study_prewarm` now gives the editable Study baseline one strict,
versioned, task-local registry. `memcommit.eval.study_compare_registry`
publishes an already retained exact `ComparisonAnalysis` into that fixture
without a provider call. A new `init-study` copies only this declared fixture,
validates its artifact digest, task, task-description digest, Context and
Memory revisions, descendant scopes, Compare ruleset, provider contract,
model, and reasoning setting, then installs it through Compare's production
authorization and CAS boundary.

Only the semantic `ComparisonAnalysis` is portable. The source run's granted
artifact wrapper is deliberately excluded because every new run receives new
participant, authority, and Grant identities. Installation resolves the new
run's Sources and writes a new wrapper under its current `READ`, `DERIVE`,
`COMBINE`, and analysis-retention authority. A mismatch fails before provider
connection and before a semantic artifact is published. Ordinary checkpoints,
sessions, logs, and ad-hoc caches still start empty.

The first real end-to-end proof used Task 2's declared descendant-inclusive
`advisor1 150` versus `advisor2 150` basis. The original exact prewarm needed
`256.097` provider seconds. A fresh Study run installed it with zero provider
calls, regenerated both Grant bindings, and rendered the actual CLI report as
`EXACT PREWARM · SAVED · RETAINED` in `0.44` seconds including Python process
startup, Context and Grant resolution, validation, lookup, and report output.
The analysis UID and all semantic content were byte-identical to the prepared
artifact. The old and new Profile, authority, and Grant UIDs differed.

Parallelism is intentionally asymmetric. Independent offline provider calls
may be prepared concurrently because they do not split one semantic frame.
`init-study` registry publication and Grant rebinding remain serialized under
the Profile and operation locks. That serialized work is local host work and
does not add a participant-facing provider wait.

Subset projection is enabled as a visibly labeled, ephemeral Study preview by
an explicit latency-first study decision. Projecting the actual retained Task
2 analysis to `75:150` took a median `0.234` ms with exact
`225/225` coverage, but agreement with one fresh partial result was only
`27.1%` by source relation kind, `7.1%` by exact group and kind, and `0.166`
pairwise F1. A different retained baseline previously produced `0.784`
pairwise F1, while two full stochastic runs also differed substantially. This
variance is accepted for the qualitative prototype, but it is not hidden:
projection is rendered as `PROJECTED · NOT SAVED · PREVIEW`, cannot seed Meld,
does not enter the saved Compare session catalogue, and is never described as
an exact or freshly interpreted result.

The production resolver permits only two current Contexts that descend from
opposite sides of one declared same-task parent artifact. Every requested
Memory must keep the parent's durable UID and exact content. Deletion and
lexical descendant selection can hit; an addition, edit, cross-task request,
same-parent-side pair, ambiguous parent, task-description drift, provider
configuration drift, or `--refresh` takes the ordinary live path. One actual
`advisor1/style 13` versus `advisor2/style 13` command projected five relation
groups in `0.46` wall-clock seconds including process startup, with zero
provider calls and complete `26/26` primary-ledger coverage.

The production transfer order after the Atomize slice is:

1. add exact Update proposal reuse, preserving Source-to-Target direction;
2. record Impact as the deterministic projection of its owning typed proposal
   rather than creating another semantic cache;
3. verify that symmetric Meld opens provider-free from the installed exact
   Compare basis while keeping participant-authored responses live;
4. add Task 1 directional Meld as a separate exact raw-response contract; and
5. add Task 3 Sever as an exact whole-Source plus whole-Criteria contract.

### Tutorial Atomize exact prewarm

The second production slice moves only the fixed tutorial analysis out of the
participant turn. `memcommit.eval.study_atomize_registry` publishes an already
validated `AtomizeAnalysisSession` into the baseline registry. A new Study run
checks the exact `practice/source` direct-Memory ledger, the complete
`practice/description` digest, Atomize ruleset and prompt/decoder contract,
and configured provider, model, and reasoning effort. It then installs the
analysis into Atomize's existing production analysis slot and creates a fresh
run-local workbench with `practice/source-atomized` as the not-yet-created
Output.

The portable unit contains semantic analysis only. Review responses,
grounding dialogue, application state, and checkpoints are not copied. The
foreground command visibly reports `EXACT PREWARM · CURRENT` and reopens with
zero provider calls. Editing either the Source or tutorial instruction fails
the setup binding, while a provider configuration mismatch is counted as an
explicit skip so the ordinary live route remains available. `--refresh`
continues to be a deliberate live provider call and overwrites the exact slot
only through Atomize's existing validation and rollback boundary.

The real frozen tutorial run used `gpt-5.6-sol` at reasoning `medium`. Its cold
CLI path took `23.29` seconds wall-clock and produced eight source-grounded
children. A fresh participant run installed both the existing Compare seed and
the new Atomize seed in `1.08` seconds. The identical participant-facing
Atomize command then rendered in `0.36` seconds including Python startup. Ten
direct production reopens had a `0.140` ms median (`0.129`–`0.244` ms), kept
the same analysis UID, and connected the provider zero times. The content-free
metrics are recorded in
[`outputs/atomize-prewarm/20260810-tutorial-e2e.json`](../outputs/atomize-prewarm/20260810-tutorial-e2e.json),
with ordered real-PTY evidence under
[`docs/screenshots/study-atomize-exact-prewarm-20260810/`](screenshots/study-atomize-exact-prewarm-20260810/).

### Task 1 peer Compare basis

The second declared Compare basis freezes descendant-inclusive
`task-1/participant/construction-updates` `75` against
`task-1/campus-wiki` `300`. Its prepared all-pairs artifact matched the current
baseline's endpoint names, Context UIDs, complete digests, Memory counts, and
`375/375` source ledger exactly. The compact call failed its unused-group
validator, so preparation correctly used the exhaustive fallback rather than
publishing the malformed compact result. The two calls took `414.006` provider
seconds and yielded 51 validated groups with complete exactly-once coverage.

The artifact was explicitly promoted into the same production Compare
registry used by Task 2; participant commands never search the all-pairs output
tree. A new run installed both Compare bases and the Tutorial Atomize basis in
`1.22` seconds. The exact Task 1 CLI report reopened in `0.41` seconds, while
ten direct production lookups had a `7.370` ms median and zero analyzer calls.
Three declared opposite-side topic projections also remained below one second:
building access `11:50` in `0.43` seconds, route changes `9:50` in `0.43`
seconds, and shop updates `13:50` in `0.44` seconds. Every projection was
visibly labeled `PROJECTED · NOT SAVED · PREVIEW`; group counts remained no
larger than input count. Content-free evidence is stored in
[`outputs/compare-prewarm/20260810-task1-exact-projection-e2e.json`](../outputs/compare-prewarm/20260810-task1-exact-projection-e2e.json).

There is no independent production Refine operator in the current repository,
so it is not an implementation target yet. Generic Update, Meld, Atomize, and
Sever subset projection also remains disabled until each operation's frozen
fresh-partial campaign passes its own authority, coverage, provenance, and
semantic-usefulness gates.

### Task 1 directional Update basis

Task 1 Update now installs one exact descendant-inclusive
`construction-updates → campus-wiki` proposal into the ordinary
`impact-plan.json` slot. The portable artifact excludes run-local Grant and
Profile identities. Setup authorizes the current transfer, reloads both full
frames, verifies their exhaustive semantic payload digests and every operation
owner and Source reference, then freezes the new run's Grant binding and
Context fingerprints. This rebinding matters because Study setup regenerates
run-local graph bindings even when every Memory UID and content value is
unchanged.

The retained Sol-medium preparation took `134.730` seconds for the `75:300`
basis and produced `74` target actions: `32 EDIT`, `42 ADD`, and `0 REMOVE`.
A fresh Study run installed two Compare bases, the Tutorial Atomize basis, and
this Update basis in `1.27` seconds. Its complete saved Update Impact rendered
in `0.38` seconds; ten direct validated reads had a `0.786 ms` median and
`5.066 ms` maximum. The public Update command disclosed `EXACT PREWARM`, called
no provider, and applied all `74` actions in `0.53` seconds. The target grew
from `300` to `342` Memories, the Source digest remained unchanged, and public
Undo/Redo restored and reapplied the same `32` edits and `42` additions.

This artifact is directional and exact. Reversing the endpoints, changing
either semantic input digest, changing descendant scope, task description,
provider contract, model, or reasoning setting is a miss. Setup stores only a
non-mutating Impact proposal; review and application continue through Update's
ordinary authority, CAS, checkpoint, Undo, and Redo boundaries. Generic Update
subset projection remains outside this step because filtering a full proposal
cannot discover actions whose meaning changes when evidence or an existing
Target Memory disappears.

### Task 1 symmetric Meld transfer

Task 1 symmetric Meld requires no additional semantic cache family for its
initial review state. A fresh run imported the exact Task 1 Compare basis and
created the empty result Context and `AWAITING_REPLY` Meld session in `0.47`
seconds with no Meld provider call. The session exposed all `51` relations and
`24` optional issues while leaving both Sources and the empty result unchanged.

The deterministic `--preserve-all` branch then covered `375/375` source
Memories and `51/51` relations, produced `375` provenance-bearing result
Memories in `0.46` seconds, and remained unapplied until the separate exact
`--accept`. Apply completed in `0.52` seconds and materialized exactly `375`
Memories in the new result Context. This is a conservative quality control: it
proves provider-free, lossless transfer and application mechanics, not that
preservation-only is the preferred semantic merge. Any participant comment,
choice, or synthesis request remains a live Meld turn.

### Task 2 symmetric Meld transfer

The same production path transferred without Task 1-specific logic to the
Task 2 `advisor1 + advisor2` basis. A fresh run imported the exact `150:150`
Compare, opened `98` relations and `45` issues in `0.52` seconds, and made no
Meld provider call. The deterministic preservation branch completed in `0.44`
seconds and exact acceptance in `0.47` seconds. It materialized `249` result
Memories from `300` inputs because exact equivalent claims were coalesced while
distinct source claims retained provenance. The five required conflicts remain
visible in the ordinary participant-guided route; preserve-all is again a
mechanical coverage control rather than a substitute for those choices.

### Task 3 year-pair Compare bases

All three frozen year pairs are now declared exact Compare bases: `2024:2025`
(`120:120`), `2024:2026` (`120:60`), and `2025:2026` (`120:60`). Their existing
all-pairs Sol-medium runs required two calls each because compact validation
fell back to exhaustive output, taking `355.413`, `377.982`, and `393.082`
seconds respectively. Promotion reconstructed typed production analyses only
after exact frame digest and `240`, `180`, and `180` source coverage checks.

A fresh run installed five total Compare bases. Provider-forbidden production
lookups reopened the three year pairs in `3.983`, `2.994`, and `2.908` ms with
`119`, `96`, and `102` relation groups. The public report labels the result
`EXACT PREWARM`. This step also corrected a storage bug exposed only by local
Task 3 pairs: Compare save/load now honors the explicitly supplied
`MemoryStore` root during `init-study` instead of writing through the process's
previous global active-store path. Granted Task 1/2 storage had hidden that
boundary error.

### Task 3 year-pair symmetric Meld transfer

Each declared year Compare now initializes its own symmetric Meld session with
an explicit empty result Context and no Meld provider call. `2024+2025`,
`2024+2026`, and `2025+2026` opened in `0.425`, `0.409`, and `0.411` seconds,
retaining `119`, `96`, and `102` relation groups. The operation adapter derived
`7`, `10`, and `2` review issues from those exact relation ledgers. No result
Memory was created before a participant response or the deterministic
preservation control. The three result Context names and sessions remain
separate so one year-pair choice cannot leak into another pair.

### Task 3 rule-pair Compare basis

The frozen rule pair is local `guardrails` (`75` Memories) against the readable
authority-owned `transmission-guidance` frame (`25` Memories), both with
descendants. Its compact decision-vector run completed in one Sol-medium call
(`144.524` provider seconds), covered all `100` inputs, and produced `57`
relations: `14 COMPATIBLE`, `2 SCOPED`, and `41 DISTINCT`. A fresh run installed
the basis with a new Grant binding and reopened it in `1.599` ms with the
analyzer forbidden. The public report labels it `EXACT PREWARM · SAVED ·
RETAINED`; the artifact contains no portable Grant identity.

### Task 3 rule-pair symmetric Meld transfer

The mixed-authority rule pair opened as equal symmetric peers in `0.430`
seconds with no Meld provider call. It retained all `57` relations, derived
`16` optional review issues, and kept the new local result empty. The
provider-free preservation control covered all `100` Source Memories in
`0.405` seconds; exact acceptance materialized `100` result Memories in
`0.419` seconds. Neither the local guardrails nor the granted authority frame
was changed. A directional rule-to-rule merge remains a different, undeclared
operation.

### Task 1 directional Meld quality gate

The current exact Task 1 directional basis is not prewarmed. Three older
directional sessions were rejected because their Source or Baseline digest no
longer matches the frozen `75:300` inputs. A fresh Sol-medium attempt then ran
for `375.21` seconds but failed the production decoder because turn zero
changed its imported Compare relation ledger. No session or partial proposal
was published. This is a semantic-contract failure, not a latency miss that can
be hidden by caching. Directional Meld therefore remains `LIVE · UNPREPARED`
until a fresh response preserves the exact relation ledger and passes owner,
provenance, `EDIT`/`ADD`, and application checks.

### Task 3 exact Sever basis

Task 3 Sever now prepares the exact descendant-inclusive
`local/personal-memory` Source (`300` Memories) under the exact
`local/guardrails` Criteria (`75` Memories). The retained Sol-medium turn took
`192.178` provider seconds and returned complete coverage with `300 FORGET`
recommendations. The artifact key binds the two full frame digests, Task 3
description, fixed output name, schema and prompt/decoder contract, provider,
model, and reasoning setting.

`init-study` validates this artifact under Sever's ordinary combination,
derived-transfer, analysis-retention, and require-new-output boundaries, then
stores only a hidden installation receipt. It deliberately does not add a
researcher-prepared review to the participant's saved-session picker. When the
exact public command is issued, the semantic decisions are rebound to the
current run and cloned under a fresh session and candidate UID set. The public
report discloses `ANALYSIS · EXACT PREWARM · PROVIDER NOT CALLED`.

A fresh run installed all nine declared semantic artifacts in `1.74` seconds.
The actual `300:75` Sever command rendered in `0.43` seconds, with no provider
events in the Study action ledger. Twenty direct exact lookups had a `7.598 ms`
median and `8.179 ms` maximum. Applying the all-forget recommendation created
the required new empty local Context in `0.39` seconds, preserved the Source's
exact `300`-Memory frame digest, and public Undo and Redo removed and restored
the same zero-Memory result.

This is exact reuse, not generic Sever projection. A Source addition or edit,
Criteria change, task-description change, output-name change, scope change,
provider-contract change, model change, or reasoning change misses and uses
the existing one-shot whole-frame live path. Source-deletion projection remains
the separately disclosed latency-first follow-up; it is never labeled as this
exact artifact.

## Relationship to the earlier FIT idea

The surviving repository account of the earlier `fit` notes describes a
`YES / MAY / NO` judgment about whether Memories fit together inside one
Context. The original FIT archive is not present in this checkout, so this note
does not claim a fuller reconstruction.

Current Compare has a different and stronger contract. It takes two complete,
equal-authority Context frames, changes neither, and gives every input Memory
exactly one primary `1:1`, `1:N`, `N:1`, or `N:M` relation disposition. The
reference side controls presentation order only and is not a baseline that
wins disagreement. In the study, cache preparation must preserve this
user-visible meaning rather than reduce Compare to a topical-fit gate.

## Decision rule

Before participant interaction, freeze a task-local table of exact large
semantic routes whose waiting time the study will remove. Prewarm a route when
its exact frame is fixed and historical evidence indicates that foreground
execution may exceed 30 seconds. Cache inclusion is decided from the operation,
task, source, target, scope, revision, and expected workload before inspecting
the provider result.

Do not retain only outputs that look good to the researcher. A contract-invalid
artifact is unusable, but post-hoc semantic preference must not determine which
condition appears instantaneous. Otherwise cache preparation becomes hidden
result selection rather than a latency intervention.

Every operation and route that passes the product's ordinary authority and
semantic validation remains available, whether or not it appears in this
table. A noneligible route runs live and reports its actual waiting state. An
unusual request such as melding a 2024 Context with 2025 and 2026 Contexts can
still be a legitimate user action; absence from the prewarm table is not a
semantic prohibition.

The same rule applies when a participant adds or edits material. The changed
Context digest misses the prewarmed key, and the operation runs live against
the complete current frame. An old parent projection must not omit the new
Memory and masquerade as current. The study may ask afterward why the
participant introduced the change or requested additional verification, but
that question is qualitative data collection rather than a gate on the action.

## Operation policy table

| Operation | Prewarm unit | Reuse or projection | Live path | Boundary |
| --- | --- | --- | --- | --- |
| Compare | Exact ordered pair, descendant-scope pair, task description, ruleset, model, and reasoning setting | Exact hit for the frozen pair; declared opposite-side descendant subsets use a visibly labeled ephemeral parent projection | Unlisted, changed, same-side, cross-task, ambiguous, and refreshed requests run as complete two-frame Compare calls | Same-side sibling relations cannot be recovered from an opposite-side parent artifact; projection is not a fresh semantic judgment or a Meld basis |
| Meld | Exact Compare basis plus direction, destination, source revisions, and any already-fixed study instruction | Reuse the reviewed Compare seed; deterministic materialization may reuse an exact reviewed proposal | A new response, direction, destination, or source revision requires a new semantic turn | Compare relations alone do not authorize or determine target content |
| Update | Exact ordered Source and Target frames plus operation criteria and revisions | Reuse only an exact directional proposal; unchanged reviewed application can be deterministic | Changed evidence, criteria, direction, or target runs live | Update cannot use symmetric Compare cache identity |
| Sever | Exact whole Source frame and exact Criteria frame | Exact hit; deletion-only projection may be shown only with an explicit projected status | Changed Criteria, transformed content, or newly complete claims require a whole-frame call | Source remains unchanged and the result is require-new derived material |
| Forget | No participant-path prewarm in the current study | None | Every instruction uses the complete live whole-frame path | Per-Memory calls are not equivalent to interpreting the Context together, and a bounded selector cache would bias which user-grounded requests appear fast |
| Atomize or Impact | Exact Source revision and operation contract | Exact unchanged result can be reopened | Changed Source or instruction runs live | Cached analysis does not itself authorize mutation |
| Refine | Exact Memory or bounded frame, instruction, and revision | Exact unchanged proposal can be reopened | New wording instructions normally run live | Meaning preservation and authority must be revalidated |
| Find or Query | Normally use ordinary indexes and exact saved results rather than semantic prewarm | Reopen an exact retained result when its contract permits | New questions or queries run live | A saved answer is not reusable for a different question |

The `Live path` column is not an exceptional fallback. It is the universal
execution path. Exact prewarm and the explicitly disclosed Compare projection
are latency shortcuts for frozen rows. Other operation families still require
their own quality and authority decision before enabling projection.

## Initial Task 2 Compare rows

| Route | Policy | Reason |
| --- | --- | --- |
| `task-2/advisor1` versus `task-2/advisor2`, both descendant-inclusive | `EXACT_PREWARM` | The complete `150:150` comparison is a meaningful user action and has taken far longer than 30 seconds |
| Any `advisor1/...` view versus any `advisor2/...` view whose Memories are unchanged subsets of the exact parent sides | `PARENT_PROJECTED` | Host filtering is immediate and complete by coverage; the accepted semantic-loss tradeoff is disclosed as `PROJECTED · NOT SAVED · PREVIEW` |
| Two sibling views below the same advisor | `LIVE`, or a separately enumerated exact prewarm row when the scenario makes it likely | The opposite-side parent artifact contains no judgment between two Memories that occupied the same side |
| A cross-task pair | `LIVE`, not task-cache reuse | The study cache is task-local and cross-task semantics were not jointly precomputed |
| Any parent or descendant view after a Memory addition or edit | `LIVE` | The current revision is no longer the frame interpreted by the exact parent artifact |

The retained Sol-medium compact evidence does not establish that every small
Compare is safely below 30 seconds. Ten `7:7` calls had a 16.831-second median,
but two took 32.217 and 40.489 seconds. Small unlisted calls are therefore a
reasonable live fallback for a qualitative prototype, not a strict 30-second
guarantee.

## Per-task disclosure table

The final study protocol must publish an operation-by-task matrix before the
first participant. The study cache is a small explicit registry of the checked
canonical artifacts. The earlier all-pairs graph sidecars are not copied,
consulted, or used by the participant path.

The current recommended draft is:

| Operation | Tutorial | Task 1 peer | Task 2 peer | Task 3 year↔year | Task 3 rule↔rule | Task 3 rule→memory | Task 3 Forget live control |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Compare | ☐ | ☑ | ☑ | ☑ | ☑ | ☐ | ☐ |
| Update | ☐ | ☑ | ☐ | ☐ | ☐ | ☐ | ☐ |
| Meld — symmetric | ☐ | ☑ | ☑ | ☑ | ☑ | ☐ | ☐ |
| Meld — directional | ☐ | △ | ☐ | ☐ | ☐ | ☐ | ☐ |
| Atomize | ☑ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ |
| Refine | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ |
| Forget | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ |
| Sever | ☐ | ☐ | ☐ | ☐ | ☐ | ☑ | ☐ |
| Impact | ☑ | ☑ | ☑ | ☑ | ☑ | ☑ | ☐ |

`☑` means that one or more exact bases for that Task and operation are prepared
and disclosed. `△` means the route was attempted but remains live because the
candidate failed its production semantic contract. Impact is keyed to the
exact prepared operation proposal rather than to a vaguely similar Context
pair. `☐` means that the current protocol has no declared fixed
participant-path input for prewarming; it does not mean the operation is
unavailable or technically uncacheable.

The matrix does not repeat projection mechanics. Every checked cell uses an
exact frozen basis as a cache hit. A subset request uses a visibly projected
result only when that operation's adapter is declared and has passed the
fresh-partial quality campaign. Otherwise the subset needs its own exact
prewarm row or runs live. Any addition, edit, scope mismatch, instruction
change, or other key miss runs the complete requested operation live. Compare,
Update, symmetric Meld, directional Meld, Sever, and Impact retain separate
artifact and output contracts.

The two Meld rows are intentionally distinct cache families. Symmetric
`A + B → C` treats A and B as equal-authority read-only peers and materializes
a complete new C. Directional `INCOMING A → BASELINE B` keeps A read-only,
treats B as both authoritative baseline and mutation target, and materializes
only exact `EDIT` and `ADD` changes to B. Source order, authority, target
preconditions, output shape, and projection safety therefore differ. A
symmetric artifact never satisfies a directional cache key or vice versa.

The checked cells expand to the following initial basis list:

| Task | Operation | Canonical large basis |
| --- | --- | --- |
| Tutorial | Atomize | The frozen practice Source and fixed tutorial instruction |
| Task 1 peer | Compare, Update, symmetric Meld, directional Meld | Descendant-inclusive `participant/construction-updates` `75` and `campus-wiki` `300`; directional Meld freezes `construction-updates` as `INCOMING` and `campus-wiki` as `BASELINE`, while every operation records its own target contract |
| Task 2 peer | Compare, symmetric Meld | Descendant-inclusive `advisor1` `150` and `advisor2` `150`; symmetric Meld also records its exact new result destination and pre-response state |
| Task 3 year↔year | Compare, symmetric Meld | Every exact year pair declared before the study, such as `2024` and `2025`; a combined or newly edited year Context is a different key |
| Task 3 rule↔rule | Compare, symmetric Meld | The exact two ordinary Criteria frames selected for equal consideration; the pair must be frozen before the study |
| Task 3 rule→memory | Sever | Descendant-inclusive `local/personal-memory` `300` plus the exact ordinary Criteria Context used by the study |
| Prepared proposal in every checked Task column | Impact | The exact Atomize, Update, Meld, or Sever proposal digest and the unchanged Source/Target revisions used to produce its before-apply report |

Directional Meld is prewarmed only for Task 1's exact
`construction-updates → campus-wiki` tuple. Every other directional Meld remains
live until its own `INCOMING`, `BASELINE`, and baseline-mutation target tuple is
frozen. It never inherits a symmetric Meld artifact. Task 1 Update remains
checked independently; its directional publication contract is not
directional Meld.

### Pilot-derived Forget evaluation corpus, not a cache catalogue

Forget does not use a regulation Context as its criterion. It interprets one
complete Source frame under one process-local natural-language instruction.
The current study deliberately does not prewarm a bounded catalogue of
recurring Forget intents. Doing so would make researcher-anticipated wording
instantaneous while an equally valid participant-authored instruction remained
slow, confounding the operation study with hidden utterance coverage.

The following utterance families remain a pilot-derived quality corpus. They
test whether the live operation grounds short expressions such as `민감한 거`,
deictic references such as `description에서 말한 것`, and complements such as
`건강 관련 정보 빼고 다` against the visible Task 3 state. They do not authorize
cache lookup. Forget application still requires its ordinary explicit review
and acceptance boundary.

Freeze the evaluation corpus before the main study and apply the same version
to every model-quality campaign. Do not turn a newly observed main-study
utterance into a later participant's cache hit. Pilot evidence rather than
researcher convenience determines which entries below remain in the corpus.

The initial Task 3 utterance families and compiled selectors are:

| What a participant may say | Compiled selector | Default action |
| --- | --- | --- |
| `민감한 정보`, `민감한 거`, `개인적인 건 지워줘` | `SENSITIVE`, grounded in the frozen Task 3 description and guardrails | Forget matching Memories |
| `description에서 말하는 거`, `설명에 해당하는 것들` | `DESCRIPTION_MATCH`, bound to the exact visible description digest | Forget matching Memories |
| `건강 관련 정보`, `진료나 복약 관련된 거` | `HEALTH` | Forget matching Memories |
| `건강 관련 정보 빼고 다`, `건강 정보만 남기고 나머지는` | `HEALTH` with `EXCEPT` polarity | Keep matching Memories and forget the complement |
| `가족 얘기`, `다른 사람 정보`, `내 정보 아닌 거` | `THIRD_PARTY` | Forget matching Memories; mixed Memories may retain only the user's own content |
| `보안 관련`, `열쇠나 출입 정보`, `문서 위치 같은 거` | `SECURITY_AND_ACCESS` | Forget matching exact access, credential, and storage details |
| `돈 관련`, `세금이나 청구서`, `행정 정보` | `FINANCIAL_AND_ADMIN` | Forget matching Memories |
| `끝난 일정`, `지난 약속`, `이미 끝난 일들` | `COMPLETED_EVENT` | Forget matching completed event details |
| `2024년 거`, `작년 기록` | `TIME_RANGE`, resolved against the explicit year or study date | Show the resolved range, then evaluate the complete live Forget batch under that instruction |
| `오래된 거` | `TIME_RANGE` with an unresolved threshold | Ask for or expose the cutoff before running the live batch |
| `구체적인 일은 잊고 취향만`, `세부 사건 말고 선호만 남겨줘` | `EPISODE_TO_PREFERENCE` | Transform or drop episodic details while retaining only supported user preferences and policies |
| `description에서 말한 것 빼고 다` | `DESCRIPTION_MATCH` with `EXCEPT` polarity | Keep description-matching Memories and forget the complement |
| `공유할 것 빼고 다`, `안 보낼 건 다 잊어줘` | `CURRENT_SHARE_SET` with `EXCEPT` polarity | Resolve against the exact reviewed Sever result, then make the durable deletion consequence explicit |

The quality scorer may normalize the requests into this small criterion algebra
for analysis; the participant path still sends the person's complete live
instruction:

```text
selector: SENSITIVE | DESCRIPTION_MATCH | HEALTH | THIRD_PARTY | ...
polarity: MATCH | EXCEPT
action: DROP | TRANSFORM
referent: fixed task description | explicit time range | reviewed Sever result | none
```

`MATCH` and `EXCEPT` remain separate semantic test conditions even when one is
the mathematical complement of the other, because mixed-Memory transformation
and deictic grounding can differ. `EPISODE_TO_PREFERENCE` is scored separately
because replacement text cannot be assessed as membership alone.

Short wording is not rejected merely for being broad. The system asks only
when a material variable remains unresolved, such as the cutoff in `오래된 거`,
what `그거` refers to, or whether `안 보낼 건 다 잊어줘` really authorizes
durable deletion rather than merely Sever exclusion. Every resolved request
then takes the same complete live whole-frame path.

The 300-Memory production-contract benchmark supports this exclusion. Terra
low completed in `255.225` provider seconds and Sol none in `294.812` seconds;
both were contract-valid and agreed with the earlier applied run on `270/300`
action labels, but their error shapes differed materially. Terra low converted
many reference edits into deletes, while Sol none introduced many additional
edits. Luna low returned only after several minutes and failed the exact-KEEP
contract. The two valid ledgers are retained under `outputs/forget-latency/`.
These are agreement measurements against one stochastic earlier run, not
ground-truth accuracy, and none approaches the participant-facing latency
target.

A later evaluation-only compact-output campaign ran the first eight frozen
utterance families across eight model/reasoning conditions. It retained the
complete 300-Memory whole-frame input but replaced the exhaustive narrative
response with one dense action vector and sparse edit text. Thirty-five of 64
final calls met 30 seconds, but broad requests remained semantically unstable:
`SENSITIVE` ranged from keeping all 300 Memories to deleting all 300, and
`COMPLETED_EVENT` changed between 30 and 212. The `THIRD_PARTY` transformation
also exposed frequent disagreement between action-vector positions and sparse
edit positions. The full result is recorded in
[`outputs/forget-latency/compact-corpus-matrix-v1/`](../outputs/forget-latency/compact-corpus-matrix-v1/README.md).
It remains a pilot quality corpus rather than a cache catalogue, and it does
not justify changing the participant path or skipping review.

A checked cell is not executable until every canonical basis named by that cell
is enumerated with its exact key. A registry row is the sole cache-hit
authority. If the protocol later changes which routes receive prewarming,
version the matrix and basis list and report the amendment; do not silently
broaden them between participants.

## Registry columns and participant-visible status

The executable registry should eventually record:

- task and operation;
- canonical Source, peer, Criteria, and Target locators as applicable;
- exact versus descendant scope;
- frozen Context UID and digest inputs;
- task-description, prompt, ruleset, model, and reasoning versions;
- expected input count and the rationale for prewarming;
- artifact key, completion status, and offline provider time; and
- foreground policy: `EXACT_PREWARM`, `PARENT_PROJECTED`, `LIVE`, or
  `STALE_REFRESHING`.

It must also record whether preparation completed successfully and whether the
study adapter is permitted to use that exact artifact. Unrelated experimental
outputs do not participate in lookup.

Offline provider work and foreground participant waiting must be reported
separately. A cache hit demonstrates a low-latency interaction condition; it
does not demonstrate that fresh semantic computation met the 30-second target.

## Invalidation

Presentation-only changes do not invalidate semantic artifacts. A projection
algorithm change invalidates projected derivatives but not their exact parent
analysis. Changed Memory content or membership, Context identity, semantic
instruction, task description, prompt contract, relation ruleset, model, or
reasoning setting invalidates the corresponding exact semantic artifact.

## Repeated whole-frame and partial-frame quality campaign

Cache correctness is not sufficient evidence that the cached semantic result
is useful. The study therefore keeps two related but different registries:

- the **evaluation corpus** contains every operation-and-task case selected for
  repeated quality testing, including live-only and negative cases; and
- the **participant prewarm registry** contains only the frozen, scenario-valid
  exact artifacts and projection routes declared before the first participant.

This is not a blind Cartesian product of every verb and every Context. A case
must first satisfy the operation's type, authority, direction, and target
preconditions. For example, an Update with no editable Target is an authority
test, not a semantic prewarm basis. Conversely, participant-generated Refine
text cannot be prewarmed generically even though fixed Refine examples belong
in the evaluation corpus.

### Repetition schedule per canonical basis

For each valid canonical basis, freeze the complete inputs and three meaningful
partial cases before running a provider. Partials are selected by public
Context structure and scenario meaning, not by inspecting which examples make
projection look good. Use a small leaf or topic, a medium branch, and a large
deletion or complement when the fixture supports those shapes.

| Phase | Runs | Provider calls | Purpose |
| --- | ---: | ---: | --- |
| Fresh whole frame | 3 | 3 | Measure contract validity, latency, and ordinary same-contract variation on the complete inputs |
| Exact cache reopen | 3 | 0 | Prove byte-identical artifact recovery, zero provider calls, stable review projection, and foreground latency |
| Three partial cases | 3 projected or exact-cache reopens per case | 0 | Prove deterministic coverage and rendering for the prepared partial route |
| Fresh partial controls | 2 per partial case | 6 | Compare every prepared partial result with live semantic judgments on the exact same partial inputs |
| Key misses | 2 | 2 | Exercise one add/edit revision change and one operation-specific change such as direction, instruction, Criteria, or Target |

The default is therefore `11` provider calls per valid basis and `12`
provider-free cache/projection reopens. A smoke stage first runs one whole frame,
one fresh call for each partial, and one key miss. Only contract-valid rows
continue to the remaining repetitions, so a broken schema does not waste the
full campaign budget.

Run index `1` is declared as the canonical artifact before output is inspected;
runs `2` and `3` are audits. A contract-invalid canonical run makes the row
not cache-ready. The system must not silently choose the most attractive of
three stochastic outputs. A material semantic defect discovered under a
predeclared quality gate triggers a protocol-wide row change before the study,
not participant-specific output selection.

### Projection is an operation-specific hypothesis

Every partial case is evaluated, but not every operation receives parent
projection:

| Operation | Prepared partial hypothesis |
| --- | --- |
| Compare | Project a left subset against a right subset, repair group shapes, and compare it with two fresh partial Comparisons |
| Update | Test filtered action/provenance projection; enable it only when removed evidence cannot leave a surviving action unsupported, otherwise prewarm the partial pair exactly |
| Symmetric Meld | Do not assume that filtered full-output prose equals a fresh partial Meld; default to a separately prewarmed exact partial proposal |
| Directional Meld | Keep order and baseline authority fixed; default to separately prewarmed exact partial proposals because removed incoming evidence can change a baseline edit |
| Sever | Test deletion-only Source projection against fresh partial Sever; a Criteria subset is a different semantic basis and needs exact prewarm or live inference |
| Atomize | Treat a changed or excerpted Memory as a new exact input; atoms cannot be projected from different Source wording as if the whole Memory were unchanged |
| Refine | Cache only exact Memory, instruction, and revision tuples; new participant wording or instructions run live |
| Impact | Recompute deterministic impact from an exact prepared proposal when possible; otherwise cache the exact proposal-digest report, not a loosely related operation result |
| Forget | No cache or projection in the participant path; use repeated complete live runs in the quality corpus only |

### Operation-owned quality measurements

Fresh run `1` is not ground truth. Report inter-run agreement, comparison with
the prepared partial result, and blind human review separately. Exact string
equality is required only where the contract requires exact preservation;
generated prose is scored as claim-level meaning and provenance.

| Operation | Automatic checks | Result-quality review |
| --- | --- | --- |
| Compare | Complete exactly-once source coverage; valid group sides; relation-kind distribution; pairwise co-membership precision, recall, and F1; source-kind and issue overlap across runs | False merge, false split, relation-kind plausibility, missing consequential conflict, and whether the grouping supports the intended comparison |
| Update | Complete Source disposition; unique target actions; valid owner and authority; action-set overlap; applied target digest; atomic rollback | Unsupported add/edit/delete, missed required change, preservation of unaffected target content, and whether the applied Context satisfies the update request |
| Symmetric Meld | Both-source provenance coverage; new-target-only materialization; duplicate-claim rate; apply/undo/redo identity | Information loss, unsupported synthesis, unresolved contradiction, redundancy, and whether neither peer was treated as the hidden winner |
| Directional Meld | Incoming read-only; baseline-only owner changes; `EDIT`/`ADD` contract; action and applied-state overlap | Whether baseline authority was preserved, useful incoming evidence was incorporated, and unrelated baseline claims survived |
| Sever | Exactly one KEEP/TRANSFORM/DROP decision per Source Memory; Source unchanged; nonempty transforms; retained-set and action-vector agreement | Over-disclosure, over-removal, unsupported abstraction, transform fidelity, and usefulness for the stated Criteria |
| Atomize | Source proposition coverage; atom count; duplicate atoms; no empty atoms; reconstruction trace | Atomicity, omitted qualification, invented fact, and whether the atoms collectively preserve the original meaning |
| Refine | Required style-constraint checks; no new named entity or unsupported factual unit; exact Source and instruction identity | Bidirectional meaning preservation, grammatical or stylistic improvement, and whether qualification and formality remain appropriate |
| Impact | Predicted changed owners, counts, and before/after digests versus the actual applied operation; omitted or false impact rows | Whether the report exposes the consequences a participant needs before acceptance |
| Forget, live only | Complete decision coverage; exact KEEP; empty DELETE; nonempty EDIT; action-vector agreement and latency | False deletion, insufficient forgetting, survival of independently meaningful remainder, and fidelity of every transformed Memory |

Human review uses source content, operation instruction, and result without
showing whether the result was fresh, exact-prewarmed, or projected. Reviewers
record `acceptable`, `repairable`, or `unsafe/invalid` plus one operation-owned
error code. The campaign reports disagreement rather than calling one fresh
model run accurate. A projection may remain useful for the qualitative study
while differing from fresh inference, but it must be visibly labeled and may
not pass a predeclared critical safety, authority, provenance, or invention
gate.

### Task-specific execution set

The first campaign uses the following scenario-grounded cases. The exact three
partial locators for each basis must be added to the executable registry before
provider work begins.

| Task | Repeated whole-frame operations | Partial cases and live controls |
| --- | --- | --- |
| Tutorial | Atomize the frozen practice Source; reopen its exact Impact; exercise fixed Refine examples only as evaluation fixtures | Modified instruction and modified Source are live misses; an excerpt is a separate exact Atomize input, never a parent projection |
| Task 1 | Compare, Update, symmetric Meld, directional Meld, and Impact on descendant-inclusive `construction-updates` `75` and `campus-wiki` `300` | Three scenario topics such as building access, route/facility changes, and parking/shop effects; reverse Meld direction and one Source or baseline edit are live controls; fixed Refine samples are evaluator-only unless the protocol displays those exact Memories |
| Task 2 | Compare and symmetric Meld on `advisor1` `150` and `advisor2` `150`, plus Impact for the exact prepared Meld | Three aligned section pairs, including structure, methods/evaluation, and style/expression, plus one asymmetric-size partial; same-advisor comparison and a changed advisor revision are live controls; Update without an editable participant Target is a negative precondition test |
| Task 3 | Every declared year-pair Compare and symmetric Meld; every declared rule-pair Compare and symmetric Meld; full `personal-memory` `300` to exact Criteria Sever; Impact for exact prepared Sever/Meld proposals | Year-to-month and month-to-month Compare controls; Source-year, Source-month, and large-deletion Sever projections; Criteria-subtree Sever as exact/live rather than projected; changed Criteria and added personal Memory as misses; Forget utterance families run live only |

Each materializing operation runs on an isolated copy for quality evaluation.
The campaign records the proposal, review decision, applied result, read-only
verification, undo, and redo. No run is allowed to consume the durable result
of another run unless the task case explicitly defines that dependency and
freezes its digest.

## Implementation and verification plan

The implementation uses one small versioned Study prewarm registry and only
the artifacts named by its checked basis rows. It does not import or search the
earlier all-pairs graph sidecars.

| Work item | Implementation | Required verification |
| --- | --- | --- |
| Registry and lookup | Persist the frozen matrix, exact basis keys, preparation status, offline provider time, and allowed `EXACT_PREWARM` or projection route. Lookup is an optimization decision, never operation authorization. | A checked exact key hits with zero provider calls; an unchecked route, wrong operation mode, changed digest, or unlisted key takes the ordinary live path. No unrelated output file is searched. |
| Compare | Store one canonical whole-pair relation artifact per declared basis. Project only a requested left subset versus right subset, repair relation sides and coverage, and label the result projected. | Extend `test_compare_prewarm_projection.py`: exact hit, subset coverage, group-count bound, same-side rejection, add/edit miss, stale ruleset miss, and zero partial publication. |
| Update | **Task 1 exact basis implemented.** Store an ordered Source-to-Target action proposal keyed by both complete revisions, scopes, task description, provider identity, and operation contract; regenerate run-local authority bindings during setup. Keep partial projection experimental until repeated fresh-partial controls show that surviving actions remain supported. | Exact reuse, Source change, configuration skip, current owner/provenance rebinding, existing multi-owner apply, and public undo/redo are covered. Projected-versus-fresh action support remains future work. |
| Symmetric Meld | **Task 1, Task 2, and all declared Task 3 initial paths verified.** Reuse the exact peer Compare seed, bind only to a valid empty new C, and keep participant-authored synthesis turns live. Prepare partial Melds exactly unless a later claim-provenance projection passes the quality gate. | Exact basis reuse, complete provenance coverage, empty-C precondition, provider-free preserve-all, and exact apply are verified for Task 1, Task 2, every year pair, and the rule pair. Live synthesis quality and partial controls remain. |
| Directional Meld | **Task 1 candidate rejected by the production quality gate.** The attempted `construction-updates` `INCOMING` to `campus-wiki` `BASELINE` response changed its imported Compare relation ledger, so no artifact was published. | The failed attempt is recorded with zero partial publication. Exact reuse, owner/action checks, recovery, and fresh-partial comparison remain blocked until a contract-valid basis exists. |
| Forget live quality corpus | Keep Forget out of the participant prewarm registry. Run the frozen pilot utterance families through the complete one-turn whole-frame contract for latency, contract validity, and result-quality evidence. | Exactly-once KEEP/TRANSFORM/DROP coverage, exact KEEP, valid transforms and drops, repeated-run agreement, blind review, no partial publication, and no Source mutation before explicit acceptance. |
| Sever | **Task 3 exact basis implemented.** Store exact whole-Source plus exact ordinary-Criteria decisions as a hidden artifact, clone a fresh review only after current authority and frame validation, and keep changed inputs live. | Exact hit, configuration skip, Source-addition and output-name miss, complete disposition, provider-forbidden start, hidden session catalogue, Source unchanged, require-new output, and apply/undo/redo are verified. Source-deletion projection and a changed-Criteria live E2E control remain. |
| Tutorial Atomize | **Implemented.** Store only the exact frozen practice Source and instruction analysis in Atomize's existing durable slot; create fresh run-local review state. | Exact reopen without provider, Source or instruction change miss, complete source provenance, configuration skip, atomic installation rollback, and no mutation before its existing review boundary. |
| Refine | Store only frozen exact Memory, instruction, revision, and style-contract tuples that the protocol actually exposes. Participant-authored wording remains live. | Exact reopen, instruction or Source miss, bidirectional meaning review, required style checks, no unsupported factual unit, and unchanged Source until acceptance. |
| Impact | Key a prepared report by the exact proposal and Source/Target revision digests, or recompute it deterministically when the proposal already contains the full typed diff. | Predicted-versus-applied owner, action, count, and digest agreement; exact reopen; proposal change miss; review before mutation; and read-only post-apply verification. |
| Participant-visible status and study ledger | Render and record `EXACT PREWARM`, `PROJECTED`, or `LIVE`, registry version, foreground elapsed time, and separate offline provider work. | End-to-end Study runs assert the same registry for every participant. If UI changes materially, capture the required ordered color-PTY states for exact hit, projection, live miss, review, apply, and read-only verification. |

The final integration campaign uses the frozen Study Profile and the repetition
schedule above. It exercises every declared whole basis, all three predetermined
partial cases, exact hit, applicable projection, unchecked live route, and both
key misses for each implemented operation family. Foreground lookup and
deterministic projection are measured separately from offline preparation and
live provider time. The target is under 30 seconds for exact hits and declared
projections; no claim is made that every unexpected live provider call satisfies
that bound. Forget remains a measured live-only control rather than an exception
silently routed through a cache.
