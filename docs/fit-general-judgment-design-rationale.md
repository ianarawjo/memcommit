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
| Distill, Elaborate | Use generative model capabilities, so their proposals remain unverified. A later Fit judgment can test compatibility but cannot establish truth or evidential support. |
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
mem fit "[proposition A]" "[proposition B]" ["[proposition C]" ...]
mem fit "[A]" "[B]" --background "[background K]"
```

It is read-only and process-local. It creates no Context, Memory, Ground, or
receipt. Its stable marks are `✓ YES`, `? MAY`, and `! NO`.

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

## Limits and next work

- Fit judges practical consistency under ordinary readings; it is not a
  theorem prover and does not quantify over every imaginable world.
- A `YES` result does not establish that any proposition is true, supported,
  useful, ethical, authorized, or safe to apply.
- Goal and Rule adapters must present their already-stated constraint meaning;
  Fit must not silently rewrite an imperative into a more convenient claim.
- Provider quality still needs calibration cases. Exact contract validation
  proves coverage and shape, not semantic correctness.
- Other operations should adopt the theory through their own explicit design
  reviews. This decision records the shared premise; it does not silently
  change their current provider contracts.
