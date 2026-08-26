# Resolve application-boundary matrix

Last reviewed: 2026-08-25.

## Status

`CLOSED` for the current direct-Memory, one-Context route. The exact semantic
policy remains explicitly empirical: changing a rule or canonical output must
version and update the authored corpus, prompt projection, verifier, tests, and
this matrix together.

## Operation shape

```text
complete frozen Memory frame + target Fit MAY|YES
                         |
                         v
initial whole-frame Fit YES|MAY|NO
                         |
                         v
all exact rules + all canonical/known-wrong cases
                         |
                         v
one exact plan or non-interactive STOP
                         |
                         v
independent rule/grounding/information verifier
                         |
                         v
complete exact post-image Fit
                         |
           +-------------+-------------+
           |                           |
    target reached                 target missed
           |                           |
   one atomic checkpoint          no publication
```

The sole authored rule and exact-case source is
`memcommit/eval/fixtures/resolve.json`. `memcommit.resolve_rules` validates it
with duplicate-key rejection, derives every expected post-image from its exact
effects, and projects every rule, canonical case, and known-wrong result into
both production semantic prompts. This matrix records ownership and coverage;
it does not become a second source for exact strings.

## Package ownership

The canonical terminal-independent owners now live together under
`memcommit.operations.resolve`. `application.py` owns requests, frozen frames,
semantic outcomes, exact-plan validation, and Apply orchestration;
`runtime.py` owns Store, Grant, freshness, checkpoint, and atomic mutation
adapters. API, CLI, quality-finding handoff, Impact, targeting, semantic, and
TUI consumers import those operation-owned modules directly.

The historical `memcommit.resolve_application` and
`memcommit.resolve_runtime` paths remain behavior-free module-identity aliases
for import-order, monkeypatch, and serialized-global compatibility. Importing
the package alone does not eagerly load either implementation module. New
production code must use the operation paths; the aliases are compatibility
boundaries, not secondary owners.

This relocation changes physical ownership only. It does not change the rule
corpus, whole-frame Fit and planning calls, requested-effect authority,
freshness or CAS behavior, apply-first policy, checkpoint evidence, receipts,
or terminal interaction. Consequently the existing ordered PTY evidence
remains valid and no screenshot refresh is required.

## Rule matrix

| Rule | Boundary | Required behavior | Host enforcement |
| --- | --- | --- | --- |
| `R01_WHOLE_FRAME` | freeze, planner, verifier, post-Fit | Issue focus and mutable selection never shrink the semantic read frame | every semantic stage receives the complete frozen direct-Memory frame |
| `R02_DEFAULT_REMOVE_NO` | request and acceptance | default Resolve may finish at resolution level MAY or YES | `ResolveRequest.target_fit=MAY`; a grounded MAY-level candidate may publish after compatible post-Fit |
| `R03_STRICT_YES` | request and acceptance | `--yes` requires resolution level YES and an independently judged YES post-image | target participates in the frozen revision; MAY-level candidates do not publish even when their explicit alternative relation is jointly compatible |
| `R04_EXACT_GROUNDING` | planner and verifier | supplied scope, time, exception, identity, or transition produces the smallest exact edit | verifier rejects imported facts; post-Fit checks the exact post-image |
| `R05_SAFE_ALTERNATIVE` | planner and verifier | safe descriptive alternatives use one local relation-bearing edit before two MAY weakenings or a meta-summary | every exact and known-wrong calibration case is present in both prompts |
| `R06_NO_INVENTED_DISCRIMINATOR` | planner and verifier | no fabricated weekday, location, audience, cause, or precedence | unsupported discriminators fail grounding or remain explicit assumptions and cannot Apply |
| `R07_NO_ARBITRARY_PRIORITY` | planner and verifier | order, UID, wording length, or edit convenience never chooses a winner | whole-frame evidence and exact source citations are required |
| `R08_STOP_CONSEQUENTIAL_CHOICE` | planner and verifier | mutually exclusive directives, recipients, permissions, amounts, and destructive targets remain unchanged | planner returns zero plans; host publishes no effects or checkpoint |
| `R09_PRESERVE_UNAFFECTED` | verifier and Apply | unrelated Memories and qualifiers remain byte-for-byte unchanged | exact sparse effects plus Context pre-image CAS |
| `R10_NO_DELETE_FOR_FIT` | planner, verifier, Apply | easier Fit alone never justifies deletion | prompt prohibition, deletion review, capability projection, and inbound-reference gate |
| `R11_EXACT_POSTCHECK` | semantic acceptance and Apply | the complete exact post-image must meet the requested target before publication | MAY/YES target filter, candidate digest, revision check, and one atomic checkpoint |

## Canonical exact-case matrix

The table is intentionally compact. The JSON corpus owns every exact Source,
before, after, ordered result, rule list, rationale, and known-wrong result.

| Case | Exact mutation outcome | Expected boundary |
| --- | --- | --- |
| `opening-time-safe-alternative` | keep `The office opens at 8.`; UPDATE `The office opens at 9.` to `The office opens at 9 as an alternative to opening at 8.` | `SAFE_ALTERNATIVE`, resolution MAY, post-Fit MAY or YES |
| `opening-time-exact-schedule` | UPDATE the two short records to `8 on weekdays` and `9 on weekends`; keep the authoritative schedule unchanged | `EXACT_GROUNDING`, post-Fit YES |
| `opening-time-alternative-with-holiday` | make the same one-record alternative edit; keep `The office is closed on public holidays.` unchanged | `SAFE_ALTERNATIVE`, resolution MAY, post-Fit MAY or YES |
| `payment-account-choice-stops` | keep exact account A and account B directives; no effects | `CHOICE_REQUIRED`, STOP at NO |
| `retention-directive-choice-stops` | keep exact 30-day retain and 7-day delete directives; no effects | `CHOICE_REQUIRED`, STOP at NO |
| `opening-time-explicit-transition` | UPDATE `The office opens at 9.` to `Before September 1, the office opened at 9.`; keep the effective-date transition | `EXACT_GROUNDING`, post-Fit YES |
| `already-exact-scopes` | preserve both exact weekday/weekend Memories | `ALREADY_ACCEPTABLE`, unchanged YES |

## Application ownership matrix

| Concern | Application owner | Invariant |
| --- | --- | --- |
| Exact rules and cases | `memcommit.resolve_rules` plus `memcommit/eval/fixtures/resolve.json` | one versioned source is shared by production prompts and regression tests; all cases enter the prompt |
| CLI target normalization | `memcommit.resolve_targeting` composed from `memcommit.context_targeting` | mixed Context, UUID-shaped Memory, qualified Memory, `--context`, and `--memory` forms produce exactly one canonical Context and an optional exact mutable set before provider construction; bare Memory owner discovery is local-only |
| Request target | `ResolveRequest.target_fit` | MAY is the default resolution floor; YES is a separately frozen strict resolution target |
| Source freeze | `MemoryStoreResolvePort.freeze` | complete direct frame, exact mutable UID set, authority, digest, and target-bound revision precede provider connection |
| Initial judgment | `fit_judgment` through `ProviderResolveSemanticPort` | the complete frame is judged once; initial MAY is still eligible for an exact YES improvement |
| Planning | `_generation_prompt` | exactly one recommended exact effect plan or one non-interactive stop reason |
| Decode | `_decode_candidates` | strict schema, aliases, effect capabilities, mutable targets, issue membership, and exact source citations |
| Verification | `_verify_candidates` | complete rules/cases, original frame, Issue ledger, and effects are independently checked; safe descriptive OR is distinct from unsafe actionable OR |
| Post-image | `_post_image` plus `fit_judgment` | no truncation or partial frame; the post-image must be jointly compatible, while the separate resolution level records whether applicability remains an alternative |
| Apply | `apply_resolve` plus `MemoryStoreResolvePort.apply` | only one grounded target-reaching candidate crosses CAS and writes one checkpoint |
| Presentation | CLI/TUI/public/agent adapters | target and exact Fit verdict are projected without becoming semantic owners |

## Regression and evaluation boundary

- Structural tests fail when the corpus schema, exact effects, or derived
  ordered result drift.
- Prompt tests require the planner and verifier to receive every authored rule,
  canonical case, and known-wrong result, not a hand-selected subset.
- Deterministic providers test host acceptance for MAY versus strict YES,
  authority, stale state, and atomic Apply.
- Command-entry tests cover positional Contexts, globally unique bare Memory
  owners, qualified and explicit Memory forms, canonical Context collapse,
  cross-Context rejection, and resolved-Memory duplicate rejection before a
  provider can connect.
- Configured-provider trials are calibration evidence because the same cases
  are in the prompt. Independent accuracy claims require a separately authored
  held-out corpus that is never projected into production prompts.
- Exact comparison is intentional. A semantically plausible paraphrase first
  fails; a person then changes the canonical output or adds a separately
  reviewed variant rather than letting a second model grade equivalence.

## Current non-goals

- This ownership relocation does not consolidate `resolve_rules`,
  `resolve_semantic`, or `resolve_targeting` into the package. They remain
  separately reusable policy and adapter modules with canonical dependencies
  directed toward the operation application contract.
- The first rule corpus does not claim exhaustive natural-language coverage.
- Resolve still materializes primitive CREATE/UPDATE/DELETE effects; it does
  not add a new durable relation object in this iteration.
- Guidance-grounded legacy DELETE remains a compatibility surface, but none of
  the canonical ordinary Resolve cases uses it. Removing that surface requires
  a separate public/agent compatibility migration.
- A STOP result is terminal and non-interactive. Later Memories may make a
  future Resolve exact; the current turn does not ask the person to choose.
