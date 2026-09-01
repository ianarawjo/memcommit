# Meld Audit–Resolve–Update design rationale

Last reviewed: 2026-08-31.

## Problem

Meld previously treated an exhaustive peer-relation/Compare analysis as its
semantic basis, then maintained its own issue choices, follow-up turns,
preservation action, proposal materializer, and Apply path. That split the same
human decision problem from Resolve and made a saved Compare artifact part of
Meld execution. It also let console, Python, and agent callers expose different
ways to continue the same review.

Meld now has one production lifecycle:

```text
freeze Sources and Target
→ build a deterministic lossless candidate Context
→ acquire the candidate's complete Audit
→ derive Resolve directions for every Audit item
→ collect one complete human decision set
→ run ordinary Update once over the complete candidate
→ materialize the detached post-image
→ run the complete post-image Audit
→ verify every frozen Source claim remains represented
→ apply the exact verified post-image, or retain another Resolve round
```

Compare is not called, reused, refreshed, or accepted as an input to this
production route. Compare remains an independent read-only operation. Persisted
Compare-backed Meld sessions remain parseable and inspectable as historical
evidence, but they cannot continue or Apply; `--restart` is the explicit
migration into the current route.

## Ownership

- `application.operations.meld.model.candidate` owns the lossless candidate,
  the one-to-one Source-claim ledger, and the durable candidate review.
- `application.operations.audit` remains the only owner of duplicate,
  ambiguity, conflict, and whole-set Fit discovery. Meld calls canonical
  `run_resolve`, which reuses an exact stored Audit when present and otherwise
  records a complete new Audit.
- `application.operations.resolve` owns direction generation and the three
  decisions: confirm the proposed understanding, provide a different intent,
  or force continuation while retaining the item as unresolved.
- `application.operations.update` alone proposes mutations. Meld supplies the
  operation goal plus all non-forced finalized decisions as one Source Context
  and passes the complete candidate as the Update Target. There is no Meld
  post-image generator beside Update.
- `application.operations.meld.coverage` owns the independent, exhaustive
  Source-claim-to-post-image check. It is a whole-frame judgment and cannot be
  overridden by Force.
- `runtime.candidate_resolution` owns Target CAS, source revalidation,
  checkpoint evidence, exact post-image projection, and session publication.
- The console reuses Resolve's compact decision workbench with a `MELD` label.
  Python and the agent adapter submit the same complete decision set through
  `resolve_meld`.

## Candidate and Audit identity

The candidate is deterministic for the frozen ordered Source frames, Meld mode,
and Target snapshot. It is not keyed by the transient Meld session UID. An exact
restart therefore reconstructs the same candidate UID and digest and can reuse
the existing Audit. A changed Source, mode, or Target creates a different
candidate identity and requires a new Audit.

Directional candidates place the BASELINE Memories first and then the INCOMING
Memories. Symmetric candidates preserve PEER A/B order. UID collisions are
resolved deterministically without changing content. Every frozen Source Memory
has exactly one durable claim linking its Source frame and Memory identity to
its initial candidate identity.

Audit supplies all configured sections rather than a Meld-specific subset:
duplicates, ambiguities, conflicts, and whole-set Fit, plus conformance whenever
Rules are explicitly supplied by an owning caller. Meld currently supplies no
Rules frame, so its ordinary complete Audit consists of the three finders and
Fit. A clean initial Audit does not bypass Update: the Meld goal still runs once
over the complete candidate and the resulting post-image is independently
audited and coverage-checked before Apply.

## Decision and retry invariants

Resolve never proves a conflict away automatically. Every displayed item needs
exactly one decision before Update. Confirm and Intent become Update Source
evidence; Force is control state only and cannot authorize an unrelated edit.
If the forced Audit key still exists in the post-image, the receipt records it
as unresolved. A forced key that disappears is no longer carried forward.

Any unforced post-image Audit item blocks Apply. Meld stores the complete
post-image, Audit, newly derived directions, and accumulated still-active forced
keys as the next candidate round. This includes issues that did not exist in the
initial candidate. The Target remains unchanged until a round has no unforced
Audit item and exhaustive Source coverage succeeds.

## Console and external-call contract

The console opens Resolve's compact `1 ↔ 2 ↔ 3` decision surface for each Meld
Audit item. `1` confirms the proposed understanding, `2` edits the inline Intent
field, and `3` forces continuation. Prev/Next traverse items and Finalize submits
the complete set. If the initial Audit has no item, the console proceeds directly
through Update and verification to the applied receipt; if verification opens a
new item in a non-interactive call, it returns the new saved review without
publishing the Target.

The current Python and agent lifecycle is Start/Restart, read-only Open, and
`resolve_meld(decisions, expected_version)`. The former comment, preserve,
defer, and separate Apply methods were removed rather than retained as a second
executable grammar. The candidate resolution call performs decisions, Update,
verification, and eligible Apply as one version-bound operation.

## Safety boundaries and current limitations

- Update and both Audits are whole-frame operations; they fail their semantic
  budget rather than silently splitting or truncating the candidate.
- Source coverage names post-image Memory evidence for every frozen claim. A
  missing claim blocks publication even when the post-image Audit is otherwise
  clean or its issues were forced.
- Sources and Target are reloaded and revalidated immediately before Apply.
  Target effects must reproduce the verified post-image exactly.
- Candidate Meld currently accepts direct local Contexts, direct Memory focus,
  and inline INCOMING text. Descendant-scoped placement and granted Targets are
  rejected before provider work because a flat whole-candidate Update does not
  yet carry a safe owner-placement proof for synthesized Memories. This is an
  explicit limitation, not silent flattening or a fallback to the old route.
- Target checkpoint publication still physically precedes the final session
  receipt write. Both now share one command/source/target lock scope, and any
  process exception rolls the Context record, checkpoint, and session back to
  their exact prior bytes. A durable crash in that narrow interval still needs
  candidate-specific reconstruction. Existing legacy recovery code is not used
  as a fallback because it proves a different change-set contract.

The intentionally retained legacy model and runtime files exist only to decode
historical sessions and checkpoints. New production preparation, resolution,
console, Python, and agent routes do not call their relation analysis,
proposal-turn, preservation, or Apply services.
