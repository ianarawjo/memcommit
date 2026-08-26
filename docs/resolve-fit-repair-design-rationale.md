# Resolve Fit-repair design rationale

## Status

Resolve's first automatic-interpretation iteration is implemented as a public,
direct-Memory, exact-Context operation through CLI, TUI, Python, agent, and MCP
projections. All interfaces call the same application boundary. Every semantic
turn reads the complete frozen direct-Memory frame; an Issue narrows edit focus,
not evidence scope. Semantic execution returns at most one recommended plan, so
a person does not choose among model-authored alternatives. The execution
command automatically applies a grounded plan whose independent post-Fit
reaches its frozen MAY-or-YES target as one `resolve` checkpoint. `ASSUMED`
factual premises and other non-applicable outcomes remain read-only.

This is deliberately an empirical starting policy, not the final definition of
reasonable resolution. The preferred balance among a concise added
interpretation, a local OR/alternative edit, edits that expose supplied scope,
and other information-preserving forms is governed by the versioned exact-case
ruleset. Keep this note, fixture, prompts, matrix, and recorded interaction
evidence current as those rules change rather than retrofitting a fixed
rationale after the behavior stabilizes.

The current automatic-plan terminal evidence is recorded under
[`screenshots/mem-resolve-automatic-interpretation-20260820/`](screenshots/mem-resolve-automatic-interpretation-20260820/README.md).
It supersedes the earlier multi-candidate interaction evidence without erasing
that historical design record.

## Motivating scenario

A complete Context can contain propositions that Fit as `MAY` or `NO` without
showing which stored text may safely change. A conflict finder can identify a
problem but cannot authorize a rewrite, while generic Meld or Merge semantics
would change the operation: Merge chooses structural collision dispositions,
and Meld combines two Context frames. Resolve instead changes one frozen
Memory frame from `NO` to at least `MAY`, or under `--yes` from `NO`/`MAY` to
`YES`, with the smallest grounded effects it can defend.

The public flow is:

```text
freeze exact direct-Memory frame and authority
-> complete initial Fit judgment and material focus
-> identify Issues inside that complete frame
-> read every named rule, exact canonical input/effect/output case, and
   known-wrong adjacent result
-> select one reasonable interpretation and small UPDATE/CREATE plan, or STOP
-> independently verify grounding, assumptions, information preservation,
   and any exceptional deletion basis against the complete original frame
-> independently Fit the complete effective post-image
-> revalidate authority and Context digest
-> automatically apply one grounded target-reaching plan as one checkpoint,
   or publish a non-applicable read-only outcome
```

The execution and exact-replay forms are:

```text
mem resolve [CONTEXT | MEMORY_UID_PREFIX | CONTEXT:MEMORY_UID_PREFIX ...]
  [--context CONTEXT] [--memory [CONTEXT:]UID_OR_PREFIX ...]
  [--no-create] [--yes] [--allow-delete --guidance TEXT] [--plain | --tui]

mem resolve [FULL_MEMORY_UID ...] --context CANONICAL_NAME [same effect flags]
  --candidate FULL_CANDIDATE_UID --expected-revision REVISION --apply --plain
```

Resolve uses the shared mixed Context/direct-Memory operand grammar before it
constructs an operation request. A positional eight-or-more-character
UUID-shaped value is a strict Memory selector, `CONTEXT:UID` is an
owner-qualified Memory selector, and other positional values begin as existing
Context locators. When a shorter hexadecimal value is not an exact readable
Context, one unique ordinary-local direct-Memory match promotes it to Memory;
zero matches retain Context meaning and multiple matches fail closed.
`--memory` makes the Memory role explicit, while `--context` preserves explicit
legacy UUID-shaped Context names. Every Context spelling, including relative
qualifiers, resolves against one command-start current-Context snapshot.

A bare Memory selector with no named Context searches the strict local direct-
ownership catalog and must have exactly one owner; current Context has no
hidden priority. This global lookup never enumerates Grant contents. A granted
Memory restriction therefore names its readable public Context through either
`PUBLIC_CONTEXT:UID` or `--context PUBLIC_CONTEXT --memory UID`, after which
the existing Grant-aware Resolve port authorizes and freezes the full frame.
All positional, qualified, and option-derived Contexts must canonicalize to
one target. Repeated spellings of that same Context collapse, different
Contexts fail before provider construction, and repeated selectors for one
resolved Memory remain an error. These entry rules narrow the mutable set only;
they never narrow the complete semantic evidence frame.

The CLI form is an execution command: after all semantic gates and freshness
checks, one grounded plan applies without a model-choice or approval turn.
The default target removes `NO`: an independently verified MAY or YES
post-image may Apply. `--yes` freezes the stricter target and rejects MAY.
`--plain` changes presentation, not mutation semantics; `--tui` requires the
interactive read-only Viewer for a non-applicable outcome. The explicit
`--candidate ... --apply` form remains an exact replay path for an externally
reviewed plan, such as one obtained from `mem impact resolve`.

### Apply-first and recovery policy

Ordinary Resolve is intentionally apply-first once its execution contract has
produced exactly one grounded plan, the independent verifier has accepted it,
the complete post-image reaches the requested Fit target, and authority,
freshness, pre-image, and CAS checks still hold. The invocation is the request
to execute that verified judgment; Resolve does not add a second pre-effect
approval screen merely because the effect was selected semantically.

The compensating boundary is one atomic `resolve` checkpoint. A successful
receipt must expose the checkpoint-backed Review route and `mem undo`, while a
failure before checkpoint publication must expose no partial Resolve effect.
This recovery policy does not make unsupported or unresolved output
actionable: `ASSUMED`, `NEEDS_INPUT`, `NEEDS_AUTHORITY`, non-target-reaching,
multi-candidate, stale, and incompletely authorized outcomes remain
non-applying. Irreversible effects outside the checkpointed MemoryStore are
not part of this automatic execution contract.

The agent adapter retains a grounded typed analysis process-locally so the next
agent turn can Apply the exact plan it already showed without asking a
nondeterministic provider to reproduce it. It consumes that cache entry after
successful Apply. After an agent-process restart, `apply` falls back to
stateless replay: it regenerates under the expected revision, requires the
exact candidate UID to be present, and fails closed otherwise. Python callers
may likewise keep the returned typed analysis object and pass it directly to
`apply_resolve`.

An `ASSUMED` result is a reasonable effective view for a later agent turn, not
durable truth. It carries its unsupported premises explicitly and cannot cross
`apply_resolve`. The current CLI does not persist that overlay across processes;
the in-process Python/agent caller must carry it into its next turn.

## Effect and authority contract

Resolve exposes primitive durable effects rather than a separate integration
permission:

- `UPDATE` and information-preserving `CREATE` are requested by default;
- `--no-create` narrows an invocation to existing-Memory edits;
- `DELETE` is requested only with `--allow-delete`, and that flag is invalid
  without nonblank guidance that states when retirement is justified; and
- an integration is represented by the exact combination of CREATE, UPDATE,
  and DELETE effects that produces its post-image.

For a local Context, requested effects are locally available. `mem impact
resolve` uses the same CREATE-by-default effect request, so preview does not
silently analyze a narrower operation. For a granted
Context, effective effects are the intersection of requested effect kinds and
the Grant's `CREATE`, `UPDATE`, and `DELETE` capabilities. Semantic use also
requires `READ` and `DERIVE`. Missing capability is reported before provider
construction when no requested effect remains or `DERIVE` is absent. A denied
optional effect does not prevent a candidate that uses only the remaining
capabilities.

The current iteration reads and mutates one authority resource, so it does not
claim `COMBINE`, `EXPORT`, or `ACCEPT_DERIVED`. Those permissions become
relevant only if a later version accepts multiple authority frames or
materializes into a different owner.

## Grounding and minimum-change invariants

The provider receives aliases such as `m1`, not durable Memory UIDs. Initial
Fit, automatic interpretation planning, verification, and final Fit each receive
the complete applicable frame. No Issue or explicit Memory selector turns into
a partial semantic input. Planning may cite only supplied Memory content and
explicit guidance. Every planning and verification prompt also contains the
complete versioned rule and exact-case corpus. It must report typed Issues with
exact members, a selected ordinary interpretation, basis Memories, and any
assumptions. The separate
verifier receives the complete original frame, Issue ledger, and exact effects.
It judges grounding, information preservation, and deletion justification. A
separate Fit call then judges the complete effective post-image. The default
resolution target accepts `MAY` or `YES`; `--yes` accepts only a YES-level
interpretation. An exact local
OR/alternative edit can be grounded by the two cited descriptive claims even
when the frame does not determine which alternative applies. That unresolved
applicability is the reason for resolution level MAY and ordinarily remains
post-Fit MAY, although the independent judge may find the explicit alternative
jointly compatible and return YES. The exact corpus therefore records a
`MAY_OR_YES` post-Fit acceptance range for this case while keeping its exact
output string and resolution level fixed. Exact supplied scope or transition
grounding instead requires both values to be YES. Resolution level and
proposition Fit are retained as separate evidence rather than treating a
planner label as the post-image check.

When no explicit Memory selectors are supplied, only Memories identified as
material by the initial Fit judgment may be updated or deleted. Explicit
selectors freeze the exact mutable UID set instead. CREATE may cite any direct
source Memory and is ordinary because an added concise interpretation can
preserve original text. Planning prefers one local UPDATE for a safe
alternative before weakening every claim with MAY or adding a meta-summary. It
prefers exact scope edits when the complete frame actually supplies the scope,
time, subject, audience, exception, or modality. DELETE remains exceptional.

Change shape remains a transparent diagnostic vector:

```text
(delete count, create count, update count, changed text units)
```

The first automatic policy does not claim a global minimum search. The model
reads the whole frame and returns zero plans or exactly one recommended plan,
with minimum semantic commitment taking priority over text length. The vector
explains that plan; it does not ask a person to choose among unlike effects.
The execution command crosses the durable boundary automatically only for this
grounded, independently verified, target-reaching unique plan. `ASSUMED` never
does.

## Exact rule and example ledger

The clozemaking-style authored source is
`memcommit/eval/fixtures/resolve.json`. It contains named rules, exact ordered
Source Memories, exact effects with before/after values, the exact ordered
post-image, expected post-Fit, and known-wrong post-images with violated rule
IDs. `memcommit.resolve_rules` validates duplicate keys, field sets, rule
references, mutable targets, exact pre-images, and the result derived from the
effects before a provider can be connected.

Unlike a sampled few-shot prompt, every authored rule and every case enters
every production planning and verification turn. This is a deliberate
calibration contract: it makes runtime behavior traceable to the same exact
examples used by regression tests. It is not held-out accuracy evidence. A
future evaluation corpus must be authored separately and must never enter the
production prompt.

The focused ownership and coverage record is
[`resolve-application-boundary-matrix.md`](resolve-application-boundary-matrix.md).
The JSON fixture remains the sole source of exact strings; the matrix locates
each rule at its planner, verifier, post-Fit, and Apply boundary.

## Exact identity and Apply

The revision hashes the contract version, Context identity and digest,
canonical display target, actionable Memory UIDs, requested effects, guidance,
and MAY-or-YES target. A candidate UID hashes that revision plus exact owner, Memory,
pre-image, post-image, and source identities for every effect. Explanatory
provider prose is deliberately outside mutation identity.

Apply validates the candidate through the operation-neutral Resolution
lifecycle, revalidates the Context and Grant, acquires the mutation boundary,
checks every pre-image, and writes one checkpoint. The checkpoint retains the
selected Issue interpretations and bases beside the exact effects, verifier,
and final Fit evidence so the rationale does not exist only in provider prose.
DELETE additionally scans the direct Context graph under the command lock and
fails if any inbound `MemoryRef` still targets a deleted Memory. This is
conservative: the current iteration does not rewrite references or publish
partial effects.

## Alternatives considered

A generic `reconcile` command was rejected because it would combine ambiguity
clarification, conflict repair, duplicate survival, and Context combination
under one name despite different evidence and Apply contracts. A generic
solver callback inside the shared Resolution lifecycle was also rejected: the
common layer validates the frozen automatic plan identity before Apply, while
Resolve owns semantic generation, verification, and mutation.

Treating permission to DELETE as a semantic reason to delete was rejected.
Fit can always be improved by removing propositions, so deletion requires an
independent guidance basis. Persisting provider candidates as a new session
schema was deferred because exact revision-and-candidate replay provides a
smaller V1 safety boundary without hidden durable drafts.

Making every Issue an isolated provider call was rejected for this iteration.
Small Issues are output and edit units, not read boundaries: overlapping Issues
may interact, and a locally coherent edit may conflict elsewhere. One complete
planning turn followed by whole-post-image Fit uses the large model's ordinary
reading capability while retaining typed audit evidence.

The earlier CREATE-before-UPDATE preference was replaced after configured-
provider trials produced broad meta-interpretation Memories. The first exact
rule corpus now prefers one relation-bearing local edit for a safe descriptive
alternative and exact multi-edit scope repair when supplied grounding supports
it. This remains empirical: revise the versioned rule, canonical and
known-wrong cases, matrix, and tests together rather than preserving it merely
because it shipped first.

## Initial configured-provider trials

The first implementation pass was exercised against the configured semantic
provider using fresh isolated temporary Stores rather than only deterministic
fixtures. The observed cases were:

- two unqualified opening times produced one explicit `ASSUMED` scope
  interpretation and a CREATE-shaped working view, with zero checkpoints;
- explicitly scoped weekday/weekend Memories returned `ALREADY_FIT` after the
  initial complete-frame Fit turn;
- two unqualified times plus an authoritative weekday/weekend Memory and
  matching guidance produced one grounded CREATE, passed independent
  verification and final Fit, and applied as one checkpoint;
- explicit obsolete-record guidance over a three-Memory frame produced one
  grounded DELETE of the named obsolete Memory and one checkpoint; and
- the same DELETE scenario over only two Memories failed closed as
  `NEEDS_INPUT`, because deleting one would leave fewer than two propositions
  for complete Fit.

One useful negative observation is that the authoritative schedule Memory
without matching guidance returned `NEEDS_INPUT` in the sampled run. The host
correctly published no plan, but the example suggests the planner/verifier
boundary may currently be more conservative than the intended ordinary
grounding policy. Keep this as an empirical prompt/evaluation case rather than
weakening the grounding gate from one run.

A second eight-case batch on 2026-08-20 used the configured provider and one
fresh temporary Store. It exercised the public analysis and Apply boundary,
not a fixture-only decoder path:

| Frame | Result | Durable effect |
| --- | --- | --- |
| two unqualified opening times | `ASSUMED` | none; the unsupported different-schedules premise was exposed |
| the same times plus an authoritative schedule and matching guidance | `PROPOSAL` | one grounded CREATE checkpoint |
| already scoped weekday/weekend times | `ALREADY_FIT` | none |
| current, obsolete, and holiday records with explicit retirement guidance | `PROPOSAL` | one grounded DELETE checkpoint |
| the same retirement request with only two records | `NEEDS_INPUT` | none; the post-image cardinality guard stopped it |
| authoritative schedule, CREATE disabled, two selected short records | `PROPOSAL` | two grounded UPDATEs in one checkpoint |
| absolute no-animals wording plus an explicit controlling service-animal exception | `ALREADY_FIT` | none |
| two unqualified export limits plus a Memory assigning each to a different method | `ALREADY_FIT` | none |

The batch supports the intended asymmetric policy: an unsupported but
reasonable reading can be shown without mutation; grounded CREATE and UPDATE
plans apply; DELETE requires the separate retirement basis; and all effects
remain atomic. It also exposes a Fit-policy question. The provider treated the
explicit service-animal precedence Memory as sufficient to contextualize even
the phrase “under any circumstances,” and therefore skipped an arguably useful
wording edit. Similarly, the export-scope Memory made the full frame Fit
without rewriting the two shorthand records. These are not execution failures:
they show that Resolve can only be as strict as the initial Fit judgment. Keep
both cases as evaluation inputs when revising whether Fit should accept a
later contextualizer or require the directly ambiguous Memory wording itself
to be repaired.

A third six-case batch on 2026-08-20 exercised the complete exact-rule corpus
in both planner and verifier prompts against fresh temporary Stores. It did not
Apply, and every scenario Context lived in a temporary Store:

| Exact input | Target | Observed output |
| --- | --- | --- |
| `The office opens at 8.` + `The office opens at 9.` | MAY | one grounded `SAFE_ALTERNATIVE` UPDATE: `The office opens at 9 as an alternative to opening at 8.`; resolution MAY, post-Fit MAY in this run |
| the same two opening times | YES | `NEEDS_INPUT`; exact input preserved because the frame supplied no applicability grounding |
| the two opening times + an authoritative weekday/weekend schedule, with only the short records mutable | MAY | two grounded exact UPDATEs to `8 on weekdays` and `9 on weekends`; resolution YES, post-Fit YES |
| the two opening times + `The office is closed on public holidays.` | MAY | the same one-record alternative UPDATE; holiday Memory preserved byte-for-byte; resolution MAY, post-Fit MAY |
| `Send the payment to account A.` + `Send the payment to account B.` | MAY | `NEEDS_INPUT`; no OR and no effect |
| 30-day retention + mandatory deletion after 7 days | MAY | `NEEDS_INPUT`; no OR and no effect |

The first live attempt also exposed a provider compatibility boundary:
Codex structured output rejected JSON Schema `uniqueItems` on `rule_ids`.
Resolve now enforces uniqueness in its decoder instead, while the provider
schema stays within the supported subset; a regression assertion covers that
exact boundary.

Two immediate end-to-end repeats of the first case exposed normal provider
variance without crossing the safety boundary. One returned `ASSUMED`, so
Apply rejected it and wrote no checkpoint. The next returned the exact grounded
UPDATE again, its independent post-Fit was YES, and Apply produced exactly one
UPDATE checkpoint whose reloaded Memories were `The office opens at 8.` and
`The office opens at 9 as an alternative to opening at 8.`. This is why the
corpus fixes the resolution level at MAY but accepts post-Fit MAY or YES.

## Intentional limitations

- The current iteration handles only directly owned Memories in one exact
  Context. It has no lexical-descendant or embedded traversal mode.
- It may consume a same-Context typed conflict-finder handoff, but rechecks the
  complete source and does not treat the finder's review draft as resolution
  guidance or mutation authority.
- A rule-required STOP or zero target-reaching candidates returns the legacy
  non-applicable `NEEDS_INPUT` status with a non-interactive reason; it does not
  ask the person to choose. A reasonable interpretation with explicit
  unsupported factual premises returns `ASSUMED` and remains process-local.
  A safe alternative derived exactly from cited descriptive claims may instead
  be grounded, finish at MAY, and Apply. `NEEDS_AUTHORITY` is
  reserved for a deterministically missing
  `DERIVE` capability or for a request with no effective mutation kind; a
  denied optional effect alone is not proof that more authority would solve
  the semantic problem.
- DELETE never migrates inbound references.
- There is no hidden batching. Every Fit, generation, and verification stage
  is whole-frame and fails before publication when its budget is exceeded.
- Plain CLI exact Apply and agent Apply after process restart still regenerate
  a candidate rather than loading a durable reviewed plan. A nondeterministic
  provider may produce a different exact post-image and fail closed.
  Process-local TUI/Python Apply and the next-turn agent cache avoid that replay
  boundary; durable plan persistence remains future work.
- The process-local proposal is not a claim of factual truth. Resolve proves
  only supplied-evidence grounding, information preservation, authorization,
  and complete-frame Fit under the operation's reviewed contract.

## 2026-08-20 execution-receipt migration

A `PROPOSAL` status already contains exactly one independently Fit-verified,
minimum-change candidate. The ordinary Resolve invocation now treats that as
its operation-owned judgment and applies it atomically instead of making the
proposal the public outcome. The checkpoint retains the candidate summary,
grounding, Fit reason, and exact effects for `mem review resolve --receipt
UID`. `--apply --candidate --expected-revision` remains a compatibility replay
boundary, not the default lifecycle.

## 2026-08-22 compact proposal projection

Resolve no longer uses its former full Viewer, Responses, Items, and To Do
workbench for a `PROPOSAL`. That layout repeated a report after generation and
made a single verified automatic plan look like an unresolved interpretation
choice. A compact projection remains available to explicit hosts that inspect
a process-local proposal, but the ordinary CLI execution route applies its
unique verified plan directly under the apply-first policy above; it does not
insert the compact projection as a second approval step. Read-only terminal
outcomes remain in the semantic Viewer.

Conflict Find hands the exact finding to the same ordinary Resolve execution
route, so direct Resolve and conflict handoff cannot drift into different
application semantics. Both routes still carry the frozen candidate UID and
revalidate authority and revision before mutation. The removed second
exact-command page was presentation duplication, not the source of those
invariants. Supporting several Pareto-incomparable candidates would require an
explicit typed design; such a result is not eligible for automatic Apply.

Plain Resolve now reports observable outcomes instead of using `FIT REPAIR` as
a status-independent report heading. Every route begins with `RESOLVE · NAME`.
An `ALREADY_FIT` result adds only `FIT · YES|MAY · NO CHANGE`, using the actual
initial verdict because the default target can already be met at MAY. A
`NEEDS_INPUT` or `NEEDS_AUTHORITY` result adds its one actionable reason.
`ASSUMED` remains slightly longer because hiding an unsupported premise would
weaken the safety boundary: it retains the temporary interpretation, every
named assumption, the question needing input, and the fact that no durable
change occurred.

An applied result reports its nonzero primitive effect counts and independently
checked post-Fit verdict, followed by the checkpoint, its exact
`mem review resolve --receipt UID` route, and `mem undo`. It omits zero counts,
duplicate receipt/checkpoint identity, revision, and candidate ID. Those
details, candidate reasoning, and exact effects remain in the immutable
checkpoint; naming that checkpoint-backed Review route prevents a compact
receipt from becoming a dead end without copying the report into terminal
scrollback. This does not weaken Apply's authority, freshness, or atomicity
checks. The explicit `--tui` inspection route and typed analysis remain
detailed.
