# `mem sever` design rationale

## Problem

Task 3 needs a local disclosure-review operation between finding personal
Memories and any later transmission. Query-only healthcare Q&A cannot supply
that operation's semantic criteria: `QUERY + SESSION_LOG` permits questions and
retention of visible Q/A, but does not grant `READ`, `DERIVE`, or `COMBINE`.
Treating the Q&A view as an ordinary Sever input would silently widen its
authority and could expose personal source text to the wrong provider.

## Command and interaction contract

One Sever pass has exactly three roles:

```text
SOURCE ordinary Context × one CRITERIA ordinary Context
    → new local OUTPUT Context
```

The explicit form is:

```text
mem sever --source SOURCE --criteria CRITERIA --save-as OUTPUT
# optional: --source-only / --source-descendants
#           --criteria-only / --criteria-descendants
```

`--against` is an alias for `--criteria`. `--to` is deliberately absent because
Sever does not address or transmit to a recipient; a future `mem share --to`
owns that separate consent boundary. With no operands in a TTY, Sever opens one
simultaneous three-pane setup view: `SOURCE`, `CRITERIA`, and `OUTPUT` are
stacked vertically in operation order. Output is a framed, directly editable
field, so its default name and edit boundary remain inside the OUTPUT box. The
first two panes expose the same
frozen ordinary Context catalog, while query-only rows remain visible and
unavailable. Both trees begin with the current Context selected and reuse the
`mem switch` namespace behavior: only the current ancestry begins expanded,
`Left`/`Right` collapse or expand branches, and `A` temporarily expands the
whole tree. The former `ROOTS` summary above each tree is replaced by an
independent `THIS CONTEXT ONLY / INCLUDE DESCENDANTS` scope row. `Up` from the
first visible Context enters that row, `Down` returns to the tree, and
`Left`/`Right` select exact/subtree scope. The default includes descendants to
preserve Sever's earlier recursive behavior; exact-only is the
disclosure-minimizing alternative. Source and Criteria must be made distinct
before continuing.
Output is not another selection pane. It uses the same bottom-composer shape as
interactive Find and begins with a fresh directly editable name under the
current local Context, such as `local/personal-memory/severed`, adding a numeric
suffix when necessary. It never offers an existing Context as an overwrite
target. `Tab` and `Shift-Tab` move between the two trees and Output field,
`Enter`/`Space` select Source or Criteria, and `Enter` in Output continues only
after all three roles are valid.
The resulting proposal then opens the shared Resolution Workbench. The
workbench lets a person retain the recommendation, use exact source text,
exclude an item, or submit exact custom outbound text. `--resume`,
`--candidate`, `--choice`, and `--accept` expose the same saved-session
transitions for recovery, scripts, and exact command review.

The initial provider turn is analysis only. It creates a retained Sever session
and no output Context. `--accept` creates a require-new local Context and an
automatic checkpoint. The source and criteria remain unchanged, and every
screen and snapshot says `NOT SENT`.

Sever treats its Source as already selected for the current review, normally by
an earlier `find` or an explicit Context choice. Its semantic job is local
minimization, de-identification, condition preservation, and exclusion—not
recipient selection or delivery approval. Recipient identity, authority,
channel, approval, retention, and downstream-use Criteria remain visible as
deferred Share preconditions, but missing delivery facts alone must not turn
every Source Memory into `DO_NOT_SEND`. This phase distinction lets one
guardrail tree remain useful across preparation and delivery without treating a
locally saved draft as a transmission attempt.

## Context and capability model

Both Source and Criteria must resolve through ordinary `READ` access. Query-only
rows remain visible but unselectable in the Context picker and cannot enter the
Sever payload. An `INCLUDE DESCENDANTS` frame freezes both embedded children
and every readable ordinary lexical descendant below the selected root. `THIS
CONTEXT ONLY` loads only directly owned items. Both projections skip
`QueryContextRef` records and fail on live `MemoryRef` records rather than
copying content through a pointer.

One Criteria root is accepted, with its exact/subtree scope recorded
separately. This makes the provider frame, authority intersection, provenance,
and user-visible rationale unambiguous.
When two criteria deserve equal consideration, the person may first create one
reviewed criteria Context with `mem meld`. Running Sever twice is also allowed,
but it is intentionally order-dependent: a later pass sees the earlier output
and cannot reconsider text already excluded by that pass.

For granted inputs, Sever requires the existing derived-work capabilities:

- `READ` to open the ordinary projection;
- `DERIVE + COMBINE` when it is analyzed with the other frame;
- `EXPORT` because the result leaves the authority resource for a local output;
  and
- `SAVE_ANALYSIS` because the session retains exact source and criteria
  snapshots.

Task 3 therefore splits government material at the authority boundary:

- `remote/government/healthcare-agent/info-request/official-guidance` is an ordinary 12-Memory published
  Context with read, derivation, combination, export, and analysis-retention
  permission; and
- `remote/government/healthcare-agent/info-request/questions-and-answers` remains a 75-Memory query-only view with
  only `QUERY + SESSION_LOG`.

The public set is curated before publication. Sever never copies or promotes a
query-only answer or concealed Memory into public guidance.

## Persistence and freshness

A Sever session retains:

- complete Source and Criteria recursive Memory frames;
- every direct Context name, UID, and canonical record digest in each frame;
- the exact granted binding when a frame crosses Profiles;
- one proposal per Source Memory;
- the person's current selection and exact custom content; and
- an application receipt after output creation.

Session writes use a record-digest compare-and-swap. Output publication uses the
ordinary require-new Context boundary. Every local contributing Context is
rechecked under the output creation lock set. Granted frames are retained only
after `SAVE_ANALYSIS` authorization, so later materialization uses the reviewed
snapshot instead of turning provider latency into an authority lease.

The output checkpoint records the Sever session identity, pre-application
digest, Source, Criteria, output name, result-to-source mapping, and selection.
Local rationale and excluded content stay in the Sever session rather than
becoming ordinary outbound Memories.

## Provider invariants

The provider receives only opaque aliases, exact Source content, and exactly one
ordinary Criteria frame. It must return one candidate for every Source Memory
exactly once. `SEND_AS_WRITTEN` must be byte-for-byte equal to the source;
`DO_NOT_SEND` must have empty outbound content; every other disposition must
have standalone nonempty content. Criteria citations must use supplied aliases.
Malformed, incomplete, duplicate, or invented identifiers fail closed.
The structured-output schema bounds citations to those aliases, while citation
uniqueness is checked after decoding because the Codex response-schema subset
does not accept JSON Schema's `uniqueItems` keyword.

## Alternatives considered

### Use query-only Q&A as guidance input

Rejected because `SESSION_LOG` permits transcript retention and replay inside
the query operation, not general derivative combination. A human may consult
Q&A separately, while machine-usable guidance must be published with explicit
ordinary derived-work authority.

### Accept several Criteria Contexts directly

Rejected for the initial operation because provider precedence and authority
intersection would be hidden inside Sever. Meld already provides an explicit
place to review how multiple criteria relate before producing one criterion.

### Make `--to` name the Q&A view

Rejected because it resembles the actual recipient spelling of a transmission
command. Sever has no recipient and uses `--criteria`; later sharing retains
`--to` for the receiving boundary.

### Delete or mutate Source Memories

Rejected. “Sever” means separating a reviewed disclosure artifact from its
private source, not erasing that source. Removal remains an independent command.

## Current limitations

- The output checkpoint retains source mapping, but `mem trace` and
  `mem rationale` do not yet render Sever-specific lineage as a dedicated
  presentation.
- A crash after output creation but before the session application receipt is
  saved leaves an inspectable output Context; automatic receipt recovery is not
  yet implemented.
- Sever itself never sends the reviewed draft. The separate initial
  `mem share` implementation accepts only an unchanged applied Sever output
  and delivers its ordinary Memories through a grant-backed endpoint.
