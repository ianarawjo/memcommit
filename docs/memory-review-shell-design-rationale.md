# Shared semantic review shell

## Decision

Memcommit now has one implemented interactive review adapter:

```text
mem review ambiguities
```

It consumes the existing read-only `find-ambiguities` result, saves a durable
review session, and opens a prompt-toolkit terminal interface. The static
finder remains independently callable and read-only:

```text
mem find-ambiguities
```

This separation preserves the difference between discovery and response.
`find-ambiguities` reports a judgment; `review ambiguities` lets a person
select a proposed reading and/or add clarification evidence. Neither command
edits a Memory or creates a checkpoint.

The finder-wide prompt contract is strengthened to request English candidate
readings and English operational explanations for this shared output. Its
storage and mutation contract is unchanged, but its visible language behavior
for non-English Contexts is therefore intentionally different.

The current implementation also supports:

```text
mem review                 # resume the one saved review
mem review --snapshot      # print one stable, non-interactive frame
mem review ambiguities --replace-review  # explicitly discard and rescan
```

Only the ambiguity adapter is implemented. Conflict and update have existing
semantic producers but no adapter in this shell yet. `reconcile`, `distill`,
`meld`, and `sever` are future or design-only operations whose semantic
contracts are not created by this UI work.

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

The shell also offers `PRIORITY`, which currently orders the overall
clarification label as:

```text
REQUIRED → HELPFUL → NONE → canonical source order
```

It does not claim to rank by the number of downstream proposals changed.
Doing that correctly requires structured, identifiable consequences and a
counterfactual recheck for each reading. That remains a separate extension.

## Durable state and stale detection

The full-screen terminal is not the source of truth. One active prototype
session is stored atomically in:

```text
~/.mem/review-session.json
```

The session records:

- schema version and session UID;
- adapter kind;
- Context UID and name;
- a digest of every directly owned Memory UID and content in canonical order;
- finding labels, reasons, questions, and proposed readings;
- current cursor and sort mode;
- selected readings and verbatim freeform responses.

The one-shot semantic report is saved before terminal control begins so a PTY
disconnect does not lose the expensive result. On resume, any change to the
Context identity, direct-Memory content, or canonical direct-Memory order makes
the session stale. The shell refuses to reinterpret an old answer against a
new local frame.

Starting another adapter never silently overwrites that artifact. When a saved
review already exists, `mem review ambiguities` refuses before opening the
provider; `--replace-review` is the explicit destructive boundary.

References, embedded Contexts, and query-only sources remain outside the
direct-Memory review boundary. In particular, review never opens
`~/.mem/query-sources/`.

The single active session matches the existing prototype style of one staged
update, but it is a deliberate concurrency limitation: another review process
can replace or last-write the same file. Multi-session storage and locking are
future work.

## Terminal and chat-controller boundary

The shell accepts ordinary concrete terminal input through prompt-toolkit:

- left/right: previous or next issue;
- up/down or digits: select a proposed reading;
- Enter or Tab: focus the freeform response;
- Escape: return to issue navigation;
- F2 or Ctrl-S: save and move to the next issue;
- `S`: toggle source/priority order;
- `L`: toggle split/stacked layout;
- `Q` or Ctrl-C: save and close.

These keys are not a natural-language command grammar. In a Codex chat, the
controlling agent observes the current frame, translates instructions such as
“오른쪽,” `->`, “4번,” or `답 "..."` into the appropriate PTY events, performs
the operation, and returns an actual snapshot. The PTY is transport and view;
the saved ReviewSession is durable semantic state.

Model-produced and stored strings are rendered as terminal data. C0 control
characters other than newline and tab are replaced before entering the PTY so
a proposed reading cannot inject terminal escape behavior.

## Shared shell, separate operation semantics

The visual shell is intended to be generalized and reused, but the implemented
controller is currently ambiguity-specific. Future reuse does not merge the
operations:

| Adapter | Status | Primary source unit |
|---|---|---|
| ambiguity | implemented | one Memory plus proposed readings |
| conflict | future adapter over an implemented finder | two Memories plus conflict scope |
| update | future adapter over existing staged-update artifacts | target Memory/edit or addition |
| atomize uncertainty | future adapter over the persisted atomize analysis | one composite or uncertain Memory |
| reconcile | future semantic contract | ambiguity/conflict evidence and proposed resolution |
| distill | design-only | summary claim and supporting Memories |
| meld / sever | Task 2/3 design-only | policy combination or disclosure boundary |

An update adapter must consume the existing `impact-plan.json` and
`staged-update.json` contracts rather than create a competing generic source
of truth. Similarly, a future conflict adapter must retain its pair-shaped
semantics even if it uses the same list, detail, choice, and response controls.

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
uses a vertical issue list plus one expanded detail. Split and stacked layouts
are two presentations of the same state, not different review models.

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
look complete, but the freeform response has not yet been classified,
normalized, or provenance-linked. It may be a comment rather than replacement
content. Responses therefore remain staged evidence until a future
reconciliation/apply step can show an explicit diff and checkpoint one
confirmed mutation.

### Build a fully generic operation framework first

Conflict, update, atomize uncertainty, reconcile, distill, meld, and sever can
share list/detail/response interaction patterns, but their source arity,
evidence, and mutation boundaries differ. A generic schema invented before
those contracts exist would either be vague or encode ambiguity-specific
assumptions under generic names. The implementation therefore proves the
ambiguity adapter first and records visual reuse as intent rather than claiming
that a generic framework already exists.

### Translate or rewrite the source for display

Normalizing every source Memory into English would make the screen uniform but
would hide whether the model misunderstood the original wording. The source is
therefore displayed verbatim, while proposed readings and operational
explanations use English as the comparison language. Reviewer input remains
verbatim in whatever language was entered.

## Intentional non-goals

The implemented ambiguity review does not:

- resolve, edit, add, remove, or checkpoint a Memory;
- synthesize the freeform response into an English replacement;
- decide whether the response is a refinement, comment, or different reading;
- calculate unsupported affected-Memory or changed-proposal counts;
- infer true creation chronology;
- persist multiple concurrent review sessions;
- implement conflict, update, reconcile, distill, meld, or sever adapters.

These boundaries keep the first shell useful for the user study while making
its evidence, mutations, and future claims inspectable.
