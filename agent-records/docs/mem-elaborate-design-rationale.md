# `mem elaborate` design rationale

## Purpose

Elaborate owns top-down proposal generation that must not be confused with
evidence-bound Distill:

```text
Goal  --Elaborate--> suggested Rules
Rules --Elaborate--> suggested FIT / BOUNDARY / CONTRAST Case propositions
```

All outputs are `[Suggested] [Unverified]`. A Goal is intent rather than
evidence, and generated Cases are not real-world observations. Each direction
must nevertheless return a complete candidate set. Elaborate exists to make an
abstract or underspecified idea concrete enough to inspect and correct, so a
sparse input is not a valid reason to return an empty result. Omitting the
number means exactly three proposals in both directions. `--n N` (also `-n`
and `--number`) overrides that default with another exact count or the complete
operation fails. Exact count applies to ordered, UID-backed proposal
occurrences, not distinct content: repeated Rule content or Case propositions
remain valid within one proposal set when repetition is intended or useful.
When an existing Target supplies ambient Memories, however, an output that
only restates one of those Memories is rejected before validation or Add.

## Shared application contract

`ElaborateRequest` accepts exactly one direction: one nonempty Goal or one or
more distinct nonempty Rules, plus an optional override for the exact proposal
number and a Rules-to-Cases-only strict flag. The normalized request always
carries an exact count, defaulting to three, and one explicit quality policy.
`BEST_EFFORT` is the default; `STRICT` is selected only by `--strict`.
An explicit count may be any positive integer; three is a default, not a
maximum. `ElaborateSemanticConfig` owns optional host-injected directional
safety ceilings plus the text, rationale, overview, and response limits. Both
directional ceilings are `None` in the ordinary CLI and public API contract.
One complete request is
`WHOLE_FRAME_ONLY`; hidden batching could duplicate, omit, or distort the
requested proposal set. Input normalization occurs before prepared lookup; on
an exact prepared miss, the one-turn budget is validated before provider
construction.

Provider output uses a strict direction-specific schema. Both directions
return exactly three proposals by default, while `--number` fixes both JSON
Schema bounds to the requested override.
The ordinary supported count domain is therefore every positive integer in
both directions; there is no fixed product-level count ceiling. A host that
injects a nondefault configuration may set a positive directional one-turn
ceiling. The provider instruction, decoder, typed analysis validator,
prepared-result check, and atomic publication count all share the exact request
value. A count mismatch publishes nothing. General provider input and response
envelope limits remain independent of this count contract, so a provider may
still fail an exceptionally large exact request rather than silently reducing
its count. Strict Rules-to-Cases also fails before provider construction when
the complete Rule-by-Case Conformance/Fit validation frame exceeds the shared
whole-frame item or text limits. Best-effort does not inherit limits belonging
only to semantic calls it does not make.

Proposal identity is not derived from normalized content. Every returned Rule
or Case has a distinct proposal UID even when its content repeats, and
standalone Add materializes every occurrence as a separate Memory with its own
UID. Content equality therefore neither invalidates the analysis nor silently
reduces the requested count. This matches the Store's identity model and keeps
intentional repetition observable in Context order, receipts, Review, and
Undo. Reusing one proposal UID remains invalid because that would collapse two
ordered occurrences onto one identity. This allowance applies among new
occurrences in one request; it does not authorize re-adding content already
present in the frozen Target ambient frame.

Every Case is classified as `FIT`, `BOUNDARY`, or `CONTRAST` and carries one
ordered `rule_checks` entry for every current input Rule. An individually
applicable Rule must hold for that Case. A family-level Rule such as a seed,
ordering, position, or recurrence invariant instead governs the ordered
collection, so it need not be restated by every member in isolation. A contrast
may appear in the rationale but is not stored as a violating Example.
Structural domain validation and active-config validation are separate so an
injected configuration is applied consistently to live and prepared output.

Every generative provider prompt quotes the complete café, lost-property, and Cloze
Rule/Example reference pairs. Rules-to-Cases reads them in the generative
direction. Goal-to-Rules uses their Rule sides as examples of independently
reviewable Rule form and their paired Example sides as the reason those Rules
are operational. The references are present in both directions but never
become current input Rules: `rule_checks` still range exactly over the
request's Rule tuple. Provider contract version 4 prevented an unreferenced
prompt result from replaying; version 5 introduced typed Target ambient
context, version 6 introduced an optional exact proposal number, and version 7
makes the omitted number normalize to the exact default of three. Version 8
removes the ordinary directional count ceilings so every positive explicit
count reaches the exact one-turn contract. Version 9 makes proposal identity
UID-backed rather than content-backed and explicitly admits repeated output
content without weakening exact count or complete Rule coverage.

Provider contract version 10 added mandatory post-generation validation for
Rules-to-Cases. Provider contract version 11 corrects its validation unit:
every Source Rule must conform over the complete ordered collection, every new
Case must conform under at least one applicable Rule without violating any
Rule, and the complete Source/Target-prefix/generated-Case frame must receive
general Fit `YES` before an analysis can be returned or published.

Provider contract version 12 generalizes the generation prompt from
"every Case shows every Rule" to parent/child applicability without changing
the exact-count or validation schema. The provider must first distinguish a
conjunctive record schema, whose Rules jointly constrain every child, from
independent sibling criteria, conditional subfamilies, diagnostic indicators,
and collection-level relationships, whose coverage may be distributed across
children. Every `rule_checks` row is still present so the complete parent frame
is read; its evidence now identifies `APPLIES`, `NOT APPLICABLE`, or
`COLLECTION` meaning. For an ordered Target prefix, materially used references
must establish origin, position, and lineage, not merely name the final two
operands needed to compute the next member.

Provider contract version 14 separates generation quality from optional
acceptance gating. A best-effort analysis retains no strict validation object;
a strict analysis must retain complete collection Conformance and Fit evidence.
Prepared reuse, digests, public projections, agent projections, and Add receipts
bind this policy so validation state cannot be replayed across modes.

### Best-effort default and optional independent Source validation

Generator-authored `rule_checks` remain useful evidence pointers, but they are
not acceptance evidence because the same turn produced both the Case and its
self-assessment. Default Rules-to-Cases nevertheless stops after that one
generation turn and publishes the structurally valid exact-count collection as
`SUGGESTED`, `UNVERIFIED`, and `BEST_EFFORT`. It does not run Conformance or Fit
and then hide or ignore their result. This keeps Elaborate a responsive proposal
operation and leaves strict assessment to an explicit `--strict` request or the
separate `mem check-conformance` operation.

Strict Rules-to-Cases composes two existing judgment contracts after generation.
Context Conformance checks every Source Rule over one ordered frame: materially
referenced Target Memories first, then generated Cases. Every Rule-level
judgment must be `CONFORMS`, and every generated Case must be a conforming
governed member; different members may be governed by different applicable
subsets. General Fit then checks the complete Rule and Case collection once,
with referenced Target Memories as explicit background, and must return `YES`.
`VIOLATES`, `PARTIALLY_CONFORMS`, `NOT_APPLICABLE`,
`INSUFFICIENT_EVIDENCE`, Fit `NO`, and Fit `MAY` all fail strict publication;
the operation does not silently reduce or regenerate the requested set.

Fit remains compatibility rather than factual grounding. A concrete value
that does not appear in Source is allowed when it is a legitimate Rule
instantiation and creates no Source contradiction. The validation must not
treat missing support as incompatibility, establish objective truth, or turn a
synthetic Case into real-world evidence. Both policies therefore remain
`SUGGESTED` and `UNVERIFIED`; strict means Source compatibility was checked,
not that the generated Case became true or accepted evidence.

Each invoked semantic primitive keeps one complete frame: generation is always
`WHOLE_FRAME_ONLY`; strict Conformance judges all referenced Target Memories,
generated Cases, and Source Rules in one turn; strict Fit judges the same
complete collection in one question. No primitive batches or truncates its
frame. The typed Case, digest, public and agent projections, plain detail, and
Add checkpoint retain either `BEST_EFFORT` plus `NOT_RUN`, or `STRICT` plus the
accepted Conformance/Fit result.

### Study failure reconstruction

The policy change was motivated by three recorded Study attempts whose
generation turn completed successfully but whose complete candidate collection
was then discarded by the former mandatory Conformance gate: one 10-Case
attempt in `study-20260825T110027Z-59cb6a29`, and 40-Case and 10-Case Fibonacci
attempts in `study-20260824T170446Z-585b70f0`. Under the best-effort default,
those same control paths stop after structural decoding and make all 60
candidates eligible for atomic Add; `--strict` deliberately retains the former
rejection behavior. Failed-attempt ledgers do not retain provider response
bodies and no Add checkpoint exists, so exact historical candidate strings
cannot be recovered or honestly regenerated after the fact.

The complete ledger-derived reconstruction is recorded in
`agent-records/outputs/elaborate-best-effort-reconstruction-20260825/README.md`. Across the
eight substantive Elaborate attempts in the two Studies, the recorded
generation-boundary counterfactual skips 13 judgment turns and 222.847 seconds
of observed post-generation elapsed time. These observations motivate the
default but are not a provider-latency guarantee.

### Why the former 4/3 ceilings were removed

The first standalone Elaborate slice used four Rule proposals and three Case
proposals as conservative one-turn maxima. When the exact `--number` option was
added, those existing maxima were deliberately retained to avoid making an
arbitrary provider call unbounded. A later change made three the omitted exact
default but left the same maxima in place. That history caused the defect: the
small proposal sets chosen for the initial workflow became public validation
limits, so `--number 5` failed before provider construction even though the
caller had explicitly requested an exact positive count.

The ordinary contract now separates the two concerns. Three is only the
omitted count, while a supplied positive integer is the exact requested count.
Keeping 4/3 as hidden product ceilings was rejected because it makes the
default workflow size silently govern caller capability. Removing all
one-turn safeguards was also rejected: an embedding host may inject an
explicit directional ceiling, and the shared input and response-envelope
limits still fail closed. Hidden batching remains a non-goal because it could
change the meaning or coverage of one exact proposal set.

The nonempty-output invariant is enforced independently by the Provider
instruction, JSON Schema `minItems`, strict decoder, and typed analysis. This
redundancy is intentional: a Provider or prepared lookup cannot turn an empty
array into a successful Elaborate result. The Provider contract version was
advanced when this invariant replaced the earlier zero-proposal behavior.

An injectable exact prepared lookup may avoid provider construction only when
the normalized direction, complete input tuple, exact-number request, quality
policy, and Target ambient frame match. A strict Rules-to-Cases result must
contain validation evidence; a best-effort result must not claim it. There is
no persisted Elaborate cache artifact yet and no subset/projection reuse claim.

## Standalone Add and endpoint contract

Standalone Elaborate is a semantic Add. It generates a complete proposal set
and appends every generated proposition to one existing ordinary Context in a
single checkpoint; there is no `--apply` gate. Best-effort is the default, while
`--strict` adds the independent pre-publication gates for Rules-to-Cases. The
two endpoint options fill
from one Current snapshot:

| Invocation | Source | Target |
| --- | --- | --- |
| `mem elaborate` | Current | Current |
| `mem elaborate --to B` | Current | `B` |
| `mem elaborate --from A` | `A` | Current |
| `mem elaborate --from A --to B` | `A` | `B` |

With no inline input, directly owned ordinary Source Memories are interpreted
as Rules by default and Elaborate generates Cases. `--as goal` instead requires
exactly one direct Memory and generates Rules. This role belongs to the
invocation, not to the Context name: `goals`, `rules`, and other naming
conventions carry no hidden semantics. `--goal` uses the shared Goal operand
and may identify a direct-Memory Context, one direct Memory, or process-local
text. When supplied alone, its exactly one item is also the Goal-to-Rules
generative Source for compatibility. Beside `--rule` or a Context `--from`, it
is auxiliary relevance focus and does not become Source evidence. Repeatable
`--rule` remains available and uses Current or `--to` as its existing Target.
`--n`/`-n`/`--number` has the same exact meaning for inline input, Context input, and
both Ground directions.

Source and Target may be the same Context. The command freezes their common
pre-image before provider construction, so a provider turn cannot consume the
Memories that it generates. A later invocation naturally sees earlier output;
the operation does not maintain a hidden exclusion set across runs. Separate
Source bindings and the Target digest remain locked through the atomic write.
If either exact input changes, no generated Memory is published.

### Exact Target ambient context

Elaborate also treats content already present in its exact existing Target as
ambient destination context. This is narrower than an automatic Profile-wide
read. The selected Goal or Rule tuple remains the generative Source, while the
Target frame helps new proposals preserve the destination's established
terminology, presentation form, distinctions, and useful variation. The three
packaged café, lost-property, and Cloze families still demonstrate how the
operation works; Target ambient items instead describe where this particular
result would live.

The Target graph is frozen before provider construction. Direct ordinary
Memories and live local Context or Memory embeds are followed recursively.
Cycles terminate by Context identity and the same logical Memory is transmitted
once. A dangling or identity-replaced local embed fails before provider
connection rather than becoming a silently incomplete destination frame.
QUERY-only entries contribute only their public Context name; no hidden
content or source identity enters the semantic payload. A persisted granted
Embed contributes content only while `READ`, `EMBED`, `DERIVE`, and `COMBINE`
are all effective. Its Grant binding and authority Context digest are frozen,
held through the provider turn, and revalidated before publication. A
proposal-only Impact or Ground run stops at that boundary. Direct Add also
requires `EXPORT` because the derived result leaves the granted resource and
`SAVE_ANALYSIS` because the durable receipt retains the reviewed analysis;
both are checked before provider connection and again at publication.

For ordered family Rules, ambient Memory order is semantic: referenced Target
Memories form the existing prefix and generated Cases form its proposed suffix.
The provider must continue after the final applicable Target item rather than
restart at a seed. Independently of the provider's explanation, normalized
case-insensitive content equality with any frozen Target Memory fails locally
before optional validation or Add. This is a narrow no-restatement boundary, not
general semantic deduplication; nonidentical overlap still belongs to explicit
reconciliation operations.

When Source and Target are the same Context, directly consumed Source Memory
UIDs are excluded from the ambient frame. Source meaning therefore wins and
the same string is not sent twice under two semantic roles; safe embedded and
query-name context can still remain ambient. An unrelated Context, readable or
otherwise, is never pulled in merely because it exists in the Profile.

Provider output includes `target_context_refs` for every proposal. These
aliases report exactly which ambient items the provider says it materially
used, may be empty, and are locally restricted to the frozen Target aliases.
They do not replace `rule_checks` and do not turn Target Memories into Rule
evidence. The typed analysis, plain and TUI details, public proposal, agent
projection, digest, and version-5 Add receipt retain this trace. The receipt
also records `quality_policy` and `case_validation`, using `NOT_RUN` rather
than fabricating validation evidence for best-effort Cases. Any root,
embedded, referenced, or granted ambient pre-image drift rejects the proposal
or Add without partially appending generated Memories.

Distill intentionally does not receive destination ambient content in this
change. Distill remains a reduction over its selected Source evidence. A later
Distill design may use existing destination Rules for novelty or reconciliation,
but duplicate removal belongs to an explicit reconciliation/Dedun boundary and
must not silently change what the current Source supports.

`mem impact elaborate` runs the same preparation path and displays the exact
would-add set while leaving both endpoints unchanged. Generated propositions
remain explicitly `SUGGESTED` and `UNVERIFIED` after Add; durable storage is
not evidence acceptance.

### Compact Rule rows preserve complete content

Goal-to-Rules catalogs use `[N] CONTENT — SUGGESTED · UNVERIFIED` and
Rules-to-Cases catalogs use `[N] CONTENT — ALL N RULES · UNVERIFIED`. The
suffix stays adjacent to every proposal, while its rationale remains available
in detail instead of consuming a second default catalog row. Case proposals
are classified as `SUGGESTED`, not as generic Resolution `CHANGE` items:
Impact has not mutated either endpoint, and presentation must not imply
otherwise. Their FIT/BOUNDARY/CONTRAST kind remains available in Items and
detail.

The renderer folds stored whitespace into one logical row but never truncates
or paraphrases Rule content. A terminal may visually wrap a long row at its
viewport edge, yet the complete Rule remains present in display projection,
copy output, typed analysis, and any later Add. An ellipsis would be unsafe
here because the omitted tail may carry the condition that distinguishes an
unverified suggestion from a broader claim. Focused and whole-proposal copy
retain the full rationale even though the default catalog keeps it in detail.

`PROPOSED RULES` or `PROPOSED CASES` is the single default report location for
generated Memories. The read-only Impact route hides the generic
`IMPACT`/`[ADD]` effect ledger and Results block in both directions because
they merely restate that catalog. Rationale remains available in detail, and
exact endpoint immutability remains visible in the Context-location header and
close-time digest verification.

Case detail summarizes the structurally exhaustive check as one
`RULE COVERAGE · ALL N` boundary followed by the expected result and any Target
aliases used. It does not replay one provider-authored explanation per Rule:
those explanations remain in the typed result and the full plain/copy
projection, but repeating them on the default Impact canvas added volume
without proving semantic correctness. For the same reason, exact Target
ambient contents are not repeated in the Impact overview. The Target location
and ambient count remain visible, used aliases remain in proposal detail, and
the complete ambient frame remains in the typed result and full projections.

## Ground route

Ground CLI accepts one exact saved Ground and either `--from-goal` or
`--from-rules`, plus the same optional exact `--number` and Rules-to-Cases
`--strict` policy. It calls the same
`run_elaborate` application function. The Ground adapter freezes and
revalidates the exact operation-consumed Goal or Rule frame before and after
the provider sequence. A physical Ground uses
`/rules` as Goal-to-Rules destination ambient context and `/examples` as
Rules-to-Cases destination ambient context; other lanes are not included.
Active Ground Rules are ordinary Memories in the physical `/rules` lane.
Ground Elaborate remains proposal-only by default. Explicit `--adopt`
additionally requires the reviewed whole-Ground
revision and destination pre-image, then appends the complete result to
`/rules` or `/examples` as one revision and one Ground-local Undo unit.

No Elaborate route promotes or accepts a Ground Rule or Case automatically.
The shared focus and adoption contract is documented in
[`goal-focus-operand-design-rationale.md`](goal-focus-operand-design-rationale.md).

## Interfaces

The standalone Context route is plain, line-oriented output by default even in
a TTY. The explicit semantic TUI Viewer and plain CLI project the same typed result. The Viewer
uses shared neutral report chrome and deterministic focused/whole-document
`y`/`Y` copy. The public Python client exposes the same two directions plus
exact Ground projections. Versioned agent and MCP tools expose all four input
forms and the same optional exact-count override, and return
`verification: UNVERIFIED` and `effect: NONE`; this first Add
slice does not silently broaden those callable adapters into mutations.
Agent contract version 3 added the name-only/content-safe Target ambient frame
and per-proposal Target references; standalone public calls without a Target
continue to return no ambient frame. Agent contract version 4 adds accepted
per-Case Source conformance and Fit evidence. Agent contract version 5 adds the
optional `strict` request, explicit `quality_policy`, and nullable Case
validation for best-effort output. Its JSON Schema still publishes no
`maximum` for `number`.

Elaborate currently opens directly on its result Viewer rather than providing
an input-composer TUI. That is intentional for this slice: CLI, Python, or
agent input is validated before provider construction, while a future composer
can remain a presentation adapter over the same request.

The console-specific proposal presentation is co-located under
`memcommit.adapters.console.commands.elaborate`. `proposal.py` owns the stable
plain-text projection, `viewer/` owns the read-only semantic document and
clipboard projection, and `runner.py` selects between those presentations for
the Ground proposal route. These values are proposals rather than receipts:
they explicitly remain `REVIEW ONLY`, `SUGGESTED`, and `UNVERIFIED`, and their
presentation proves no durable effect. Apply and Ground-adoption receipts stay
at their separate mutation boundary. The former operation-specific CLI/TUI
paths and the generic-bootstrap Elaborate factory are removed without facades;
this is an ownership relocation and does not alter proposal text, Viewer
interaction, execution, adoption, or authority behavior.

## Remaining limits

- no durable proposal/review session;
- no automatic Ground promotion or Ground-source Add;
- no persisted hidden-prewarm artifact;
- no interactive input composer; and
- no guarantee that an external provider can fulfill an arbitrarily large
  exact count within one response envelope;
- no promise that exact-count proposal content is unique; repetition is a
  valid, separately identified result; and
- no claim that a best-effort Case conforms to every Source Rule unless a later
  explicit check establishes it; and
- no claim that generated or stored Case propositions are evidence.
