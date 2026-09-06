# Study task-local Compare graph prewarm design rationale

> Historical design: the prewarm implementation was removed on 2026-09-06.
> Scenario data and ordinary sessions remain; see [retirement rationale](study-prewarm-retirement-design-rationale.md).

## Decision

The existing graph-v2 evaluator prepares every unordered Compare pair inside
each task before participant interaction. It remains an exhaustive experimental
baseline and resumable evidence bundle, not the preferred foreground
architecture. Do not create cross-task pairs. A Context view means the selected
Context with descendants included, so a root, an intermediate parent, and a
leaf remain independently addressable views.

The current frozen plan is:

| Task | Views | Within-task pairs | Provider pairs |
| --- | ---: | ---: | ---: |
| Tutorial | 3 | 3 | 3 |
| Task 1 | 17 | 136 | 136 |
| Task 2 | 38 | 703 | 630 |
| Task 3 | 50 | 1,225 | 1,225 |
| Total | 108 | 2,067 | 1,994 |

The revised implementation direction is parent-pair-first. Prewarm a Compare
that is itself a meaningful user action, such as the two complete advisor
Contexts in Task 2, and project descendant requests from that artifact when the
requested left and right views are subsets of its respective sides. The
existing all-pairs bundle is retained to evaluate this reduction and must not be
described as the required production cache shape.

Task 2 contains two empty participant workspace views. Its 73 pairs involving
an empty view require no semantic inference. A nonempty Memory can only be
one-sided under that frozen pair, so the cache writes deterministic DISTINCT
entries. The empty-to-empty pair has an empty decision ledger. These records
remain explicit completed pair artifacts rather than looking like missing
work.

The tutorial graph is built from the canonical fixture constructor, not an
older initialized run's copied practice prose. Task 1 through Task 3 use the
active run's frozen readable Context catalog, including authorized public READ
views and ordinary local views. QUERY-only Context content never enters the
graph.

## Motivation

The foreground target is not to make approximately two thousand provider
calls complete within 30 seconds. It is to move the fixed-fixture analysis
before the measured interaction so an unchanged task-local request needs only
validated lookup and rendering. A selected Context still enters inference as
one complete descendant-inclusive frame. Prewarming many independently valid
pairs does not split one selected frame or publish a partial comparison.

The graph also makes the operation boundary explicit for the HCI study. It
records which task-local Contexts were jointly interpreted, which exact
revisions were used, and which later changes require projection or refresh.
It is not claimed as a generally optimal semantic graph or an NLP accuracy
contribution.

## Hidden bundle contract

`memcommit.study_scenarios.legacy.prewarm.generation.compare_graph` writes a resumable sidecar bundle
under `agent-records/outputs/study-compare-graph-prewarm/`. It does not write participant
Compare sessions, reports, or the production latest-pair slot.

The manifest binds:

- active Profile identity;
- task and task-description digest;
- model and reasoning effort;
- Compare ruleset and compact prompt versions;
- descendant scope;
- every view's public name, Context identity, Context digest, ordered Memory
  identities, and Memory content digests; and
- the prohibition on cross-task pairs.

Each pair key additionally binds its canonical left and right view names and
digests. A completed pair file stores only relation membership, kind, status,
a bounded comment, issues, coverage, and provider timing evidence. It does not
repeat Memory prose or contain a participant-facing narrative report. Memory
content remains in its authoritative Context; the manifest has enough digest
evidence to reject a stale lookup.

Pair files are published atomically as soon as they validate. Restarting the
runner validates and reuses each completed key, then schedules only missing
pairs. Independent pair calls may run concurrently because concurrency changes
only offline batch wall time. It does not divide or reconcile one comparison.

## Compact semantic contract

Nonempty pairs use the previously measured compact decision-vector Compare
contract with `gpt-5.6-sol` reasoning `medium`. Both complete view frames enter
one provider turn. The provider returns positional group assignments, relation
kinds, sparse material comments, and issues. The host validates exactly-once
coverage and reconstructs the typed exhaustive partition before projecting it
to the hidden compact artifact.

This is intentionally different from the minimal-I/O condition. The graph
retains sparse comments and review issues because later Meld, Update, or other
operation adapters may need more than a bare kind vector. It still omits the
large repeated overview, report prose, member objects, and boilerplate that
dominated the original exhaustive JSON response.

The live contract is owned by
`memcommit.study_scenarios.legacy.prewarm.compare_compact`. On 2026-08-27 its schema, prompt,
strict decoder, typed reconstruction, and one-call evidence boundary moved out
of the retired latency A/B runner so Study preparation no longer imports a
private experiment helper. This intermediate ownership cleanup deliberately
retains compact prompt version 1 and the existing provider operation label;
changing the semantic contract or graph preparation policy requires a later,
separately reviewed revision.

## Output cardinality and parent-pair projection

The compact contract permits at most one relation group per input Memory. It
also requires every input Memory to occur exactly once and every declared group
to contain at least one Memory. Therefore a `7:7` Compare can contain at most
14 groups and a `150:150` Compare can contain at most 300 groups. This is a
semantic-cardinality bound, not a guarantee that serialized JSON bytes or
output tokens are shorter than the input prose.

A completed parent pair can be filtered to any left-descendant versus
right-descendant request because both requested membership sets are subsets of
the original two sides. Projection removes memberships outside the requested
views, drops empty groups, converts a group that loses one complete side to
`DISTINCT`, and recomputes coverage. The projected group count therefore cannot
exceed the requested input-Memory count.

Lexical depth is not the projection criterion. Two views at the same level but
under the same parent side cannot be compared from a parent-left versus
parent-right artifact, because that artifact contains no relation judgment
between Memories that both occupied its left side. Such a pair needs its own
semantic comparison or a separate internal multi-frame relation contract.

Projection preserves a valid exhaustive shape but is not a fresh semantic
judgment. A parent partition can hide a secondary relationship that becomes
salient in a smaller frame, and an `N:M` group can narrow differently after
filtering. Every such result must therefore be labeled
`PROJECTED_FROM_PARENT_PAIR`; a later fresh audit may replace it without
blocking the foreground interaction.

The retained Task 2 graph provides a useful size comparison for Sol medium's
compact contract. Ten completed `7:7` calls had a 16.831-second median,
19.245-second mean, and 10.757--40.489-second range; eight of ten completed
within 30 seconds. The one completed advisor-root `150:150` call took 196.403
seconds. These calls ran in the same four-worker offline campaign, so the ratio
is not an isolated causal benchmark, but the approximately 11.7x median
difference is large enough to reject the assumption that input cardinality is
irrelevant. The `7:7` calls produced 4--14 groups, while the root pair produced
138. Within the small calls, fewer groups did not consistently mean lower
latency, so relation count alone does not explain the timing.

## Deletion projection

A deletion does not automatically issue a provider call. The deterministic
projection:

1. removes every deleted Memory membership;
2. drops empty relation groups;
3. changes a cross-source group that loses one complete side to DISTINCT;
4. removes issue references to dropped groups and drops an issue with no
   surviving group;
5. recomputes coverage; and
6. labels the artifact `PROJECTED_FROM_PREWARM`.

The label is an invariant. Projection is useful for immediate interaction and
invalidation bookkeeping, but it is not represented as a fresh complete
semantic reanalysis. The earlier 75:150 audit showed that shape repair alone
can differ substantially from a new provider judgment. Improving semantic
equivalence after large deletion is a later NLP research opportunity rather
than a present qualitative-study acceptance gate.

## Addition and other invalidation

Adding or editing a Memory can create new relations and change existing
groups. Changing the task description, model, reasoning effort, ruleset,
compact prompt, or descendant membership likewise changes the interpretation
contract. Any of these changes misses the exact key and schedules a new whole-
view pair calculation. The old artifact may remain historical evidence but
must not be returned as exact.

The study fixture is fixed, so additions should not occur on the normal
measured path. Supporting them remains important for implementation integrity
and later deployments.

## Operation transfer boundary

The graph bundle contains Compare decisions only. Its ordered deletion-proof
is now reused by operation-specific adapters, but never as action authority by
itself. Symmetric Meld may durably install a validated projected Compare as its
prerequisite. Directional Meld and Update additionally project their own
ordered action payloads and re-run owner and completeness validation. Sever
projects its own candidate/support ledger. Forget retains live whole-frame
semantics and has no declared Study cache. A cached Compare relation still does
not by itself authorize or reconstruct another operation's actions.

## Limitations

- The current sidecar is hidden preparation evidence and does not yet replace
  the production Compare store or install itself into a participant report
  adapter.
- Storing all fixed pairs moves latency out of the foreground but increases
  total provider work. The experiment records both provider-seconds and batch
  wall time rather than presenting precomputation as free.
- Pairwise stochastic decisions can disagree where overlapping views describe
  the same material. The bundle preserves pair authority and does not force
  every result into one falsely canonical global partition.
- The graph is task-local by construction. Similar content in two different
  tasks is never used for cross-task reuse.
- Semantic quality relative to expert-reviewed judgments is not established by
  cache completeness. That evaluation belongs to later NLP work and paper
  Discussion, separate from the current HCI contribution.
