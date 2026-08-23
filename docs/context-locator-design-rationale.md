# Existing Context locator resolution

## Status

The first shared rollout is implemented in:

```text
mem switch LOCATOR
mem branch RESULT_NAME --from LOCATOR
mem compare LOCATOR
mem compare LOCATOR LOCATOR
mem compare --to LOCATOR
mem compare --from LOCATOR --to LOCATOR
mem meld LOCATOR
mem meld LOCATOR LOCATOR
mem meld LOCATOR LOCATOR RESULT_NAME
mem meld [LOCATOR] --into LOCATOR
mem meld --from LOCATOR
mem impact [--from LOCATOR] [--to LOCATOR]
mem impact update LOCATOR LOCATOR
mem update LOCATOR LOCATOR
mem update [--from LOCATOR] [--to LOCATOR]
mem sever LOCATOR LOCATOR [RESULT_NAME]
mem sever [--source LOCATOR] --criteria LOCATOR [--save-as RESULT_NAME]
mem list [LOCATOR]
mem ls [LOCATOR]
mem show [SELECTOR] --context LOCATOR
mem log [--memory SELECTOR] --context LOCATOR
mem revert [CHECKPOINT] --context LOCATOR
mem trace [SELECTOR] --context LOCATOR
mem rationale [SELECTOR] --context LOCATOR
mem find [QUERY] --context LOCATOR
mem audit [LOCATOR]
mem dedun [LOCATOR]
mem find-{ambiguities,duplicates,redundancies,conflicts} [LOCATOR]
mem resolve [LOCATOR | MEMORY | LOCATOR:MEMORY ...]
mem resolve [--context LOCATOR] [--memory [LOCATOR:]MEMORY ...]
mem query SELECTOR --context LOCATOR
mem review [KIND] --context LOCATOR
mem impact atomize [LOCATOR]
mem atomize [LOCATOR]
mem forget INSTRUCTION --context LOCATOR
mem clear [LOCATOR]
mem delete LOCATOR
mem remove LOCATOR
mem merge LOCATOR [LOCATOR]
mem embed LOCATOR --into LOCATOR [--before ITEM | --after ITEM]
mem reference SELECTOR --from LOCATOR [--into LOCATOR]
mem dev query-source install ... --into LOCATOR
```

These commands use `memcommit.context_locator.resolve_context_locator` for
their existing-Context operands, normally through the command-entry
`ContextOperandSnapshot` that freezes one active-Context base for the complete
invocation.

`RESULT_NAME` in the three-operand Meld form is deliberately not an
existing-Context locator: the symmetric Result may be created, so it remains
an exact ordinary Context identifier. Only the two peer operands use this
resolver.

## Motivation

Slash-delimited Context names form a lexical namespace. `mem switch` already
allowed a person at `test/update/from` to select the sibling Context with:

```text
mem switch ../to
```

The implementation lived as private functions inside the Switch command.
Consequently, the equivalent Compare operand was treated as a literal invalid
Context name:

```text
mem compare ../to
mem compare ../from ../to
mem compare --to ../to
Compare error: Compared Context '../to' does not exist.
```

This was not a meaningful operation-specific distinction. It was duplicated
locator policy: one command understood explicit relative notation and another
existing-Context lookup did not.

## Locator contract

A **canonical Context name** is a durable slash-delimited identifier such as
`test/update/to`. A **Context locator** is CLI input used to find an existing
ordinary Context. It may be either a canonical name or an explicitly relative
spelling:

| Current Context | Locator | Canonical result |
| --- | --- | --- |
| `test/update/from` | `../to` | `test/update/to` |
| `organization/wiki` | `./facilities` | `organization/wiki/facilities` |
| `test/update/from` | `.` | `test/update/from` |
| `test/update/from` | `../../archive` | `test/archive` |

Bare names remain global. From `organization/wiki`, `child` still means the
canonical Context named `child`; only `./child` means
`organization/wiki/child`. This preserves scripts and prevents the same bare
argument from changing meaning when current state changes.

Resolution is purely lexical. It never reads the shell working directory,
filesystem layout, embedded Context graph, Memory contents, or query-only
sources. One trailing slash is accepted, while repeated or interior empty
segments, namespace-root results, and attempts to escape above the root are
rejected.

The resolver does not test existence and does not choose between `load`,
`load_direct`, or `load_for_update`. Those are operation-specific authority
and privacy decisions that remain with each command.

## Snapshot, persistence, and concurrency

A command captures the active Context name once and uses that same value as
the base for every relative operand in that invocation. It must not resolve
one operand, reread global current state, and resolve another against a
different base.

After resolution, equality checks, source loading, cache lookup, session
binding, output frames, checkpoints, and durable artifacts use only the
canonical name. Thus:

```text
mem compare --to ../to
mem compare --to test/update/to
mem compare --from ../from --to ../to
```

identify the same ordered comparison slot and the second spelling can reuse
the first analysis. A single positional locator is the peer and uses current as
the reference; two positional locators explicitly supply reference and peer.
The option aliases retain the same roles for compatibility.

## CLI operand grammar

Existing-Context resolution and public command syntax are separate concerns,
but commands with the same semantic Context role should expose the same small
grammar. The rollout uses this table as the authored cross-operation rule:

| Operation family | Zero Context operands | Positional form | Compatibility options |
| --- | --- | --- | --- |
| `atomize`, `impact atomize` | Use current Context | `[CONTEXT]` | `--context CONTEXT` |
| `audit`, `dedun`, `find-{ambiguities,duplicates,redundancies,conflicts}` | Use current Context | `[CONTEXT]` | `--context CONTEXT` |
| `resolve` | Use current Context, unless bare Memory operands uniquely locate one local owner | mixed `CONTEXT`, UUID-shaped `MEMORY`, and `CONTEXT:MEMORY`; every owner must canonicalize to one Context | `--context CONTEXT`, repeatable `--memory [CONTEXT:]UID`; short Memory prefixes require `--memory` or qualification |
| `compare` | Open saved-session launcher | `PEER` uses current as Reference; `REFERENCE PEER` is fully explicit | `--from REFERENCE`, `--to PEER` |
| `branch` | Open compact Source/new-target setup | `RESULT_NAME` creates from current | `--from SOURCE` chooses one existing local Source; Result remains a new identifier |
| `update` | Open saved Update work | `SOURCE TARGET` only | `--from SOURCE`, `--to TARGET`; one omitted option endpoint uses current |
| `impact update` | Inspect saved Update Impact | `SOURCE TARGET` starts a new preview | same `--from`/`--to` endpoint aliases |
| root `impact` | Error without a named route or endpoint | none, because the first token is a subcommand | retained `--from`/`--to` directional alias |
| `forget`, `impact forget` | Context defaults to current; instruction is still required outside the setup TTY | the position is reserved for `INSTRUCTION` | `--context CONTEXT` |
| `impact meld`, `impact sever` | Inspect saved operation work | none | `--session UID` only |

For the ordinary unary families, supplying both the positional Context and
`--context` is a usage error rather than a precedence rule. Resolve is the
deliberate mixed-target exception: it collapses repeated spellings of the same
canonical Context because positional Memory qualifiers and explicit options
may independently carry the same owner, while rejecting distinct owners. For
Update, exactly one positional Context is also a usage error because it does
not say whether the operand is Source or Target. The established one-sided
current-filled forms remain unambiguous through `--from` and `--to`.

This table changes only command entry. The no-operand unary route keeps its
existing current-Context behavior, and every mutation, Grant, provider,
receipt, cache, and Apply boundary remains operation-owned.

Directional Impact and Update resolve both optional endpoint operands against
the same captured current name. `--to B` fills the source with current,
`--from A` fills the target with current, and `--from A --to B` needs no
current Context when both locators are canonical global names. A relative
locator still requires current even when the other endpoint is explicit.

Sever follows the same command-entry rule for its positional Source/Criteria
inputs and their `--source`/`--criteria` aliases. When Source is omitted, the
captured current Context supplies it; a relative Criteria locator is still
resolved against that exact same snapshot, not against a later reread of
global current state. When Result is omitted, Sever self-saves by reusing the
canonical Source name from that snapshot. An explicit positional Result or
`--save-as` value is not passed through the existing-Context resolver: it must
either equal that canonical Source name for self-save or be a fresh ordinary
Context identifier for other-save. A raw relative Result is never reinterpreted
against later global current state.

Merge similarly resolves positional SOURCE and TARGET, or SOURCE plus its
`--into` Target alias, against one captured current snapshot. Omitting Target
uses that snapshot directly; supplying it positionally never switches current.

Resolution itself grants no mutation authority and replaces no existing
identity or freshness checks. Switch still compare-and-sets current state and
the selected Context UID/digest. Compare still binds the exact source
snapshots and ordered analysis slot. A later mutating command must retain its
own locks, UID/digest checks, and canonical-target confirmation.

## Reuse rule and rollout boundary

When a CLI operand locates an **existing ordinary Context**, it should use the
shared resolver rather than implement dot-segment parsing or pass explicit
relative spelling directly to `MemoryStore`.

List is a read-only adopter: it resolves `mem ls ../sibling` against one
captured current-Context snapshot, then uses the canonical result for loading,
the output heading, namespace-child discovery, and structured copy identity.
Read and analysis commands use the same command-entry snapshot without
changing their operation-specific loader. Mutation-oriented operands add the
required authority boundary: prompts display the escaped canonical name,
targets retain their UID/digest CAS, and source-dependent writes revalidate
canonical source name/UID/digest receipts under the final lock set.

The resolver must not be applied indiscriminately:

- `init NAME`, the Branch Result `NAME`, `checkout -b NAME`, and `--save-as`
  values define new canonical identifiers; they are not existing-Context
  locators. Branch's separate `--from` value is an existing-Context locator.
- Memory selectors, embedded-item selectors, requirement targets, and
  query-only source selectors have different namespaces.
- Embed's `--before` and `--after` values select direct items inside the already
  resolved target Context. They are not existing-Context locators and never
  receive dot-segment resolution.
- `mem delete` and `mem remove` deliberately combine the existing-Context and
  direct-item selector domains. Their ambiguity and explicit `--context`
  boundary are specified in `unified-delete-selector-design-rationale.md`.
- Ground frame binding requires a separate approval-aware integration. A raw
  relative argument must never retain a meaning that can change with the
  global active Context after the exact-command receipt is displayed.
- Provider-returned or already persisted Context names are canonical data and
  are never reinterpreted as relative CLI input.

These distinctions make the resolver universal for one semantic role—
locating an existing normal Context—without making every string that happens
to contain a Context name depend on mutable current state.

## Remaining intentional boundaries

Public existing-ordinary-Context CLI operands now use the common locator. The
remaining Context-shaped strings are intentionally outside that role: new
identifiers, Memory and query-only selectors, provider output, saved artifact
bindings, and Ground's separately reviewed frame-binding receipt. Adding a new
ordinary existing-Context operand requires adding it to the rollout list and a
test that proves every relative operand shares one current snapshot.

The internal graph-migration, identity, reference, checkpoint, query-only, and
failure semantics retained for operation-owned relocation are specified in
[`mem-rename-design-rationale.md`](mem-rename-design-rationale.md).
