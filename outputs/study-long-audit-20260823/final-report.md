# Six-world user audit report

Status: **provisional while collection continues**. This document becomes final
only after the strict verifier proves 1,980/1,980 attempts and all six world
issue ledgers have been integrated.

## Verified progress

- Fixed Study: `study-long-audit-20260823`
- Fixed public catalog: 66 operations
- Contract: 6 worlds x 66 operations x 5 materially different methods = 1,980
  actual attempts
- Strictly verified at this checkpoint: **1,350/1,980 attempts**
- Verified operation-world units: **270/396**
- Complete: all six core phases and all six transform phases
- Pending: 21-operation admin phase for all six worlds

The verifier checks exact phase membership and counts, attempt IDs, required
evidence fields, five-method signature uniqueness, frozen-launcher use, and
both missing and excess attempts. A passing aggregate count alone is not
accepted as completion.

## Preliminary outcome

The higher-value findings came from treating each operation as part of a user
goal and chaining its real output into later work. The campaign did not stop at
flag grammar or isolated command success. It accumulated state, exercised
recovery, ran actual 180x52 color TUI routes, and allowed independent worlds to
overlap where the product claimed their explicit Context targets were enough.

That method has already exposed five defect classes that ordinary command-level
debugging would probably miss:

1. **Wrong goal state can be consumed successfully.** Query can answer from the
   wrong readable source, and Update/Diff can consume another parallel world's
   saved operation state.
2. **A successful result is often not a reusable handoff.** Merge, Chunk,
   Checkpoint, Review, and Dedun receipts omit identity mappings or print
   identifiers rejected by the next documented consumer.
3. **Semantic confidence can preserve or manufacture unsafe content.** Elaborate
   introduced unsupported facts, while positive Fit/Resolve outcomes sometimes
   left explicitly challenged healthcare claims or visibly incomplete ticker
   fragments unchanged.
4. **Complete output is not the same as a usable decision.** Whole-Profile
   discovery, recursive quality reports, Audit, Impact, Trace, and TUI viewers
   can serialize the entire evidence frame while burying the one action the user
   must decide.
5. **Semantic decomposition can change the user's rule.** Atomize classified
   the same unchanged Memory differently by scope and applied a child that
   detached a protected word from its document-title trigger; Chunk showed the
   same broader user-level risk across all six worlds.

## Provisional priority order

### P1: correctness, isolation, and destructive-intent risk

- `CF-12` -- implicit saved-operation state bleeds across parallel worlds.
- `CF-01` -- an explicitly named granted Query target is not authoritative.
- `CF-02` -- readable EXPORT grants do not support selective provenance-safe
  handoff.
- `CF-14` -- generated examples can become asserted facts and survive later
  semantic review.
- `CF-15` -- natural-language Forget can remove the rule the user meant to
  preserve.
- `CF-10` -- positive Conformance/Fit/Resolve is not auditable proof that
  challenged content was transformed, repaired, or safe.
- `CF-11` -- opaque semantic prewarm failures make central transform routes
  unusable.
- `CF-03` -- Chunk can separate safety conditions from facts and gives no direct
  created-UID handoff.
- `CF-16` -- Atomize can change atom identity with scope and apply a child that
  loses the source trigger/exception boundary.

P1 candidates that remain deliberately unconfirmed are `CF-17` (a missing
Impact endpoint defaulted to shared current) and `CF-18` (an applied Atomize
event disappeared from later Diff/Review surfaces). Each has strong
practice-source evidence but only one underlying route/event so far.

### P2: workflow integrity, reuse, and operator cost

- `CF-13` -- successful receipts omit or advertise unusable identities.
- `CF-06` -- exhaustive recursive and saved-analysis reports scale as output,
  not decisions.
- `CF-09` -- broad-looking quality routes judge narrower isolated frames than
  their presentation implies.
- `CF-05` -- sibling quality operations do not share a learnable scope grammar.
- `CF-04` -- whole-Profile Context discovery repeatedly hides the active world.
- `CF-07` -- current-only orientation conflicts with parallel goal work.
- `CF-08` -- semantic output can silently change the working language.
- `CF-19` -- a stale proposal with zero current Source coverage still advertises
  Apply (single-route candidate).

The canonical descriptions, affected worlds, consequences, workarounds, and
evidence IDs remain in [`common-findings.md`](common-findings.md); this report
does not replace that evidence ledger.

## Decision boundary

The agent can continue automatically when work is read-only, targets an exact
local scratch Context, has a verified checkpoint/recovery route, or collects a
failure without publishing partial state. It should pause when an operation
would:

- transfer or share content outside the participant Profile;
- decide whether unsupported/generated content is factually acceptable;
- choose between equally plausible goal meanings;
- publish a destructive semantic disposition whose reviewed per-Memory mapping
  differs from the user's stated preservation rule;
- replace a stale global stage when ownership of that stage is not proven.

The detailed matrix of agent default actions, exact pause conditions, and UI
affordances is being maintained separately in
[`decision-boundary-matrix.md`](decision-boundary-matrix.md) while collection
completes.

## Automation architecture

The next campaign should use two complementary lanes:

1. six isolated Profile Stores, one per goal world, for fast complete coverage;
2. a smaller shared-Profile concurrency lane for Update/Diff/Review, current,
   Undo/Redo, Profile/provider, session ownership, and disjoint command commits.

Pure isolation would improve speed but hide the saved-state bleed found here.
The required process-pinned Profile/Store execution boundary and migration
reasoning are specified in
[`runner-isolation-analysis.md`](runner-isolation-analysis.md).

## Remaining proof before completion

- execute all 21 admin operations five ways in all six worlds (630 attempts),
  serializing only the genuinely global transaction windows;
- update provisional cross-world patterns with the admin evidence;
- verify every phase ledger and exact total 1,980/1,980;
- inspect each required evidence/decision/report artifact before marking the
  long-running goal complete.
