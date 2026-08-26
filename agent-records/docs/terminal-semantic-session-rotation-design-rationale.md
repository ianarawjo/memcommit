# Terminal semantic session rotation

## Motivating mismatch

Atomize, Meld, and the compatibility Ambiguities Review each kept one mutable
latest record. After that record reached a terminal outcome, a later explicit
request could still be interpreted as a resume or be rejected as an attempted
replacement. From a person's perspective the first command had already
finished; requiring destructive replacement made the next valid command look
like a duplicate-application bug.

The motivating forms are:

```text
mem atomize CONTEXT
mem atomize CONTEXT --refresh
mem meld INCOMING BASELINE
mem meld OTHER_INCOMING BASELINE
mem review ambiguities --context CONTEXT
mem review ambiguities --context OTHER_CONTEXT
```

## Shared lifecycle contract

The mutable latest record is a work slot, not the operation's history.

1. An unfinished record resumes when the request names its exact frame.
2. An unfinished record blocks a different frame unless the person supplies
   the operation's explicit fresh-work control.
3. An exact retry of a terminal request is idempotent and returns or renders
   the existing result without another provider call or application.
4. A provably different explicit request after terminal completion creates a
   new UID automatically.
5. When the text of a request cannot distinguish retry from intentional
   reanalysis, an explicit fresh-work control is required.
6. Replacing the latest slot cannot erase terminal evidence. The displaced
   record is retained under its immutable session or analysis UID before the
   new complete result becomes latest.
7. Provider or validation failure leaves the prior latest record in place.

This policy does not infer intent from elapsed time, terminal focus, or whether
a TUI was closed. It uses persisted operation state plus the complete typed
request frame.

## Operation adapters

### Atomize

The exact Context, Memory scope, prompt policy, and saved analysis determine
reuse. Bare exact retry remains provider-free. `mem atomize --refresh` forces a
new semantic analysis for an otherwise indistinguishable request, and the
Atomize launcher's `New` action submits that same explicit signal.

Displaced analysis and workbench state are stored together under
`atomize-session-history/<context-uid>/<analysis-uid>.json`. Impact, Review,
and saved-session discovery resolve those retained analysis UIDs. A terminal
workbench is historical evidence and does not claim that a later live Context
still has the same name or contents.

### Meld

`APPLIED` and `KEPT_REVIEW_ONLY` are terminal. A plain request with a different
mode, ordered directional source, symmetric peer set, descendant scope, Memory
focus, or inline Memory automatically performs the typed CAS Restart path.
The prior terminal record is first retained under
`meld-session-history/<target-uid>/<session-uid>.json`. An exact terminal retry
remains provider-free; `--restart` is the explicit fresh-work signal for an
otherwise identical request. Choosing `New` in Meld setup supplies that signal
when setup resolves to an occupied saved target.

An applied symmetric Result may still be unavailable as the output of another
Meld because the Result Context is no longer empty. That is a Result ownership
precondition, not a terminal-session blocker; the next symmetric operation
must select a new Result Context.

### Ambiguities Review

Because Review never applies Memories, a review is terminal when every item is
answered or the finder returned no items. Repeating the same Context frame
resumes the same UID. A distinct Context identity or direct-Memory digest after
terminal completion creates a new Review automatically. `--new` forces a fresh
finder run for the same frame; `--replace-review` remains its compatibility
alias and malformed-singleton recovery route.

Displaced terminal sessions live in `review-session-history/<session-uid>.json`.
The exact direct Context snapshot is written once at initial save under
`review-session-sources/<session-uid>.json`, so historical review does not
reinterpret source UIDs against later Memory content. Retained sessions are
read-only and can be selected by UID or from the Review launcher.

## Persistence and safety boundaries

- Archive creation happens only after new semantic work has completed but
  before latest-slot publication. A provider failure therefore publishes
  neither a new latest record nor a misleading terminal history.
- Existing target/Context locks and canonical-digest CAS remain authoritative.
  Rotation does not weaken stale-command rejection.
- UID archive files are immutable. Reusing a UID with different content is a
  storage error rather than last-write-wins behavior.
- Context deletion removes active records, retained records, and Review source
  snapshots that contain that Context's local evidence.
- Historical records are evidence, not resumable mutation state. Opening one
  cannot Apply, answer, or redirect it into the latest slot.

## Alternatives rejected

Always starting new work for an identical terminal command would break retry
recovery after a lost terminal response. Always resuming terminal work would
preserve machine idempotence at the cost of making legitimate subsequent work
appear broken. Overwriting the singleton after completion would allow both
behaviors but destroy the UID receipt needed to explain the earlier operation.
The selected split—exact retry, automatic rotation for distinguishable input,
and explicit refresh for indistinguishable input—preserves both user intent and
recovery evidence.

## Verification

Tests cover exact provider-free retries, distinct terminal rotation, explicit
same-frame refresh/restart/new, immutable UID lookup, retained historical
rendering, source snapshots, launcher handoff, and Context-deletion cleanup.
