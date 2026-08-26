# Shared semantic review shell

## Decision

The original shared review-shell design covers two implemented surfaces:

```text
mem review ambiguities
mem review atomize
```

The ambiguity adapter consumes the existing read-only `find-ambiguities`
result and uses the older global review-session artifact. The atomize command
family consumes one Context-scoped aggregate analysis and uses a separate
Context-scoped workbench. It exposes proposed splits, atomize uncertainties,
one-source ambiguities, and two-source conflicts from that same analysis.
Both surfaces use the same list/detail/choice/response interaction pattern,
but they deliberately retain different persistence and evidence contracts.
The separately implemented symmetric `mem meld` workbench now reuses that
interaction grammar with a Context relation ledger and explicit application
boundary; it is not a third adapter over the same review-session artifact.
The static ambiguity finder remains independently callable and read-only:

```text
mem find-ambiguities
```

The common Resolution Session is the only live host for the older global
ambiguity Review. The former `commands.review_shell` prompt-toolkit app had no
production caller after that migration and was removed rather than retained as
a second left/right and TextArea grammar. Its deterministic non-TTY projection
now lives in `interfaces.cli.review`; moving that pure presenter does not alter
the saved Review schema, the `REVIEW · n/total · REQUIRED/OPTIONAL` detail, the
operation-authored choices, or the independent inline Response control.

This separation preserves the difference between discovery, response,
reanalysis, and application. `find-ambiguities` reports a judgment;
`review ambiguities` lets a person select a proposed reading and/or add
clarification evidence. `mem impact atomize` is the primary atomize workbench
entry; bare `mem atomize` and `mem review atomize` resume its exact saved
analysis/workbench without another provider call. When no analysis exists,
bare `mem atomize` may create that first analysis once; `mem review atomize`
does not. Eligible unary responses
influence a new proposal only after explicit
`mem impact atomize --with-review`; that reanalysis still edits no Memory and
creates no checkpoint. `mem atomize --save` or `--save-as` remains the only
atomize mutation boundary.

The finder-wide prompt contract is strengthened to request English candidate
readings and English operational explanations for this shared output. Its
storage and mutation contract is unchanged, but its visible language behavior
for non-English Contexts is therefore intentionally different.

The current implementation also supports:

```text
mem review                 # resume global review, or atomize as fallback
mem review --snapshot      # print one stable, non-interactive frame
mem review ambiguities --new             # explicitly rescan the same frame
mem review ambiguities --replace-review  # compatibility alias / corrupt-state recovery
mem review atomize --replace-review      # reset mutable workbench state
mem review atomize --respond-to UID --response TEXT  # save without a TUI
mem impact atomize --refresh             # explicit unframed reanalysis
```

## Aggregate saved-Review selector

TTY bare `mem review` projects the independently enumerable Atomize, Compare,
Meld, and Sever artifacts, the Update/Impact singleton, and the older global
Review singleton into the common picker. This is a union of existing operation
records, not a new universal Review persistence model. In particular, the
ambiguity Review appears exactly once; the launcher does not imply unavailable
history behind its global latest slot.

The selector sorts recent-first, allows Context grouping and filtering,
freezes one selected operation kind and record key, and revalidates that exact
artifact before rendering. It does not rescan semantic input, replace a
review, call a provider, promote staged evidence, or expose an Apply action
merely because a row was selected. Every retained operation state remains
visible; this is not a completed-only history view.

TTY bare `mem review` now opens the aggregate saved-session launcher. Choosing
an Audit row resumes the exact saved three-finder snapshot and its response
ledger without rerunning a provider. Choosing an Atomize row resumes its exact
analysis/workbench, while choosing the older global ambiguity Review resumes
that singleton in this shell. Non-TTY and explicit snapshot/response
compatibility forms retain the prior precedence: the global Review slot first,
then the current Context's Atomize workbench.

Standalone conflict and update have existing semantic producers but no
dedicated adapter in this shell yet. Conflict issues produced inside an
atomize analysis are reviewable in the atomize workbench, but their pairwise
responses remain staged. `reconcile` and `distill` remain future or
design-only operations. The separate `mem meld` workbench now reuses this
list/detail/comment/accept interaction grammar while retaining its own
Context-to-Context relation ledger and mutation contract.

## Implemented atomize grounding and next direction

One selected atomize issue can now start a multi-turn grounding dialogue: the
agent
states its provisional understanding, surfaces a concrete required
consequence, asks whether a plausible downstream scope extension is intended,
accepts correction or confirmation, and only then proposes exact Memory
changes.

This direction is modeled on grounding in ordinary human communication rather
than on one-shot form submission. A later reviewer turn may supersede an
earlier interpretation, so comments cannot simply be concatenated into one
declared frame. Agent inference must remain distinct from user confirmation,
and no proposed implication may mutate Memory before explicit permission.

The implemented atomize-specific entry points are:

```text
mem atomize --evaluate ISSUE [--comment TEXT]
mem atomize --reply TEXT
mem atomize --accept-grounding
mem atomize --keep-review-only
```

This dialogue is an atomize grounding session, not an extension of the global
ambiguity-review artifact. One resumable latest record is paired with
immutable Context-scoped records for terminal `APPLIED` and
`KEPT_REVIEW_ONLY` dialogues. Its turn lineage now uses the common meld
revision contract and exposes a lossless issue-scoped directional adapter;
the atomize-specific issue, assessment, and persistence schema remains intact.

The full motivation, state machine, evidence boundary, mutation contract,
provenance requirements, and rejected alternatives are recorded in
[`mem-review-conversational-grounding-design-rationale.md`](mem-review-conversational-grounding-design-rationale.md).

## Motivating interaction

An ambiguity finding can offer useful readings without fully containing the
reviewer's answer. For example, the source may contain:

```text
같은 NFC 쓰는데 교직원들만 출입 가능하다.
```

The finder can propose English readings such as:

```text
[DOMINANT]    The door uses the previously described NFC mechanism.
[ALTERNATIVE] The door accepts the same credential and permission rule.
```

A reviewer must be able to say that the first reading is right while adding
that authorization at this particular door is restricted to staff. Requiring
the reviewer to classify that response as either a refinement, comment, or
replacement adds a premature judgment and does not improve the stored
evidence.

The shell therefore has exactly one freeform control:

```text
REFINE, COMMENT, OR ENTER A DIFFERENT READING
> ____________________________________________
```

The session stores only:

- the selected proposed-reading identity, if any; and
- the reviewer's freeform response exactly as entered.

This represents all of the following without guessing a subtype:

- accept a proposed reading with no comment;
- select a reading and qualify or correct it;
- comment on the finding without selecting a reading;
- enter an entirely different reading.

The raw response is clarification evidence. It is not automatically treated as
canonical Memory content, translated, or merged into the source. A future
reconciliation/apply contract must show a proposed edit and preserve
provenance before it can mutate the Context.

## Atomize workbench responses

The atomize workbench is broader than its earlier uncertainty-only adapter. A
single aggregate analysis provides:

- atomize classifications and proposed children for every direct Memory;
- source-linked understanding, change, and unresolved overview sections;
- one-source ambiguity findings with reading choices; and
- two-source `YES`/`MAY` conflict findings.

All issue kinds use the same freeform control:

```text
REFINE, COMMENT, OR ENTER A DIFFERENT READING
> ____________________________________________
```

Where a finding offers readings, the selected reading identity and verbatim
response are stored independently. A source, proposed child, reason, and
reading are terminal data; none is rewritten just to fit the shell.

The ordinary workflow is:

```text
mem impact atomize                    # create once, then resume
mem atomize                           # resume the same analysis/workbench
mem review atomize                    # compatibility resume
mem impact atomize --with-review      # explicit reviewed reanalysis
mem atomize --save                    # or --save-as NEW_CONTEXT
```

`mem impact atomize --refresh` is the separate explicit unframed reanalysis
boundary. Ordinary entry, resume, snapshot, sorting, and layout changes never
call the provider. A Context change makes the saved analysis stale and fails
closed rather than silently replacing what the user reviewed.

An eligible response on a one-source issue can become an untrusted,
per-Memory **declared frame** during `--with-review`. It is not concatenated to
the Memory, treated as a globally true Context fact, or accepted as a child
assertion. Local validation still requires every proposed child to cite at
least one literal span from the original Memory. A declared frame can support
an additional qualifier, but it cannot create a frame-only child. Original
source spans and declared-frame spans are stored separately and remain
distinguishable through `mem trace` and `mem rationale`.

A response on a conflict stays attached to the exact two-source issue. It is
not converted into a declared frame for one side merely so atomize can consume
it; `--with-review` rejects a workbench with any answered pairwise issue before
the provider is called. This includes a workbench containing both unary and
pairwise answers: the prototype has no review archive, so creating a fresh
workbench while skipping only the pairwise answer would erase it. Those
responses remain staged for a future reconcile contract.

If two answered unary issues point to the same Memory, `--with-review` also
fails closed. The current trace schema can bind a declared frame to one issue
UID, not an ordered set of origins. The user must consolidate the exact context
into one response and clear the other instead of accepting misleading
provenance.

The workbench is bound to the exact Context UID, ordered direct-Memory digest,
analysis UID, issue projection digest, and selectable reading identities.
Explicit reanalysis creates a new analysis UID and a fresh workbench; comments
are never migrated implicitly. Only the latest analysis/workbench pair is
retained per Context, so a full revision archive and analysis-to-analysis diff
remain future work.

An eligible saved response is also a save gate. `mem atomize --save` and
`--save-as` refuse if the selected analysis does not record the same workbench
UID and semantic response digest. Applying a reviewed analysis copies the
declared frame, digests, reason, and per-child source/frame citations into
checkpoint trace metadata. This durability is also a privacy boundary: an
applied comment is retained in Context checkpoint history, not only in the
replaceable workbench file.

## Ambiguity explanation and reading roles

The finder retains its two independent machine judgments:

```text
interpretation: SINGLE | DOMINANT | COMPETING
clarification: NONE | HELPFUL | REQUIRED
```

The review UI renders both under `CLASSIFICATION` and renders the provider's
reason under `WHY THIS IS UNCLEAR`. The provider is instructed to connect the
two axes to a concrete consequence:

- `REQUIRED`: name what cannot be determined reliably;
- `HELPFUL`: name what can still be done and what would become more precise;
- `NONE`: explain why no operational result depends on resolving the
  readings.

When one uncertainty affects several decisions, the reason can use additional
sentences. Generic topic labels such as `access` or an unsupported
`AFFECTED 5` count are not a substitute for saying what remains undecidable.
The current finder schema does not return structured downstream-result IDs, so
the shell does not invent counterfactual counts.

Reading roles are derived locally rather than added as a fourth semantic
label:

| Machine interpretation | Presentation roles |
|---|---|
| `SINGLE` | the one reading is `[SINGLE]` |
| `DOMINANT` | the first reading is `[DOMINANT]`; later readings are `[ALTERNATIVE]` |
| `COMPETING` | every reading is `[COMPETING]` |

`ALTERNATIVE` is presentation metadata only. The machine-level interpretation
remains `DOMINANT`.

Proposed readings, reasons, and clarification questions are requested in
English even when a source Memory is in another language. The source is always
shown unchanged in its original language. A freeform response can be entered
in any language and is preserved verbatim.

## Ordering

`Memory` currently contains only `uid` and `content`; it has no creation
timestamp. The default `SOURCE` mode therefore means canonical direct-Memory
order from `Context.order`, not chronological creation order and not the
grouped presentation order of `mem ls`.

For this user-study prototype, canonical Context order is the explicit
encounter-order convention. A future timestamp design must add
`Memory.created_at`, define migration behavior for older records with unknown
times, and specify branch/merge semantics. Checkpoint times, UUID values, and
JSON dictionary order must not be presented as Memory creation time.

The shell also offers `PRIORITY`. For the standalone ambiguity adapter it
orders the clarification label as:

```text
REQUIRED → HELPFUL → NONE → canonical source order
```

The atomize workbench also has conflicts, atomize uncertainties, and proposed
splits. Its grounded priority tiers are:

```text
conflict / atomize uncertainty / REQUIRED ambiguity
-> HELPFUL ambiguity
-> NONE ambiguity / proposed split
-> canonical source order within a tier
```

It does not claim to rank by the number of downstream proposals changed.
Doing that correctly requires structured, identifiable consequences and a
counterfactual recheck for each reading. That remains a separate extension.

## Durable state and stale detection

The full-screen terminal is not the source of truth. The older ambiguity
adapter stores one global prototype session atomically in:

```text
~/.mem/review-session.json
```

The atomize workflow stores one latest analysis/workbench pair per Context UID
and retains displaced pairs by analysis UID:

```text
~/.mem/atomize-analyses/<context-uid>.json
~/.mem/atomize-workbenches/<context-uid>.json
~/.mem/atomize-session-history/<context-uid>/<analysis-uid>.json
```

Completed `mem audit` runs use a multi-session UID catalog rather than a
latest slot:

```text
~/.mem/quality-audits/<audit-uid>.json
```

Each Audit record keeps its immutable frozen Source, all three typed finder
reports, and per-check ruleset/provider provenance beside a CAS-protected
mutable response ledger. Unlike the current-frame ambiguity and Atomize
adapters, `mem review audit --session UID` is historical review: a later live
Context change does not reinterpret or invalidate the frozen artifact.

The relevant records include:

- schema version and session UID;
- adapter kind;
- Context UID and name;
- a digest of every directly owned Memory UID and content in canonical order;
- the exact atomize analysis UID and immutable issue-projection digest;
- finding labels, arity, source order, priority, reasons, questions, and
  proposed readings when an issue has choices;
- current cursor and sort mode;
- atomize workbench layout; and
- selected readings and verbatim freeform responses.

State is saved before terminal control begins so a PTY disconnect does not
lose the expensive semantic report or its binding. On resume, any change to
the Context identity, direct-Memory content, or canonical direct-Memory order
makes the relevant session stale. The shell refuses to reinterpret an old
answer against a new local frame.

An unfinished global ambiguity adapter resumes for the same frame and blocks a
different frame until `--new` is supplied. Once every item is answered, or the
finder returned no items, a distinct Context frame automatically becomes new
work. The displaced terminal session and its original direct-Context snapshot
remain UID-addressable, read-only evidence. An exact terminal retry still
resumes provider-free; `--new` explicitly reruns the same frame, while
`--replace-review` remains a compatibility alias and malformed-state recovery
route. `mem review atomize --replace-review` continues to reset only the
current Atomize workbench. Atomize reanalysis uses `mem atomize --refresh`,
`mem impact atomize --refresh`, or `--with-review` as appropriate.

Deleting a Context removes its analysis and workbench. It also deletes the
global review when that artifact names the deleted Context, while preserving a
global review for another Context. This avoids retaining a freeform comment
after its interpretation frame has been removed.

References, embedded Contexts, and query-only views remain outside the
direct-Memory review boundary. Review never opens legacy `query-sources/` or
authority Contexts reachable only through a `QUERY` grant.

The global ambiguity adapter retains one mutable active slot, plus immutable
terminal history by UID. Atomize workbenches remain isolated by Context UID
with one mutable latest slot, but displaced analysis/workbench pairs are also
retained by analysis UID. Concurrent mutable Review writers still use the
legacy last-write behavior; terminal rotation does not claim a new general
cross-process response-edit CAS.

## Terminal and chat-controller boundary

The older standalone ambiguity shell remains a compatibility entry point and
accepts ordinary concrete terminal input through prompt-toolkit. Its frames now
use the same one-column composition rule as the common Resolution Session:

- left/right: previous or next issue;
- up/down or digits: select a proposed reading when the current ambiguity
  finding offers choices;
- Enter or Tab: focus the freeform response;
- Escape: return from Response to issue navigation, then close from the root
  issue surface;
- F2 or Ctrl-S: save and move to the next issue;
- `S`: toggle source/priority order;
- `Q` or Ctrl-C: save and close.

The atomize workbench now keeps the same list/detail/choice/response semantics
but uses a visible drill-down interaction: up/down moves through issues, Enter
expands the current issue, up/down then moves through its readings, and Enter
toggles the focused reading. Escape or Backspace returns one level and Tab
enters the response field. This intentionally replaces its numbered-choice
shortcut; the exact atomize key contract and migration reason are recorded in
`mem-atomize-workbench-design-rationale.md`.

These keys are not a natural-language command grammar. In a Codex chat, the
controlling agent observes the current frame, translates instructions such as
“오른쪽,” `->`, “4번,” or `답 "..."` into the appropriate PTY events, performs
the operation, and returns an actual snapshot. The PTY is transport and view;
the saved ReviewSession is durable semantic state.

Model-produced and stored strings are rendered as terminal data. Newline and
tab remain explicit layout, while all other Unicode `C*` categories and
`Zl`/`Zp` line separators are replaced before entering the PTY so a proposed
reading cannot inject terminal escapes, bidi reordering, or invisible format
behavior.

## Shared shell, separate operation semantics

The visual shell is shared, but each adapter retains its own evidence and
response contract:

| Adapter | Status | Primary source unit |
|---|---|---|
| ambiguity | implemented | one Memory plus proposed readings |
| atomize workbench | implemented | typed split, uncertainty, one-source ambiguity, and two-source conflict issues from one exact analysis |
| standalone conflict | future adapter over an implemented finder | two Memories plus conflict scope |
| update | implemented read-only Resolution Workbench projection over exact Update artifacts; semantic issue turns remain future | target Memory/edit, addition, or removal |
| reconcile | future semantic contract | ambiguity/conflict evidence and proposed resolution |
| distill | design-only | summary claim and supporting Memories |
| meld | implemented shared Resolution Workbench adapter | two direct-Memory peer Contexts and one empty result target |
| Context-directional meld | implemented shared Resolution Workbench adapter | INCOMING and BASELINE Context frames |
| sever | implemented partial adapter | one Source × one Criteria disclosure boundary |

The Update projection consumes the existing `impact-plan.json` and
`staged-update.json` contracts rather than creating a competing generic source
of truth. A future Update resolution session must remain separate and export a
ready exact plan into that existing application contract. Similarly, an atomize conflict response retains its pair-shaped
semantics even though it uses the same list, detail, choice, and response
controls: it stays staged for reconcile rather than becoming a unary declared
frame.

## Alternatives considered and why they were not selected

The shell design emerged through several narrower alternatives. Recording them
matters because some remain plausible future modes, while others would erase
evidence or overstate what the prototype knows.

### Static report only

The existing `find-ambiguities` output could have remained the only interface.
It is suitable for logs and scripts but cannot preserve which proposed reading
a reviewer accepted or what additional context they supplied. The static
finder therefore remains available, while review is a separate consumer
rather than a replacement.

### Review one issue at a time without an overview

A sequence of isolated yes/no prompts was considered. It hides the size and
shape of the review, makes prioritization difficult, and gives a remote
controller no stable overview to return as a snapshot. The selected design
uses a vertical issue list plus one expanded detail. Older split-layout
implementations were retained only while the shared Resolution Session was
introduced; current live screens use one stacked presentation so visible frame
order and keyboard order cannot diverge.

### Separate refinement and replacement inputs

An earlier screen had both `REFINE THE SELECTED READING` and
`ENTER A DIFFERENT READING`. Real answers can do both at once: a reviewer can
accept a candidate, correct one clause, and add a missing scope condition.
Forcing a subtype before later reconciliation would manufacture metadata.
The shell therefore stores a selected candidate and one raw response under:

```text
REFINE, COMMENT, OR ENTER A DIFFERENT READING
```

### Generic `AFFECTED` topics or one opaque score

Showing `AFFECTED 5` followed by topics such as `access` or `parking` was
rejected because it does not explain why clarification is needed. It can also
make an unsupported model estimate look like a measured dependency. The
current screen instead says what cannot be determined for `REQUIRED`, what
would become more precise for `HELPFUL`, or why no decision depends on
resolution for `NONE`.

The more ambitious alternative—ranking by the number of concrete required and
helpful downstream results changed—remains useful, but it requires structured
result identities and per-reading counterfactual rechecks. Until that contract
exists, `PRIORITY` uses only the finding's declared clarification class and
does not present a fabricated count.

### True time order, Context order, or importance order

True creation-time ordering was considered first, but the current Memory
schema has no timestamp. Inferring time from UUIDs, checkpoints, or JSON order
would be false. Canonical Context order is therefore the reproducible
user-study default, and clarification-class priority is an optional alternate
view. A real chronological mode remains tied to the explicit
`Memory.created_at` TODO.

### A natural-language command parser inside `mem`

The CLI could have implemented literal rules for Korean and English commands
such as “오른쪽,” `->`, or “4번.” That would duplicate chat interpretation,
be brittle across languages, and confuse issue numbers with reading numbers.
Instead, the TUI exposes ordinary keys. A controlling agent interprets the
user's current instruction against the visible frame, sends the necessary PTY
events, and returns the resulting snapshot.

### PTY state as the only session

Keeping all state inside one full-screen process is smaller, but a disconnect,
app restart, or context compaction would lose both the semantic report and the
reviewer's progress. The selected design treats the PTY as transport and saves
semantic state atomically. A Context fingerprint prevents convenient resume
from becoming silent reuse of stale findings.

### Apply clarification immediately

Immediately rewriting a Memory after a selection would make the interaction
look complete, but the freeform response has not yet been classified or
normalized. It may be a comment rather than replacement content. Ambiguity
responses therefore remain staged evidence for a future reconciliation/apply
contract. Eligible unary atomize responses have a narrower implemented
consumer: `mem impact atomize --with-review` treats them as per-Memory declared
frames and produces another non-mutating analysis. Pairwise conflict responses
remain staged and block that reanalysis rather than being dropped when the
single workbench is replaced. Only a later explicit `mem atomize --save` or
`--save-as` can apply the reviewed atomize proposal.

### Build a fully generic operation framework first

Conflict, update, atomize, reconcile, distill, meld, and sever can share
list/detail/response interaction patterns, but their source arity, evidence,
and mutation boundaries differ. A generic schema invented before those
contracts exist would either be vague or encode ambiguity-specific assumptions
under generic names. The implementation first proved the global ambiguity
adapter, then built a Context-scoped atomize workbench with the same interaction
language but an analysis-bound issue digest, multiple typed issue shapes, and
an explicit reanalysis gate.

### Keep atomize review uncertainty-only

The first atomize adapter exposed only `UNCERTAIN / RECONCILE` records. That
made comments possible but hid proposed split children, the source-level
content overview, ambiguities, and pairwise conflicts returned by the aggregate
analysis. The implemented workbench therefore starts conceptually at
`mem impact atomize` and presents all actionable typed issues. The older global
review format remains readable only as a compatibility input to reviewed
reanalysis; it is not the final atomize interface.

### Translate or rewrite the source for display

Normalizing every source Memory into English would make the screen uniform but
would hide whether the model misunderstood the original wording. The source is
therefore displayed verbatim, while proposed readings and operational
explanations use English as the comparison language. Reviewer input remains
verbatim in whatever language was entered.

## Intentional non-goals

The standalone ambiguity review and non-applying atomize impact/review
workbench themselves do not:

- resolve, edit, add, remove, or checkpoint a Memory;
- synthesize the freeform response into an English replacement;
- decide whether an ambiguity response is a refinement, comment, or different
  reading;
- treat an atomize comment as trusted source text or let it create a child
  without an original-source citation;
- move comments to a later atomize analysis automatically;
- turn a pairwise conflict response into one source's declared frame;
- calculate unsupported affected-Memory or changed-proposal counts;
- infer true creation chronology;
- archive multiple atomize analysis revisions or lock concurrent writers to one
  Context; or
- implement standalone conflict, update, reconcile, or distill
  adapters. Context meld is implemented in its own workbench rather than
  pretending its peer relation ledger is an ambiguity-review artifact.

These boundaries keep the first shell useful for the user study while making
its evidence, mutations, and future claims inspectable.

## Memory report picker ownership

The shared read-only Memory report picker used by `mem trace` and
`mem rationale` is owned by
`memcommit.interfaces.tui.components.memory_report_picker`. The established
`memcommit.commands.shared.memory_picker` path remains an exact module alias so
existing imports and legacy-path monkeypatches reach the same implementation
globals.

This is an ownership-only relocation. The implementation body moved without
changes; picker state, Context reach, row projection, terminal checks,
validation and error text, selection receipts, and cancellation behavior are
unchanged. Trace and rationale may continue importing the compatibility path
while their command modules are being changed for unrelated reasons.

## Shared terminal chrome

Review now imports terminal sanitization and slot-based frame composition from
the neutral TUI layer also used by Ground and meld. This is presentation reuse
only. Review retains its list/detail navigation, response autosave, finder
evidence, and non-applying boundary. It does not acquire Ground's exact-command
approval semantics merely because the frames share components. The boundary is
specified in
[`shared-tui-command-review-design-rationale.md`](shared-tui-command-review-design-rationale.md).
