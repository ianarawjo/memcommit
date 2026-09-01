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
mem sever LOCATOR LOCATOR
mem sever [--source LOCATOR | --from LOCATOR]
           [--criteria LOCATOR | --against LOCATOR]
mem list [LOCATOR]
mem ls [LOCATOR]
mem show [LOCATOR | ITEM | LOCATOR:ITEM] [--context LOCATOR]
mem log [--memory SELECTOR] --context LOCATOR
mem revert [CHECKPOINT] --context LOCATOR
mem trace --context LOCATOR
mem trace [LOCATOR:]SELECTOR
mem rationale --context LOCATOR
mem rationale [LOCATOR:]SELECTOR
mem find [QUERY] --context LOCATOR
mem audit [LOCATOR]
mem dedun [LOCATOR]
mem find-{ambiguities,duplicates,redundancies,conflicts} [LOCATOR]
mem resolve [LOCATOR | MEMORY | LOCATOR:MEMORY ...]
mem resolve [--context LOCATOR] [--memory [LOCATOR:]MEMORY ...]
mem query SELECTOR --context LOCATOR
mem review [KIND] --context LOCATOR
mem impact atomize [LOCATOR | MEMORY | LOCATOR:MEMORY]
mem atomize [LOCATOR | MEMORY | LOCATOR:MEMORY]
mem chunk [LOCATOR | MEMORY | LOCATOR:MEMORY] [--context LOCATOR]
mem translate [LOCATOR | MEMORY | LOCATOR:MEMORY]
mem forget INSTRUCTION --context LOCATOR
mem checkpoint LOCATOR MESSAGE
mem checkpoint LOCATOR --message MESSAGE
mem checkpoint --context LOCATOR [MESSAGE]
mem clear [LOCATOR]
mem clear [LOCATOR] --recursive
mem delete LOCATOR
mem remove LOCATOR
mem merge LOCATOR [LOCATOR]
mem merge --from LOCATOR [--to LOCATOR | --into LOCATOR]
mem embed LOCATOR --into LOCATOR [--before ITEM | --after ITEM]
mem embed --from LOCATOR [--to LOCATOR | --into LOCATOR]
mem reference SELECTOR --from LOCATOR [--into LOCATOR]
mem reference --from LOCATOR [--to LOCATOR | --into LOCATOR]
mem dev query-source install ... --into LOCATOR
```

These commands use `memcommit.application.capabilities.context_locator.resolve_context_locator` for
their existing-Context operands, normally through the command-entry
`ContextOperandSnapshot` that freezes one active-Context base for the complete
invocation.

Clear's recursive form resolves its root through that same snapshot, then
freezes the materialized local lexical descendants of the canonical result.
The raw locator is never reused for membership, checkpoint identity, output,
or Undo reconstruction.

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
the first analysis. A single positional endpoint is the peer and uses current
as the reference; two positional endpoints explicitly supply reference and
peer. Positional Compare endpoints use the shared typed Context/direct-Memory
resolver. `--from` and `--to` use the same existing-Context name, relative,
and UID finder rather than a separate name-only path.

## CLI operand grammar

Existing-Context resolution and public command syntax are separate concerns,
but commands with the same semantic Context role should expose the same small
grammar. A directional endpoint should be expressible either positionally or
through an explicit role option without changing its meaning. `--from` and
`--to` are shared aliases only where they accurately describe data flow;
operation-specific names such as `--into`, `--criteria`, and `--save-as` remain
available. Duplicate spellings for one role fail before current-Context capture
instead of inheriting Click's last-option-wins behavior. The rollout uses this
table as the authored cross-operation rule:

| Operation family | Zero Context operands | Positional form | Compatibility options |
| --- | --- | --- | --- |
| `atomize`, `impact atomize` | Use current Context | auto-typed `[CONTEXT | MEMORY | CONTEXT:MEMORY]`; a Memory target focuses one exact directly owned Memory | `--context CONTEXT`; `--memory UID` retains explicit short-prefix focus |
| `audit`, `dedun`, `find-{ambiguities,duplicates,redundancies,conflicts}` | Use current Context | `[CONTEXT]` | `--context CONTEXT` |
| `chunk` | Chunk every direct Memory in current Context | auto-typed `[CONTEXT | MEMORY | CONTEXT:MEMORY]`; a Memory target chunks only that row | `--context CONTEXT` forces a positional selector to be Memory-owned by that Context |
| `translate` | Translate the current Context's direct Memories | auto-typed `[CONTEXT | MEMORY | CONTEXT:MEMORY]`; a Memory target narrows the same-UID view | no separate Context option; `--to` still names the semantic translation target |
| `show` | Show the current Context | `[CONTEXT | ITEM | CONTEXT:ITEM]`; a bare UUID-shaped item finds one unique ordinary-local direct owner, while a current direct named row retains precedence over a same-spelled Context | `--context CONTEXT` names the Context when no ITEM is supplied and explicitly owns ITEM otherwise |
| `resolve` | Use current Context, unless bare Memory operands uniquely locate one local owner | mixed `CONTEXT`, UUID-shaped `MEMORY`, and `CONTEXT:MEMORY`; every owner must canonicalize to one Context | `--context CONTEXT`, repeatable `--memory [CONTEXT:]UID`; short Memory prefixes require `--memory` or qualification |
| `compare` | Open new A/B endpoint setup | auto-typed `PEER` uses current as Reference; auto-typed `REFERENCE PEER` is fully explicit; each endpoint accepts Context, UUID-shaped Memory, or `CONTEXT:MEMORY` | explicitly Context-typed `--from REFERENCE`, `--to PEER`; `--reference-memory`/`--compared-memory` retain short-prefix focus; `--sessions` opens saved analyses |
| `branch` | Open compact Source/new-target setup | `RESULT_NAME` creates from current | `--from SOURCE` chooses one existing local Source; Result remains a new identifier |
| `merge` | Open Source/Target setup | `SOURCE [TARGET]`; omitted Target is current | `--from SOURCE`; `--to TARGET` and `--into TARGET` are equivalent |
| `update` | Open new Source/Target setup | `SOURCE [TARGET]`; omitted Target is current. An unambiguously non-Context Source is one process-local Memory | `--from SOURCE`, `--to TARGET`; `--memory TEXT` forces inline Source content; one omitted endpoint uses current; `--sessions` opens saved work |
| `impact update` | Inspect saved Update Impact | `SOURCE TARGET` starts a new preview | same `--from`/`--to` endpoint aliases |
| root `impact` | Error without a named route or endpoint | none, because the first token is a subcommand | retained `--from`/`--to` directional alias |
| `forget`, `impact forget` | Context defaults to current; instruction is still required outside the setup TTY | the position is reserved for `INSTRUCTION` | `--context CONTEXT` |
| `checkpoint` | Use current Context; one positional operand remains its compatibility `MESSAGE` | `CONTEXT MESSAGE`, or `CONTEXT --message MESSAGE`; the explicit message makes the Context role unambiguous | `--context CONTEXT` makes an optional positional operand the message; `--message MESSAGE` makes an optional positional operand the Context |
| `sever` | Open Source/Criteria in-place setup | exactly `SOURCE CRITERIA`; Source owners stay in place | `--source`/`--from`, `--criteria`/`--against` |
| `embed`, `reference` | Open Source/Target setup | `ITEM`; omitted Target is current | A Context Source may use `--from SOURCE`; `--into`/`--to` select Target. With an explicit Memory ITEM, `--from` retains its owner-Context qualifier meaning |
| `impact meld`, `impact sever` | Inspect saved operation work | none | `--session UID` only |

Update and Meld are deliberate mixed Context-or-inline Source boundaries. They
first preserve any existing Context, relative locator, or portable-looking
missing name as a Context operand; only a value that cannot be a portable
Context name becomes inline Memory content. This fail-closed order prevents a
misspelled Context name from silently becoming provider evidence. The exact
shared contract and operation-specific limits are recorded in
[`context-or-inline-memory-operand-design-rationale.md`](context-or-inline-memory-operand-design-rationale.md).

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

Checkpoint retains its older one-positional message grammar: `mem checkpoint
"MESSAGE"` still targets current. Two positional operands instead mean
`CONTEXT MESSAGE`; `--message` disambiguates one positional Context, while
`--context` disambiguates one positional message. Supplying both named roles
allows no positional operands. The asymmetry deliberately preserves scripts
without deciding whether an existing Context happens to share a message's
spelling.

Sever follows the same command-entry rule for its positional Source/Criteria
inputs and their `--source`/`--from` and `--criteria`/`--against` aliases. When
Source is omitted, the captured current Context supplies it; a relative Criteria locator is still
resolved against that exact same snapshot, not against a later reread of
global current state. The canonical Source name from that snapshot is also the
internal in-place post-image identity; no Result operand is accepted or later
reinterpreted against global current state.

Merge similarly resolves positional SOURCE and TARGET, or `--from` SOURCE plus
the `--into`/`--to` Target aliases, against one captured current snapshot.
Omitting Target uses that snapshot directly; supplying it positionally never
switches current.

Embed and Reference preserve their mixed Context/Memory selector contract. An
omitted ITEM plus `--from CONTEXT` means the complete Context Source; an
explicit Memory ITEM plus `--from CONTEXT` still qualifies that Memory's direct
owner. `--into` and `--to` select the same Target. This arity distinction adds
the missing explicit Context form without reinterpreting existing Memory
scripts.

Resolution itself grants no mutation authority and replaces no existing
identity or freshness checks. Switch still compare-and-sets current state and
the selected Context UID/digest. Compare still binds the exact source
snapshots and ordered analysis slot. A later mutating command must retain its
own locks, UID/digest checks, and canonical-target confirmation.

Compare freezes readable Contexts and ordinary-local direct Memories before it
interprets a bare UID. Exact/relative Context names win; a UID then resolves
across both kinds and fails on a cross-kind or multi-owner ambiguity. An
owner-qualified `CONTEXT:MEMORY` may resolve an authorized public Grant
Context, but bare Memory enumeration remains local. Both sides share one
command-start current name, candidate catalog, and Grant-registry snapshot.
The resulting exact owner and Memory UID feed the existing focused-Compare
contract, so automatic typing neither widens descendants nor promotes
neighboring Memories from context-only evidence.

Atomize, Impact Atomize, Chunk, and Translate use the same typed local target
resolver.
Their bare Memory operands require one unique ordinary-local direct owner, so
the active local Context receives no hidden priority. Chunk alone preserves an
already selected nonlocal public Grant current pointer as the explicit owner,
because that authority-bearing row is intentionally absent from local global
enumeration. Their Context operands retain ordinary current-relative
resolution. Translate permits a noncurrent explicit Context or Memory for its
read-oriented saved view, but its `--save-as` and
`--in-place` materialization routes require that exact Source to remain current
and fail before provider connection otherwise. This preserves Translate's
existing state-switch and compare-and-swap boundary instead of turning operand
convenience into cross-Context mutation authority.

Show extends the grammar from direct Memory to any direct item because its
typed result can safely represent MemoryRef, embedded Context, and query-view
rows. A bare UUID-shaped item still uses strict unique ordinary-local owner
discovery; a qualified owner uses Show's existing READ/Grant path. Non-UID text
first preserves Show's established current direct named-item lookup, then
falls back to an existing Context locator. `--context` is the explicit
disambiguator, and recursive reach is accepted only when the resolved operand
is a Context.

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
  query-only source selectors have different namespaces. An operation that
  explicitly accepts `Context | Memory` may reuse the shared typed union, but
  this does not turn a Memory-only or query-only operand into a Context locator.
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
