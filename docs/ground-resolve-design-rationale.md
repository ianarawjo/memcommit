# Ground Resolve design rationale

## Problem

Ground Fit, Distill, and Elaborate are intentionally read-only. Fit publishes
an immutable Ground-revision-bound judgment, Distill proposes Rules bound to
the complete included Example frame, and Elaborate suggests possible Rules or
Examples without evidence. The named Ground dialogue can already issue a
reviewed deterministic command, but no common boundary connects those exact
semantic artifacts to that command path.

Without such a boundary, an adapter can accidentally treat a displayed result
as accepted, use a stale result after another Ground turn, erase the difference
between cited evidence and an unverified suggestion, or bundle several model
recommendations into one opaque mutation.

## Decision

Resolve is a planning boundary, not another semantic operation and not an
approval action. It consumes exactly one artifact tied to one exact Ground
UID, name, revision, and record digest, then projects at most one existing
deterministic Ground action. Creating a `GroundResolutionPlan` has no durable
side effect.

The initial source contracts are:

| Source | Source verification | Permitted initial projection |
| --- | --- | --- |
| Ground Distill result | `EVIDENCE_BOUND` | one exact cited Rule becomes one still-proposed Rule |
| Ground Elaborate result | `UNVERIFIED` | one exact Rule or Example suggestion becomes one still-proposed item |
| current Ground Fit receipt | `REVISION_BOUND_JUDGMENT` | one deliberate response to one non-FIT Example |

Fit responses may revise the Goal, refine one cited Rule, refine the judged
Example, change that Example's USE state, or explicitly defer. Replacement
text is not promoted to evidence merely because a Fit receipt motivated it;
it therefore remains `UNVERIFIED` until ordinary Ground review settles it.
A USE change or defer retains the receipt's revision-bound judgment label
because it introduces no new semantic claim.

Resolve plans use the existing Ground action vocabulary. A later application
adapter must render the exact corresponding command, obtain separate approval,
reload the source artifact and Ground, and commit through the existing store
CAS. The approved action creates at most one Ground revision, which naturally
makes older Fit receipts stale.

## Invariants

- One source artifact produces at most one action.
- The Ground UID, canonical name, semantic revision, and complete record digest
  must all still match before a plan can be created or applied.
- A stale Fit receipt cannot be resolved, even when its selected Example still
  exists by UID.
- A `FIT` row has no issue to resolve.
- A Fit Rule refinement may name only a Rule cited by that exact judgment.
- Distill Rule text and evidence identity are projected exactly; Resolve does
  not paraphrase or widen them.
- Elaborate candidates remain visibly `UNVERIFIED` after selection.
- Deferral is an explicit no-mutation plan, not an empty successful edit.
- Resolve cannot accept its own proposed Rule or Example, canonicalize a whole
  Ground, alter a Fit receipt, or mutate a bound Context.

The plan carries its own deterministic digest over the complete source
identity, action, explanation, and verification labels. This digest is an
approval/display identity, not a substitute for revalidating the source
artifact or Ground CAS.

## Alternatives rejected

### Let every semantic operation apply directly

That would give Distill and Elaborate different mutation semantics and would
turn Fit from an auditable receipt into an editing side effect. It would also
make exact Ground review depend on which analysis screen happened to be open.

### Feed every result into an unrestricted chat turn

Natural-language orchestration remains useful for proposing a response, but a
chat transcript is not an exact artifact identity. The typed source and
one-action plan must exist beneath any conversational adapter so a stale result
or uncited Rule cannot be smuggled into application.

### Apply all selected candidates as a batch

The ticker exercise deliberately exposes dependencies: one accepted Rule can
change the Fit status of many prior Examples. Applying several candidates
before rerunning Fit would hide which revision caused the change and would
make rejection or correction less traceable.

## Current boundary and next slice

`memcommit.ground_resolution` owns dependency-light plan values and their
deterministic digest. `memcommit.ground_resolution_application` owns
source-specific projection, local freshness validation, and application, so
importing the value contract does not eagerly assemble Fit storage or the
Ground Distill and Elaborate adapters.

Application rebuilds the plan from the supplied exact source artifact, rejects
a hand-authored or changed action, reloads all bound Contexts, invokes one
existing Ground primitive, and saves with UID/revision/digest CAS plus locked
frame verification. A concurrent Ground turn wins independently and the
Resolve action fails without being partially added. A changed bound Context
also fails before Ground publication. `DEFER` returns a typed non-mutating
receipt and writes no Ground revision.

The stable Python facade exposes the separation directly:

```python
fit = client.fit_ground("ticker-ground")
plan = client.plan_ground_resolution(
    fit,
    example_uid=fit.judgments[0].example_uid,
    action="REFINE_RULE",
    rule_uid=fit.judgments[0].rule_uids[0],
    content="...replacement Rule...",
    rationale="...review reason...",
)
# Reviewing a plan has changed nothing.
receipt = client.apply_ground_resolution(plan)
```

Ground Distill and Elaborate proposals use the same plan/apply pair. Their
public values retain a private process-local exact artifact only when produced
by `distill_ground` or `elaborate_ground`; a standalone proposal has no Ground
identity and is rejected as a Resolve source. Ground Fit additionally supports
reopening an exact receipt UID so an older receipt remains auditable and is
projected as stale after a successful Resolve revision.

The default agent/MCP registry exposes `memcommit_ground_resolve` with four
closed request kinds: `fit_ground`, `plan_candidate`, `plan_fit`, and `apply`.
Ground Distill and Elaborate adapters retain their returned opaque public value
in one shared bounded process-local registry; Ground Fit does the same inside
the Resolve adapter. Planning returns the complete action plus the exact
`apply` request and has effect `NONE`. Applying requires that separately
submitted plan digest and reports either `GROUND_REVISION` or `NONE` for an
explicit defer.

The registry is intentionally process-local, capacity-bounded, and opaque. It
does not serialize hidden application objects or make a semantic proposal
durable. Restart or eviction returns `artifact_expired`/`plan_expired` and the
agent must rerun analysis or planning. Ground and Context freshness checks
remain authoritative even while an item is retained.

The named Ground workbench now composes the same service for current non-FIT
rows. `X` on a selected Example opens one process-local response menu: revise
the Goal, refine any Rule cited by that exact judgment, refine the Example,
change USE, or defer. Edit choices reuse the existing pane-local editor and
then show the existing exact command/effects review. Enter approval invokes
the typed Resolve application in-process; it does not shell out or recreate
planning logic. A successful edit creates one Ground revision and immediately
reprojects the retained Fit receipt as stale.

TUI Defer deliberately remains a process-local acknowledgement because it has
no durable Ground command or state change. It is shown as `NOTHING APPLIED`
and explicitly says it is not durable. The Python and agent boundaries can
still apply a typed `DEFER` plan and receive a no-mutation receipt. Persisting
deferrals would require a separately designed Ground decision rather than a
fake executable command.

Resolve plans are not persisted and the TUI does not call a provider to
suggest a Fit response. The person chooses the affected semantic layer and
authors replacement text; the Fit reason is retained as the default rationale
unless the person supplies a visible inline comment.

The staged ticker benchmark in
[`ground-ticker-iterative-flow-todo.md`](ground-ticker-iterative-flow-todo.md)
is the first end-to-end evaluation. Its four deliberately unsupported cases
must remain unresolved unless a separately reviewed policy is added; Resolve
must never turn provider confidence into fabricated ticker outcomes.

The focused production-TUI evidence is stored under
[`screenshots/mem-ground-fit-resolve-ticker-20260815/`](screenshots/mem-ground-fit-resolve-ticker-20260815/README.md).
