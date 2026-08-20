# `mem distill` design rationale

## Status

Distill has one typed analysis path shared by CLI, Impact, the public Python
client, the versioned agent tool, MCP projection, and the bound-Ground adapter.
The ordinary standalone route now freezes an existing Target before inference
and atomically adds the complete supported Rule set without an `--apply` gate.
`mem impact distill` owns process-local preview. The former require-new
`--save-as`/`--apply` route remains executable as a compatibility boundary but
is no longer the primary command contract. A persisted hidden-prewarm artifact
and a durable review session are not implemented.

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
- Distill proposes evidence-linked abstractions and adds them to an existing
  Target; explicit Impact previews the exact would-add set.
- Elaborate proposes top-down hypotheses and may store them while retaining
  their suggested, unverified status.
- Atomize restructures existing meaning and may change its Source after Apply.

## Evidence and provider contract

One request freezes one exact local Context or its lexical/embedded traversal
plus an optional Goal. Every Rule contains standalone content, rationale,
supporting Memory UIDs, and optional boundary/contrast Memory UIDs. Every
Source Memory must be cited by at least one Rule or appear in the analysis-wide
outside set. Cited and outside sets are disjoint, aliases are resolved locally,
and every provider response crosses a strict schema and local decoder.

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

## Directional existing-Context publication

Both endpoint options are optional and are resolved from one frozen Current
snapshot:

| Invocation | Source | Target |
| --- | --- | --- |
| `mem distill` | Current | Current |
| `mem distill --to B` | Current | `B` |
| `mem distill --from A` | `A` | Current |
| `mem distill --from A --to B` | `A` | `B` |

The Target must already exist. Distill freezes it before provider construction,
revalidates the complete Source after inference, and publishes all Rules in one
checkpoint only while the exact Source bindings and Target digest still match.
Source and Target may be identical: one digest then protects the shared
pre-image, and the provider never sees output from its own turn. Repeating the
command is intentionally a fresh derivation over the now-larger Context.

`mem impact distill` accepts the same endpoint matrix and prepares the same
exact proposal without writing a Memory or checkpoint. This explicit Impact
route replaces an implicit TTY preview as the ordinary way to inspect before
saving.

## Interfaces and interaction

Direct standalone Add is line-oriented by default and rejects `--tui`; the
Impact route owns interactive read-only inspection. The legacy review route's
TUI composes the shared Context-summary workbench with Distill's typed
projection. It supports one Context plus exact/subtree reach, explicitly omits
Summarize's ambiguous `BOTH` mode, performs no provider call until the run
action, and uses the shared semantic Viewer and focused/whole-document `y`/`Y`
clipboard contract. Its Context surface also composes the common lazy
direct-item preview: `m` shows or hides items only for the focused Context and
`M` does so for every Context in the frozen readable catalog. Preview rows are
read-only viewport stops, never a narrower Distill selection, and opening them
does not call the provider. The optional Goal is currently supplied by CLI
input; a dedicated TUI Goal editor is a named remaining boundary.

Ground composition uses the same workbench in caller-frozen mode. It shows the
single bound candidate Context and exact reach for traceability, but removes
it from selection while retaining read-only focus for evidence inspection. A
Ground Example or workspace route previews the exact frozen `SummaryFrame`
consumed by Distill; the legacy candidate-Context route previews its frozen
binding's directly owned items and later rejects any Context change. The
adapter also rechecks the submitted request against the
frozen Ground request immediately before execution. This avoids a misleading
screen where a person could appear to retarget Ground Distill while the
application correctly continued to use the bound frame.

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

Standalone publication consumes the exact prepared proposal and appends every
Rule to the existing Target as one Undo unit. Its checkpoint records Source and
Target names, Source scope/digest, Goal digest, provider contract, Rule
evidence, outside evidence, analysis digest, and exact result Memory UIDs. A
distinct Source remains unchanged. When Source equals Target, only the new
Rules change it. The compatibility require-new Apply retains its earlier
checkpoint contract.

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
- no agent/MCP mutation tool.
