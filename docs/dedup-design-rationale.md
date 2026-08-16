# Deterministic Dedup application boundary

## Status

`mem dedup` is implemented as a provider-free operation across CLI, TUI,
public Python, agent, and MCP projections. It consumes typed
`find-duplicates` receipts, constructs connected components from confirmed
positive equivalence edges, collects exactly one existing survivor UID per
component, and applies the complete deletion set in one checkpoint.

The quality finder remains read-only. Selecting `CONFIRM LINK` is process-local
review state until the person activates the `DEDUP` To Do row. That activation
submits a typed batch; it does not itself authorize or perform deletion.

## Motivating scenario

Task 1 can legitimately use this visible pipeline:

```text
merge
  -> find-duplicates
  -> confirm eligible duplicate links
  -> dedup
  -> continue conflict/ambiguity review
```

This does not make Merge semantic. Merge still owns deterministic structural
collision handling. The later finder supplies duplicate evidence over the
merged result, and Dedup owns the separate survivor/deletion decision.

## Typed contract

```text
QualityFindingHandoff[DUPLICATE, DEDUP]...
  -> DedupRequest
  -> fresh source/Grant validation
  -> FrozenDedupPlan(components, revision)
  -> ResolutionCase(one required survivor choice per component)
  -> DedupSelection...
  -> exact whole-set review
  -> atomic Apply + DedupReceipt
```

Only `EXACT`, `SURFACE_EQUIVALENT`, and `SEMANTIC_EQUIVALENT` edges are
eligible. `OVERLAP`, `UNKNOWN`, and `DISTINCT` cannot enter a Dedup plan.
Duplicate edges must name two directly owned Memories in one exact frozen
Context. Connected components use all eligible confirmed edges, including
transitive links. Finder edge order does not choose the survivor.

The deterministic recommendation is the first component member in the
Context's existing direct-item order. It is a proposal, not automatic Apply.
The reviewer may choose any existing member of that exact component.

## Invariants

- Keep exactly one existing stable UID per connected component.
- Keep the survivor's wording byte-for-byte unchanged.
- Name and remove every other component member UID.
- Leave unrelated direct items and their relative order unchanged.
- Bind the plan to the complete Context record digest, direct-Memory finder
  digest, Context UID, public display name, handoff identities, and component
  identities.
- Reject stale Source or revision replay before mutation.
- Require every component decision through the shared Resolution validator.
- Scan the direct Context graph for inbound `MemoryRef` values while holding
  the same command lock used for deletion and checkpoint publication.
- Publish all component deletions in one checkpoint or publish nothing.

The receiver deliberately ignores `QualityFindingReviewDraft`. Review state
becomes executable input only when its adapter explicitly selects eligible
confirmed handoffs and constructs `DedupRequest`. A crafted handoff still gains
no mutation authority: Dedup resolves and revalidates the Source and Grant.

## Authority and Grant boundary

Ordinary local ownership needs no Grant. A granted target requires
`READ + DERIVE + DELETE` before the plan is shown and again through Apply.
Revocation or any Grant-binding change invalidates the frozen plan. Explicit
root Python clients do not inherit host Profile Grants.

Dedup V1 exposes only deletion of absorbed duplicates. It has no CREATE,
UPDATE, canonical rewrite, or information-integration capability to grant or
deny. Those effects belong to Normalize, Meld, Update, or Fit Resolve and must
use their own operation contracts.

## TUI and adapter boundary

Dedup uses the same visible deterministic Resolution Session topology as Merge
and Fit Resolve:

```text
VIEWER -> conditional RESPONSES -> ITEMS -> TO DO -> exact final review
```

The shared shell owns focus, selection markers, frame order, back navigation,
and exact approval mechanics. The Dedup adapter owns component evidence,
existing-survivor choices, exact argv, receipt wording, and application calls.

Find quality sessions use the compatible shared topology but retain their own
process-local response model. `SessionPicker` is intentionally absent because
Dedup plans are one-shot process-local artifacts, not durable resumable
sessions. Trace and Rationale may reuse read-only Viewer/navigation mechanics;
they do not acquire Responses, mutation decisions, or Dedup persistence.

CLI exact replay repeats every canonical finding handoff and supplies one
`--survivor COMPONENT=MEMORY` per component plus `--expected-revision` and
`--apply`. Python keeps the typed frozen plan object. The agent/MCP adapter
reconstructs the plan from handoffs and requires the reviewed opaque revision
and survivor array before Apply. All routes converge on `prepare_dedup()` and
`apply_dedup()`.

## Rejected alternatives

- **Merge and then silently collapse duplicates:** rejected because structural
  combination does not prove semantic substitutability and would hide a
  deletion inside another operation's checkpoint.
- **Rewrite a canonical combined Memory:** rejected because equivalence does
  not authorize wording changes, and `OVERLAP` may contain unique facts.
- **Let finder drafts mutate directly:** rejected because inspection and
  mutation require separate authority, freshness, and exact-approval checks.
- **Pick the shortest or model-preferred wording:** rejected because that adds
  a semantic authoring policy to a deterministic deletion operation.
- **Persist an implicit finding cache:** rejected for V1. Exact receipts and
  revision replay keep the boundary visible without a new sensitive session
  artifact.

## Intentional limitations

- Inbound references block the entire V1 Apply. Safe reference migration is
  not silently inferred and remains future operation-owned work.
- Cross-Context duplicate groups are rejected. Moving or coalescing ownership
  is a different multi-Context operation.
- A free-form finder response is retained as review context only; it cannot
  create a new Dedup relation or survivor choice.
- Dedup does not establish truth, provenance quality, or Fit. It trusts only
  the eligible confirmed relation receipts as deletion candidates and retains
  the reviewer's exact survivor decision.
