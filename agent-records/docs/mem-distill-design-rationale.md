# `mem distill` design rationale

## Status

Distill has one typed analysis path shared by CLI, Impact, the public Python
client, the versioned agent tool, MCP projection, and the bound-Ground adapter.
The ordinary standalone route now freezes an existing Target before inference
and atomically adds the complete supported Rule set without an `--apply` gate.
`mem impact distill` owns process-local preview. The former require-new
`--save-as`/`--apply` route remains executable as a compatibility boundary but
is no longer the primary command contract. Its hidden `--save-as` form is
always read-only unless the same invocation includes `--apply`; terminal
interactivity never inserts a second `y/N` decision. A persisted
hidden-prewarm artifact and a durable review session are not implemented.

## Meaning and direction

Distill is the evidence-bound upward operation. `Rule` remains the durable
output lane, but semantically each returned Rule is a parent proposition
relative to the exact child propositions it cites:

```text
child propositions in a Context --Distill--> reusable parent Rules
                              Goal? --selects output contract--^
```

The optional Goal cannot support a Rule. It selects the intended use,
abstraction hierarchy, quantity, exclusions, and modality of the
evidence-supported parent set. Every proposed Rule must still cite at least one
Source Memory, and an empty Source fails before provider connection even when a
Goal exists. Top-down Example generation remains owned by Elaborate: a Goal may
suggest Rules, and Rules may suggest Case propositions, but those outputs
remain explicitly unverified.

When a Goal is present, Distill runs one second, whole-result Goal Fit audit
after the evidence-bound Rule set has been decoded. When no Goal is supplied,
Distill is intentionally a one-provider-turn operation: there is no independent
relevance question to audit, so constructing an empty second judgment would add
latency without adding evidence or safety. The audit asks only whether every
proposed Rule is materially relevant to and compatible with the Goal. It does
not turn Goal text into evidence, require the Goal wording to reappear as a
Rule, or invent a missing Rule. The result is `FIT`, `NOT_FIT`, or
`UNDETERMINED`; `NOT_FIT` blocks every Add path, while `UNDETERMINED` remains a
recorded non-blocking judgment. This asymmetry preserves Goal-as-focus meaning
while preventing a known incompatible proposal from being published.

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

Rules recover the complete generative family rather than only behavioral
advice. The mandatory audit therefore compares shared language and
language-mixing, register, tone, formality, person, viewpoint, tense, voice,
exact expressions, actor and subject transitions, label order, sentence and
event sequence, markup, placeholders, delimiters, capitalization, and
punctuation. A surface-form claim is exact only when every cited support
literally contains that form in the claimed position. Observed particle,
inflection, spelling, or punctuation variants must remain alternatives or a
conditioned form only when the Source itself supports that condition; hidden
linguistic causes are not inferred. A majority pattern is not universal.
Support and boundary aliases remain disjoint, and a mechanical consequence is
not duplicated as a second Rule unless it independently constrains a new
Example. Every provider prompt also quotes the complete café, lost-property,
and Cloze Example-to-Rule reference pairs. These demonstrate the reduction
without becoming current evidence: only aliases from the selected Source may
appear in a Rule's support or boundary fields. Provider contract version 6
prevented prepared results from the earlier unreferenced prompt or partial
form audit from replaying under that stricter meaning. Version 7 removes the
arbitrary default Rule-count ceiling.

Provider contract version 8 adds the exhaustive post-generation Goal Fit
record. Its decoder requires every proposed Rule exactly once and in order;
`NOT_FIT` and `UNDETERMINED` must identify the material Rule UIDs. An empty
supported Rule set is deterministically `FIT` because a relevance focus cannot
itself authorize a Rule and there is no proposal to contradict it.

Provider contract version 9 changes only the prompt-level reduction method and
prepared-result identity, not the JSON schema or evidence boundary. The
provider now reads the complete Source before deciding applicability and may
derive parents over a supported subset, an ordered collection, independent
sibling criteria, or diagnostic indicators. When the Source is itself a
coherent normative Rule set, a final whole-set audit may additionally return
one governing Goal-like parent while retaining independently useful lower
Rules. A parent must state an objective, constraint, classification, or
judgment; a bare topic label remains invalid. No operation code recognizes
Fibonacci, cleanliness, languages, or any other evaluation domain.

Provider contract version 10 keeps the same JSON schema and evidence boundary
but promotes the optional natural-language Goal from a relevance phrase to an
output-selection contract. The provider applies one ordered procedure: read the
whole Source, enumerate supported semantic and form candidates, interpret the
Goal's intended use/hierarchy/count/exclusions/modality, reconcile a minimal
nonredundant Rule topology, and finally account for every Source Memory. A
surface-form audit remains mandatory internally so the no-Goal café,
lost-property, and Cloze families remain reconstructable, but a semantic Goal
may exclude dates, viewpoint, or platform metadata from the returned Rule set.
No host code parses Goal vocabulary, computes a target compression ratio, or
contains evaluation-family branches. A Goal also remains non-evidence: it may
select supported operational criteria but cannot turn neutral observations
into duties or authorize a fabricated concrete Task.

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

The ordinary configuration has `max_rules=None`: Distill asks for the smallest
complete set of independently meaningful, evidence-supported Rules and does
not stop at a fixed count such as 20. An injected configuration may set an
explicit positive `max_rules` for a constrained integration or test, in which
case planning, schema, decoding, and prepared-result validation enforce that
same ceiling. “No Rule-count ceiling” does not remove the provider response
character bound or per-field text limits; those remain transport and resource
boundaries rather than semantic instructions to omit a supported Rule.

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
When a Goal exists, publication additionally requires that its frozen Goal Fit
audit is present and is not `NOT_FIT`.

`mem impact distill` accepts the same endpoint matrix and prepares the same
exact proposal without writing a Memory or checkpoint. This explicit Impact
route replaces an implicit TTY preview as the ordinary way to inspect before
saving.

### Compact Rule rows preserve complete content

Proposal catalogs use the same content-first visual grammar as compact
Reference rows: `[N] CONTENT — METADATA`. Distill's suffix reports local
evidence counts as `SUPPORT n · BOUNDARY n`; the exact supporting and boundary
UIDs plus the rationale remain in the Rule detail. This keeps the default
catalog to one logical row per Rule without treating rationale as a second
peer Rule row.

Rule content is folded to one logical line but is never shortened or
paraphrased by the renderer. In particular, this route has no character-limit
or ellipsis option. A narrow terminal may wrap the complete row physically;
viewport wrapping must not change the copied text, proposal artifact, or
durable Rule. The distinction matters because a trailing qualification can be
the semantic boundary that makes an evidence-derived Rule safe. Focused Rule
copy and whole-proposal copy retain the full rationale and exact evidence UID
detail even though the default catalog projects only evidence counts.

The `PROPOSED RULES` catalog is the single default report location for these
generated Memories. The read-only Impact route therefore suppresses its
generic `IMPACT`/`[ADD]` effect ledger and Results block for Distill: both
would repeat the same complete Rules without introducing another decision.
This is a presentation boundary, not a loss of proposal data. Rule detail and
copy still contain rationale and evidence, while the Context-location header
and close-time digest checks continue to prove that Source and Target were not
changed. Mutation-oriented operations retain their distinct Impact ledgers.

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
does not call the provider. The optional Goal is supplied by the shared Goal
operand as an existing direct-Memory Context, one direct Memory, or
process-local text; a dedicated TUI Goal editor is a named remaining boundary.

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
`--save-as`/`--apply`. It remains read-only by default. The explicit `--adopt`
form revalidates the exact reviewed physical Ground revision and `/rules`
pre-image, then adds the complete proposal as one Ground-local command unit. A
semantic proposal without `--adopt` is not acceptance.

## Apply, provenance, and authority

Standalone publication consumes the exact prepared proposal and appends every
Rule to the existing Target as one Undo unit. Its checkpoint records Source and
Target names, Source scope/digest, the complete typed Goal focus receipt,
provider contract, Rule
evidence, outside evidence, analysis digest, and exact result Memory UIDs. A
distinct Source remains unchanged. When Source equals Target, only the new
Rules change it. The compatibility require-new Apply retains its earlier
checkpoint contract. Version-3 Distill operation metadata also records the
Goal Fit verdict, reason, complete considered Rule UIDs, and material Rule UIDs
without adding another participant-facing report.

The current runtime rejects any granted Source before provider connection.
Visibility or `READ` alone does not authorize derivation or retention. A later
grant adapter must explicitly satisfy `DERIVE`, `EXPORT`, retained-analysis,
target acceptance, and freshness requirements.

The compatibility require-new form treats `--apply` as the complete
publication approval. `--save-as` without `--apply` renders the proposed name
as `READY TO CREATE` and leaves it absent in both terminals and noninteractive
hosts. This keeps one command contract across TTY boundaries and avoids a
prompt that an agent or pipeline cannot answer.

## Remaining limits

- no persisted Distill hidden receipt/prewarm installer;
- no safe subset or ancestor cache projection;
- Goal Fit is a bounded semantic reading audit, not proof of factual truth or
  evidence completeness; `UNDETERMINED` intentionally does not block Add;
- no durable Distill review session or resume path;
- no granted-frame derivation;
- no TUI Goal editor; and
- no agent/MCP mutation tool.

The shared operand and physical-Ground adoption invariants are recorded in
[`goal-focus-operand-design-rationale.md`](goal-focus-operand-design-rationale.md).
