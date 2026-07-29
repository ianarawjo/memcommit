# Case-guided rule induction

## Status

`induct` is a proposed inner semantic primitive of
[`mem ground`](mem-ground-design-rationale.md). No standalone `mem induct`
command, provider contract, rule language, or rule mutation path is
implemented.

An earlier draft treated `induct` as the complete interactive workflow. The
common-grounding discussion corrected that scope: induction produces a rule
delta, while `ground` owns the repeated human interaction, case curation,
decisions, regression checks, and approval.

## Decision

Given a reviewed candidate, the current rules, accepted cases, and a user
judgment that exposes a rule gap, induction may propose exactly one of:

```text
KEEP
NARROW
BROADEN
ADD_EXCEPTION
ADD_RULE
```

Its primary output is a readable, scoped conditional rule delta with:

- the concrete case that motivated it;
- the condition and expected judgment;
- a rationale identifying the decisive distinction;
- the accepted cases expected to change;
- the accepted cases that must remain unchanged; and
- at least one positive case plus a materially adjacent contrast.

The output remains a proposal. It cannot add a golden case, approve a rule,
change Memories, or mark a grounding contract complete.

## Relation to the grounding loop

```text
ground
  candidate
  → current-contract check
  → if RULE_GAP: induct a rule delta
  → curate supporting and contrast cases
  → user adjudication
  → regression check
  → next grounding round
```

A candidate can reveal several outcomes without requiring induction:

- `COVERED`: the current contract already explains it;
- `EXAMPLE_GAP`: the rule is adequate but the accepted casebook lacks a close
  representative or boundary case;
- `NEEDS_CLOSER_CASE`: the decisive distinction is not yet visible;
- `RULE_GAP`: a rule delta is needed;
- `CONTRACT_CONFLICT`: accepted rules or cases support incompatible outcomes;
- `CASE_INCOMPLETE`: the candidate needs minimal context;
- `OUT_OF_SCOPE`: another contract owns the judgment.

Only `RULE_GAP` normally invokes `induct`. `EXAMPLE_GAP` belongs to case
curation, while all statuses remain part of the interactive `ground` session.

## Rediscovered design history

The name and rulemaking idea predate this prototype:

- IdeenKasten `20260324193907`–`20260324193917`: the person supplies
  approximate intent and expected behavior, the AI proposes a readable
  heuristic, the person reviews a rule diff, and a failure becomes an explicit
  boundary case.
- `20260427090004`–`20260427090010`: expected input/output examples guide a
  rule proposal; a wrong result reveals that the rule is too broad or narrow;
  the wording is corrected and cases are rerun.
- `20260629090067`–`20260629090077`: rulemaking is explicitly named
  `/induct` and distinguished from summarization, generalization, and
  abstraction. Rules and conditions are primary; representative and edge
  cases support them.
- `20260719090010`–`20260719090011`: stored precedents and user judgments help
  resolve underspecified or conflicting principles locally.

The local archive is:

```text
IdeenKasten/gum_projects/using_ideenkasten/my_GUM_data.json
```

The same record explicitly calls the repeated human–AI rule iteration
"common grounding." That broader process now belongs to `ground`; the
historical `/induct` name remains appropriate for the rule-producing move.

## Boundaries

- `induct` is not `fill`: induction proposes a reusable judgment rule; fill
  proposes evidence-backed target content under an established contract.
- `induct` is not case curation: a valid rule may need a closer accepted
  example without changing its wording.
- `induct` is not the earlier public `fit` idea: `fit` described whether
  Memories coexist under ordinary Context readings. Case-to-rule coverage is
  a grounding stage and should not overload that polarity.
- `induct` is not `dream`: background consolidation may discover a candidate,
  but it cannot promote a rule.
- `induct` is not approval: a model-generated delta must be reviewed and
  regression-checked inside its grounding session.

## First implementation boundary

The first induction adapter should target the already documented
`find-ambiguities` contract because its reading and clarification dimensions
and contrast cases are explicit. One provider call should receive the small
accepted rule/case contract plus one candidate and return strict structured
output with known local IDs.

The provider may propose a distinction but may not:

- invent an accepted judgment;
- cite an unknown rule or case;
- mutate the contract;
- open query-only content;
- change more than the proposed scoped delta; or
- count its motivating case as independent held-out evaluation.

Promotion belongs to a later explicit grounding decision and creates a new
contract revision only after regression over previously accepted cases.
