# Meld application boundary matrix

Last reviewed: 2026-08-31.

## Status

`MIXED`: the direct-local candidate route is implemented and shared by console,
Python, and agent callers. Compare is detached from production execution and
legacy sessions are read-only. Descendant placement, granted Target mutation,
and crash recovery between Target and session receipt publication remain
explicitly incomplete.

## Current route

| Stage | Canonical owner | Input | Durable output / boundary |
| --- | --- | --- | --- |
| Start/Restart | `meld.preparation` + `runtime.preparation` | ordered Source names, mode, Target, optional direct Memory focus or inline INCOMING, restart version | exact frozen frames and schema-10 session; rejects relation analysis, descendants, and Grants |
| Candidate | `meld.model.candidate` | frozen frames, mode, Target snapshot | deterministic lossless Context plus one Source claim per frozen Memory |
| Initial analysis | `resolve.run_resolve` over `audit` | complete detached candidate | exact reused-or-new Audit and one proposed direction per Audit item |
| Human decision | `resolve.decisions` | one Confirm, Intent, or Force per displayed item | revision-bound complete decision set |
| Proposal | ordinary `update.plan_update` | complete candidate Target plus Meld goal and non-forced decisions | one validated UpdatePlan and detached complete post-image |
| Verification | `audit.run_quality_audit` + `meld.coverage` | complete post-image and complete frozen claim ledger | blocking Audit keys, active forced keys, exhaustive coverage report |
| Next round | `meld.resolution` + session CAS | unforced post-image issues | saved candidate, Audit, and Resolve directions; no Target write |
| Apply | `runtime.candidate_resolution` | clean/forced Audit, complete coverage, exact Source/Target revalidation | exact ADD/EDIT/REMOVE projection, checkpoint, applied session receipt |

## Public routes

| Caller | Start / Restart | Inspect | Decide, Update, verify, Apply |
| --- | --- | --- | --- |
| Console | `mem meld ...`, `--restart` | saved-session resume and `mem review meld` | Resolve compact workbench; no-issue candidate proceeds directly |
| Python | `start_meld`, `restart_meld` | `open_meld` | `resolve_meld` with the full `MeldDecisionInput` tuple and expected version |
| Agent | `start`, `restart` | `open` | `resolve` with the full decisions array and expected version |

The prior comment, preserve, defer, and separate Apply routes are not current
public operations. CLI compatibility flags fail for candidate sessions rather
than entering old proposal-turn code. Historical Compare-backed sessions can be
opened but must be restarted before execution.

## Compare boundary

The production preparation path neither imports nor calls peer-relation
execution, Compare repositories, Compare prewarms, or a comparison seed.
Candidate session JSON contains `candidate_review` and omits
`comparison_seed`. The legacy `MeldSession` decoder still knows older schemas;
that compatibility does not authorize their execution.

## Required invariants

- Candidate identity depends on frozen semantic inputs, not session identity,
  so an exact restart reuses the exact stored Audit.
- Every initial Source Memory has one and only one Source claim.
- Audit, Resolve directions, decisions, UpdatePlan, post-image, post-image
  Audit, coverage, and Target effects remain revision-bound.
- A clean initial Audit still runs one whole-candidate Update.
- Every displayed item receives one explicit decision. Force does not become
  Update evidence.
- An unforced post-image item opens another round, including a newly introduced
  conflict or ambiguity.
- Source coverage is exhaustive and non-forceable.
- No Target mutation occurs on incomplete decisions, failed Update/Audit,
  missing coverage, stale Source/Target evidence, or a blocking next round.
- Applied receipts report the count of forced items that remain unresolved.

## Verification

- `tests/test_meld_candidate_resolution.py` covers lossless claims, all four
  ordinary Audit calls, exact Audit reuse, one Update, clean Apply, newly opened
  post-image conflict, persistent Force state, missing-coverage no-write,
  applied-session failure rollback, and no-issue console completion.
- `tests/test_resolve_decision_update_flow.py` covers the shared three-choice
  decision semantics and compact workbench.
- `tests/test_meld_public_api.py` and `tests/test_meld_agent_adapter.py` cover the
  shared complete-decision external boundary.
- Ordered PTY evidence lives under
  `agent-records/docs/screenshots/meld-audit-resolve-update-20260831/`.

## Remaining rollout

1. Add an owner-placement contract for descendant-scoped directional
   post-images before re-enabling descendants.
2. Carry that exact placement and effect set through granted Target authority
   and its owner locks before re-enabling Grants.
3. Add candidate-specific checkpoint recovery for the Target-written/session-
   receipt-not-written crash interval.
4. Remove legacy relation/proposal implementation files only after all retained
   historical session and checkpoint readers no longer import them.
