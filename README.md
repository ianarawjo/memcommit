# memcommit

A git-like local memory store CLI.

## Semantic providers

Semantic commands use Codex through the local ChatGPT login by default. Pin the
subscription-backed Codex provider to GPT-5.6 Luna with low reasoning through
the named option, then verify its strict structured-output path:

```zsh
mem provider use codex_chatgpt --preset luna-low
mem provider status
mem provider probe
```

The equivalent explicit spelling is
`mem provider use codex_chatgpt --model gpt-5.6-luna --reasoning low`. Use bare
`mem provider use codex_chatgpt` to restore Codex-managed model and reasoning
selection.

Select an installed Ollama model for tool-less local execution:

```zsh
mem provider use ollama --model qwen3.6:35b-a3b \
  --context-tokens 65536 --max-output-tokens 8192
mem provider status
mem provider probe
```

Ollama thinking defaults to `auto`: it is enabled only when the exact installed
model advertises that capability. Use `--thinking on` or `--thinking off` for
an explicit evaluation condition. The Ollama endpoint is restricted to the
local loopback interface.

OpenRouter uses an exact model slug and reads its credential only from
`OPENROUTER_API_KEY`. Provider fallback is disabled and structured calls
require a compatible route:

```zsh
export OPENROUTER_API_KEY=...
mem provider use openrouter --model qwen/qwen3.5-27b --zdr
mem provider probe
```

Provider failure never silently falls back to another provider or makes a
hidden repair completion. See
[`docs/semantic-provider-design-rationale.md`](docs/semantic-provider-design-rationale.md)
for privacy, query-only, provenance, and rollout boundaries.

## Semantic calibration campaigns

The first provider-comparison harness scores one bounded ambiguity
classification per case. It runs the existing ten examples as
`CALIBRATION / LEAVE-ONE-OUT`; this is intentionally not reported as an
independent holdout score. Pipelines V1--V6 range from a one-call two-label
contract to conditional binary probes and two-stage evidence censuses.
Provider selections passed to a campaign are transient and do not rewrite
`mem provider` configuration:

```zsh
mem eval semantic run ambiguity \
  --provider codex_chatgpt --model gpt-5.6-sol --reasoning high \
  --pipeline v2
mem eval semantic run ambiguity \
  --provider codex_chatgpt --preset luna-low \
  --pipeline v6 --runs 3
mem eval semantic run ambiguity \
  --provider ollama --model qwen3.6:35b-a3b --thinking off \
  --pipeline v2 --runs 3 --corpus holdout
mem eval semantic status
```

The second bounded operation classifies duplicate relations:

```zsh
mem eval semantic run duplicate \
  --provider ollama --model qwen3.6:35b-a3b --thinking off --runs 3
```

Exact content and conservative Unicode/whitespace surface equivalence are
decided by the host without a provider call. Only semantic equivalence,
overlap, unresolved scope, and distinct meaning reach the model. On the
current six-case leave-one-out calibration, Qwen and Luna both matched 18/18
repeated attempts; this operation still needs a separately frozen holdout.

The shared first-stage gate suite covers the next nine operations without
asking any model to produce a complete operation result in one shot:

```zsh
mem eval semantic run gates \
  --provider ollama --model qwen3.6:35b-a3b --thinking off \
  --tier SHORT --runs 3
mem eval semantic run gates \
  --provider ollama --model qwen3.6:35b-a3b --thinking off \
  --tier LONG --runs 3
```

The latest pilot composes a frozen 37-case baseline with 38 reviewed additions:
75 cases across Conflict, Atomize, Translate, Compare, Update, Ground, Meld,
Forget, and the retired Integrate benchmark, including 57 short and 18 long
Task 1--3 gates. Qwen
thinking-off matched 225/225 repeated attempts across all 75 cases, with mean
0.550 seconds and p95 1.081 seconds per attempt in the warm campaign. Conflict,
Translate, Compare, and Meld expose resolution evidence before the host projects
their public labels; this prevents a small model from silently choosing a
likely referent. This remains consumed calibration evidence for bounded labels,
not full-operation or independent-holdout parity. Both the 37-case base and
75-case composite are digest-locked, and the fixture enforces a 200-case
campaign cap. `--layer base` and `--layer additions` isolate either composite
layer; `--case` selects exact cases for failure-driven reruns.

Task 2 now has a separate end-to-end discovery campaign. It gives each provider
the same opaque, independently shuffled advisor sets and scores recovery of the
reviewed relationship groups before scoring their bands:

```zsh
mem eval semantic run task2-discovery \
  --provider ollama --model qwen3.6:35b-a3b --thinking off --groups 26
mem eval semantic run task2-discovery-v2 \
  --provider codex_chatgpt --preset luna-low --groups 26
mem eval semantic run task2-retrieval-v3 \
  --provider ollama --model qwen3.6:35b-a3b --thinking off --groups 26
mem eval semantic run task2-retrieval-v4 \
  --provider ollama --model qwen3.6:35b-a3b --thinking off --groups 26
mem eval semantic run task2-classification \
  --provider codex_chatgpt --model gpt-5.6-sol --reasoning high --groups 26
mem eval semantic task2-status
mem eval semantic task2-parity FIRST_DISCOVERY_LEDGER SECOND_DISCOVERY_LEDGER
mem eval semantic task2-retrieval-v3-parity FIRST_V3_LEDGER SECOND_V3_LEDGER
mem eval semantic task2-retrieval-v4-parity FIRST_V4_LEDGER SECOND_V4_LEDGER
mem eval semantic run task2-candidate-v5 --provider ollama --model qwen3.6:35b-a3b --thinking off --candidate-count 5 --groups 26
mem eval semantic run task2-judge-replay-v5 --candidate-ledger V4_A --candidate-ledger V4_B --provider ollama --model qwen3.6:35b-a3b --thinking off
mem eval semantic task2-judge-v5-parity FIRST_V5_JUDGE_LEDGER SECOND_V5_JUDGE_LEDGER
mem eval semantic run task2-judge-replay-v6 --candidate-ledger V4_A --candidate-ledger V4_B --preset luna-low
mem eval semantic task2-classification-parity FIRST_BAND_LEDGER SECOND_BAND_LEDGER
```

The locked scale ladder is 26, 50, 100, then all 138 groups over 150 versus
150 Memories. The current full one-shot baseline is intentionally red: Sol
recovered 85/138 exact structures and Qwen 72/138, and both violated exhaustive
partition coverage. The two-call structure-only V2 recovered 26/26 for Sol and
Luna-low on the first slice but 12/26 for Qwen. These are retained calibration
failures, not hidden repairs. The next revision uses source-anchored,
bidirectional microbatches instead of free-form global grouping. V3 asks for
opposite-side hypergroup co-members in 4, 8, 16, then 20 fixed calls. Its first
Qwen 26-group run was retained red: one of four calls mixed source aliases into
target output, group co-membership was 19/56, and the reviewed 1:1 subset was
17/48 in 69.001 seconds. The ranked candidates nevertheless contained every
reviewed co-member for 50/56 sources, motivating a separate candidate-verifier
stage instead of a larger one-shot prompt.
On that same V3 slice Sol was contract-valid at 55/56 co-membership, 48/48 on
the reviewed one-to-one subset, and 26/26 reconstructed groups in 130.425
seconds. Luna-low was valid at 48/56, 44/48, and 22/26 reciprocal groups in
74.933 seconds. Qwen/Sol co-membership agreement was only 18/56, so the new
parity command and status board do not mistake teacher availability for parity.

V4 then separated top-3 candidate retrieval from bounded subset verification.
All three 26-group runs were contract-valid, but all failed the single-run rung
gate. Candidate recall was Qwen 60/64, Sol 64/64, and Luna-low 61/64; final
co-membership fell to 36/56, 37/56, and 35/56 respectively, with zero of two
multi-member groups recovered by every provider. Pipeline time was 88.563,
317.249, and 121.218 seconds. This demonstrates a verifier-contract failure,
not Qwen/Sol parity: Qwen and Sol agreed on only 34/56 final sets, and each had
seen different candidates. The next judge-isolation replay freezes one
Gold-blind candidate union and requires every provider to label the identical
pairs before candidate top-K is tuned further.

That common-input replay now contains 249 directed pairs and a complete 64/64
candidate ceiling. V5 was contract-valid for all providers but failed parity:
Qwen/Sol agreed on 174/249 binary decisions and 122/249 relationship enums.
The V6 strict-boundary prompt, with candidate schedule and scorer held fixed,
raised those preliminary counts to 199/249 and 170/249. It also reduced the
partition-induced FP proxy from 60 to 40 for Qwen, 106 to 22 for Sol, and 104
to 31 for Luna. This is not a promotion: Qwen source-set exact is still 19/56,
and Sol multi-member recall regressed to .812. Status reports V5→V6 deltas,
time ratios, multi-member behavior, and the fact that cross-hypergroup
negatives are not independently reviewed atomic-pair Gold.

Optimization replays are Qwen-only from V7 onward. Existing Sol/Luna V5 and V6
ledgers remain frozen references; those slower providers are not called for
every red Qwen revision. They receive one common-freeze confirmation only
after Qwen clears the 26-group stability gate and the 50→100→138 ladder.

The first Qwen V7 run is retained red rather than scored: it returned exact
IDs for all 169 canonical pairs in 205.247 seconds, but 38 five-field evidence
vectors violated the frozen projection contract. Whole-call rejection then
made 120 pairs unavailable, including 82 otherwise supported peers. V8 is the
next Qwen-only ablation: it replaces that multi-axis one-shot response with a
coarse relationship-unit gate, a relationship-family step, and one
branch-specific evidence step. Final labels remain host-derived, and explicit
abstention, item-local invalid evidence, and call-level missing data are
reported separately. No Sol or Luna V7 run was made.

The single Qwen V8 campaign is strict-replay-valid: 14/14 calls produced final
host projections for all 169 canonical pairs in 148.321 seconds, with zero
abstain, invalid, missing, or call anomalies. The staged contract works, but
the 26-group quality gate remains red: directed precision/recall is
`.755/.625`, reviewed one-to-one enum is `20/48`, and multi-member recall is
`.375`. Frozen Sol V6 comparison gives 198/249 binary and 190/249 enum
agreement, yet accepted-pair Jaccard is only `.452`; common rejections dominate
the headline agreement. Work is intentionally paused at V8, with no new Sol,
Luna, V9, or scale-ladder run.

The sidecar is group-level Gold, not 22,500 independently reviewed pair labels.
Its five bands also contain fine authoring-policy distinctions that neither Sol
nor Qwen reproduced reliably from content alone. Group discovery, oracle-group
classification, provider agreement, and reviewed-Gold accuracy are therefore
reported separately.

Every attempt is written to a machine-readable campaign ledger and its elapsed
time appears in live progress. Terminal results and provider-free status report
exact-label and failure distributions, connection time, completion
mean/median/p95/max, campaign and total time, and stage mean/p95 when
applicable. The current adapters are non-streaming, so time to first token is
not available.

The twelve-case independent holdout is frozen by
`ambiguity_holdout.lock.json`; its fixture digest is `be722ce23163...` and its
calibration-source digest is `003654c092e0...`. A holdout run fails before a
provider call when either frozen file, case count, or identity changes. The
holdout is scored against all ten fixed calibration examples, but no holdout
case is ever supplied as an example to another holdout case.

On its first frozen evaluation, Qwen with thinking `off` and V2 matched 36/36
attempts across all 12 holdout cases. Luna-low V2 matched 34/36 and passed
11/12 case gates; Luna V6 matched 29/36 and passed 10/12 while taking 2.88
times longer per attempt. The holdout has now been consumed by these pipeline
comparisons. Any revision informed by its failures requires a newly frozen
holdout before another independent-generalization claim.

See
[`docs/semantic-eval-harness-design-rationale.md`](docs/semantic-eval-harness-design-rationale.md)
for V1--V6 contracts, corpus roles, pass gates, timing definitions, full
observed distributions, the frozen holdout contract, and the next
profile-selection or new-holdout steps before any possible V7 experiment.
The Task 2 scale ladder, group-versus-pair Gold boundary, V3/V4 contracts,
promotion gates, and failure-driven steering loop are recorded in
[`docs/task2-portable-semantic-harness-design-rationale.md`](docs/task2-portable-semantic-harness-design-rationale.md).
The duplicate split and its limits are recorded in
[`docs/semantic-duplicate-eval-design-rationale.md`](docs/semantic-duplicate-eval-design-rationale.md).

## Interactive command picker in zsh

After installing the `mem` entry point, enable the zsh integration in the
current shell:

```zsh
eval "$(mem shell-init zsh)"
```

Run `mem help`, choose a command with the arrow keys, and press Enter. The
selected `mem <command> ` text is placed in the next zsh input line so it can
be completed or edited before execution.

Add the same `eval` line to `.zshrc` to enable it in future shells. The command
only prints shell code; it does not edit shell startup files itself.

## Whole-store profiles

`mem switch` changes Context inside one MemoryStore. Use `mem profile` when a
complete local store should change instead:

```zsh
mem import profile rehearsal-baseline --from path/to/source/.mem
mem import profile rehearsal-copy --from-profile rehearsal-baseline
mem profile rehearsal-baseline
```

Profiles and complete Study runs can be permanently deleted. This removes the
complete selected store, including Memories, sessions, and every checkpoint,
and removes connected Grants. The operation cannot be undone or recovered by
`mem`:

```bash
mem profile remove rehearsal-copy
mem profile remove-study pilot-001
```

In the interactive `mem profile` selector, Study headings are focusable rows.
Press `D` on a Study heading to review whole-Study removal, or on a child row to
review only that Profile. `Enter` or `A` applies the exact displayed command
after the irreversible-deletion warning. After deletion, the refreshed
selector stays open with a success receipt so more old Profiles can be removed
without restarting `mem profile`. While deletion runs, `.`, `..`, `…` shows
that the approved store/checkpoint cleanup is still active. The direct CLI
commands remain one-shot. The active, fixed `authoring`, and fixed
`study-baseline` Profiles cannot be removed. Stable UID and Study provenance
tombstones remain only so a surviving child can keep its Study heading; they
do not retain or restore deleted content.

`mem import` accepts `profile`, `context`, and `memory` resources. It preserves
Context and Memory identity while excluding source operational history. For
example, import a closed Context subtree or one Memory from another Profile:

```zsh
mem import context campus-wiki --from-profile rehearsal-baseline --recursive
mem import memory MEMORY_UID --from-profile rehearsal-baseline \
  --context campus-wiki/routes --into participant/notes
```

Context and Memory imports write into the active Profile without changing its
selection or current Context. Name or UID collisions fail without overwriting.
`mem import NAME --from PATH` remains a compatibility spelling for clean
Profile import, while `mem profile import` remains the explicit archival copy.

```zsh
mem profile import-study --from outputs/study-fixtures
mem profile list
mem profile study-baseline
mem switch task-1
mem switch granted-memory/task-1
mem profile authoring
```

`profile import-study` is a one-time bootstrap into one live, editable source
Profile. It contains `task-1`, `task-2`, and `task-3`, plus
`granted-memory/task-1`, `granted-memory/task-2`, and
`granted-memory/task-3`. Continue refining that Profile while the Study
Memory is unstable.

When the generated fixture packages change, refresh that visible source
explicitly before starting another run:

```zsh
mem profile refresh-study --from outputs/study-fixtures
```

The refresh preserves the `study-baseline` Profile identity and the active
Profile selection, but atomically replaces its store and frozen grant
templates. It refuses to replace edits made in the live baseline since its
last import. Use `--replace-edited-baseline` only after deciding those edits
are already represented in the fixture sources or may be discarded.

For a fresh repeatable rehearsal or participant run, snapshot the current
baseline rather than rebuilding from generated fixture files:

```zsh
mem init-study pilot-001
mem profile pilot-001
```

`mem init-study` with no name generates a unique timestamped name. It reads
`study-baseline` by default (`--from-profile` selects another self-contained
live Profile), freezes one consistent snapshot, and atomically publishes one
ordinary Profile. The entire `task-1`, `task-2`, `task-3`, and
`granted-memory/task-{1,2,3}` topology is copied without splitting or renaming.
Context and Memory identity and the current Context are preserved, while
operational history is empty. Later baseline edits affect only later
initializations, never an existing copy.

`mem profile use NAME` remains the equivalent explicit form for scripts.

The existing `~/.mem` is the fixed `authoring` Profile. The editable source is
one `study-baseline` Profile, and each new initialization is one independent
complete copy. `granted-memory` is an ordinary Context branch in that copy;
`init-study` does not create or clone registry grants. A source that already
participates in grants is rejected because its capabilities cannot be
represented faithfully inside one self-contained Profile. Existing legacy
split Study groups and grants remain readable and selectable but are not
created by new initializations.

## Write protection

Protect the current Context, a recursive Context snapshot, one directly owned
Memory, or the active Profile from later writes:

```zsh
mem lock
mem unlock
mem lock --recursive
mem lock context
mem lock context CONTEXT [--recursive]
mem unlock context CONTEXT [--recursive]
mem lock memory MEMORY_UID [--context CONTEXT]
mem unlock memory MEMORY_UID [--context CONTEXT]
mem lock profile
mem unlock profile
```

Bare `lock` and `unlock` target the current Context. A Context lock blocks
record changes, rename, and deletion but still permits reads, checkpoints,
switching, and branching to a new writable Context identity. `--recursive`
atomically applies that policy to the root and its existing lexical descendants;
it is a frozen bulk operation, not an inherited rule for future descendants. A
Memory lock blocks editing or removing only that occurrence and does not
silently lock a same-UID branch copy.

A Profile lock is the upper read-only policy for that Profile's durable store:
it also blocks new Contexts, checkpoints, Ground and workflow sessions, derived
artifacts, and saved query transcripts. Reads and Context/Profile switching
remain available. Unlocking a Profile preserves narrower Context and Memory
locks, and no protected write has a force bypass.

## Meld quick start

The implemented meld workflows have different entry points:

- one-issue directional grounding, informally called atomic meld:
  `mem atomize --context CONTEXT --evaluate ISSUE`;
- directional Context intake into an authoritative baseline:
  `mem meld --into BASELINE` when the current Context is incoming, or
  `mem meld INCOMING --into BASELINE` when both roles are explicit. When the
  current Context is the baseline, `mem meld --from INCOMING` is equivalent
  convenience grammar;
- symmetric combination of two equal-authority Contexts:
  create an empty result Context, then run `mem meld LEFT_PEER RIGHT_PEER`.

See [`docs/mem-meld-usage.md`](docs/mem-meld-usage.md) for the canonical
commands, interactive controls, acceptance boundaries, and the deliberate
distinction between directional `--into` and the reserved future symmetric
`--to` destination.
