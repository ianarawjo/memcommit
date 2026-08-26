# Participant-facing operation copy design rationale

## Motivation

Participant-facing Search, Query, Find, review, and progress surfaces had begun
to expose implementation-state vocabulary such as `COMPLETE`, `FROZEN`,
`PROCESS-LOCAL`, and `DETERMINISTIC`. In the motivating path, a person entered
`mem query "nihao"` or opened Search and saw several of those qualifiers around
an otherwise simple read-only result. The labels were technically true but did
not help the person decide what to enter, what was happening, or what to do
next.

## Copy contract

User-visible operation copy now prioritizes one of three facts:

1. the required action, such as `ENTER A QUESTION` or `ENTER A PATTERN`;
2. the current activity, such as `QUERYING` or `SEARCHING`; or
3. the observable outcome, such as `ANSWER READY`, `2 RESULTS`,
   `REPLACE APPLIED`, or `NO CHANGES`.

Headings name the command or object once. Repeated mode subtitles and status
suffixes do not restate that the UI is interactive, one-shot, process-local,
complete, or backed by a frozen input frame. Counts retain explicit nouns and
correct singular/plural forms because they remain useful without color.

The same rule applies to Resolve's semantic outcomes. Its ordinary plain
projection uses `RESOLVE · NAME` once, then reports the actual result:

- an already-sufficient frame is `FIT · YES|MAY · NO CHANGE`;
- a blocked route is `NEEDS INPUT · reason` or `NEEDS AUTHORITY · reason`;
- an ungrounded working view retains its temporary interpretation, every named
  assumption, the question needing input, and an explicit no-change boundary;
  and
- a successful mutation reports only its nonzero CREATE, UPDATE, and DELETE
  counts, independently checked post-Fit verdict, checkpoint, and recovery
  command.

These receipts do not repeat the internal status name, target, available
effects, revision, candidate identifier, or initial judgment reason. The
checkpoint retains the complete applied evidence for later Review.

Safety review copy states the consequence instead of the implementation
mechanism. For example, Apply screens say that Apply stops if a Context changed,
and stale-selection errors tell the person to reopen the operation and select
again. `FIXED` is used only when a setup role cannot be edited; it does not imply
that the underlying Context is immutable.

## Preserved invariants

This is a presentation change. Command-start catalog snapshots, frozen semantic
inputs, exact reviewed revisions and digests, provider disclosure boundaries,
compare-and-swap checks, all-or-none publication, and read-only Source behavior
remain unchanged. Internal model names, progress event identifiers, docstrings,
and exceptions may continue to use `frozen` or `complete` when those terms name
an actual implementation invariant rather than participant copy.

`complete` remains acceptable where it distinguishes the whole document from a
focused subpart, such as copying the complete Query answer, and in established
domain terminology such as complete DUN coverage. Natural uses such as “could
not be completed” are also outside this status-label rule.

## Alternatives and limits

Removing every status line was rejected because the same location provides
useful progress, count, error, and next-action feedback. Replacing every
`frozen` label with `fixed` was also rejected: it would preserve the jargon and
could falsely describe data that may change outside the reviewed operation.

The change intentionally does not rename public Python types, serialized stage
events, or application-layer contracts. Those names are compatibility and
research evidence, not terminal copy. New participant-visible text should be
reviewed by meaning rather than by a repository-wide ban on individual words.

## Verification

Focused tests cover the affected CLI and TUI projections, every compact Resolve
plain outcome, progress text, selection errors, review safety lines, and
receipts. The ordered
`agent-records/docs/screenshots/participant-facing-copy-20260822/` capture set records Query,
Search, and Find entry, active work, result, and read-only close states in a
`180 × 52` true-color PTY.
