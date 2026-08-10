# Targetless peer-Context comparison

## Status

The first bounded Compare slice is implemented as:

```text
mem compare
mem compare --sessions
mem compare --to PEER
mem compare --from REFERENCE --to PEER
mem compare --to ../PEER
mem compare --to PEER --refresh
mem compare --to PEER --snapshot
mem compare --to PEER --ledger
```

Bare `mem compare` and `mem compare --sessions` open the shared saved-work
picker. This is compatible with the earlier command because omitting `--to`
previously produced only a missing-option error; it did not mean “start a new
comparison.” Explicit `--to` behavior is unchanged. `--refresh` still requires
an explicit peer and is rejected on the picker route.

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
the current Compare ruleset, and only then opens the saved analysis workbench
in a TTY. It does
not consult or switch the global current Context after selection, connect a
provider, refresh an analysis, save a replacement, or create a checkpoint. A
deleted, replaced, stale, or older-ruleset selection fails with an explicit
refresh instruction instead of silently entering the normal `--to` path.

The shared picker currently requires an argv-shaped presentation field. The
Compare adapter displays `mem compare --to COMPARED` as a route hint and states
that it requires the displayed reference Context to be current; the picker
does not execute it. The frozen analysis UID is the authority for the selected
render. A public UID route and multiple historical revisions of one ordered
pair are outside this first selector slice.

The picker includes both ordinary comparison slots and authorized retained or
grant-bound comparison artifacts. Otherwise a participant could successfully
save a granted Compare result but have no route back to it from bare
`mem compare`. Reopening revalidates the artifact according to its retention
mode and never broadens its source grant.

The active Context is the display reference and `--to` names the compared
Context when `--from` is omitted. When both `--from REFERENCE` and `--to PEER`
are supplied as canonical names, Compare does not require any current Context
and never changes one that exists. A current snapshot is needed only for an
omitted reference or an explicitly relative locator. The shared New setup may
select both A and B without switching the active Context; it invokes the same
explicit endpoint contract. Both sources have equal
authority. `REFERENCE` controls layout and navigation only; it is not a
baseline and does not win a disagreement.

`--from` and `--to` are existing-Context locators. A canonical name remains
global, while an explicit `.` or `..` spelling is resolved lexically against
the same active-Context snapshot captured at command start. The resolved
canonical names are used for loading, frames, cache identity, and output, so
relative and canonical spellings reuse the same durable analysis. The shared
contract and its
non-goals are recorded in
[`context-locator-design-rationale.md`](context-locator-design-rationale.md).

Compare performs one aggregate semantic call over the two complete bounded
direct-Memory frames. It saves an immutable `ComparisonAnalysis` containing:

- exact ordered source Context identities, names, digests, Memory order, and
  Memory snapshots;
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

## Why the analysis persists

One-shot interaction does not imply disposable analysis. Provider output is
not assumed to be deterministic, and a later Meld must be able to identify
the exact relations the person inspected. Reopening an unchanged ordered pair
therefore renders the saved analysis without another provider call.

The latest ordered slot is:

```text
~/.mem/comparison-analyses/
  <reference-context-uid>--<compared-context-uid>.json
```

Context names do not determine storage paths. If either source UID, name,
complete direct record digest, or order changes, ordinary `mem compare`
performs a fresh analysis and atomically replaces that ordered latest slot.
`--refresh` forces a fresh analysis even when both source snapshots still
match. A changed semantic ruleset also performs a fresh analysis while an
older supported artifact remains readable for replacement CAS. Provider or
validation failure leaves the prior saved analysis intact.

Version 1 intentionally keeps `A → B` and `B → A` as separate ordered slots.
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

## Compare-to-Meld handoff

A new symmetric Meld always consumes the exact current ordered Compare slot
for its two sources and the exact same descendant-scope pair. `mem meld LEFT
RIGHT` loads only `LEFT → RIGHT`; it never silently substitutes `RIGHT →
LEFT`, because the two saved slots deliberately retain observable
presentation-order effects. A fresh slot is reused provider-free. A missing,
stale, differently scoped, or older-ruleset slot is regenerated and saved
through the same shared Compare execution path before the Meld session is
created. An invalid stored artifact still fails closed.

The fresh-slot handoff is provider-free. The new Meld session embeds the
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
direct Memory content, source order, and equal-authority instructions. Context
names remain local presentation metadata: sending advisor names is unnecessary
for comparison and could introduce identity or ordering bias. The provider may
return only `overview`, `reports`, `relations`, and `issues` under a strict
JSON schema.

The four reports are produced in the same one-shot call as the exhaustive
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

Schema version 2 adds these reports. Schema-version-1 artifacts remain
strictly readable and preserve their old serialization shape so they can
participate in ordered-slot replacement CAS. Ruleset version 3 requires
reports for newly created analyses, so an unchanged pair with a version-1/2
analysis is refreshed rather than reused.

The schema deliberately omits JSON Schema `uniqueItems` because the Codex
structured-output subset rejects that keyword. Alias uniqueness remains an
invariant and is enforced by the strict local parser before an analysis can
be saved.

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

Compare has no independent direct-Memory count gate. It accepts the complete
frozen pair while its encoded input fits the shared 1,000,000-character
effective provider capacity, and rejects an over-capacity frame rather than
truncating or hiding retrieval calls.

After provider latency, both Contexts are reloaded while their cooperative
write locks are held. Their complete records must still match the analysis.
The ordered slot is also compare-and-swapped against the analysis UID observed
before the call. A changed source or newer concurrent analysis prevents the
new result from being saved.

Comparison artifacts copy source text and derived explanations. Deleting
either bound source therefore removes both ordered orientations involving
that Context. Compare never opens query-only sources.

## Interactive workbench, compact snapshot, and exact ledger

In a TTY, a newly completed or reopened analysis enters one read-only
workbench. The upper Viewer receives roughly seventy percent of the available
content height and initially preserves the complete compact report. The lower
item navigator is deliberately short: it contains individually selectable
report sections, individual Potential Conflict items, one explicit Relation
Ledger boundary, and every relation in that exact saved ledger as compact
single-line rows. Relation count therefore increases scroll depth without
taking the report's reading area away.

The Viewer is focused initially. `Tab` or `Shift-Tab` switches focus between
the upper Viewer and lower item navigator. `Up`/`Down` scroll the Viewer when
it is focused by jumping to the previous or next semantic section heading, and
move the selected item when the navigator is focused. The Viewer retains the
complete report and moves a hidden cursor anchor between semantic headings.
While the next heading remains inside the visible viewport, only the blue
focus line moves. Prompt-toolkit scrolls the Viewer by the minimum required
amount only after that anchor crosses the upper or lower boundary. Upward
navigation follows the same boundary behavior instead of forcing every focused
heading to the first line;
`PageUp`/`PageDown` scroll the Viewer by a larger step from either pane.
The panes are titled `VIEWER` and `ITEMS`. Both use the same focused-frame
border and label styling as Ground, so the active pane remains visually
explicit in addition to the footer's textual `FOCUS` indicator. Within the
Viewer, the current logical section identity is rendered in the common focus
color without rewriting the report heading. The focus overlay and hidden
viewport anchor identify the exact semantic section while leaving snapshot and
persisted report text unchanged. Compare projects those blocks into the shared
`SemanticViewerDocument`, so navigation order and rendering order come from the
same stable section identities.
Selecting a lower item replaces the Viewer content with that item's report or
source-linked detail, while returning to the first `REPORT` item restores the
whole report. `Left`/`Right` select an exact source frame when one is available,
and `Enter` expands the selected section, conflict, or relation. The renderer
escapes each untrusted line separately so trusted report layout newlines remain
real terminal newlines rather than visible `\\n` text. Cursor, scroll, source,
focus, and expansion state remain process-local and are never written into the
analysis artifact.

`B` is the explicit detail-back action: it selects the first `REPORT` item,
collapses any source detail, and resets Viewer scroll. `Escape` performs the
same back action while a detail item is selected, but closes Compare when the
complete report is already selected. `Q` always closes Compare. Keeping Back
and Close distinct prevents a person from losing the workbench merely while
trying to leave one deeply inspected relation.

`R` leaves the workbench and runs Rationale for the selected exact source
Memory. It never invents a rationale for an aggregate report or relation: an
issue first resolves to its linked relation, and the source selection supplies
the exact Context name and Memory UID. The normal Rationale grant boundary
still applies, so granted READ material exposes current readable-subtree
inference but not authority Trace or checkpoint history.

`L` leaves the workbench and prints the complete static ledger. `M` leaves and
opens Meld's result-target picker. The picker can select an existing empty
local Context or validate one new exact name; it creates nothing itself. Meld
then revalidates the frozen Compare UID, both source bindings, grant/transfer
policy, and the target before atomically creating any new result and its
target-bound session. `Q` closes with no semantic or durable change. These
actions deliberately exit rather than returning to a hidden cursor so their
terminal output remains visible; bare `mem compare` is the stable resume
route.

Non-TTY execution and explicit `--snapshot` use the compact report ordered by
decision relevance:

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

The footer uses the canonical compared Context name, not the raw relative
locator, and display-escapes terminal controls after POSIX shell quoting.
Running it immediately reuses the current Reference. If current state later
changes, the person must first switch back to the Reference named in the
header; Compare has no stateless `--from` operand.

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
