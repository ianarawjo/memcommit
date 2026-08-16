# Iterative ticker Ground flow TODO

## Decision and order

The ticker replay is an evaluation of the Ground authoring loop, not a shortcut
that imports an already known Rule set. It begins with the exact vague Goal
`티커가 어떻게 만들어지는지 규칙을 알고 싶어`, then reveals reviewed
Example propositions in frozen rounds of 5, 10, 20, 35, and 50. Elaborate may
suggest unverified candidate Rules, Distill may induce evidence-bound Rule
proposals from the included Examples, and Fit may judge the accepted Rules
against those Examples. None of those read-only results revises the Ground.

Before automating the replay, add a typed Resolve boundary that can turn one
exact semantic artifact into one reviewed Ground action. Resolve must retain
the source artifact's verification status, freeze the Ground identity, and use
the existing exact command and CAS boundary for application.

Finish and commit the current Distill application/result contract before
adding a persisted hidden receipt. The receipt is a later runtime/prewarm
adapter over `DistillPreparedLookup`; it must not change Distill's meaning,
whole-frame validation, proposal schema, evidence coverage, or Apply contract.

## Frozen benchmark

`memcommit/eval/fixtures/ticker_ground_workflow.json` is the authoritative
staged corpus and `memcommit.eval.ticker_ground_workflow` is its strict loader.
Only the vague Goal and Examples revealed through the current round may be sent
to a provider. Host-side category and expected-resolution labels are scoring
evidence, not prompt hints.

The corpus uses fictional names and synthetic tickers. It contains 46 exact
mapping propositions plus four late boundary propositions that must remain
explicitly unresolved until a policy is supplied:

- transliteration of non-ASCII names;
- slash-separated name components;
- debt-security descriptors; and
- unsupported series designations.

This means convergence is not synonymous with inventing 50 ticker strings. A
successful final Ground explains every determined mapping, preserves all four
unknowns as visible boundaries, and does not claim official or unique market
symbols. The fixed categories also cover leading articles, legal suffixes,
connectors, single-word mnemonics, numeric and mixed tokens, hyphens, acronym
tokens, share classes, preferred shares, and permitted collisions.

## Representative progression

Exercise these visible rounds:

1. create a proposition-schema Ground with the vague Goal and the first five
   reviewed INCLUDE Examples;
2. Elaborate the Goal, review no suggestion implicitly, select one candidate
   through Resolve, then Fit the separately accepted Rule;
3. reveal Examples 6–10, Distill an evidence-bound delta, Resolve one exact
   proposal, and rerun Fit after the resulting Ground revision;
4. repeat at 20 and 35 Examples, revising or splitting Rules when boundary or
   contrast Examples expose an overgeneralization;
5. reveal all 50, including the four intentionally unresolved policies, and
   refuse any Resolve proposal that fabricates their outcomes;
6. optionally add or edit ordinary Context Memories outside Ground, making the
   saved binding stale;
7. explicitly refresh or replace the affected binding, showing the old and new
   frame identities and which Ground judgments require review; and
8. verify that the final Ground remains open until the person explicitly
   approves it and all required unresolved boundaries have been handled.

Every round must show the current Goal, accepted Rules, active INCLUDE Example
set, Context binding freshness, latest Fit freshness, and exact analysis origin
(`LIVE` or `PREPARED_EXACT`). Distill and Elaborate remain proposal-only: they
cannot promote their own Rules or Examples.

## Resolve contract

Resolve consumes exactly one frozen source artifact:

- a current immutable Fit receipt bound to the same Ground UID, revision, and
  digest;
- a Distill result whose complete source and Goal still match; or
- an Elaborate result explicitly labelled `UNVERIFIED`.

It produces at most one deterministic Ground action or one explicit
no-action/defer outcome. An action may revise the Goal, propose or refine one
Rule, propose or refine one Example, or change one Example's USE state. It may
not bundle several revisions, approve its own proposal, widen evidence, or
silently rewrite a failing Example to agree with the Rules. A proposal derived
from Elaborate remains unverified after projection; selection does not turn it
into evidence.

Application freezes and revalidates the source artifact and Ground
UID/revision/digest, display the exact action before approval, and use the
existing Ground store CAS. A successful action creates exactly one Ground
revision and makes every prior Fit receipt stale. Stale artifacts fail before
provider connection or mutation.

## Executable replay contract

`memcommit.eval.ticker_ground_replay` now exercises the deterministic
application path against an injected semantic provider. It creates and binds a
fresh proposition-schema Ground, adds and separately accepts every frozen
Example, and records every read-only artifact, Resolve plan, Resolve apply,
ordinary Rule acceptance, Fit receipt, and revision transition in one
JSON-serializable ledger.

The replay deliberately selects only one candidate from each semantic result.
The first Elaborate Rule is selected during the five-Example round; each
Distill round selects the non-duplicate Rule with the widest cited Example
coverage. Resolve leaves that Rule proposed, and an ordinary Ground review
accepts it as a separate revision. Suggested Elaborate Cases remain
`UNVERIFIED` and unapplied because inserting them would change the frozen
benchmark rather than evaluate it. If a Fit issue has no reviewed repair, the
replay records an explicit no-mutation `DEFER` instead of changing an Example
to make the test pass.

Host fixture roles, coverage categories, and expected-resolution labels are
added only to the returned evaluation ledger after provider-facing work. They
are never semantic prompt input. This keeps the real-provider run diagnostic:
it may converge, expose regressions, or leave boundaries unresolved, but it
cannot receive the answer key from the harness.

## Missing Context-binding capability

The current binding contract correctly marks a Ground stale after a bound
Context changes, but it has no non-destructive refresh path. Design one typed,
reviewed application action after Resolve's single-revision contract is proven.

That action must:

- freeze the old Ground UID/revision/digest and old frame identities;
- freeze and authorize the proposed replacement Context frames;
- display the exact old-to-new binding diff before approval;
- create one new Ground revision without mutating either Context;
- preserve unchanged source-linked Examples and their provenance;
- mark changed, removed, newly introduced, or ambiguously remapped evidence as
  requiring review rather than guessing an identity;
- make prior Fit receipts stale and prevent stale Fit or Distill material from
  being presented as current;
- preserve prior Rules as reviewed history while requiring a new Fit after the
  evidence frame changes; and
- fail atomically on stale Ground CAS, stale Context identity, lost authority,
  ambiguous mapping, or persistence failure.

Context mutation itself remains owned by ordinary Context operations such as
Add or Edit. Ground reviews the resulting binding transition; it does not edit
Context JSON or combine a Context mutation and Ground refresh into one hidden
action.

## Distill hidden-receipt follow-up

After the live iterative flow and Distill contract are stable, add an exact
hidden artifact adapter using the shared Study prewarm registry. The first
version may hit only when the complete ordered Source frame, Goal, semantic
configuration, provider identity, and Distill contract version match. It must
validate authority and input before lookup, avoid provider construction on a
valid hit, revalidate the Ground/Context after lookup, and create no visible
session during Study initialization.

Do not claim ancestor, descendant, or subset projection for Distill merely
because another operation can project its cache. Removing or adding one
Example can change the complete induced Rule set. Any broader equivalence must
be proved as a separate Distill compatibility rule.

## Verification gates

- strict corpus tests for exact size, monotonic stages, category coverage, and
  the four non-inventable boundaries;
- deterministic Resolve planning tests for source identity, verification
  labels, action cardinality, revision/digest freshness, and no-op outcomes;
- provider-spy tests proving stale/all-off/unauthorized inputs fail before
  connection;
- a complete 5-to-50 replay with stored per-round Ground revisions, semantic
  artifacts, reviewed Resolve commands, and Fit receipts;
- regression evidence that earlier Examples remain visible and are not
  silently reclassified after a Rule or binding revision;
- Python, agent, CLI, and TUI parity through the same typed application action;
  and
- an ordered `180x52` PTY capture covering entry, Example growth,
  contradiction, Rule revision, explicit unresolved boundaries, stale receipt,
  reviewed Resolve, new Fit, and final read-only verification.

## Progress

- [x] freeze and strictly validate the 5→10→20→35→50 benchmark;
- [x] define one-source/one-action Resolve plans and verification labels;
- [x] revalidate exact artifacts and apply one existing Ground primitive with
  bound-frame checks and Ground CAS;
- [x] expose Ground Fit and Resolve planning/application through the stable
  Python boundary;
- [x] expose process-local Ground artifacts and Resolve through the agent/MCP
  boundary;
- [x] compose the same action into the Ground workbench and exact approval UI,
  with ordered 180×52 PTY evidence for non-FIT selection, cited-Rule edit,
  exact command/effects review, one-revision Apply, and stale receipt;
- [x] execute the complete 5→10→20→35→50 path against a deterministic semantic
  provider and verify proposal-only artifacts, one-revision mutations, stale
  Fit projection, separately reviewed acceptance, and prompt-label isolation;
- [x] run and capture the complete provider-backed ticker progression, retaining
  the first fail-closed evidence-overlap failure and the fresh post-contract-fix
  rerun; and
- [x] evaluate convergence, regressions, and explicit unresolved coverage: the
  run reached 48/50 FIT with no prior-FIT regression, preserved all four
  unsupported boundaries without fabricated outputs, exposed one genuine Rule
  conflict and one internally inconsistent Fit verdict, and showed that the
  issue-triggered Goal refinement policy can leave the visible Goal vague.
