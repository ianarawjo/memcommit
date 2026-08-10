# Alternative-strategy Study run · 2026-08-10

## Purpose and method

This run tested whether Tasks 1–3 converge when approached through materially
different command affordances. The participant agent used only each Task's
description, `mem help`, readable Contexts exposed by the CLI, and visible
terminal output. It did not inspect answer keys. Every experiment used an
isolated `init-study` Profile, real TTY key input, and ordinary `mem` commands.
Non-TTY commands were used only for public status/count checks and regression
diagnostics.

The comparison is exploratory rather than a quality ground truth. A matching
count can conceal different wording, provenance, or abstraction, while a
different intermediate count can still converge once the final purpose gate is
applied.

## Results at a glance

| Task | Strategy | Main observable result |
|---|---|---|
| 1 | Merge start | Six child merges contributed `11+10+15+13+17+9=75`; target reached 375 and all 75 incoming UIDs/content were present exactly |
| 1 | Branch start | Branching and reassembly eventually produced the same 75 incoming items and 375 target total, but required substantially more structural repair |
| 2 | Advisor 1 → Advisor 2 | 20 relations, 4 required conflicts; Preserve All produced 0 proposed changes; final incorporation stalled without progress |
| 2 | Advisor 2 → Advisor 1 | 8 relations, 5 required conflicts; Preserve All produced 72 proposed changes; final incorporation stalled without progress |
| 3 | One-shot subtractive Sever | 300 Source × 75 Criteria produced 0 retained Memories |
| 3 | Deterministic strict allowlist | No item-level necessity was established, so the result remained empty; sharing the empty Context was safely refused |
| 3 | Four incremental Forget criteria | `300 → 251 → 231 → 187 → 0` |
| 3 | Four single-Criterion Sever rounds | `300 → 248 → 224 → 155 → 0` |

## Task 1 · construction updates

### Merge-start route

Profile: `study-alt-20260810-t1-merge`.

The participant merged the six readable child update Contexts individually
because the readable root had no directly owned Memories. The additions were
11, 10, 15, 13, 17, and 9 Memories. Public `show`/status inspection verified
all 75 incoming UIDs and contents in the 375-Memory target; the operation did
not collapse the six areas into six or one aggregate Memory.

### Branch-start route

Profile: `study-alt-20260810-t1-branch-local` (a contaminated administrative
import attempt was excluded).

Branching the root was shallow and retained embedded originals. Branching the
children and then embedding them alongside the originals produced duplicate
UID/name conflicts. After removing the inherited embeds and re-embedding the
local branches, semantic Meld failed its v6 preservation validation. Ordinary
deterministic child merges then produced the same 75-item contribution and
375-item target as the merge-start route.

This route exposed two meaningful boundaries:

- A granted current Context is not a local Branch source. The previous
  storage-level `Context not found` error was corrected to report this local
  source requirement directly.
- History/undo selection did not make authority-side merges as visible as
  local structural checkpoints, so the first Undo targeted an older local
  embedding action. Redo restored it. This was recorded as a history
  visibility issue rather than treated as a semantic result.

## Task 2 · directional integration

Profiles: `study-alt-20260810-t2-a-into-b` and
`study-alt-20260810-t2-b-into-a`.

The first direction analyzed 20 relations and required 4 answers. The reverse
direction analyzed 8 relations and required 5. The participant used `P` for
Preserve All, opened the unresolved Items, used visible options where adequate,
and entered exact custom responses for conditional or bounded cases. Examples
included a primary method with a bounded contingency, a conditional hybrid,
and a sentence-level condition that preserved segmentation flexibility.

The strongest asymmetry appeared before application: Preserve All yielded 0
changes in Advisor 1 → Advisor 2 but 72 in Advisor 2 → Advisor 1. Relation and
conflict counts also differed. This supports treating directional Meld as an
ordered semantic operation rather than assuming it is a symmetric merge with
the arrows reversed.

Both directions reached fully answered final review, then stalled during
`INCORPORATE RESPONSES` for more than ten minutes without a progress heartbeat.
Both were interrupted; both 150-Memory targets remained unchanged. These two
runs are therefore blocked application attempts, not successful Meld results.
One apparent shortcut/draft corruption was reproduced as operator input: a
hidden third option meant typed shortcut characters navigated the choice layer.
It remains a discoverability hazard, but was not classified as state corruption.

## Task 3 · disclosure minimization

The Task asks for a transfer to a broad government healthcare agent. The
query-only recipient guidance established no exact service, exact department,
retention guarantee, or item-level minimum necessity. It also warned that
downstream sharing may occur and withdrawal does not automatically delete
delivered copies. A query initially failed when addressed without its required
local attachment anchor; retrying through
`task-3/local/personal-memory` succeeded. This was an authorization boundary,
not a query failure.

### One-shot subtractive and deterministic allowlist

Profile `study-alt-20260810-t3-subtractive` ran one complete 300 Source × 75
guardrail-Criteria Sever turn. All 300 recommendations were `FORGET`, producing
an empty local result while leaving Source unchanged. Profile
`study-alt-20260810-t3-allowlist` began with an empty result because no Memory
had confirmed item-level necessity. `mem share` refused that empty Context with
`An empty Context cannot be shared.`

### Incremental Forget

Profile: `study-alt-20260810-t3-forget`.

The 300 source Memories were copied into one flat working Context. Four
instructions were then applied separately:

1. Remove third-party identity/private circumstances and residential,
   credential, identity-document, account, or access-security details:
   49 deleted, 34 edited, 251 retained.
2. Remove unverified current medication, status, appointment, contact,
   location, availability, price, credential, and access claims while retaining
   independently stable preferences: 20 deleted, 3 edited, 231 retained.
3. Remove finance, tax, purchase, gift, inventory, maintenance, event-menu,
   entertainment, and travel-logistics material unless it independently states
   an accessibility, communication, scheduling, support, or safety constraint:
   44 deleted, 2 edited, 187 retained.
4. Require confirmed item-level necessity for one exact healthcare service and
   permitted recipient: all remaining 187 deleted, 0 retained.

Provider turns took 308, 271, 230, and 126 seconds and returned 71,681, 68,155,
59,150, and 34,282 characters respectively. Forget had no elapsed-time
heartbeat: only `Consulting ...` remained visible until each result arrived.

The first attempt exposed a real routing bug: Forget still required the legacy
Ollama-only `llm` setting even though Meld, Query, and Sever used the configured
semantic provider. Forget was migrated to the common configured provider and
complete-coverage output schema. The repaired path passed targeted tests and
then completed all four live Codex-backed turns.

### Incremental Sever

Profile: `study-alt-20260810-t3-sever-incremental`.

Each criterion above was stored as one Memory in its own Criteria Context. Each
Sever result became the next round's Source:

1. `300 → 248` under third-party/security exclusion (321 seconds).
2. `248 → 224` under stale-status exclusion (257 seconds).
3. `224 → 155` under unrelated-domain exclusion (236 seconds).
4. `155 → 0` under the exact-purpose gate (112 seconds).

Unlike Forget, Sever displayed stage, Source/Criteria cardinality, animation,
and elapsed seconds throughout provider work. It also produced durable sessions
and kept every intermediate Source unchanged.

The intermediate results differed both quantitatively and qualitatively. The
first two Sever rounds retained 3 and then 7 fewer Memories than Forget's
corresponding states. After domain curation the gap reached 32. Sever frequently
used `KEEP_SUMMARY` or `KEEP_PREFERENCE_OR_POLICY` to turn event evidence into
communication, accessibility, scheduling, or safety constraints; Forget more
often kept exact text or performed a narrower edit. For example, Sever treated
an outdoor area's light/shade claim as unverified current location information,
while Forget retained it. Both operations nevertheless converged to zero once
the same explicit item-level purpose gate was applied.

At 80×24, opening Sever's final review with its additional Save Location frame
rendered only `Window too small...`; navigation to Apply was unavailable. The
saved session remained intact. Reopening at 120×50 restored the full review and
allowed application. This is a terminal-size usability defect, not data loss.

## Exact review-key pattern

The repeated Resolution flow was:

```text
A                 open the first unresolved required decision, or final review
Tab, Enter        focus Responses and accept the visible recommendation
A                 open final review after all required decisions are answered
End, Enter        move to the exact final action and apply
```

Exploratory runs also used `Tab` to traverse Viewer → Responses → Items → Save
Location → To Do, arrow keys for visible choices, `P` for Preserve All, and `G`
for whole-set guidance. Pressing Enter immediately after opening an Item acted
on the still-focused read-only Viewer and displayed the expected instruction to
use Responses. The footer text `A review & apply` remains ambiguous inside final
review: `A` opens/resets review, while actual application requires the explicit
final action's Enter.

## Study action ledger verification

The automatic Study ledger is content-free but sufficiently detailed to
reconstruct interaction mechanics. In the incremental Forget Profile it
recorded 23 `KEY`, 7 `TEXT_INPUT`, 4 provider turns, 4 approvals presented, 4
approvals accepted, and 4 semantic TUI actions. In the incremental Sever Profile
it recorded 20 `KEY`, 10 `TEXT_INPUT`, 4 provider turns, 4 approvals presented,
4 approvals accepted, and 5 TUI actions; the extra action is the close/reopen
caused by the 80×24 final-review failure. Command events also recorded whether
stdin/stdout were TTYs and their terminal rows/columns. Prompt, Memory, and
response content was not copied into these action records.

## Interpretation for later study design

The experiments separate two research questions:

- **Outcome convergence:** an explicit final policy gate made all Task 3 routes
  converge to zero disclosure.
- **Affordance and intermediate meaning:** Merge vs Branch, directional Meld,
  Forget, and Sever encouraged different decompositions, review burdens, and
  abstraction levels well before the final answer.

Participant questions should therefore ask not only whether the final result is
acceptable, but what they expect verbs such as Meld, Update, Forget, and Sever
to preserve, rewrite, summarize, or delete when backed by semantic inference.
The Task 2 directional asymmetry and Task 3 Forget/Sever divergence are useful
elicitation cases. They should not be presented as evidence that one wording has
one deterministic semantic result.
