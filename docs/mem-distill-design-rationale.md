# `mem distill` design rationale

## Status

Distill now has one typed application/runtime path shared by plain CLI, the
interactive Context/range setup and semantic Viewer, the public Python client,
the versioned agent tool, MCP projection, and the bound-Ground adapter. Apply
is available only for an exact reviewed standalone proposal and creates one
fresh local Result Context. A persisted hidden-prewarm artifact and a durable
review session are not implemented.

## Meaning and direction

Distill is the evidence-bound upward operation:

```text
Case or Example propositions in a Context --Distill--> reusable Rules
                                     Goal? --focuses relevance only--^
```

The optional Goal cannot support a Rule. Every proposed Rule must cite at
least one Source Memory, and an empty Source fails before provider connection
even when a Goal exists. Top-down proposal generation is owned by Elaborate:
a Goal may suggest Rules, and Rules may suggest Case propositions, but those
outputs remain explicitly unverified.

This separates neighboring operations:

- Summarize produces process-local comprehension.
- Distill proposes evidence-linked abstractions and may materialize reviewed
  Rules into a fresh Result.
- Elaborate proposes top-down hypotheses without claiming evidence or saving
  them.
- Atomize restructures existing meaning and may change its Source after Apply.

## Evidence and provider contract

One request freezes one exact local Context or its lexical/embedded traversal
plus an optional Goal. Every Rule contains standalone content, rationale,
supporting Memory UIDs, and optional boundary/contrast Memory UIDs. Every
Source Memory must be cited by at least one Rule or appear in the analysis-wide
outside set. Within one Rule, support and boundary evidence are disjoint; cited
and outside sets are also disjoint. Aliases are resolved locally, and every
provider response crosses a strict schema and local decoder. The prompt states
both exclusion rules explicitly because a real 50-Example ticker run otherwise
put the same late boundary Example in both evidence lists. The decoder correctly
failed closed, but the provider contract had described only the cited/outside
exclusion. Provider contract version 3 prevents an exact prepared result made
under the weaker instruction from being treated as compatible.

Distill is `WHOLE_FRAME_ONLY`. Relations among any Source propositions can
change the complete Rule set, so an oversized frame is rejected instead of
being silently batched. On an exact prepared miss, this complete-frame plan is
validated before the provider object is constructed. The same reason makes
cache projection unsafe: only an
exact Source frame, Goal, provider contract, and limit snapshot may reuse a
prepared analysis. A subset, ancestor, or descendant projection is a miss or a
fail-closed adapter error, even when a different operation can safely project
its cached result.

The application owns an injectable exact prepared-analysis lookup and reports
`LIVE` or `PREPARED_EXACT`. No persisted Distill prewarm registry is installed
yet, so this is a tested reuse port rather than a claim that ordinary runs
already have a hidden cache artifact.

## Configuration

Behavioral limits live in `DistillSemanticConfig`. Request normalization,
schema limits, response decoding, and prepared-result validation use the same
frozen snapshot. Domain values enforce structural validity; they do not
silently reapply module defaults after a caller injects a different validated
configuration. Provider credentials, endpoint, model, reasoning, and timeout
remain provider-infrastructure concerns.

## Interfaces and interaction

The TUI composes the shared Context-summary workbench with Distill's typed
projection. It supports one Context plus exact/subtree reach, explicitly omits
Summarize's ambiguous `BOTH` mode, performs no provider call until the run
action, and uses the shared semantic Viewer and focused/whole-document `y`/`Y`
clipboard contract. The optional Goal is currently supplied by CLI input; a
dedicated TUI Goal editor is a named remaining boundary.

Ground composition uses the same workbench in caller-frozen mode. It shows the
single bound candidate Context and exact reach for traceability, but removes
them from focus and selection. The adapter also rechecks the submitted request
against the frozen Ground request immediately before execution. This avoids a
misleading screen where a person could appear to retarget Ground Distill while
the application correctly continued to use the bound frame.

The public Python client returns a stable `DistillProposal`; the private frozen
application token remains attached for exact in-process Apply. The agent and
MCP tools expose proposal generation only and report `effect: NONE`; they do
not combine inference and materialization into an unreviewed mutation.

## Ground composition

`mem distill --ground NAME` projects the exact bound Ground Goal and
`WORKING_CANDIDATES` frame into the same `DistillRequest`. Ground UID, revision,
record digest, candidate Context UID, frame digest, item counts, and request are
checked before inference and again before the proposal is returned. Neither
the Ground nor any bound Context is changed.

Ground Distill intentionally rejects Context/range/Goal overrides and
`--save-as`/`--apply`. Promotion into Ground Rules is a separate reviewed
Ground action; a read-only semantic proposal is not acceptance.

## Apply, provenance, and authority

Standalone Apply consumes the exact reviewed proposal, rebuilds the complete
Source, and creates one require-new local Result. Its checkpoint records Source
scope/digest, Goal digest, provider contract, Rule evidence, outside evidence,
and the analysis digest. Source remains unchanged and the Result is one Undo
unit.

The current runtime rejects any granted Source before provider connection.
Visibility or `READ` alone does not authorize derivation or retention. A later
grant adapter must explicitly satisfy `DERIVE`, `EXPORT`, retained-analysis,
target acceptance, and freshness requirements.

## Remaining limits

- no persisted Distill hidden receipt/prewarm installer;
- no safe subset or ancestor cache projection;
- no durable Distill review session or resume path;
- no granted-frame derivation;
- no TUI Goal editor; and
- no agent/MCP Apply tool.
