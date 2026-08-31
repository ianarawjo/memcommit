# Targetless peer-Context comparison

## Status

The first bounded Compare slice is implemented as:

```text
mem compare
mem compare --sessions
mem compare PEER
mem compare REFERENCE PEER
mem compare PEER_MEMORY
mem compare REFERENCE_MEMORY PEER_MEMORY
mem compare REFERENCE:MEMORY PEER:MEMORY
mem compare ../PEER
mem compare REFERENCE PEER --refresh
mem compare REFERENCE PEER --snapshot
mem compare REFERENCE PEER --ledger
mem compare --to PEER
mem compare --from REFERENCE --to PEER
```

Bare `mem compare` opens the shared A/B endpoint setup for one new transient
summary. `mem compare --sessions` alone opens the shared saved-work picker.
Choosing New there delegates to the same endpoint setup but retains the
launcher's explicit exhaustive saved-analysis contract, so it produces a row
that the launcher can reopen. One positional operand is
the peer and retains the active Context as reference; two positional operands
explicitly name reference and peer. Each positional endpoint uses the shared
Context/direct-Memory classifier: an eight-or-more-character UUID-shaped value
is a bare Memory selector, `CONTEXT:UID` is an owner-qualified Memory selector,
and other values begin as existing Context locators. A shorter hexadecimal
endpoint preserves an exact readable Context first and otherwise becomes a
Memory only when the complete ordinary-local catalog has one unique match.
`--from` and `--to` remain explicitly typed Context compatibility aliases, but
positional endpoints and endpoint options cannot be mixed in one invocation.
`--refresh` still requires an explicit peer and is rejected on the picker
route.

The unqualified explicit-pair route is now a transient lightweight summary.
It returns exactly one bounded source-linked relation paragraph under the
minimal `Compare · A ↔ B` / `COMPARISON` receipt, without constructing or
saving relations, assignments, Issues, or a Meld basis. The paragraph leads
with the dominant relationship and preserves at most the decisive difference
needed to understand it; frame size does not increase its output budget.
`--ledger` explicitly selects the exhaustive saved analysis described by the
remainder of this document; `--refresh` retains that deep replacement contract.
The split and migration boundary are recorded in
[`compare-summary-design-rationale.md`](compare-summary-design-rationale.md).

The picker presents Compare as a **saved read-only analysis**, not as a chat,
dialogue, or mutable session. Each row names the ordered pair, reports relation
and grounding-candidate counts, groups under the reference Context, and sorts
by the latest analysis modification time by default. Its detail pane is the
complete compact Compare report that opening the analysis will preserve; the
generic key/status/route metadata envelope is intentionally omitted because
the selected row already provides identity and status and the envelope would
push the semantic report below the initial viewport.
`PageUp`/`PageDown` scroll that preview without changing the selected analysis.
The shared metadata label is `Summary`, not the implementation-oriented
`Subtitle`. The existing order is preserved: `A → B` and `B → A` remain
distinct entries even though the compact title uses a symmetric peer marker.

Selecting a row freezes its analysis UID process-locally. Compare reloads that
exact persisted UID after the picker closes, loads both sources by the names
and UIDs captured in the artifact, verifies their complete direct digests and
the current Compare ruleset, and only then prints a bounded saved-analysis
receipt with the exact `mem review compare --session UID` route. It does
not consult or switch the global current Context after selection, connect a
provider, refresh an analysis, save a replacement, or create a checkpoint. A
deleted, replaced, stale, or older-ruleset selection fails with an explicit
refresh instruction instead of silently entering the normal `--to` path.

The shared picker currently requires an argv-shaped presentation field. The
Compare adapter displays `mem compare REFERENCE COMPARED`, including both
canonical endpoints so the route remains stable if the active Context changes;
the picker does not execute it. The frozen analysis UID is the authority for
the selected render. A public UID route and multiple historical revisions of
one ordered pair are outside this first selector slice.

The picker includes both ordinary comparison slots and authorized retained or
grant-bound comparison artifacts. Otherwise a participant could successfully
save a granted Compare result but have no route back to it from
`mem compare --sessions`. Reopening revalidates the artifact according to its
retention mode and never broadens its source grant.

The active Context is the display reference when one positional `PEER` or only
`--to PEER` is supplied. Two positional Contexts are `REFERENCE PEER`; the
legacy equivalent is `--from REFERENCE --to PEER`. A fully explicit canonical
pair does not require any current Context and never changes one that exists. A
current snapshot is needed only for an omitted reference or an explicitly
relative locator. The shared New setup may select both A and B without
switching the active Context; it invokes the same explicit endpoint contract.
Both sources have equal
authority. `REFERENCE` controls layout and navigation only; it is not a
baseline and does not win a disagreement.

### Auto-typed positional endpoints

Each positional endpoint uses the shared Context/direct-Memory shape
classifier. A bare positional Memory searches one strict ordinary-local
direct-owner snapshot and must have exactly one owner. New Branch copies have
fresh occurrence UIDs, so Branch alone no longer makes the immediately visible
selector ambiguous. Legacy stores or independently imported data may still
contain the same UID under several owners; those cases fail closed and require
`CONTEXT:UID`. Qualified Memory owners use the same Context resolver and may
name an authorized public Grant Context. Bare Memory lookup never enumerates
Grant contents. Short prefixes remain available through qualification or the
explicit `--reference-memory` and `--compared-memory` options. Existing
UUID-shaped Contexts remain accessible through the explicitly Context-typed
`--from` and `--to` compatibility routes.

Automatic classification changes only command entry. It freezes each derived
owner and exact Memory UID, then enters Compare's existing focused-frame path:
the selected Memory is actionable and the rest of its loaded Context remains
context-only evidence. Memory selection is still incompatible with descendant
expansion on that side, and the two resolved owners must remain distinct. Both
roles use the same command-start current-name and Grant-registry snapshot.

### Why Compare has asymmetric positional arity

Compare is the strongest positional-operand case because it is read-only and
its two Contexts have equal authority. Zero operands opens saved work, one
operand unambiguously preserves the established current-reference behavior,
and two operands fully specify the pair. Endpoint options remain aliases for
existing scripts; rejecting mixed syntax prevents one Context from acquiring
two competing role declarations.

The wider command audit is now implemented as a shared grammar rather than a
list of future candidates. Unary Context operations use zero operands for the
current Context and one for an explicit Context. Directional Update requires
an explicit positional pair, while Forget keeps `--context` because its sole
position belongs to the natural-language instruction. The complete table,
including named Impact routes and compatibility aliases, is maintained in
[`context-locator-design-rationale.md`](context-locator-design-rationale.md#cli-operand-grammar).

Both positional Context endpoints and their `--from`/`--to` aliases are
existing-Context locators. A canonical name remains global, while an explicit
`.` or `..` spelling is resolved lexically against the same active-Context
snapshot captured at command start. The resolved canonical names are used for
loading, frames, cache identity, and output, so relative and canonical
spellings reuse the same durable analysis. The shared contract and its
non-goals are recorded in
[`context-locator-design-rationale.md`](context-locator-design-rationale.md).

Deep Compare performs one aggregate semantic call over the two complete
bounded readable-evidence frames. It saves an immutable `ComparisonAnalysis`
containing:

- exact ordered source Context identities, names, digests, evidence order,
  content snapshots, and host-only source provenance;
- one overview;
- four short category reports for shared, differing, reference-only, and
  compared-only material;
- one exhaustive N:M primary relation ledger; and
- visible issues that may later become grounding turns.

It has no target Context, target proposal, conversational turn, readiness
state, acceptance action, checkpoint, or mutation authority.

The complete frame is not silently split when model latency is high. Compare
uses a 900-second operation-local aggregate ceiling for the Codex adapter,
matching Meld's whole-ledger window. This was raised after a valid 113,198-
character Task 1 subtree frame passed every local bound but the xhigh provider
was still running when the configured 600-second transport limit expired. The
larger ceiling does not relax input, output, schema, coverage, or one-call
invariants; it only allows the already-authorized indivisible call to finish.

## Why the deep analysis persists

Deep one-shot interaction does not imply disposable analysis. Provider output is
not assumed to be deterministic, and a later Meld must be able to identify
the exact relations the person inspected. Reopening an unchanged ordered pair
therefore renders the saved analysis without another provider call.

The latest ordered slot is:

```text
~/.mem/comparison-analyses/
  <reference-context-uid>--<compared-context-uid>.json
```

Context names do not determine storage paths. If either source UID, name,
complete direct record digest, or order changes, `mem compare --ledger`
performs a fresh analysis and atomically replaces that ordered latest slot.
`--refresh` forces a fresh analysis even when both source snapshots still
match. A changed semantic ruleset also performs a fresh analysis while an
older supported artifact remains readable for replacement CAS. Provider or
validation failure leaves the prior saved analysis intact.

Compare intentionally keeps `A → B` and `B → A` as separate ordered slots.
This preserves the ability to study whether presentation order changes a
model's judgments. A later product decision may canonicalize the pair and
render two projections from one analysis, but that must not be silently
inferred from the sources' equal authority.

Only the latest analysis for an ordered pair is retained. Revision history,
diffing two analyses, and selecting an older analysis remain future work.

## Relation contract

Every source Memory appears in exactly one primary relation. Relations may be
1:1, 1:N, N:1, or N:M; positional zipping and Cartesian pair enumeration are
both rejected.

| Relation | Meaning |
| --- | --- |
| `EQUIVALENT` | The peers express the same operational claim under the same relevant scope. |
| `COMPATIBLE` | Both claims can remain without inventing a missing scope distinction. |
| `SCOPED` | An explicit condition explains the difference and must be retained. |
| `CONFLICT` | Ordinary scope-aligned readings cannot jointly govern the same case. |
| `DISTINCT` | One peer contains independently useful information absent from the other. Absence is not automatically a deficiency. |
| `UNCLEAR` | The supplied frames do not justify safe placement or interpretation. |

`EQUIVALENT`, `COMPATIBLE`, `SCOPED`, and `DISTINCT` are resolved comparison
descriptions. `CONFLICT` and `UNCLEAR` are unresolved and must be linked to a
visible `REQUIRED` issue. These issues are candidate Ground Memories, not user
judgments, golden Ground Memories, or permission to reconcile anything.

`COMPATIBLE` requires a shared operational decision or policy dimension;
mere coexistence or broad topical similarity would arbitrarily pair unrelated
Memories. Likewise, `DISTINCT` is not a miscellaneous one-sided bucket.
Several same-side Memories may share a `DISTINCT` relation only when they
restate or split one underlying claim. Independent one-sided claims receive
independent relations so a later relation-by-relation viewer has a meaningful
unit of inspection.

The schema deliberately omits Meld dispositions and target Memories. Compare
describes what exists in both, what differs, and what exists on only one side;
Meld later decides what an accepted target should contain.

### Content-bearing direct items

Compare treats every readable content-bearing occurrence as an ordinary
semantic claim. An owned Memory, live Memory Embed, immutable Memory Reference,
Memory reached through a Context Embed or Context Reference, and readable
granted Context content all enter the same ordered content frame. Their text is
not prefixed with a Context name or acquisition label, and the semantic provider
receives no real Context name, Memory UID, Grant identity, or ownership hint.
This keeps comparison about the claims rather than their storage form.

Acquisition remains typed host metadata rather than being erased. Each saved
evidence row binds its placement UID and path, source form, Source Memory UID,
and owning Context identity. A live Memory Embed uses the Embed placement UID as
the evidence identity and retains the Source Memory UID separately. This means
two placements are two evidence occurrences, while a same-text retarget is
still a source change. Recursive Context graphs visit an exact Context UID once
to prevent cycles and duplicate graph exposure.

Freshness follows the source form. A Reference binds its retained snapshot and
remains comparable after the original Source disappears. A live Embed or live
Context graph is reprojected before reuse; local external owners are included in
the save-time lock set, and a content, owner, target, or placement change stops
publication. Compare and Compare Summary use the same projection and freshness
identity. The exhaustive ledger may display host provenance such as `EMBED
FROM` or `REFERENCE FROM`, but that annotation is never part of the claim sent
for semantic judgment.

Query-only Context routes are not readable Memory evidence. Compare fails
explicitly before provider connection instead of opening hidden content or
silently omitting the row. Likewise, a dangling live Embed names the unavailable
Source in the error. These errors describe the concrete boundary and do not
advertise an implementation-version capability label.

### Explicit descendant scope

Each interactive A/B pane shares the role-based setup shell's default-off
`INCLUDE ALL DESCENDANT CONTEXTS (OWNED OR GRANTED)` control. The matching
explicit flags are `--reference-descendants` and `--compared-descendants`.
Checked means the selected Context graph plus every lexical descendant visible
through that endpoint's same owned store or frozen Grant view; it never treats
a Grant attachment as a hierarchy edge or opens query-only material.

Schema v3 persists both booleans independently. Cache reuse, post-provider
revalidation, saved report rendering, and a later symmetric Meld must use that
exact pair. This makes two momentarily identical projections with different
future scope contracts distinct analyses and prevents a new descendant from
silently entering an unchecked analysis.

## Meld basis reuse

Compare never starts Meld, chooses a Result, or presents a Meld-specific
handoff. When a person separately starts a new symmetric Meld, Meld consumes
the exact current ordered Compare slot for its two sources and the exact same
descendant-scope pair. `mem meld LEFT
RIGHT` loads only `LEFT → RIGHT`; it never silently substitutes `RIGHT →
LEFT`, because the two saved slots deliberately retain observable
presentation-order effects. A fresh slot is reused provider-free. A missing,
stale, differently scoped, or older-ruleset slot is regenerated and saved
through the same shared Compare execution path before the Meld session is
created. An invalid stored artifact still fails closed.

Fresh-slot reuse is provider-free. The new Meld session embeds the
complete `ComparisonAnalysis`, its canonical digest, and the same frame,
relation, issue, and option identities. Its initial assessment is the
inspected Compare overview, ledger, and grounding candidates with no target
proposals and no readiness authority. The first issue or whole-set response
becomes the first Meld semantic call; that grounded turn may then revise
relationships and produce exact target Memories.

Embedding the full basis instead of storing only a pointer is intentional.
Compare retains only the latest ordered analysis and deletes pair artifacts
when a source Context is deleted. A target-bound Meld must remain
self-describing after a later Compare refresh while continuing to reject live
source changes through its own Context-digest checks.

Existing unseeded Meld sessions remain readable under their legacy schema.
When an exact current ordered Compare exists, schema-7 Directional Meld now
freezes its classification ledger and remaps the members by Memory UID onto
raw owner-aware `INCOMING → BASELINE` frames. Directional authority still owns
placement and target materialization, and an absent Compare retains the
schema-6 direct-analysis compatibility path. The handoff therefore never
infers that a resolved relation ledger is itself permission to write a target.

## Provider and trust boundary

The provider receives call-local opaque frame and Memory IDs, full bounded
evidence content, source order, and equal-authority instructions. Context names,
source forms, and ownership remain local presentation metadata: sending them is
unnecessary for comparison and could introduce identity or ordering bias. The
provider may return only `overview`, `reports`, `paired_relations`,
`distinct_relations`, `source_assignments`, and `issues` under the current
strict JSON schema. `paired_relations` excludes `DISTINCT` by construction;
each `distinct_relations` row declares `DISTINCT` plus its exact
`REFERENCE`-or-`COMPARED` side.

Relation definitions carry semantic judgment and prose but no nested member-ID
arrays. `source_assignments` instead contains exactly one
`{source_memory_id, relation_key}` row per frozen Memory. Its schema fixes the
row count to the Source count and restricts every source ID to the exact frozen
alias enum. This source-indexed shape was selected after a 300-Memory Task 2
frame repeatedly returned structurally valid relation JSON that omitted or
duplicated at least one member. It gives structured generation one uniform
coverage task instead of asking the model to maintain a global partition across
variable-size nested arrays. Separating paired and one-sided relation records
also gives structured generation the same side-shape vocabulary already used
by Meld. JSON Schema still cannot prove that the source rows assigned to one
paired relation include both sides, so the host remains authoritative.

The repaired contract was verified live against the same Task 2 route that had
failed twice under the nested-array contract. The provider completed a
87,527-character prompt in about 304 seconds and returned 58,201 characters.
The saved analysis contained 109 relations, 300 relation members, and 300
unique `(frame_uid, memory_uid)` pairs for the frozen 150+150 frame. Symmetric
Meld opened the imported result workbench, and closing it without acceptance
left the target Context at zero Memories and zero checkpoints.

The four reports are produced in the same complete response as the exhaustive
ledger. They are not presentation-layer concatenations of relation summaries.
Joining a few ledger rows would silently turn truncation into semantic
synthesis and make a compact screen look more complete than it is. Local
validation instead derives each report's supporting group from the ledger:

- `both`: `EQUIVALENT` and `COMPATIBLE`;
- `differences`: `SCOPED`, `CONFLICT`, and `UNCLEAR`;
- `reference_only`: reference-side `DISTINCT`; and
- `compared_only`: compared-side `DISTINCT`.

A report must be non-empty exactly when its group has at least one relation.
An absent group must have an empty provider field. The compact view omits that
section because the complete zero counts are already visible in top metadata;
the fixed audit ledger still renders the empty category explicitly. This
prevents prose from being invented for an empty category without duplicating
relation references in the report schema.

Compare follows the shared result-workbench attention budget without
multiplying it by the number of headings. The overview normally uses at most
roughly 40-50 English words. The four category reports subdivide the remaining
report layer and together target no more than roughly 100 words, keeping all
top-level report prose near the shared 150-word first-frame envelope. These are
soft generation targets, not truncation or validation rules. A material
difference, exception, or unresolved relation must be retained even when doing
so exceeds the target; exact relations remain complete in `--ledger`.

Schema version 2 added reports, version 3 added independent descendant scope,
and version 4 adds optional typed evidence provenance. Schema-version-1 through
version-3 artifacts remain strictly readable and preserve their old
serialization shape so they can participate in ordered-slot replacement CAS.
Ruleset version 4 requires the current content-evidence contract for newly
created analyses, so an unchanged pair with an older ruleset is refreshed
rather than reused.

The schema deliberately omits JSON Schema `uniqueItems` because the Codex
structured-output subset rejects that keyword. Exact row count and alias enums
therefore reduce, but cannot prove, global uniqueness. The shared exact-source
decoder rejects a repeated, omitted, or unknown alias and a relation key that
was not returned. The operation parser then reconstructs relation members in
canonical Source order and rechecks side shape and exhaustive coverage before
an analysis can be saved. Legacy call-local responses that embedded member
arrays remain parser-compatible for tests and older provider adapters; all new
schema-constrained turns use source assignments. The provider response schema
does not expose or reproduce host provenance; the host attaches and validates
that metadata independently.

Provider contract `exhaustive-validation-repair-v2` permits at most one
explicit validation-repair call after a complete response fails a local
cross-record invariant. The repair payload contains the unchanged complete
frame payload, the complete rejected response, and one trusted structural
validation error. The error is not semantic evidence and cannot ground a new
claim or resolve uncertainty. Repair returns another complete response under
the same schema, never a patch, and the host validates it from the beginning.
A second invalid response still fails closed, and nothing is saved from the
rejected response. Transport retries remain an outer execution concern rather
than permission to weaken the decoder.

This bounded repair was added after the 718-row Study regeneration using the
v1 provider contract completed 711 rows but repeatedly left seven rows with a
non-`DISTINCT` relation whose assignments came from only one PEER side. Each
surviving row failed six provider attempts across three resumable init runs.
The v2 split schema, explicit side instruction, and validation feedback repair
the generation contract at the shared Compare boundary instead of special
casing Study prewarm or rewriting an invalid relation locally.

Local validation rejects:

- missing, duplicate, unknown, or wrong-side Memory references;
- a `DISTINCT` group containing both sources;
- a non-`DISTINCT` group missing one source;
- omitted or multiply assigned source Memories;
- unknown relation references;
- an unresolved relation without a visible required issue;
- unknown fields, duplicate JSON keys, invalid enums, excessive results, or
  over-limit input; and
- target, proposal, readiness, command, or approval-shaped output.

The persisted frame also recomputes its canonical Context record digest from
the exact ordered Memory snapshot. A stored analysis cannot retain a valid
live-Context digest while displaying altered “exact source” text.

Compare has no independent evidence-count gate. It accepts the complete
frozen pair while its encoded input fits the shared 1,000,000-character
effective provider capacity, and rejects an over-capacity frame rather than
truncating or hiding retrieval calls.

After provider latency, both Contexts and every local live external evidence
owner are reloaded while their cooperative write locks are held. Their complete
projected content and provenance must still match the analysis. The ordered slot
is also compare-and-swapped against the analysis UID observed before the call.
A changed source, retargeted placement, or newer concurrent analysis prevents
the new result from being saved.

Comparison artifacts copy source text and derived explanations. Deleting
either bound source therefore removes both ordered orientations involving
that Context. Compare never opens query-only sources.

## Explicit workbench, compact default receipt, and exact ledger

Compare owns one console presentation family under
`memcommit.adapters.console.commands.search_explain.synthesize.compare`: the lightweight summary,
bounded receipt, compact snapshot, and exhaustive ledger. Interactive endpoint
setup is co-located with that family because line-oriented and prompt-toolkit
routes are two presentations of the same console operation, not independent
public interfaces. The still-staged shared terminal components remain reusable
dependencies; they do not own Compare labels, setup meaning, or report prose.

Symmetric Meld and Review may render an exact saved `ComparisonAnalysis`
through this Compare-owned presenter. That downstream reuse is an explicit
Compare-artifact dependency, not evidence that the renderer is
operation-neutral. Those consumers must not import or invoke Compare's Typer
entrypoint, and the renderer must not acquire Meld target, response, Apply, or
mutation semantics.

Completing or reopening Compare does not automatically enter a Viewer in a
TTY. A transient summary stays line-oriented; an exhaustive saved analysis
returns a bounded receipt with overview, relation/attention counts, analysis
UID, and the exact `mem review compare --session UID` route. Explicit
`--snapshot` prints the complete compact report and `--ledger` prints its full
relation ledger. The read-only workbench described below belongs to explicit
Review, so durable detail remains available without making every execution a
second full-screen reading task.

Explicit Compare Review is hosted by the common Review report shell. It opens
the complete saved report in Viewer and remains read-only: Compare has no
response, Apply, or hidden transition capability. The Review controller binds
the exact analysis UID and canonical digest to that projection, while the
shared shell owns scrolling, focus, back navigation, terminal escaping, and
close behavior. `mem compare --sessions` selects a saved artifact only; after
selection, the normal compact receipt or explicit Review route is used.

The former `commands.compare_workbench` application duplicated Viewer/Items,
relation expansion, and shortcut routing without any production caller. It
was removed rather than retained as a second claimed Compare UI. Full ledger
inspection remains `mem compare --ledger`, Rationale remains its own command
over an exact source Memory, and Meld remains its own setup and execution
boundary. Review does not synthesize those commands as report actions.

Explicit `--snapshot` uses the compact report ordered by decision relevance:

```text
METRICS
WHAT MEM UNDERSTOOD
WHAT BOTH CONTAIN
WHAT DIFFERS
ONLY IN REFERENCE
ONLY IN COMPARED
POTENTIAL CONFLICTS
```

Memory, relation, relation-kind, and grounding-candidate counts appear directly
under the source identities. They orient the reader before prose and make the
amount of remaining judgment work visible without forcing a scan of every
relation.

The four middle sections contain complete short semantic reports rather than
one row per relation. The person already knows the source Contexts; the default
view should communicate their overall overlap, difference, and one-sided
contributions rather than repeat every source Memory. A zero-count report is
omitted from this compact body, as is a zero-count grounding section. The top
metadata remains the explicit proof that these categories were evaluated and
found empty rather than skipped.

When non-empty, `POTENTIAL CONFLICTS` remains a complete final list because
those are the places where human intervention can change later
reconciliation. Each conflict is one compact paragraph: title, source Context
names, relation summary, consequence, and the effect of each available option.
Provider priority labels, `RELATED · R…`, `WHY`, `ASK`, and indented option rows
are deliberately omitted from the report; stable relation numbers remain in
the exhaustive Ledger, where they are meaningful audit locators. After the
last non-empty semantic section, one plain footer sentence
states that the relation ledger is saved and ends with `Inspect it with:`.
The next line contains the complete shell-quoted command for the provider-free
`--ledger` view. Omitting another label keeps this small navigation hint
subordinate to the report and makes the command easy to select without copying
explanatory prose. The footer separates the final report text from the next
shell prompt without relying on arbitrary extra blank lines; it is not another
semantic result section.

The footer uses both canonical Context names, not raw relative locators, and
display-escapes terminal controls after POSIX shell quoting. It therefore
remains stateless and preserves the reviewed orientation even if current state
later changes.

`--ledger` renders every validated relation, its exact source snapshots, and
its explanation without another provider call. The exhaustive ledger remains
part of the durable analysis and is therefore available for audit and the TTY
relation browser; it is merely not the default snapshot reading burden.
This differs from Atomize, where unchanged atomic Memories can be omitted from
the issue list.

Every source string and provider-authored explanation is rendered through an
injective single-line escape boundary. Embedded newlines, tabs, bidi controls,
or other terminal controls therefore cannot impersonate trusted section
headings.

The workbench is only a presentation layer over the immutable analysis. It
adds no chat state, provider state, target, or mutation authority.

## Task 2 smoke-test observation

The first 20-by-20 advisor fixture exposed two useful design failures. The
initial ruleset grouped nine unrelated one-sided Memories into one
`DISTINCT` relation and paired two broadly audience-related but operationally
independent claims as `COMPATIBLE`. Version 2 added the shared-decision rule
and the prohibition on miscellaneous `DISTINCT` buckets. A fresh run then
produced 30 inspectable relations: ten cross-source relations and twenty
independent one-sided relations, with three required conflict questions.

Running the same snapshots in both orientations preserved the same two scoped
relations, three conflicts, and twenty distinct relations. It nevertheless
shifted the short/descriptive-heading pair across the
`EQUIVALENT`/`COMPATIBLE` boundary, yielding counts of 2/3 in one orientation
and 3/2 in the other. This is a small but concrete order effect despite the
equal-authority prompt, so version 1's decision to retain separate ordered
slots remains useful for the research prototype. Canonicalizing A↔B into one
model call would hide that observation.

## Relationship to Atomize and Meld screens

The Atomize workbench already demonstrates the useful interaction grammar:
overview, list, arrow navigation, exact-source detail, explanation, stable
resume, and a separate application boundary. Compare can reuse that grammar
and the neutral terminal primitives, but not Atomize's semantic session.

The primary deep-inspection unit remains a **relation**, not an Atomize issue
or a Meld target proposal. Report-section and Potential Conflict rows are
navigation projections whose linked relations remain authoritative. The
implemented workbench uses:

```text
complete compact report
→ individually selectable report sections and Potential Conflicts
→ Relation Ledger boundary and relation list
→ arrow/Enter source-linked detail
→ exact source Memories, classification, and reason
→ return to the same saved position
```

Choice, free-form comment, impact propagation, and acceptance belong to a
subsequent grounding/Meld session. Compare view state must not be stored as
Atomize choices, and peer relations must not be disguised as atomization
findings.

This follows the existing boundaries in
[`mem-atomize-workbench-design-rationale.md`](mem-atomize-workbench-design-rationale.md),
[`mem-meld-design-rationale.md`](mem-meld-design-rationale.md), and
[`shared-tui-command-review-design-rationale.md`](shared-tui-command-review-design-rationale.md):
share tested terminal mechanics and interaction grammar while preserving
operation-specific identities, evidence, persistence, and mutation semantics.

## Current limitations and next connection

- Compare accepts readable ordinary or granted Context subtrees and flattens
  their Memory paths into immutable frames. Query-only sources remain
  concealed, and live Memory references are rejected rather than copied.
- The interactive workbench has no category filter, JSON output, history
  browser, analysis diff, or persisted cursor. `--ledger` remains the complete
  static audit view.
- Automatic fresh analysis after a source change is intentional for Compare;
  it differs from an in-progress Atomize review, whose reviewed proposal fails
  stale rather than silently changing.
- Symmetric Meld imports the exact `ComparisonAnalysis`, but the two operations
  still retain separate persisted schemas after the handoff: Compare has no
  target or turns, while Meld owns target proposals, dialogue, acceptance, and
  application receipts.
- The initial handoff imports no target proposal. If Compare has no grounding
  candidates, the user currently needs a whole-set comment or preserve-all
  turn to materialize a reviewable target proposal.
- The Meld checkpoint records the complete source and turn evidence but does
  not yet expose the originating Compare UID as a separate trace field; the
  exact basis remains embedded and digest-bound in the saved Meld session.
