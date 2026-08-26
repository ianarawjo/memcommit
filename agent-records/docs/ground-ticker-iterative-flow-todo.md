# Iterative ticker Ground flow TODO

## Decision and order

Finish and commit the current Distill application/result contract before
adding a persisted hidden receipt. The receipt is a later runtime/prewarm
adapter over `DistillPreparedLookup`; it must not change Distill's meaning,
whole-frame validation, proposal schema, evidence coverage, or Apply contract.

The next Ground slice should instead prove the iterative authoring loop that
the ticker scenario requires. A person must be able to grow concrete Example
propositions toward roughly twenty reviewed cases, revise Rules as boundaries
appear, and deliberately change or extend the bound Contexts without losing
the history that explains those revisions. Twenty is a representative stress
case, not an automatic completion or approval threshold.

## Representative progression

Use synthetic company names and generated ticker expectations so the fixture
tests transformation policy rather than asserting official market symbols.
Exercise at least these visible rounds:

1. create a Ground with a Goal and one reviewed INCLUDE Example;
2. Distill an initial Rule proposal, review the Rule separately, then run Fit;
3. grow to four ordinary Examples and expose the first contradiction;
4. add boundary and contrast Examples, including legal suffixes, class suffixes,
   acronym-like words, punctuation, and a deliberately ambiguous expectation;
5. revise or split Rules and rerun Fit without silently rewriting a failing
   Example to agree with the Rules;
6. add or edit ordinary Context Memories outside Ground, making the saved
   binding stale;
7. explicitly refresh or replace the affected binding, showing the old and new
   frame identities and which Ground judgments require review;
8. continue through eight, twelve, and approximately twenty reviewed Examples,
   alternating Distill, human Rule review, and Fit; and
9. verify that the final Ground remains open until the person explicitly
   approves it and all required unresolved boundaries have been handled.

Every round must show the current Goal, accepted Rules, active INCLUDE Example
set, Context binding freshness, latest Fit freshness, and whether a Distill
proposal is LIVE or PREPARED_EXACT. Distill remains proposal-only inside the
Ground: it cannot promote its own Rules.

## Missing Ground capability

The current binding contract correctly marks a Ground stale after a bound
Context changes, but it has no non-destructive refresh path. Design one typed,
reviewed application action before automating the ticker flow. Its exact name
is not fixed; `refresh binding` is used here as the semantic description.

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

- deterministic domain tests for binding-refresh classification and CAS;
- provider-spy tests proving stale/all-off/unauthorized inputs fail before
  connection;
- a complete 1-to-approximately-20 ticker replay with stored per-round Ground
  revisions and Fit receipts;
- explicit Context-addition, Context-edit, Context-replacement, and unchanged
  rebind cases;
- regression evidence that earlier Examples remain visible and are not
  silently reclassified after a Rule or binding revision;
- CLI/TUI parity through the same typed application action; and
- an ordered `180x52` PTY capture covering entry, Example growth, contradiction,
  Rule revision, stale binding, reviewed refresh, new Fit, Distill proposal,
  and final read-only verification.
