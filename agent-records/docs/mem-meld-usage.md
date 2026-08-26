# Meld Usage

This is the canonical user-facing command guide for the meld behavior that is
currently implemented. Update this file, the relevant CLI help, and the
associated tests together whenever hands-on testing changes the workflow.

## Canonical terms

| User-facing term | Technical contract | Command | Status |
|---|---|---|---|
| **Atomic meld** *(informal shorthand)* | An issue-scoped directional meld embedded in atomize grounding | `mem atomize --evaluate ISSUE` | Implemented |
| **Inline-Memory meld** | One exact process-local Memory melded into an authoritative local baseline Context | `mem meld --memory TEXT`; `--from SENTENCE --to BASELINE` and an unambiguously non-Context one-operand sentence are shorthands | Implemented |
| **Directional Context meld** | A read-only incoming Context melded into an authoritative baseline Context | `mem meld INCOMING BASELINE`; omit `BASELINE` to use the current Context | Implemented |
| **Symmetric Context meld** | Two equal-authority Contexts combined into an explicit Result Context | `mem meld PEER_A PEER_B RESULT_C`; `--to RESULT_C` is an alias | Implemented |

“Atomic” identifies the issue where review begins. It does **not** promise
that only one Memory can change. A clarification may require several
traceable edits or additions when other local Memories depend on the same
interpretation.

Internally, a unary source-grounded candidate is treated as a temporary
one-Memory Context: atomize projects it as an immutable, ephemeral `INCOMING`
frame and projects its containing Context as the bound `BASELINE` frame. The
reviewer's selected reading and comments are turn evidence attached to that
meld, not another Context. A pair-shaped conflict keeps both source Memories
in one incoming issue frame instead of flattening them.

“Temporary” does not mean that another named Context is created. The incoming
frame has no durable Context UID or locator and is never saved, switched to,
listed, or checkpointed. It is reconstructed from the bound atomize session;
only an explicitly accepted result can change and checkpoint the baseline
Context.

There is no `mem meld --atomic` command. The implemented atomize-issue entry
point remains under `mem atomize` because atomize owns the saved analysis,
issue identity, and source evidence. Standalone Meld separately accepts one
exact raw Memory through `--memory`; the existing `--incoming-memory` and
`--baseline-memory` controls select durable Memories inside named Context
frames and do not turn those durable Memories into raw input.

## Browse saved Context Meld sessions

Use either of these forms without Context operands to browse existing
Context-wide Meld workbenches:

```bash
mem meld
mem meld --sessions
```

The picker initially orders entries by the saved JSON file's modification time
and labels that view `RECENTLY MODIFIED`; it does not claim that the Meld
schema contains a semantic creation or update timestamp. Entries can also be
grouped by their persisted target Context. A target is the natural grouping
boundary because every saved Meld is target-scoped; the picker does not infer
a separate project model.

Selecting an entry does not switch a global active Meld and does not execute
the displayed command receipt. The command reloads the target-UID-keyed JSON,
checks that its session identity and complete digest still match the selected
snapshot, reloads the exact persisted source and target Context names, and
revalidates their UID and digest bindings before opening the workbench. If the
session or a bound Context changed while the picker was open, reopening fails
and the list must be opened again. Browsing, cancellation, and provider-free
snapshot rendering create no Context, checkpoint, or replacement session.

Explicit forms such as `mem meld --memory TEXT`, `mem meld INCOMING BASELINE`,
`mem meld PEER_A PEER_B RESULT_C`, and their `--into`, `--from`, and `--to`
aliases retain target-bound create-or-resume behavior.
`--sessions` cannot be combined with Context operands or semantic, terminal,
restart, or expansion actions.

## Inline-Memory meld: incorporate one exact idea

Use the current local Context as the authoritative BASELINE/Target:

```bash
mem meld --memory 'all greetings need "."'
```

Or name the local BASELINE explicitly:

```bash
mem meld --memory 'all greetings need "."' --into policies/greetings
mem meld --memory 'all greetings need "."' --to policies/greetings
mem meld --from 'all greetings need "."' --to policies/greetings
```

When the sole positional operand cannot be a portable Context locator, Meld
uses it as the same exact inline Memory. This makes the natural sentence form
work without hiding a plausible Context typo:

```bash
mem meld 'all greetings need "."'
```

An absent portable-looking value such as `hello` is still treated as a Context
name and reports that the Context does not exist. Use `--memory hello` when a
one-word or otherwise Context-shaped value is intended as content. An existing
local Context always retains Context meaning.

Memory content is preserved exactly, including ordinary punctuation, quotes,
exclamation marks, and meaningful leading or trailing spaces supplied by the
shell. Shell quoting is separate from Meld parsing. Single quotes are the
safest form when the content contains double quotes or `!`:

```bash
mem meld --memory 'keep "" and ! literally'
```

With outer double quotes, escape embedded double quotes:

```bash
mem meld --memory "all greetings need \".\"!"
```

The inline source becomes one schema-version-9 `INCOMING` frame retained in
the target-scoped Meld session. `INLINE MEMORY` is a display label, not a
Context locator: Meld creates no temporary Context, never makes it current,
and never adds it to `mem ls`. Resume and Apply reconstruct the exact source
from the session, revalidate only the real BASELINE hierarchy, and retain the
inline content in checkpoint provenance. Starting or resuming never mutates
the BASELINE. A scripted or non-TTY run saves the ready proposal for explicit
`--accept`; an ordinary local TTY run with no unresolved decision may use
Meld's existing Undo-backed automatic acceptance. Unresolved or granted-target
work still stops at its explicit review boundary.

Inline input cannot be combined with an INCOMING subtree or
`--incoming-memory`, and currently requires a local BASELINE/Target. A local
BASELINE may still use `--right-descendants` or `--baseline-memory` to control
its writable scope. Inline runs intentionally do not reuse Context-pair Compare
or directional prewarm artifacts because there is no durable incoming Context
binding to revalidate.

## Atomic meld (informal shorthand): resolve one atomize issue

### 1. Create or resume the atomize analysis

```bash
mem atomize --context CONTEXT
```

This displays the saved workbench and its visible issue numbers. Repeating the
command resumes a compatible saved analysis without another provider call.

### 2. Start from one issue

In an interactive terminal, omit `--comment` and enter the clarification when
prompted:

```bash
mem atomize --context CONTEXT --evaluate ISSUE
```

For an explicit one-shot submission:

```bash
mem atomize --context CONTEXT \
  --evaluate ISSUE \
  --comment "The Main Building entrance accepts only a physical NFC card."
```

`ISSUE` may be a visible issue number or a unique issue/source UID prefix.
Starting the dialogue may call the semantic provider once. It does not change
Memories.

### 3. Inspect or continue the grounded interpretation

Resume the open dialogue without a provider call:

```bash
mem atomize --context CONTEXT
```

Answer a follow-up, qualify the interpretation, or repair an earlier turn:

```bash
mem atomize --context CONTEXT \
  --reply "Do not recommend the app. The staff entrance uses the same physical-card-only method." \
  --revision correct
```

The supported revision labels are:

```text
confirm
extend
correct
retract
```

Each reply is a new grounded turn and may call the provider once. The result
must show what Mem understood, which issue is resolved or remains open, and
the exact proposed `EDIT` or `ADD` consequences.

### 4. Apply or retain review evidence

Only a `READY_TO_APPLY` dialogue can be applied:

```bash
mem atomize --context CONTEXT --accept-grounding
```

Acceptance is provider-free. It applies the exact ready proposal to that
Context and creates one checkpoint. The saved atomize analysis is then stale
and must be refreshed explicitly before another review cycle.

To close the dialogue without changing Memories:

```bash
mem atomize --context CONTEXT --keep-review-only
```

One invocation may contain only one grounding action. Do not combine
`--evaluate`, `--reply`, `--accept-grounding`, or `--keep-review-only` with
`--save` or `--save-as`.

## Directional Context meld: update an existing baseline

Directional meld gives the two Contexts different roles:

- `INCOMING` supplies new, corrective, or already-represented evidence and
  remains read-only;
- `BASELINE` is the authoritative existing Context and the only mutation
  target.

The smallest form names INCOMING and uses the current Context as BASELINE:

```bash
mem switch test/update/to
mem meld ../from
```

Here `../from` is resolved lexically from the current Context name
`test/update/to`, so the exact portable operation is:

```bash
mem meld test/update/from test/update/to
```

Name both roles when the baseline is not current:

```bash
mem meld INCOMING BASELINE
```

When the Context currently being viewed is the baseline, `--from` supplies
the incoming side instead:

```bash
mem switch task2/advisor1
mem meld --from ../advisor2
```

This is convenience grammar for the same directional operation, not another
Meld mode. The example is normalized to the portable route
`mem meld task2/advisor2 task2/advisor1`; saved-session identity,
follow-up guidance, and application receipts use that canonical spelling.
The same role-explicit form can name the baseline without first switching:

```bash
mem meld --from ../advisor2 --to task2/advisor1
```

Here `--to` is directional because fewer than two positional peers are
present. `--from` still cannot be combined with `--into` or positional
Contexts.

`mem meld INCOMING --into BASELINE` remains an explicit alias. Likewise,
`mem meld --into BASELINE` uses the current Context as INCOMING for
compatibility. Positional `INCOMING BASELINE` is the canonical portable form.

Bare names such as `campus/wiki` remain global Context names. Only `.`, `..`,
`./...`, and `../...` opt into current-relative lookup. They describe the
slash-delimited Context namespace, not shell directories or filesystem paths.
The command snapshots the current Context once and resolves every relative
operand against that same name.

Both directional endpoints may also be readable Grant names in the active
Profile. Grant INCOMING remains read-only. A Grant BASELINE is the actual
mutation target: `--accept` updates its authority Profile when the Grant has
`ACCEPT_DERIVED` where required and the exact proposal's `CREATE`/`UPDATE`
permissions. Cross-domain inputs additionally require the normal
`DERIVE`/`COMBINE`/`EXPORT` permissions. Saved analysis requires an allowed
retention mode, and every resume or acceptance revalidates the frozen Grant
revision and mapping. Revocation or drift leaves the participant artifact
stored but prevents Grant-bound review or mutation; retained-analysis access
follows the Grant artifact retention rules.

The first invocation performs one bounded semantic turn and saves a
non-applying relation ledger and proposal. A terminal shows only the compact
decision surface when judgments remain; otherwise the command returns a
bounded receipt. The complete ledger is explicit under the printed Impact or
Review route. If the active Profile already contains an exact fresh ordered
Compare for the same `INCOMING → BASELINE` pair and descendant flags, Meld
imports that relation ledger and asks the provider only for the
authority-specific Directional issues and materialization over it:

```bash
mem switch INCOMING
mem compare --to BASELINE
mem meld INCOMING BASELINE
```

A present but stale Compare must be refreshed; it is not silently ignored. If
no saved Compare exists, the compatible direct Directional analysis remains
available. The rendered session marks an imported basis with `Compare: … ·
IMPORTED`. Repeating the same resolved incoming–baseline command resumes
without another provider call. Directional roles are ordered: reversing the
two Contexts is a different operation and requires its own ordered Compare to
be comparison-backed.

The shared issue and whole-set actions use the directional command prefix:

```bash
mem meld INCOMING BASELINE \
  --issue 1 \
  --choice 2 \
  --comment "Only vehicle access is closed; keep the stairwell open."

mem meld INCOMING BASELINE \
  --comment "Apply this scope to every related parking-access rule."

mem meld INCOMING BASELINE --expand 1
mem meld INCOMING BASELINE --preserve-all
mem meld INCOMING BASELINE --defer-all
mem meld INCOMING BASELINE --accept
```

`--preserve-all` respects the authority direction: it keeps the baseline
unless incoming evidence explicitly supports a correction and retains
supported incoming distinctions with their scope. `--defer-all` keeps the
analysis as review-only. Neither action changes either Context.

New preservation-first directional sessions treat relation groups as analysis,
not as permission to create one topical summary. Novel `DISTINCT`,
`COMPATIBLE`, and `SCOPED` incoming Memories are separate exact additions by
default. Combining several compatible or scoped incoming Memories requires an
explicit reviewed user turn; an equivalent incoming Memory can correctly
produce no baseline change.

A ready directional proposal contains only material baseline changes:

- `EDIT` replaces the content of one cited baseline Memory while preserving
  its UID and position;
- `ADD` appends one new Memory with a fresh UID;
- unchanged baseline Memories remain untouched and in order;
- `DELETE` is not supported, so knowledge is never silently removed.

An equivalent incoming Context can therefore produce a ready proposal with
zero changes. Acceptance does not manufacture a no-op `EDIT`: it records the
resolved zero-change meld and its evidence in one baseline checkpoint. For
non-empty proposals, all accepted `EDIT` and `ADD` operations are applied in
that same single checkpoint. Acceptance is provider-free, rechecks both bound
Context snapshots, never mutates the incoming Context, and is the only point
at which the baseline may change.

Use `--restart` only when intentionally replacing the baseline's saved meld
session after its bound Contexts have been rechecked:

```bash
mem meld INCOMING BASELINE --restart
```

Symmetric Context-to-Context Meld retains the direct-owned-Memory boundary.
Directional Meld may explicitly select readable descendants for INCOMING and
writable descendants for BASELINE; it retains each Memory's exact owner and
applies accepted changes to that owner rather than flattening them into the
root. Memory references remain unsupported. Query-only routes are never
dereferenced or treated as ordinary Meld evidence or target owners.

### How operand shape distinguishes `--into` and `--to`

`--into` communicates authority and mutation: incoming evidence is considered
against an existing baseline, and explicit acceptance may create that
baseline's next state. It is the unambiguous and canonical directional
spelling.

`--to` follows the visible operand shape. With fewer than two positional
sources it names the directional baseline:

```text
mem meld --from INCOMING --to BASELINE
mem meld --memory TEXT --to BASELINE
```

With two positional peers it names the third frame of the symmetric shape:

```text
mem meld LEFT_PEER RIGHT_PEER --to RESULT_CONTEXT
```

That form names a distinct result and does not make either peer authoritative.
The equivalent positional form is
`mem meld LEFT_PEER RIGHT_PEER RESULT_CONTEXT`; there is no hidden current
Result. Saved directional commands normalize to `--into` so the durable
receipt states the authority relationship without relying on remembered
input shape.

## Symmetric Context meld: combine two equal-authority Contexts

### 1. Start with explicit sources and a result

```bash
mem meld LEFT_PEER RIGHT_PEER RESULT_CONTEXT
```

Meld freezes the exact `LEFT_PEER → RIGHT_PEER` order and descendant flags.
It reuses a matching fresh Compare basis or creates and saves that basis itself
before publishing the new Result Context and session. The reverse Compare slot
is deliberately different and is never used as a fallback. Missing or stale
analysis does not require changing the current Context.

To inspect the same basis separately first, use the fully explicit Compare
form; it also leaves the current Context unchanged:

```bash
mem compare --from LEFT_PEER --to RIGHT_PEER
```

`--to RESULT_CONTEXT` is an equivalent explicit alias. If the Result is
absent, Meld creates it atomically with the session. If it already exists, it
must be a local empty Context with no session or own the exact compatible saved
Meld session. A populated or unrelated Result is rejected. Neither form
switches the current Context.

The first invocation reuses or prepares the exact Compare overview, relation
ledger, and grounding candidates. It preserves their frame, relation, issue,
and option identities in the target-bound Meld session but does not treat
inspection as permission to create target Memories. In a terminal this opens
the interactive workbench. Repeating the same command resumes the saved
session. Outside a terminal it prints the saved snapshot.

The primary controls are:

```text
Up / Down               move between issues
Enter                   expand the selected issue
Up / Down in detail     move between proposed readings
Enter in detail         select or clear the highlighted reading
Tab                     comment on the selected issue
G                       comment on the whole set
Enter in MESSAGE        send
Ctrl-J                  insert a newline
Escape                  collapse one detail, then close without applying
P                       preserve all remaining supported distinctions
D                       keep the result as review-only
A                       accept a ready proposal
Q                       close
```

The same operations are available explicitly:

```bash
mem meld LEFT_PEER RIGHT_PEER \
  RESULT_CONTEXT \
  --issue 1 \
  --choice 2 \
  --comment "Keep both rules, but state their separate scopes."

mem meld LEFT_PEER RIGHT_PEER \
  RESULT_CONTEXT \
  --comment "Preserve every source-supported exception."

mem meld LEFT_PEER RIGHT_PEER RESULT_CONTEXT --expand 1
mem meld LEFT_PEER RIGHT_PEER RESULT_CONTEXT --preserve-all
mem meld LEFT_PEER RIGHT_PEER RESULT_CONTEXT --defer-all
mem meld LEFT_PEER RIGHT_PEER RESULT_CONTEXT --accept
```

`--expand`, resume, defer, and acceptance are provider-free. Issue comments,
whole-set comments, and preserve-all create semantic turns. `--accept` applies
the ready result to the explicit Result without mutating either peer.
When Compare reports no grounding candidates, use a whole-set comment or
`--preserve-all` to request the first reviewable target materialization; a
resolved Compare ledger alone is not write authority.

Use `--restart` only when intentionally replacing the saved review session
after rechecking that the target is still empty:

```bash
mem meld LEFT_PEER RIGHT_PEER RESULT_CONTEXT --restart
```

## Deliberate boundary

The three implemented entry points share a meld reasoning contract but retain
distinct CLI shapes and authority:

```text
one saved atomize issue + clarification
→ mem atomize --evaluate
→ issue-scoped directional meld ("atomic meld" shorthand)

one read-only incoming Context + one authoritative baseline
→ mem meld INCOMING BASELINE
→ or mem meld INCOMING while BASELINE is current
→ or mem meld --from INCOMING while BASELINE is current
→ Context-wide directional meld

two equal-authority Contexts + empty result Context
→ mem meld LEFT_PEER RIGHT_PEER RESULT_CONTEXT
→ or mem meld LEFT_PEER RIGHT_PEER --to RESULT_CONTEXT
→ Context-wide symmetric meld
```

“Atomic” remains a scope shorthand, not `mem meld --atomic`. One or two
positional Contexts are directional; a third positional Context or `--to`
makes the distinct symmetric Result explicit.
