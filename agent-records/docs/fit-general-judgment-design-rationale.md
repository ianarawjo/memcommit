# General Fit judgment design rationale

## Decision

`Fit` is the role-neutral semantic judgment

```text
fit_K(P1, P2, ..., Pn) -> YES | MAY | NO
```

over one complete frozen background `K` and at least two already-stated
propositions. A proposition may originate as a Memory, Rule, Goal, Example, or
plain proposition. Those roles remain visible provenance, but they do not
change Fit's polarity or authorize a different inference rule.

The public proposition form is now the meaning of `mem fit`. The older saved
Ground Rule–Example report remains available only through the explicit
`--ground` adapter. That adapter preserves its immutable receipt and stale
revision behavior, while native proposition Examples obtain their semantic
judgment from the general Fit core.

Stored Memory and Context operands are source adapters for that same public
proposition form. They do not introduce a second Context-level Fit meaning:
each selected direct ordinary Memory contributes its already-stated content as
one role-typed `MEMORY` proposition, after exact source and authority freezing.

## Motivating reconstruction

The earlier theory described `fit = YES | MAY | NO` inside one Context. It
treated Context as a selected partial Memory-graph specification `K`, with
ordinary interpretations drawn from the worlds admitted by `K`. The surviving
notes additionally described the LLM as a rough common-sense plausibility
estimator over those interpretations, not as an oracle for reality.

The name was later reassigned to a narrower Ground Rule–Example operation.
That made `mem fit "A" "B"` impossible and introduced Ground-specific labels:
`FIT`, `CONTRADICTS`, `UNDERDETERMINED`, and `NOT_APPLICABLE`. The narrower
operation was useful, but it was not the earlier general operator. Restoring
the general definition makes it reusable by Rule, Goal, Memory, and future
operation adapters without making any of those representations primary.

## Formal judgment

Let `Omega_K(P)` be the materially ordinary joint readings of the complete
frozen set `K union P`. Let `c(omega) = 1` when all propositions can jointly
hold under reading `omega`, and `0` when they cannot.

- `YES`: `c(omega) = 1` for every materially ordinary reading.
- `NO`: `c(omega) = 0` for every materially ordinary reading.
- `MAY`: at least one materially ordinary reading has `c(omega) = 1` and at
  least one other has `c(omega) = 0`.

`MAY` records semantic structure, never model hesitation. Provider
instability, low confidence, malformed output, or inadequate evidence about
provider quality is a separate failure or review condition. It must not be
encoded as `MAY`.

Different subjects, times, places, audiences, or unrelated topics return
`YES` when their propositions can coexist. Missing evidential support and an
unknown fact are not contradictions. There is therefore no general
`NOT_APPLICABLE` or `UNDERDETERMINED` verdict. A non-propositional or otherwise
invalid input fails validation rather than acquiring a semantic label.

The judgment is set-level, not merely pairwise. Three or more propositions can
be jointly inconsistent even when each isolated pair appears compatible. The
whole frame must therefore remain in one bounded provider turn. Crossing the
whole-frame limit fails before provider construction; it does not authorize
hidden batching or pairwise reduction.

## The LLM's narrow role in Fit

Fit gives the provider one strong but bounded job: identify materially
ordinary readings and judge joint compatibility. The provider must:

1. receive the complete frozen background and proposition set;
2. acknowledge every input alias exactly once and in frozen order;
3. return only `YES`, `MAY`, or `NO` plus a concise reason;
4. identify the proposition aliases material to `NO` or `MAY`; and
5. for `MAY`, expose one ordinary compatible reading and one ordinary
   incompatible reading.

It must not generate, revise, normalize, retrieve, rank, omit, or filter
propositions. It must not judge relevance, usefulness, evidential support, or
objective truth. It may use its pretrained ordinary-language, common-sense,
and domain-convention prior to distinguish ordinary readings from merely
formal or contrived ones. It may not use tools, files, network access, apps, or
unstated external facts.

This asymmetry is intentional. A language model's broad training can make it
especially useful as an estimator of how people ordinarily interpret a
statement in context. The same training does not make its output reality, and
its corpus prior can be incomplete or biased. Fit uses that prior as an
operational semantic instrument rather than granting the model epistemic or
mutation authority.

### Why this predictive prior fits Memory management

Natural-language Memory is accumulated incrementally from different times,
people, and sources. Before those propositions are combined, updated, or
reused, the practical question is whether a competent ordinary reader would
understand them as one coherent frame rather than as contradictory or
materially equivocal. This is not the same objective as a formal proof. The
frame has no complete axiom set, fixed symbolic vocabulary, or closed-world
semantics; it contains omissions, pragmatic assumptions, ambiguous reference,
and shifting scope. For Memory management, whether an invented logical model
can make the text satisfiable matters less than whether its intended readers
would ordinarily find it coherent and usable. Fit does not independently grade
all awkward writing or ambiguity: those qualities matter here only when they
change joint compatibility.

Next-token pretraining requires a model to compress recurring relationships
among linguistic expressions, situations, and propositions. This makes the
resulting model useful as a predictive estimator of ordinary semantic
expectations: how propositions are commonly interpreted and whether they
normally coexist. Fit exploits that learned prior through a complete explicit
frame and a closed judgment vocabulary. It does not treat the model as a source
of truth or formal proof. Here, `ordinary` means a reading with material weight
in that learned language-use distribution, not every merely conceivable
reading and not a claim that one culture, corpus, or model represents everyone.

This framing also distinguishes Fit from an open-ended prompt to “imagine” a
case. Asking for one compatible scenario is an existential generation task and
rewards a rare exception that saves the set; asking for one conflicting
scenario creates the opposite bias. Fit instead asks the model to judge the
ordinary reading distribution, rejects rare or contrived premises, and exposes
a genuine split as `MAY`. The complete frozen frame, closed labels, exhaustive
coverage, and read-only boundary turn that predictive prior into a repeatable,
reviewable operation rather than an unconstrained story-generation prompt.

## Repository-wide theoretical role

This theory is a foundational premise for other semantic operations, but it
does not mean every LLM operation is secretly Fit. It supplies a reusable
account of one capability: an LLM can act as an ordinary-reading and
common-sense judge over a complete explicit frame.

Future and existing operations should state whether they use this capability
and what additional contract they add:

| Operation family | Relationship to the Fit premise |
| --- | --- |
| Conflict | Pairwise projection with reversed public polarity: Fit `YES` corresponds to Conflict `NO`, and Fit `NO` to Conflict `YES`. |
| Ambiguity | Uses ordinary readings to determine whether materially different interpretations remain; it does not make a compatibility judgment by itself. |
| Compare, Meld, Update | May use the same ordinary-reading prior to judge relations, but must additionally preserve exhaustive disposition, provenance, direction, authority, and operation-specific review. |
| Distill | Uses generative reduction, so its Rules remain unverified. Goal-focused Distill composes one whole-result Fit audit; an unfocused result may receive a later Fit judgment. Neither establishes truth or evidential support. |
| Elaborate | Uses generative expansion, so its proposals remain unverified. Default Rules-to-Cases is best-effort and does not invoke Fit; explicit strict mode composes general Fit after independent Rule Conformance and accepts only Source-compatible Cases. Fit still cannot establish truth, factual grounding, or evidential support. |
| Find, Query | Use interpretation and relevance rather than compatibility; ordinary common sense can assist retrieval, but Fit labels are not relevance scores. |
| Ground | Projects selected Rules and an Example into a Fit frame. Exact-output replay remains a separate conformance adapter because deterministic output reproduction is stronger than proposition compatibility. |

Whenever an operation uses the LLM as a judge, the reusable design discipline
is: freeze the complete authorized input, define a closed judgment vocabulary,
require exhaustive coverage, keep semantic indeterminacy separate from model
confidence, and retain the operation's own authority and materialization
boundary. The Fit premise must never be cited to justify hidden input
omission, provider-side mutation, or automatic application.

## Public and adapter contracts

The general CLI form is:

```text
mem fit
mem fit [UID_OR_PREFIX] [CONTEXT] "[literal proposition]"
mem fit [CONTEXT:UID_OR_PREFIX] [CONTEXT] text:[forced literal]
mem fit "[proposition A]" "[proposition B]" ["[proposition C]" ...]
mem fit "[A]" "[B]" --background "[background K]"
mem fit --memory [UID_OR_PREFIX] --memory [UID_OR_PREFIX]
mem fit --memory [CONTEXT:UID_OR_PREFIX] --memory [CONTEXT:UID_OR_PREFIX]
mem fit --context [CONTEXT A] --context [CONTEXT B]
mem fit "[A]" --memory [UID_OR_PREFIX] --context [CONTEXT]
```

It is read-only and process-local. It creates no Context, Memory, Ground, or
receipt. Standalone output uses an explicit operation-wide grammar:
`FIT · YES|MAY|NO · [TARGETS: TYPE value, value, TYPE value ...]`. The leading
verdict is the result of the complete n-ary operation, not the status of the
first listed target.

Fit always returns a compact terminal receipt; it has no standalone Viewer or
`--tui` route. Every general result is one logical target-summary line. One
outer `[TARGETS: ...]` groups selected Context names, direct Memory UID
prefixes, and literal proposition aliases by type. A type label starts a group;
comma-separated values belong to it until the next type label. Contexts are
listed once even when they expand to several direct Memories, while directly
selected Memories retain their individual UID prefixes. The compact line
therefore does not repeat exact bodies, Context-to-Memory provenance, or the
original interleaved argv order. The typed result still retains every expanded
Memory origin, exact proposition body, reason, material alias, and both
required ordinary readings for `MAY`. A `YES` receipt ends after the target
group because no issue needs explanation. `MAY` and `NO` append their compact
reason to that same logical line as `· WHY · REASON`; they never create a
second explanation row. Display escaping keeps an embedded provider newline or
control from fabricating another receipt line. In a color-capable TTY, only the
typed `YES`, `MAY`, or `NO`
token uses its shared judgment role: green, yellow, or red respectively.
Operation chrome, punctuation, source labels, Context/Ground names, counts,
and Memory bodies remain neutral. `--plain` remains accepted for compatibility
and suppresses ANSI without changing the receipt text or preserving a second
layout mode.

Each positional operand is typed locally before provider construction. The
reserved `text:` prefix forces the remainder to be literal proposition text.
Otherwise a canonical UUID-shaped prefix of at least the eight characters
shown by the CLI is a strict Memory selector, and
`CONTEXT:UID_OR_PREFIX` is a strict qualified Memory selector. Any exact member
of the frozen Profile-wide readable Context catalog is a Context source;
explicit relative locators must also resolve inside that catalog. Every other
operand is literal proposition text. Shell quotes only keep multiword text in
one argv item: the shell removes them, so quoted and unquoted copies of the
same one-word value cannot have different types. A literal that collides with
a Context name or UID shape therefore uses `text:VALUE`.

The Context-versus-Memory portion of this decision uses the shared
`context_targeting` typed operand parser also consumed by other mixed-target
commands. Fit owns only the additional readable-catalog Context check and
literal-text fallback; it does not maintain a second UID/owner grammar.

`--memory` and `--context` remain repeatable explicit members of the same
proposition set for scripts, short Memory prefixes, source-looking literal
diagnostics, and legacy UUID-shaped Context names. They are not background or
hierarchy controls. An unqualified Memory selector resolves inside the current
Context captured once at command start. The qualified
`CONTEXT:UID_OR_PREFIX` form and every Context operand resolve existing Context
locators against that same snapshot. A Context operand expands only its direct
ordinary Memories in stored order. It does not follow lexical descendants,
embedded Contexts, live or snapshot Memory references, or QUERY-only routes.
Those axes require separate operation review rather than a hidden widening of
one selected set.

With no proposition, Memory, or Context operand, the CLI treats the
command-start current Context as one implicit Context source. This is the
convenience spelling of selecting that Context's direct ordinary Memories, not
a request to widen into descendants or embedded content. The same minimum of
two effective propositions applies after expansion, so an empty or one-Memory
current Context fails locally before provider construction.

Automatic operands retain their positional order, with a Context expanding its
direct Memories in place and stored order. Explicit `--memory` values follow
the positional frame in option order, followed by explicit `--context` values
in option and stored order. The adapter rejects an empty Context and a missing
or ambiguous strict Memory prefix. Repeating a Context, repeating a direct
Memory, or selecting the same stored coordinate directly and through a Context
preserves each argv occurrence as a distinct operator operand. Equal content
is compatible rather than an overlap error; digest maps may collapse identical
coordinates only for revalidation, never from the semantic frame or receipt.
At least two effective propositions are still required after expansion, and
repeated operands count because they were explicitly supplied; background does
not satisfy that minimum. New UUID-selector-shaped root Context names are
rejected by the common new-identity validator; existing legacy names remain
available through explicit `--context`.

Every selected Context retains its exact public name, Context UID, and either
its complete direct-record digest or the content digest of each explicitly
selected Memory. Those origins support authorization, exact revalidation, and
the grouped public target labels. The typed result retains the complete frozen
operand frame in order, while the compact receipt groups only source identities
by category. A source change during inference prevents a result from being
returned. Effectively
READ-granted inputs additionally require `DERIVE`, and
`COMBINE` when another ownership domain or caller-supplied literal participates;
the Grant binding and exact selected content are revalidated before the
process-local result is exposed. General Fit requires no analysis-retention
permission because it saves no result.

The compatibility Ground route is explicit:

```text
mem fit --ground [ground]
mem fit --ground [ground] --receipt [uid]
```

For native proposition Examples, the adapter maps `YES -> FIT`,
`NO -> CONTRADICTS`, and `MAY -> UNDERDETERMINED`. It never maps an unrelated
claim to `NOT_APPLICABLE`; unrelated but compatible propositions are `YES`.
Legacy exact-output Grounds continue through deterministic conformance replay
and retain their historic receipt vocabulary for compatibility.

The Ground adapter projects the complete stored analysis as a small receipt:
one `FIT · YES|MAY|NO|STALE · [TARGETS: GROUND <name>] · <fitted>/<total>` whole-operation
summary followed only by current non-fitting checks.
A Rule–Example issue is exactly one line: `! NO · [RULE r1] [MEMORY <uid-prefix>] <content> ↔ [EXAMPLE e3] [MEMORY <uid-prefix>] <content> · WHY · <reason>`.
It has no alias-only heading, blank separator, or expanded `WHY` row; the same
logical line ends with `· WHY · REASON`. The public line preserves
classification, both Ground roles, both Memory identities, both exact bodies,
and the decisive explanation without turning one judgment into a block. A
coherence issue follows the same rule: its axis, frozen check participants,
additional material Context Memories, and reason remain visible on one
display-escaped logical line rather than a heading-plus-evidence-plus-`WHY`
stack.
`UNDERDETERMINED` becomes `? MAY`, `CONTRADICTS` becomes `! NO`, and a legacy
`NOT_APPLICABLE` check becomes `· N/A`. Fitting Example and graph details are
omitted; they remain counted and retained in the immutable Ground receipt.
Stale results omit old issue detail rather than presenting it as current.

## Calibration boundary

`agent-records/outputs/fit-calibration/fit.json` preserves the first reviewed
consumed-calibration corpus for this contract. Its 18 cases balance `YES`,
`MAY`, and `NO` and cover explicit scope distinctions, unrelated claims,
missing verification, role neutrality, Korean and English readings, genuine
referential splits, direct contradiction, dominant antecedents, and a
three-way inconsistency that cannot be reduced to isolated pairs. The
historical `memcommit.eval.fit_calibration` runner loaded the corpus strictly
and judged every case in one whole-frame provider call.

The one-off runner and its dedicated fake-provider tests were retired from the
distributed package on 2026-08-27. Their final executable snapshot is
recoverable from commit `4fd2d0033`; the calibration was introduced and its
single observed 18/18 result was recorded in commit `1f30686e4`. The reviewed
cases moved to the retained output tree because no raw provider response,
provider identity, timing, or standalone execution ledger was kept. This
cleanup does not change the live Fit judgment contract or its production
tests.

The expected labels and rationales are scored locally and never enter the
production Fit prompt. This is consumed calibration, not an independent
holdout and not evidence of general accuracy. A separate pre-registered
holdout, repeated runs, and recorded provider/model identity are required
before making a stability or generalization claim.

## Limits and next work

- Fit judges practical consistency under ordinary readings; it is not a
  theorem prover and does not quantify over every imaginable world.
- A `YES` result does not establish that any proposition is true, supported,
  useful, ethical, authorized, or safe to apply.
- Goal and Rule adapters must present their already-stated constraint meaning;
  Fit must not silently rewrite an imperative into a more convenient claim.
- Stored Context expansion is deliberately direct-only. Reference traversal,
  descendant reach, and interactive source selection remain non-goals until
  their authority and visible range controls are reviewed explicitly.
- The retained consumed calibration locates known boundaries but does not prove
  provider quality; exact contract validation proved coverage and shape, not
  semantic correctness.
- Other operations should adopt the theory through their own explicit design
  reviews. This decision records the shared premise; it does not silently
  change their current provider contracts.
