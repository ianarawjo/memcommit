# Automatable error patterns distilled from the six-world audit

These detectors are a fast discovery lane. They can find strong candidates
without completing five goal-driven attempts, but they do not replace the
long-run confirmation, user-impact judgment, or decision-boundary review.

## A. Deterministic contract detectors

### AP-01 · Target/source identity mismatch

Freeze requested Context, Profile, session, provider route, and authority IDs.
Reject any successful receipt, Reference, Diff, or stored artifact whose actual
identity falls outside that frozen set.

Already exposed: granted Query misrouting and cross-world Update/Diff bleed.

### AP-02 · Producer-to-consumer round-trip failure

Extract every identifier and advertised next command from a successful receipt.
Immediately invoke the documented read-only consumer. Flag IDs that are
ambiguous, interpreted as another object kind, unavailable, or require manual
text rediscovery.

Already exposed: Merge/Chunk/Dedun UID omissions, Review short IDs, recursive
Checkpoint set UID, and Diff checkpoint grammar.

### AP-03 · Incomplete frozen-input coverage

For operations promising per-item judgment, alias every frozen input and require
exactly one typed disposition per alias. Duplicates, omissions, invented aliases,
or unexplained `NONE` are failures. A failed turn must publish no partial result.

Already exposed: Conformance and combined Audit/Conformance decoder failures.

### AP-04 · Failure published partial mutation

Hash every exact target before an operation. For nonzero exit, timeout,
interruption, or decoder failure, compare target, checkpoints, sessions, and
history against the allowed failure contract. Flag any unadvertised durable
change.

### AP-05 · Recovery artifact does not actually recover

Create a checkpoint, perform one known scratch mutation, validate Diff, Revert,
and exact post-state digest. Test direct Context and recursive/set receipts
separately. A printed recovery ID is not considered valid until this round-trip
passes.

### AP-06 · Global-state ownership leak

Run two labeled worlds behind a start barrier. Give every payload a unique
canary. Assert that current, Update/Diff/Review session, Undo/Redo producer,
provider route, and command receipt never contain the other world's canary or
identity.

This is the focused shared-Profile concurrency lane; isolated world Stores would
otherwise hide the defect.

### AP-07 · Success label contradicts stored postcondition

Translate typed receipt claims such as `APPLIED`, `NO CHANGE`, `FIT`, `READY`,
`NEEDS INPUT`, counts, and target names into assertions over the stored state.
Examples: challenged text still exists after correction; `NEEDS INPUT` has zero
required/optional judgments; created count lacks created objects; no-op creates
unexpected durable artifacts.

## B. Metamorphic/differential detectors

### AP-08 · Scope-dependent semantic flip

Hold one exact Memory and criterion constant while varying only presentation
scope: exact Memory, direct Context, recursive subtree, and combined frame.
Flag incompatible judgments unless the receipt names the additional evidence
that caused the change.

Observed example: the same practice-source Memory was COMPOSITE in a whole
frame and ATOMIC/KEEP when selected exactly.

### AP-09 · Equivalent route disagreement

Compare direct CLI, TUI selection, reopened session, and typed API/MCP routes
where they promise the same operation meaning. Normalize presentation and
compare target identity, disposition set, effect set, and next action.

### AP-10 · Order or concurrency changes ownership

Execute independent disjoint operations in A→B, B→A, and barrier-concurrent
orders. The goal-local results should be equivalent modulo timestamps/UIDs.
Use this specifically for saved sessions, command commits, and Profile-current
reads.

### AP-11 · Accumulated-state/idempotence drift

Repeat a documented no-op or cached read before and after unrelated world work.
Flag stale-stage collisions, a created Ground that later appears absent, a
short session ID that cannot reopen, or a no-op that creates new checkpoint/
session noise without saying so.

### AP-12 · Language and format drift

For an English fixture and request, run equivalent routes and assert the output
language, JSON schema, aliases, and word/limit contract. Flag silent language
changes, ignored limits, or provider verbosity that turns ordinary input into a
failure.

## C. Semantic safety detectors

### AP-13 · Novel unsupported assertion

Extract atomic claims from semantic output and align them to exact Source spans.
Any new person, event, diagnosis, preference, permission, alternative, or
condition without a span must be labelled inferred/unverified and kept outside
an evidence Context. Missing that label is a high-priority candidate.

### AP-14 · Governing constraint loss

Represent goal constraints such as minimum-necessary, withhold-until-approved,
equal authority, preserve meaning, and do-not-edit as explicit criterion atoms.
Require every materialization proposal to show how each atom was satisfied,
preserved, or intentionally rejected.

### AP-15 · Unsafe fragmentation

After Chunk or Atomize, detect leading conjunctions/prepositions, dangling
suffixes, pronouns without antecedents, lost negation, and facts separated from
permission/exception/verification clauses. Treat the original and children as
one compound group until an independent-safety check passes.

### AP-16 · Destructive intent expansion

Before Forget/Resolve/Delete-like Apply, compare the user's criterion with every
KEEP/EDIT/DROP decision. Flag deletion of unique general rules when the request
names duplicates, deletion caused only by missing provenance metadata, or any
effect outside the exact reviewed frame.

### AP-17 · Authority/capability contradiction

Generate a matrix from effective grants and operation requirements. If a UI
advertises READ/EXPORT/DERIVE but the exact operation rejects the same access,
or if a workaround broadens from selected Memories to a whole Context, report
the contradiction and block automatic transfer.

## D. User-cost and frontend detectors

### AP-18 · Action buried by repeated evidence

Measure tokens, terminal screens, repeated source/reference blocks,
time-to-first-required-action, and required navigation keys. Flag a no-change or
single-decision report that renders the full corpus/hashes before its outcome,
or grows pairwise without grouping.

### AP-19 · Focused control differs from visible next action

In a real 180x52 color PTY, capture entry and every semantic transition. Assert
that Enter activates the visibly focused control, writable fields retain text
keys, Escape retreats one layer, and a required Apply/approval is both visible
and distinctly focused.

### AP-20 · Error offers no exact recovery command

For every rejected plausible route, require a typed cause, frozen target, and
one copyable corrected command when a safe equivalent exists. Give higher
priority when the missing grammar blocks recovery rather than ordinary
exploration.

## Fast discovery loop

For each operation:

1. create a minimal isolated scratch fixture and freeze all identities/digests;
2. run one normal route and one boundary route;
3. round-trip every receipt output into its documented consumer;
4. run the exact-vs-frame metamorphic pair when semantic scope exists;
5. assert success labels, exhaustive coverage, and no-partial-failure state;
6. for global/session operations, run one two-world barrier collision case;
7. record the smallest counterexample and route it to the long five-method
   campaign for confirmation and user-priority assessment.

The fast lane can automatically reject deterministic contract violations. It
must still pause for factual acceptance, ambiguous semantic intent, authority
broadening, and external transfer.
