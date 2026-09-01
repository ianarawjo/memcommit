# Operation-neutral Resolution lifecycle

> **Authorization contract updated 2026-08-30.** Permission claims below that use `EMBED`, `DERIVE`, `COMBINE`, `EXPORT`, `ACCEPT_DERIVED`, or `SAVE_*` describe the retired contract preserved for design history. The current contract uses `QUERY`, `CREATE`, `READ`, `UPDATE`, and `DELETE`; `READ` covers readable semantic use and Embed traversal, while `SHARE` remains a separate endpoint capability. See `granted-derived-ownership-design-rationale.md`.

## Status

The first application-level Resolution contract is implemented.  The shared
contract binds a complete set of required or optional items to one frozen
operation artifact revision, validates exact item and choice identities,
rejects duplicate or capability-crossing submissions, preserves frozen item
order, and reports whether required work remains. Structural Merge, saved Meld
issue turns, public Fit-repair Resolve, and semantic Dedun are production
consumers.

This is distinct from the shared Resolution Workbench.  The workbench owns
presentation and UID-addressed interaction.  The lifecycle contract owns only
operation-neutral decision validity and readiness.  Neither owns semantic
provider behavior, persistence, or Apply.

Both contracts live under `memcommit.application.capabilities.resolution`: the lifecycle is
shared application policy, while the workbench is its terminal-independent
review projection and action vocabulary. Concrete prompt-toolkit rendering
remains under `memcommit.adapters.interfaces`; moving the package does not move provider,
persistence, or operation-specific Apply authority into the shared contract.

The smaller deterministic Resolution Workbench now retains the exact
`ResolutionCase` it projects. Its item and choice rows must match the case in
the same frozen order, and every individual or bulk outcome re-enters the
common validator before exact review and Apply. This closes the former gap in
which application adapters validated the same identities later, but the TUI
spec itself carried only a parallel visual vocabulary. The larger saved
Resolution Session remains a distinct presentation model because it also
supports optional items, comments, provider-backed turns, and process- or
session-local drafts.

## Motivating problem

Merge, Meld, future Fit repair, Dedun, and clarification can all contain an
unresolved stage, but the condition and legal repair differ:

| Operation | Unsatisfied condition | Operation-owned resolution |
| --- | --- | --- |
| Merge | one or more structural collisions have no legal disposition | exact `KEEP_TARGET` or `TAKE_SOURCE` choices |
| Meld | Source disposition is incomplete or a required issue remains | preservation, coalescing, synthesis, or grounded semantic revision |
| Fit repair | the complete proposition frame is `MAY` or `NO` | a grounded minimum-change candidate independently verified as `YES` |
| Dedun | a confirmed exact-plus-semantic DUN group has no survivor plan | one unchanged existing survivor plus the complete absorbed-UID plan; inbound references are blocked rather than migrated |
| Clarification | one materially ambiguous reading remains ungrounded | an explicit interpretation or scope supplied by evidence or the person |

Calling every operation Fit would erase these distinctions.  Conversely,
letting every operation reimplement item identity, allowed-choice validation,
required coverage, and stable decision order causes the same safety mechanics
to drift.

## Boundary

The common lifecycle is:

```text
frozen operation artifact
  -> operation-owned ResolutionCase projection
  -> exact submissions or an explicit bulk choice
  -> operation-neutral validation and readiness
  -> operation-owned typed plan
  -> separate review and Apply boundary
```

`memcommit.application.capabilities.resolution` imports no operation, Store, provider, CLI, or TUI
module.  It owns:

- `ResolutionBinding(operation, artifact_uid, revision)`;
- ordered `ResolutionRequirement` values with required/optional obligation,
  real choice UIDs, and explicit free-response capability;
- UID-bound `ResolutionSubmission` values collected in one
  revision-bound `ResolutionAttempt`;
- unknown-item, duplicate-item, unavailable-choice, comment-capability, and
  unresolved-required validation; and
- canonical frozen-order `ResolutionProgress`.

The contract intentionally does not own a generic solver callback.  Merge and
Meld now demonstrate real overlap in revision binding, exact item/choice
identity, obligation, and response capability; they also demonstrate that the
solver does *not* overlap.  A wrapper that merely calls an operation function
would add a second apparent lifecycle without enforcing a safety boundary.
Candidate generation, semantic verification, and minimum-change ranking stay
operation-owned until a later pair of implementations demonstrates those
stronger invariants.

## Merge vertical slice

`merge_planning` continues to classify structural collisions and materialize
the selected post-image.  `merge_application` continues to own
`FrozenMergePlan`, `MergeResolution`, completeness, receipt matching, and the
terminal-independent `run_merge` use case.  `merge_runtime` continues to own
authority, freshness, locks, CAS, checkpoints, rollback, and Undo/Redo.

`merge_resolution_case()` projects the public frozen plan into the shared
contract. Its revision digest binds process-local review actions to the frozen
endpoints and complete conflict-decision projection. The opaque runtime token
remains the stronger Apply authority and freshness boundary and is
deliberately excluded from presentation.

`resolve_merge_conflicts()` now delegates exact item/choice/coverage mechanics
to the shared validator and maps structured failures back to the established
Merge error vocabulary.  It still returns only operation-owned
`MergeResolution` values.  It performs no provider call and no mutation.

The plain CLI parser and Merge TUI both consume the same projected requirement
identities, then call the same typed Merge application use case.  The TUI may
invoke that use case through an injected application callback after exact
approval; this is interface composition, not a second mutation implementation.
The deterministic workbench spec retains `merge_resolution_case(plan)` and
rejects any item/choice projection that widens or reorders that case. Its final
UI outcome is canonically revalidated against the same binding before the
callback is invoked.

Merge deliberately uses the compact variant of that workbench. Its initial
surface shows the same two-line `MERGE PLAN` and `CLASSIFICATION` projection as
the plain conflict route, and opening a conflict shows only its stable ID,
Source/Target descriptions, reason, allowed decisions, and real choice rows.
It has no complete-report or conflict-detail Viewer stop: structural Merge
does not generate editable wording or a semantic proposal. Dedun and Fit
Resolve retain their evidence Viewers because selecting a survivor or verified
post-image requires inspecting content that is not represented by a compact
structural classification. Exact whole-set review, Apply revalidation, and the
durable receipt remain unchanged and separate from the compact presentation.

No Merge Python or agent surface is added merely by extracting the common
contract.  If Merge later becomes a public slice, those adapters must call the
same application entry rather than importing CLI or TUI code.

## Meld vertical slice

`meld_resolution_case()` projects the current saved assessment into exact
issue and option UIDs bound to the session's opaque canonical-digest version.
Required issues remain `REQUIRED`; helpful issues are `OPTIONAL`; both accept
an operation-supplied comment. Because Meld dialogue is incremental,
`prepare_meld_resolution_turn()` validates one issue response with
`evaluate_resolution()` but does not require every current required issue to
be answered in the same turn. The provider's next complete assessment remains
the authority for whether required work is actually closed.

The shared validator never sees or creates provider prose. After exact UID
validation, the Meld application layer alone translates a selected option to
`Choose this reading: ...` using the option text from that same frozen
assessment. The TUI and CLI therefore carry exact UIDs across their boundary
instead of converting `UID -> visible index -> text`. Python exposes the same
optional `option_uid` and `expected_version`; the agent requires the version
returned by `open` whenever it submits an option UID. A stale version fails
before provider construction.

Provider/cache execution, complete-assessment replacement, saved-session CAS,
and Apply remain in the existing Meld runtime. This adoption adds no common
provider callback, persistence schema, or Apply route, and changes no visible
terminal flow.

## Public Resolve naming and implementation

The internal noun **Resolution** names the general lifecycle. Public
`mem resolve` is the narrower conflict-decision operation:

```text
complete direct Context
  -> conservative conflict understandings
  -> one CONFIRM, INTENT, or FORCE decision per Issue
  -> process-local Source Context
  -> ordinary Update generates one complete-Target UpdatePlan
  -> detached complete post-image conflict check
  -> Resolve-owned atomic publication
```

The conservative understanding is not proof and never becomes authoritative
without explicit confirmation. A conflict-free post-image is an Apply gate,
not proof of truth.

The former working name `reconcile` bundled ambiguity clarification and
conflict repair too broadly.  Quality surfaces instead route by finding type:

```text
exact or semantic DUN redundancy -> dedun
ambiguity -> clarify
conflict  -> Resolve
```

Quality discovery and Audit remain read-only. Typed semantic evidence creates a
separately authorized, frozen operation request; they do not mutate from the
discovery stage. Conflict-to-Resolve and confirmed-redundancy-to-Dedun are implemented;
clarification remains separate future work.

Resolve projects three operation-authored choices for every Issue. The shared
terminal mechanics retain exact Issue and option UIDs, while Resolve owns
decision completeness and revision binding. Update alone generates exact
mutations from the finalized decision Source. Resolve then repeats authority,
freshness, pre-image, reference, complete-post-image conflict, and checkpoint
checks. The full contract is recorded in
[`resolve-fit-repair-design-rationale.md`](resolve-fit-repair-design-rationale.md).
The TUI does not construct or select a mutation candidate.

## Complete-DUN vertical slice with exact Apply

`DedunRequest` accepts typed single-Context DUN
evidence whose classification is `EXACT`, `SURFACE_EQUIVALENT`, or
`SEMANTIC_EQUIVALENT`; `mem dedup` remains the exact-only shortcut.
The operation creates connected components, projects each component as one
required Resolution item, and makes its existing member UIDs the only legal
choices. Context order supplies the deterministic recommendation; it does not
bypass explicit selection or exact whole-set approval.

The shared lifecycle validates component/choice identity and complete
coverage. Dedun alone owns Source revalidation, Grant
`READ + DERIVE + DELETE`, unchanged-survivor semantics, absorbed-UID
calculation, command locking, inbound-reference blocking, Context CAS, and the
single checkpoint. No provider or generic solver callback is involved. The
full contract is recorded in
[`dedun-design-rationale.md`](dedun-design-rationale.md).
The deterministic workbench projects component and member UIDs directly from
`dedun_resolution_case(plan)` and revalidates the complete outcome before the
Dedun adapter translates it to survivor selections.

## Interface and persistence boundary

- CLI, TUI, public Python, and agent adapters may expose different syntax but
  must call one typed application use case whenever that public surface exists.
- A TUI projection may collect decisions and show exact review; it may not
  decide semantic validity, construct a provider, or implement Store writes.
- An agent adapter must include the operation's opaque revision whenever it
  submits an exact reviewed choice. It does not gain authority from seeing an
  issue; legacy free-form Meld comments may still target the latest loaded
  revision for compatibility.
- Meld retains its saved-session CAS, complete-assessment replacement,
  provider/cache runtime, and four Apply routes. It adopts only the shared
  UID/revision/capability validation and retains incremental readiness meaning.
- Apply consumes an exact operation-owned plan and repeats ordinary authority,
  freshness, and receipt validation.  Resolution never weakens that boundary.

The boundary audit is executable rather than a directory-name convention.
Static dependency tests require the Dedun and Resolve application owners to
remain independent of command, TUI, prompt-toolkit, and Typer modules; require
their plain and TUI presenters plus public Python assembly to import the same
operation owner; and require agent adapters to enter through the public API
without importing either application internals or terminal adapters. Merge has
the same CLI/TUI gate but deliberately has no public or agent adapter yet.

## Intentional limitations

- The deterministic and saved-session Resolution TUI models are not collapsed
  into one semantic model. They now share the frozen case boundary where it is
  applicable, while optional/comment/provider-turn parity remains the
  separately tracked `TUI-03` migration.
- Merge remains provider-free and has no semantic rewrite candidate.
- Dedun reference migration and clarification persistence remain future
  operation-owned work. Typed conflict receipts and semantic redundancy evidence are implemented,
  but Resolve and Dedun deliberately retain different solvers and mutation
  semantics.

## 2026-08-31 lifecycle clarification

Resolution provides exact judgments inside an execution operation; it is not
the post-application Review phase. Merge and Dedun may omit Viewer while
retaining all decision context beside their choices. Resolve requires explicit
Issue decisions, delegates its mutation plan to Update, and applies only after
the detached complete post-image contains no unforced conflict. Terminal
evidence is opened later through the operation receipt's `mem review` route.
