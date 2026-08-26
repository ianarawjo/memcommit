# Task 2 portable semantic harness design rationale

## Goal

Task 2 is the first end-to-end portability target for semantic operations. A
provider receives 150 `advisor1` Memories and 150 `advisor2` Memories and must
recover the same independently reviewable relationship groups before assigning
relationship semantics. The target providers are Sol as a reference teacher,
Luna-low, local Qwen, and later OpenRouter routes that implement the same
provider contract.

Passing a small label classifier is not sufficient. The harness must separately
measure whether a provider:

1. retrieves the relevant opposite-side material;
2. reconstructs the reviewed hypergroups without omissions or duplicates;
3. assigns inspectable relationship evidence and a final band; and
4. produces the same result as another provider on exactly the same frozen
   input.

Sol is a reference provider, not Gold. Agreement with Sol and agreement with
reviewed Gold are reported separately, including cases where both models make
the same wrong decision.

## Retired support boundary (2026-08-26)

The V5--V8 judge-replay branch completed its consumed-calibration role but did
not pass the promotion boundary described below. Its live runners, CLI run and
parity commands, read-only V5 adjudication queue, status rendering, and focused
pytest contracts are therefore retired. Normal product behavior never depended
on that branch, and keeping it executable would preserve a large unsupported
research surface without a planned rerun.

The remaining V1--V5 discovery, classification, retrieval, and candidate-only
calibration routes were retired on the same date after this recorded experiment
had reached its conclusion and no production command depended on them. Their
frozen lock manifests, run/parity/status CLI surfaces, and focused pytest
contracts are no longer maintained. The enclosing `mem eval semantic` route
remains for unrelated campaigns; the ordinary Task 2 Study fixtures and
production Compare relation grouping also remain.

Immutable ledger JSON and the historical measurements in this note remain as
research evidence. Git history is the source for reconstructing the exact
executable calibration implementation if the experiment is ever reopened.

## Reviewed Gold and its boundary

The English sidecar partitions all 300 Memories into 138 reviewed hypergroups:
129 are 1:1 and nine have multiple members on at least one side. The shape
distribution is four 3:3 groups, two 1:2 groups, and one each of 2:1, 3:2, and
2:2. Every Memory occurs exactly once.

This is not a 22,500-row atomic-pair answer key. In a 3:3 group such as
schedule, recruitment, and technical-assumption guidance, the reviewed fact is
that the six Memories form one structured relationship group. It does not say
that every one of the nine Cartesian pairs is independently a direct semantic
match. Consequently:

- exact hypergroup recovery and opposite-side **group co-membership** are valid
  reviewed targets;
- the 129 1:1 groups also provide a reviewed directed subset covering 258 of
  300 source Memories;
- the 42 source Memories in multi-member groups must not be reported as atomic
  pair accuracy; and
- a future atomic-edge experiment needs independent review of the 52 possible
  within-group Cartesian edges, plus adjudicated hard negatives. It does not
  require reviewing all 22,500 cross-advisor combinations.

Earlier V1/V2 fields named `member_counterpart_*` are group-induced
co-membership projections. Their immutable ledgers remain useful, but those
fields must not be reinterpreted as independently reviewed pair correctness.

## Frozen corpus and provenance

The consumed English calibration is frozen by
`memcommit/eval/fixtures/task2_discovery.lock.json`. It binds the corpus,
sidecar, input, alias mapping, Gold manifests, counts, and band distributions
for four scale rungs:

| Rung | Reviewed groups | Left × right | V3 calls | Candidate+verify calls |
| --- | ---: | ---: | ---: | ---: |
| pilot | 26 | 29 × 27 | 4 | 8 |
| small | 50 | 58 × 56 | 8 | 16 |
| medium | 100 | 112 × 111 | 16 | 32 |
| terminal | 138 | 150 × 150 | 20 | 40 |

The corpus is explicitly `consumed_during_optimization=true` and
`independent_holdout=false`. Improvements on it are engineering calibration,
not evidence of generalization.

The four original V1 Sol/Qwen runs predated the lock file by minutes. Their
content and sidecar digests match the later lock, but inference did not replay
the lock before starting. They are retained as `PRE-LOCK` evidence. New runs
are marked `LOCKED`. Stored legacy scores are never overwritten: scorer V2
unions repeated-member observations to remove provider-output-order dependence,
and status displays `legacy-v1` and `v2` separately. Formal parity refuses to
compare different scorer revisions.

One remaining next-lock correction is to separate `content_digest` from
`gold_digest`. The current corpus digest includes the sidecar and salts provider
aliases and order, so changing only Gold also changes the visible prompt
condition. This is not reversible leakage, but it is an avoidable comparison
confound. Existing calibration stays frozen for ledger comparability.

## Evidence before microbatch retrieval

The observed results show that the original tests did not establish Qwen/Sol
parity:

| Pipeline and slice | Sol | Qwen | Luna-low |
| --- | --- | --- | --- |
| V1, 26 groups | valid, 26/26 structures, 17/26 bands, 60.553 s | invalid, 23/26 structures, 14/26 bands, 22.741 s | not run |
| V1, 138 groups | invalid, 85/138 structures, 33/138 bands, 364.512 s | invalid, 72/138 structures, 51/138 bands, 184.820 s | not run |
| V2 structure, 26 | valid, 26/26, 54.227 s | invalid, 12/26, 48.044 s | valid, 26/26, 48.035 s |
| Oracle-group band, 26 | 13/26, 37.371 s | 14/26, 20.733 s | 15/26, 29.695 s |

On V1's 26-group slice, Qwen and Sol shared 23 structures but only 11
structure-plus-band decisions. On the full 150-by-150 run they shared 71
structures and 26 structure-plus-band decisions. In oracle-group
classification, Qwen and Sol agreed on 19 bands, but only 11 were jointly
Gold-correct and eight were the same wrong band. Model agreement therefore
cannot substitute for correctness.

The fine band boundary is independently problematic. Both strong and local
providers systematically confuse `Near Duplicate`, `Same-Principle Variant`,
and `Compatible Complement`. Band optimization remains separate from retrieval
and needs independent evidence-axis annotations and rationale.

## V3: source-anchored group co-membership retrieval

V3 replaces a global partition response with a fixed bidirectional schedule.
Each call sees at most 15 source Memories and the complete opposite-side target
collection. For every source it returns all one-to-three opposite-side Memories
that belong to the same reviewed-style relationship group. This wording is
deliberately group co-membership rather than `direct pair`: a structured N:M
group can contain aligned parts without asserting every Cartesian pair is a
standalone paraphrase.

The provider never sees fixture IDs, bands, Gold membership, or teacher output.
The host validates source coverage, direction, aliases, target cardinality, and
duplicates. It never fills a missing selection from Gold or another provider.
Both reciprocal-edge and union-edge connected components are retained as fixed
diagnostics. Neither is selected after looking at Gold.

The score reports:

- exact and macro-Jaccard group co-membership over all selected Memories;
- the reviewed 1:1 subset separately (48/56 sources at the 26 rung and 258/300
  at the terminal rung);
- reciprocal and union exact-component recovery; and
- provider-to-provider co-membership agreement, reviewed-Gold quadrants, call
  failures, and elapsed time.

V3 uses strict structured output where supported, but host validation remains
authoritative. JSON Schema avoids unsupported `uniqueItems`; duplicates are
rejected locally. Every call retains raw response and prompt, schema, response,
and local timing digests. Known provider failures are redacted to the exception
type and later calls continue.

Campaign durability is currently `FINAL_ONLY`: the complete ledger is written
atomically after all calls and record assembly. A process death before that
write can lose completed in-memory calls. This is an explicit limitation for a
20-call run and must be replaced with append-only or snapshot progress before
large unattended campaigns are treated as interruption-safe.

The first Qwen V3 26-group attempt was a real failure. One of four calls mixed
right-side source aliases into left-target output and invalidated the contract.
The retained run scored 19/56 exact group co-membership, 17/48 on the reviewed
1:1 subset, 10/26 reciprocal components, and 2/26 union components in 69.001
pipeline seconds. A post-run candidate diagnostic over the raw ranked lists
found complete reviewed co-members in 50/56 source lists, at least one correct
co-member in 54/56, and mean co-member recall 0.929. This is evidence that V3 is
a useful candidate generator but a poor final cardinality decision for Qwen.

On the same frozen schedule, Sol was contract-valid, recovered 55/56 exact
co-membership sets and 48/48 reviewed one-to-one sources, and reconstructed all
26 reciprocal and union hypergroups in 130.425 seconds. Its only membership
miss was one source in the 3:2 group returning one of two reviewed co-members.
Luna-low was contract-valid at 48/56 co-membership, 44/48 one-to-one, 22/26
reciprocal groups, and 18/26 union groups in 74.933 seconds.

Provider agreement remained distinct from Gold accuracy. Qwen/Sol agreed on
18/56 co-membership sets (macro Jaccard 0.490); Qwen/Luna agreed on 19/56
(0.506); and Sol/Luna agreed on 47/56 (0.902). Their jointly Gold-correct
one-to-one counts were respectively 17/48, 17/48, and 44/48. Qwen's invalid
contract prevents any parity gate from passing even where a partial selection
matches another provider.

Those measurements are retained in these immutable V3 ledgers under
`agent-records/outputs/semantic-eval-v1/task2-retrieval-v3/`:

- Qwen: `20260803T223644259507Z-ca620062e2ba44719fbedcd90bbcf536-ollama.json`
- Sol: `20260803T223934243269Z-2a0e9e3ba0d7491db4d08a1997c83371-codex_chatgpt.json`
- Luna-low: `20260803T224328509380Z-d44ca97ff8e64086a22841a506fd0270-codex_chatgpt.json`

Parity validation checks retained raw-response digests and the consistency of
call-level and top-level normalized selections. It still trusts the ledger
construction boundary: because the old ledgers do not retain the complete
call-local alias map or a signature, a party able to rewrite a ledger and
recompute its digests can forge internally consistent evidence. These records
are corruption-detecting research artifacts, not tamper-proof attestations.

## V4 direction: candidate generation then bounded verification

The V3 failure should not be addressed by adding a longer monolithic prompt.
The next experiment separates retrieval recall from selection precision:

1. For each source, Stage A returns exactly three ranked candidates from the
   complete opposite collection. It makes no final cardinality decision.
2. Stage B sees only that source and its three candidate texts and selects the
   one-to-three members belonging to the same relationship group.
3. Call-local `s01...` and `t001...` aliases make source/target roles explicit
   without exposing fixture identity or supplying semantic match evidence.
4. Both directions run on the same fixed batches. Invalid or provider-error
   calls are retained; no Gold-conditioned repair or retry is allowed.
5. The host reports candidate recall@3, final co-membership precision/recall,
   component recovery, multi-member recovery, and model agreement separately.

This doubles the frozen schedule to 8, 16, 32, and 40 calls across the four
rungs. It is accepted only if the precision gain justifies the added latency.
If verification remains unstable for three revisions, the design moves to an
explicit binary evidence classifier or a bounded component-reconciliation
stage rather than accumulating more prompt prose.

### V4 observed result: retrieval improved, subset verification failed

The first locked 26-group V4 runs were contract-valid for all three providers,
but none passed the single-run rung gate:

| Provider | Candidate recall@3 | Final co-membership exact | Reviewed 1:1 | Reciprocal groups | Multi groups | Stage A / Stage B / pipeline |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen thinking-off | 60/64 | 36/56 | 36/48 | 16/26 | 0/2 | 53.822 / 34.738 / 88.563 s |
| Sol high | 64/64 | 37/56 | 34/48 | 18/26 | 0/2 | 98.942 / 218.304 / 317.249 s |
| Luna-low | 61/64 | 35/56 | 35/48 | 18/26 | 0/2 | 59.405 / 61.810 / 121.218 s |

Qwen retained only 41 of the 60 Gold co-members that were available in its
candidate lists, or 0.683 conditional recall, while accepting nine unrelated
directed candidates (41/50 final precision). Its one-to-one conditional recall
was 40/48, but multi-member conditional recall was only 1/12. Ten empty
verifier selections each had at least one Gold candidate available. Sol also
retained only 47/64 available Gold members. The failure is therefore not
explained by Qwen retrieval alone: the free subset verifier behaves too much
like a paraphrase filter and discards conflicts, context variants, and joint
parts even for the reference model.

The implementation review fixed three issues before these runs: a verifier may
now return zero candidates instead of being forced to invent a match; campaign
provenance admits that reviewed relations select and salt the consumed input
before calls; and multi-member recovery is a dedicated mechanical metric. The
retained ledgers are:

- Qwen: `20260803T230626829831Z-8fc6030f79a74f3091984b75b323b8e0-ollama.json`
- Sol: `20260803T230939914021Z-1d4df4fbdbc84383a7b4257acdb66dba-codex_chatgpt.json`
- Luna-low: `20260803T231536275203Z-35a7ce863cd64d398114d69fcecec194-codex_chatgpt.json`

End-to-end V4 agreement was also far from parity. Qwen/Sol agreed on 13/56
candidate sets and 34/56 final sets, with 27/48 reviewed one-to-one sources
jointly Gold-correct. Qwen/Luna were 11/56, 40/56, and 31/48; Sol/Luna were
23/56, 40/56, and 30/48. These are not pure judge-agreement measurements,
because each verifier saw its own provider's Stage-A candidates.

The next experiment therefore isolates judgment before changing retrieval.
It freezes a Gold-blind deterministic union of retained Stage-A candidate sets
and gives every provider exactly the same candidate pairs. Every pair must be
classified as `NEAR_DUPLICATE`, `SAME_PRINCIPLE`, `CONTEXT_VARIANT`,
`CONFLICT`, `COMPLEMENT_OR_JOINT_PART`, or `UNRELATED`; only `UNRELATED` is
excluded from group co-membership. Synthetic contrastive examples teach that
opposite prescriptions and atomized joint parts are relationships without
copying fixture answers. This lane measures label agreement, binary membership
agreement, Gold quadrants, and conditional quality on identical inputs.

Only after the judge lane passes should end-to-end retrieval expand from top-3.
Qwen recovered all 48/48 one-to-one directed members but only 12/16
multi-member directed members; one multi-group edge was absent in both
directions. A separate candidate-only ablation will test top-4 and then top-5,
without simultaneously changing verifier semantics.

The first candidate-only ablation has now run. Top-4 recovered 61/64 directed
co-members, 47/48 one-to-one, 14/16 multi-member, 24/26 exact recoverable
groups, and 1/2 multi groups in 59.123 seconds. Top-5 recovered 63/64,
47/48, 16/16, 25/26, and 2/2 respectively in 59.436 seconds. The remaining
miss was the right-to-left side of the context-dependent T2-019 group. Top-5
therefore clears the provisional aggregate 0.98 recall threshold and fixes the
known multi-group ceiling, but it does not clear exact 26/26 recoverability or
the 48/48 one-to-one regression gate. It is not yet eligible for scale-up.
The immutable ledgers are under `agent-records/outputs/semantic-eval-v1/task2-candidate-ablation-v5/`:

- Top-4: `20260803T232957077230Z-61f1c9c3808b4813848b0a246147e669-top_4-ollama.json`
- Top-5: `20260803T233124896067Z-e12c96f04e9f468290dd759fdbc3746f-top_5-ollama.json`

## V5 common-candidate judge and V6 strict-boundary ablation

V5 froze the deterministic union of all three V4 Stage-A candidate ledgers.
The resulting 26-group replay contains 249 directed candidate pairs for 56
sources in 11 fixed calls. Every provider received the same pair order, call
boundaries, call-local IDs, text, schema, and candidate ceiling. The ceiling
contains all 64 group-induced directed co-members, all 56 sources, and all 26
groups, including all 48 reviewed one-to-one directed positives. Retrieval can
therefore no longer explain a miss in this replay.

All three V5 contracts were valid, but none established judge parity or usable
final selection quality:

| Provider | TP / FP / TN / FN | Binary precision / recall | Group-induced enum | Reviewed 1:1 enum | Source sets | Multi recall | Pipeline |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen thinking-off | 59 / 60 / 125 / 5 | .496 / .922 | 154/249 | 25/48 | 14/56 | .875 | 118.044 s |
| Sol high | 64 / 106 / 79 / 0 | .376 / 1.000 | 123/249 | 30/48 | 6/56 | 1.000 | 527.013 s |
| Luna-low | 63 / 104 / 81 / 1 | .377 / .984 | 127/249 | 30/48 | 8/56 | 1.000 | 215.246 s |

The FP and TN columns above are **partition-induced negative proxies**. The
reviewed sidecar proves that their endpoints belong to different hypergroups;
it does not prove that every cross-group pair lacks any independently useful
semantic relationship. They must not be published as atomic negative-pair
accuracy. The one-to-one positive subset is direct reviewed evidence, while
multi-member pair labels and enum scores remain group-induced diagnostics.

Literal V5 agreement on the common inputs was also red. Qwen/Sol agreed on
174/249 binary decisions, 122/249 enums, and 15/56 accepted source sets.
Qwen/Luna agreed on 187/249, 125/249, and 23/56; Sol/Luna agreed on 220/249,
182/249, and 32/56. Multi-member binary/enum/source-set agreement was
28/33, 15/33, 4/8 for Qwen/Sol; 25/33, 10/33, 2/8 for Qwen/Luna; and 30/33,
25/33, 5/8 for Sol/Luna. A teacher answer is therefore not a substitute for
Gold even after retrieval is held constant.

Failure inspection found 46 cross-hypergroup pairs that all three providers
accepted and no common false negative under the partition projection. Many of
those 46 pairs are plausibly related authoring recommendations despite being
in different reviewed groups. Optimizing them blindly as `UNRELATED` would
teach the harness the partition artifact. The read-only V5 adjudication queue
therefore preserves the evidence boundary and proposes, rather than applies,
review work. On these three ledgers it contains 163 directed review items: 146
with some provider enum disagreement, 46 common accepts of a
partition-induced negative, 18 direct one-to-one positives where Sol's enum
differs from the reviewed band, 27 direct positives with at least one student
error, and dedicated multi-member failure reasons. Queue construction never
changes a fixture, score, or ledger.

V6 kept the V5 candidate freeze, call schedule, schema, parser, and scorer
byte-for-byte equivalent and changed only the decision instruction. A mandatory
relationship-unit test now rejects broad topic similarity, adjacent-section
usefulness, generic compatibility, and shared vocabulary before the six-way
enum is selected. V6 has a separate record kind, prompt-protocol digest, and
ablation-freeze digest, so retained V5 evidence is not reinterpreted.

| Provider | TP / FP / TN / FN | Binary precision / recall | Group-induced enum | Reviewed 1:1 enum | Source sets | Multi recall | Pipeline |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen thinking-off | 60 / 40 / 145 / 4 | .600 / .938 | 176/249 | 27/48 | 19/56 | .875 | 119.175 s |
| Sol high | 60 / 22 / 163 / 4 | .732 / .938 | 206/249 | 30/48 | 35/56 | .812 | 488.402 s |
| Luna-low | 63 / 31 / 154 / 1 | .670 / .984 | 199/249 | 30/48 | 32/56 | 1.000 | 226.464 s |

Against V5, V6 changed Qwen TP/FP/TN/FN by `+1/-20/+20/-1`, enum by +22,
source-set exact by +5, and latency by only 1.0%. Luna changed
`0/-73/+73/0`, enum by +72, source sets by +24, and latency by +5.2%. Sol
changed `-4/-84/+84/+4`, enum by +83, source sets by +29, and latency by
-7.3%, but its multi-member recall regressed from 1.000 to .812. The stricter
boundary is therefore useful calibration evidence, not a promotion: it reduces
over-acceptance while exposing a new Sol parts-recall tradeoff.

The provisional V6 pairwise counts before promotion remain below the required
floor: Qwen/Sol agree on 199/249 binary decisions, 170/249 enums, and 20/56
source sets; Qwen/Luna on 201/249, 169/249, and 19/56; Sol/Luna on 223/249,
208/249, and 35/56. The next revision must decompose evidence and judge each
canonical left-right pair once, then perform component reconciliation and
group-level band classification. Repeating prompt prose alone is no longer the
scale strategy.

The immutable judge ledgers are:

- V5 Qwen: `20260803T234001317928Z-7aadf9399dde4d7ea800b203aa936e86-ollama.json`
- V5 Sol: `20260803T234214069064Z-f19d6cc4cc164880aa46e84df95c12cf-codex_chatgpt.json`
- V5 Luna: `20260803T235111646822Z-aa5c280063764193a143ed69ab9f7a01-codex_chatgpt.json`
- V6 Qwen: `20260804T000919109187Z-2777bed9f334494ab4747f6ac0b16aa3-ollama.json`
- V6 Sol: `20260804T001138212561Z-ddafca23b4a34110841a574c48c62719-codex_chatgpt.json`
- V6 Luna: `20260804T001138212663Z-3825c4f632054899b71f2f80538bad9f-codex_chatgpt.json`

### V7 canonical-evidence failure and the staged V8 boundary

V7 removed provider-visible direction by folding the same 249 directed
candidates into 169 canonical left--right pairs. It then asked for five
categorical evidence fields and let a deterministic host projection create the
final relation. The input-only hashed schedule used eight 24-pair calls (the
last call contained one pair), and neither parent identities nor Gold metadata
could affect pair order. This made direction invariance auditable, but it still
asked the provider to make five mutually constrained choices in one turn.

The first actual Qwen thinking-off V7 campaign is retained as
`20260804T005946977751Z-03efb5e6e6f64481a3287de6e5f86ba5-ollama.json`.
It took 205.247 seconds. All eight raw responses were strict JSON with exact
169/169 local-ID coverage and no duplicate or omitted pair. Nevertheless, 38
evidence vectors were outside the frozen projection table:

| Unsupported evidence vector | Count |
| --- | ---: |
| unresolved plus a topic-only anchor instead of an undetermined anchor | 15 |
| same standalone claim plus complementary whole/joint composition | 12 |
| one primary decision plus incompatible guidance under a material context difference | 8 |
| same standalone claim plus incompatible peer guidance | 3 |

V7 deliberately rejected an entire call when any one vector was unsupported.
Five calls therefore became invalid: only 49 evidence records were retained,
while 120 pairs were marked missing. Offline reconstruction of the immutable
raw responses shows that 131 vectors were supported and 38 were unsupported,
so the call-level rule discarded 82 otherwise supported peers along with the
bad items. The retained record is correctly `INVALID_OUTPUT`; its partial
proxy score is not a Qwen accuracy result and cannot be compared with a valid
Sol ledger as if it were parity evidence. No V7 Sol or Luna call was made.

This failure changes the next harness rather than expanding the ontology to
fit observed answers. V8 must be a real sequence of small semantic operations,
not a single final-label-shaped enum or another five-axis one-shot response:

1. decide only whether the pair is a candidate relationship unit, a different
   topical unit, or unresolved;
2. for candidates, distinguish a claim/governing-rule family from a primary
   decision/joint-review family, with a reject and unresolved exit;
3. in a branch-specific call, choose only the evidence distinction needed to
   project that family.

The host creates the final relation only after the last applicable stage.
Every stage remains canonical and Gold-blind. When a response envelope permits
pair attribution, one malformed or unsupported item becomes
`INVALID_EVIDENCE` without deleting valid peers. Explicit provider uncertainty
is `ABSTAIN`, while transport, unparsable-root, or unrecoverable-ID failures are
`MISSING_DUE_CALL`. These denominators must stay separate, and any invalid or
missing item blocks promotion. Batch size remains 24 for the first staged
ablation because V7 proved envelope and ID reliability at that size; a smaller
batch is justified only by a later measured envelope failure, not by the V7
cross-field ontology failure.

#### Actual Qwen V8 result

The single requested Qwen thinking-off V8 campaign is retained as
`20260804T015652814353Z-9df122f19bbd4ab59654156ad4b1ad28-ollama.json`.
Strict replay validation passes. All 14 scheduled calls completed, every one of
the 169 canonical pairs reached a final host projection, and the authoritative
sentinels are `FINAL 169 / ABSTAIN 0 / INVALID_EVIDENCE 0 /
MISSING_DUE_CALL 0`. No Sol or Luna V8 call was made.

The staged route was:

| Stage | Pairs | Calls | Main outcomes | Time |
| --- | ---: | ---: | --- | ---: |
| A scope gate | 169 | 8 | 98 topic-only exits; 71 candidates | 93.370 s |
| B unit family | 71 | 3 | 30 not-one-unit exits; 28 claim/rule; 13 primary/joint | 34.279 s |
| C claim/rule | 28 | 2 | 10 unsupported; 9 same claim; 9 material-context rule variants | 14.009 s |
| C primary/joint | 13 | 1 | 3 unsupported; 3 aligned context variants; 5 conflicts; 2 joint parts | 6.597 s |

Total time was 148.321 seconds. That is 27.7% faster than the invalid
five-field V7 run despite 14 rather than eight calls, but 24.4% slower than
Qwen V6. Stage A consumed 63.0% of total time. The staged contract therefore
solves V7's response-coherence and failure-amplification problem; it does not
yet solve semantic quality.

On the canonical partition projection, V8 scored TP/FP/TN/FN
`20/8/129/12`, precision `.714`, recall `.625`, and enum exact `142/169`.
The 249 directed projection scored `40/13/172/24`, precision `.755`, recall
`.625`, enum `198/249`, reviewed one-to-one enum `20/48`, accepted source sets
`29/56`, and multi-member recall `.375`. As elsewhere in this document, FP and
TN are partition-induced negative proxies rather than independently reviewed
atomic semantic negatives.

The sequential trace localizes the 12 canonical false negatives: five exited
at Stage A, six at Stage B, and one at the claim/rule Stage C. All eight false
positives survived to Stage C, split four/four between the claim/rule and
primary/joint branches. Qwen never selected `SAME_RULE_SAME_CONTEXT`, so the
group-induced `SAME_PRINCIPLE` recall is `0/8`; context-variant recall is `2/9`,
near-duplicate recall `7/10`, conflict recall `4/4`, and complement/joint-part
recall `0/1`. This is actionable localization, but the requested pause after
V8 means no V9 repair is started here.

For a like-for-like 249-directed-candidate view, the frozen results are:

| Metric | Qwen V8 staged | Qwen V6 one-shot | Sol V6 one-shot |
| --- | ---: | ---: | ---: |
| TP / FP / TN / FN | 40 / 13 / 172 / 24 | 60 / 40 / 145 / 4 | 60 / 22 / 163 / 4 |
| Precision / recall | .755 / .625 | .600 / .938 | .732 / .938 |
| Group-induced enum | 198/249 | 176/249 | 206/249 |
| Reviewed 1:1 enum | 20/48 | 27/48 | 30/48 |
| Accepted source sets | 29/56 | 19/56 | 35/56 |
| Multi-member recall | .375 | .875 | .812 |
| Total time | 148.321 s | 119.222 s | 488.491 s |

These are different judge protocols over the same frozen candidates, so their
literal agreement is reference evidence, not same-operation reproducibility.
V8 agrees with frozen Qwen V6 on 186/249 binary decisions, 164/249 enums, and
19/56 source sets. Their accepted-pair intersection is 45, with eight V8-only
and 55 V6-only accepts (Jaccard `.417`). Against frozen Sol V6, V8 agrees on
198/249 binary decisions, 190/249 enums, and 23/56 source sets, but the accepted
intersection is only 42, with 11 V8-only and 40 Sol-only accepts (Jaccard
`.452`). The apparently high binary count includes 156 common rejections and
must not be described as Qwen matching Sol. Those Sol figures reuse the frozen
V6 ledger; no new Sol request was issued.

### Review and scale boundary after V6

The 26-group rung is a hard stop until judge quality is repaired. Running the
same design at 50 would multiply an already measured error rather than test a
new scale boundary. The available reviewed structure grows as follows:

| Rung | Left × right | 1:1 / multi groups | Sources | Directed group co-members | Multi Cartesian pairs |
| --- | ---: | ---: | ---: | ---: | ---: |
| 26 | 29 × 27 | 24 / 2 | 56 | 64 | 8 |
| 50 | 58 × 56 | 45 / 5 | 114 | 150 | 30 |
| 100 | 112 × 111 | 92 / 8 | 223 | 284 | 50 |
| 138 | 150 × 150 | 129 / 9 | 300 | 362 | 52 |

The immediate annotation pilot operates on canonical left-right pairs, not
duplicated directions. The current 249 directed candidates collapse to 169
canonical pairs. Review all 32 reviewed positive canonical pairs, all 86 pairs
that have either binary disagreement or unanimous acceptance under the
partition-negative projection, and 20 stratified unanimous-reject controls.
That is a 138-pair pilot. Two reviewers independently record structural
co-membership, direct semantic relationship, evidence axes, group-level band,
short rationale/span, and confidence; only disagreements go to a third
adjudicator. New decisions enter `PILOT / UNSCORED`, followed by a new lock and
full ladder replay. They never rewrite the current scores.

Full `150 × 150` means every source searches the complete 150-item opposite
collection and the bounded candidate graph must recover all 138 groups. It
does not mean asking a pair judge to classify 22,500 combinations. With the
current Top-5 plus 24-pair judge design, a linear terminal estimate is about
16.2 minutes for Qwen, 58.6 minutes for Sol, and 25.5 minutes for Luna before a
group-band pass. The target design source-batches the evidence judge into the
same 20-call terminal schedule as retrieval; its estimated candidate-plus-judge
budget is about 7.9, 26.4, and 10.1 minutes respectively. Sol is therefore an
offline reference SLA unless its reasoning or concurrency is separately
optimized.

## Scale promotion and regression gates

Scale-up is sequential: 26, 50, 100, then all 138 groups. During iterative
optimization, each candidate revision runs on local Qwen only: once for
debugging and then three frozen repeats after its single-run gate passes. The
retained V5/V6 Sol and Luna ledgers remain reference evidence; repeatedly
calling them for every red Qwen revision adds cost without changing the next
engineering decision. Sol and Luna receive one final common-freeze confirmation
only after Qwen clears the 26-rung stability gate and the scale ladder. Until
then, no new cross-provider parity claim is made. A contract violation,
unknown/omitted/duplicate ID, or provider failure blocks promotion.

Provisional consumed-calibration gates are:

| Rung | Candidate recall@3 | Hypergroup F1 | Co-membership exact | Multi-group recovery |
| --- | ---: | ---: | ---: | ---: |
| 26 | at least 0.98 | at least 0.90 | at least 54/56 | both reviewed multi-groups |
| 50 | at least 0.98 | at least 0.92 | at least 0.96 | at least 80% |
| 100 | at least 0.98 | at least 0.94 | at least 0.97 | at least 85% |
| 138 | at least 0.98 | at least 0.95 | at least 294/300 | at least 8/9 |

Every Qwen rung also requires contract-valid 3/3 and no more than a two-percentage
point regression on earlier frozen rungs. The later final provider-confirmation
freeze is reported separately. The terminal engineering target is at
most 12 minutes per model. A latency increase of at least 25% is rejected when
it buys less than two percentage points of structural improvement. These are
optimization gates, not release claims; a release claim requires a newly
frozen independent corpus.

A single CLI run can only report the per-run rung gate. It must not label one
passing run as scale promotion: promotion requires the three frozen repeats
and the earlier-rung regression check above. For V3, the analogous recall
diagnostic is named `co-membership micro recall`; only V4 has a true Stage-A
`candidate recall@3` measurement.

Band evaluation does not block retrieval promotion. On a future independently
adjudicated holdout, an initial band target is overall accuracy at least 0.75,
macro recall at least 0.70, per-band recall at least 0.60 where each band has at
least ten examples, and provider-to-Sol agreement at least 0.85. The dashboard
must still expose `both correct`, `teacher only`, `student only`, `both wrong
same`, and `both wrong different`.

## Failure-driven steering without moving the goalposts

New examples may be discovered while a campaign runs, but they cannot be added
to that same frozen score. The safe loop is:

```text
RUN(lock vN)
  -> inspect retained failures
  -> append candidate examples to PILOT / UNSCORED
  -> review rationale and expected contract
  -> publish fixture and lock vN+1
  -> replay the complete ladder
```

The dashboard keeps `CALIBRATION / CONSUMED`, `PILOT / UNSCORED`, and
`HOLDOUT / UNTOUCHED` distributions separate. This permits iterative steering
without silently changing the denominator or calling memorized calibration a
holdout.

## Remaining limitations

- V2 and oracle-classification campaigns currently retain invalid model output
  but can lose stage evidence on a provider/transport exception. V1 and V3
  retain configured provider errors. Status and documentation must keep this
  asymmetry visible until the older paths gain the same wrapper.
- V3/V4 progress is final-write only and not yet interruption-safe.
- The current corpus contains no one-sided `DISTINCT` group and has very few
  rare bands outside the first 26 consumed examples.
- The Korean translation is robustness data, not independently reviewed Gold.
- Provider parity does not establish reviewed-Gold correctness, and Sol output
  must never be used to repair a Qwen or Luna run invisibly.
