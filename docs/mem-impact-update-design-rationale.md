# Directional `mem impact --to` and `mem update`

`mem impact` now also exposes the unary preview
`mem impact atomize`. That form classifies and proposes splits inside one
Context; it does not target another Context, create an `UpdateSession`, or
write `impact-plan.json`. It saves a separate analysis under the source Context
UID for `mem atomize`, `mem trace`, and `mem rationale`; Context contents and
checkpoints remain unchanged. Its separate evidence and trust boundary is
documented in
[`mem-atomize-design-rationale.md`](mem-atomize-design-rationale.md).
This document specifies only the directional A-to-B form.

## Intent

These commands express a directional semantic operation:

```text
update target Context B from current Context A
```

Context A is verified evidence. Context B is a writable local working target.
This is not a symmetric merge and it is not a command for manually replacing
one Memory by UID.

## Task 1 authority boundary: query-only origin and writable local fork

Task 1 uses two different wiki-bearing objects and must not collapse them into
one Context. The canonical identifiers follow
[`task-1-naming-contract.md`](task-1-naming-contract.md):

| Role | Task 1 example | Authority |
| --- | --- | --- |
| organizational origin | `campus-wiki` | query-only; never an `impact` or `update` mutation target |
| participant fork | `participant/campus-wiki-fork` | writable local Context graph containing only the participant's assigned wiki scope |
| verified change source | `participant/construction-updates` | readable local evidence |

The study setup is assumed to provision the scoped local fork before the
participant begins. The current `mem branch` command does not create it from
the query-only origin. The fork contains a writable snapshot of the wiki
sections for which the participant is responsible, not a readable clone of the
whole organizational wiki. Its scope is selected by responsibility and
authority, not by foreknowledge of the impact result: it must include every
page that could reasonably be affected in the assigned scope, plus relevant
unchanged pages, rather than only the records already known to require edits.
`impact` still has to identify the affected subset. It may also carry a
`QueryContextRef` named `campus-wiki`, allowing questions to be sent to the
opaque organizational origin without copying that origin into ordinary Context
storage.

For the current study simplification, that provisioned fork is assumed to be
the latest approved snapshot of the assigned organizational scope when Task 1
starts, and that remote scope is assumed not to change concurrently during the
task. The query-only adapter cannot verify either condition. A future
publication adapter must replace this assumption with an upstream base revision
and a compare-and-swap or equivalent remote-divergence check.

Fixture review must separately verify that the fork covers the complete
authorized candidate scope. Otherwise a missing affected page would be
indistinguishable from a correct no-change judgment, and Task 1 could not claim
that all affected parts were updated.

This separation makes the mutation boundary explicit:

```text
query campus-wiki when additional organizational context is needed
→ preview verified changes against participant/campus-wiki-fork
→ apply them to participant/campus-wiki-fork
→ inspect the local diff
→ later push or propose that diff to campus-wiki
```

`impact` and `update` therefore target the local fork. A future `push` or PR is
the only operation that may contribute from that fork toward the
organizational origin, and it remains a separate approval and permission
boundary. `update` must never interpret access to a query-only origin as write
authority.

The current prototype does not yet create this fork, persist its upstream
binding, refresh it, or publish it. Its `QueryContextRef` can represent the
opaque origin pointer, but the scoped fork and origin relationship is presently
a Task 1 fixture and future persistence contract. This section records the
intended model; it does not claim that remote collaboration or access control
has been implemented.

This revises the original example workflow: the participant does not
`mem switch campus-wiki` or use the organizational origin as the `--to`
target. The participant may query that origin through its pointer, inspect the
local fork, and run `impact` and `update` against the fork.

## Usage

```bash
mem switch participant/construction-updates
mem impact --to participant/campus-wiki-fork
mem update --to participant/campus-wiki-fork
```

The two impact forms are mutually exclusive:

```text
mem impact --to B       directional update preview
mem impact atomize      unary atomization preview
```

Supplying both `atomize` and `--to`, or supplying neither, is a usage error.
`--context` and `--all` belong only to the unary atomize form.

`impact` plans and previews the edits, additions, and explicitly supported
whole-Memory removals that would make B reflect A. It does not change either
Context. The validated plan is cached locally so an immediately following
`update` can reuse exactly what the participant reviewed.

In a terminal, directional `impact` presents the saved plan through the shared
Resolution Workbench: arrows select a planned change and Enter expands its
exact owner, before/after content, reason, and source-reference digests.
Outside a terminal it prints the deterministic projection. These rows are
labelled `PLANNED CHANGES`, expose no comment or acceptance capability, and do
not claim that the current operations-only provider assessed an exhaustive
unresolved-issue list. `update` uses the same projection for its applied
result while preserving its existing application contract.

The `--to` operand locates an existing Context through the shared Context
locator contract. Bare names remain canonical global names; `.`, `..`,
`./...`, and `../...` resolve lexically against one current-Context snapshot
captured at command start.

The **current implementation** of `update` promotes a matching impact plan to
a staged intent and then materializes its validated edits, additions, and
constrained removals in B. It changes only directly owned `Memory` values in
the writable local fork. `MemoryRef`, `QueryContextRef`, embedded-Context
pointers, the verified source, and the query-only organizational origin remain
unchanged. Repository terminology reserves `delete` for a whole Context, so
removing one target Memory is represented as `RemoveOperation`.

A removal is permitted only when readable, verified source evidence explicitly
states that the entire standalone target Memory is obsolete and should no
longer be represented. Absence from the source never authorizes removal. If a
target Memory mixes obsolete and still-valid facts, the planner must emit an
edit that preserves the valid facts instead. Every removal carries source
references, a reason, and the target's locally captured `old_content`; the
provider selects a supplied target ID but cannot author that old-content
snapshot. The same target cannot be both edited and removed.

This deliberately narrow contract supports the compact Task 1 case without
turning update into general-purpose semantic deletion. A real ambiguity such
as “remove this listing or retain it as a cancellation notice” must block the
plan and enter the future issue-scoped directional Meld path described below.

Before the first write, application reloads the complete recorded A/B graph,
checks its identities and fingerprints, validates every operation and old
content value, and prepares detached post-images for all affected direct owner
Contexts. It then holds the active-update lock and all recorded Context write
locks, saves one post-image per affected owner, and creates one automatic
checkpoint per affected owner. Every checkpoint carries the same update
session UID and ordered-operation digest. Only after all owners have been
saved does the active record become `applied` and receive the result
fingerprints and checkpoint receipts.

`mem diff` renders the captured baseline-to-result operations deterministically
after application. It does not recompute a model result or compare arbitrary
Contexts. Publication still requires a later `push` or PR.

If the cached impact plan is stale because A or B changed, `update` plans again
instead of promoting stale operations. Running `update` repeatedly with the
same A and applied B is idempotent: it recognizes the result receipt and
neither reconnects to the provider nor creates another checkpoint. A
different, stale, or diverged active update record is preserved unless the
participant explicitly supplies `--replace-stage`.

An ordinary exception during a multi-owner write restores every owner already
written and removes the checkpoints created by that attempt, leaving the
staged record available for inspection or retry. Per-file writes are atomic,
but there is not yet a durable transaction journal. A process or machine crash
between owner writes can therefore leave a partial local application. This is
an explicit prototype limitation to resolve before remote publication.

## Task 1 resolution boundary and incomplete general path

Task 1 stipulates that Context A contains already verified local memory. Its
directional impact is expected to be reasonable and conflict-free, so the
participant path does not open a clarification or reconciliation dialogue:

```text
verified local A
→ impact preview against writable local fork B
→ optional provenance review
→ update applies B locally
→ diff of fork baseline versus local result
→ future contribution to query-only organizational origin
```

This is an intentional **Task 1 scenario boundary**, not a general invariant
of semantic updates. Introducing an artificial ambiguity or conflict into this
study path could change participant trust independently of the intended
questions about provenance, responsibility, and review behavior.

The absence of a general update-resolution adapter is nevertheless an
**incomplete prototype boundary and explicit TODO**. The current
`UpdateSession` has no named-Ground binding, Goal–Rules–Cases ledger,
unresolved-issue state, or directional-Meld turns. It cannot suspend staging
for a human grounding round, promote an accepted clarification explicitly, or
recompute a complete proposal from that turn.

A future adapter should stop on a required ambiguity, conflict, placement
question, or missing scope; bind the update to an exact Ground revision; use an
issue-scoped directional Meld to incorporate the person's resolution; and
recompute the complete bounded plan before staging. That future contract is
recorded in
[`cross-operation-grounding-design-rationale.md`](cross-operation-grounding-design-rationale.md).
It is documented design work, not behavior advertised by the current command.

The same missing state currently prevents Update from adopting the exhaustive
common semantic-result workbench defined in
[`semantic-result-workbench-design-rationale.md`](semantic-result-workbench-design-rationale.md).
An edits/additions/removals plan can explain exact proposed changes, but it cannot
say whether an omitted source was already present, irrelevant, overlooked, or
unresolved. Update must first record exhaustive source disposition,
source-linked understanding and outcome sections, unresolved findings, and
traceable inspection cases. Until then, displaying “no unresolved finding”
would fabricate evidence rather than reuse a presentation asset honestly.
The separate Resolution Workbench may still display exact planned operations
read-only because it makes no unresolved-completeness claim. That boundary is
defined in
[`semantic-resolution-workbench-design-rationale.md`](semantic-resolution-workbench-design-rationale.md).

## Method

Both commands use one planner:

1. Recursively visit explicitly embedded Contexts in A and the writable local
   fork B.
2. Treat directly owned `Memory` values in B as writable only because B is the
   participant-owned fork; never use the query-only organizational origin as
   B.
3. Treat resolved `MemoryRef` values in A as readable evidence.
4. Never open `QueryContextRef` sources and never edit `MemoryRef` values.
5. Give a temporary Codex process only per-run candidate IDs and visible text.
6. Require strict JSON containing full-content edits, additions, and
   source-backed whole-Memory removals.
7. Map every returned ID back to canonical local objects and reject unknown,
   duplicate, empty, conflicting, or unsupported operations.
8. Generate new Memory UUIDs locally and record source provenance plus source
   and target fingerprints.

An edit preserves the target Memory UID and replaces its string content with a
complete revised version. The planner must preserve unrelated target facts. An
addition receives a new local UUID and names its owning target Context.

## Diff

```bash
mem diff
mem diff --raw
mem diff --stat
mem diff --verbose
```

`diff` makes no model or network call. Its default semantic view uses yellow
operation headings, red deleted text, green added text, dim unchanged lines,
and cyan provenance. It shows collision-safe short UID prefixes and hides
low-level Git headers and terminal-newline markers. `--verbose` shows complete
UIDs and the source/target fingerprints.

`--raw` renders the exact Git-style `---`, `+++`, and `@@` representation,
including additions from `/dev/null`, removals to `/dev/null`, and
terminal-newline markers. `--stat` shows only the edit/addition/removal counts.
Raw and stat modes are mutually exclusive.

Every detailed mode prints each operation's source provenance and reason. The
command does not depend on the currently selected Context and it does not write
Contexts, checkpoints, state, or session files.

Before rendering, the command reloads the recorded A and B Context graphs. For
a staged record it verifies the captured base; for an applied record it
verifies the captured source and the receipt's result fingerprints. If those
identities or planner-visible contents changed, the captured diff is still
shown but marked stale and the command exits with a failure status. A future
push must refuse a stale applied result.

## Local artifacts

```text
~/.mem/impact-plan.json
~/.mem/staged-update.json
```

These files contain canonical operation records, owner Context identities,
applicable old and new content, provenance hashes, and source/target base
fingerprints. The
impact file remains read-only planning evidence. During `update`, the active
file first records the staged intent and, after successful local application,
records status `applied`, the operation digest, applied target fingerprints,
the application time, and one checkpoint receipt per affected owner. An empty
plan has no affected owners or checkpoints but still records an applied result.
Each individual JSON file replacement is atomic.

The automatic checkpoint recorded by the current application transaction is a
post-update checkpoint. It supports audit and repeatability but is not, by
itself, a pre-update restore point for a completed removal. Task 1 provisioning
must retain its local-fork baseline, and a general publication-ready removal
workflow still needs an explicit pre-update recovery contract. Ordinary
in-process application failure already restores the saved owner records,
including a removed Memory and its order.

`mem impact atomize` deliberately neither reads nor overwrites these files.
Its one-shot result is provisional but is cached separately at
`~/.mem/atomize-analyses/<context-uid>.json`. Only `mem atomize` consumes that
artifact for explicit in-place or save-as application; it is not interchangeable
with a directional update plan.

This is a research-prototype trust boundary, not remote collaboration or an
access-control system. A later push implementation must separately verify the
fork's upstream binding, remote base, and publication authority before
contributing anything to `campus-wiki`.
