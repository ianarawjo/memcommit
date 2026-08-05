# Meld Usage

This is the canonical user-facing command guide for the meld behavior that is
currently implemented. Update this file, the relevant CLI help, and the
associated tests together whenever hands-on testing changes the workflow.

## Canonical terms

| User-facing term | Technical contract | Command | Status |
|---|---|---|---|
| **Atomic meld** *(informal shorthand)* | An issue-scoped directional meld embedded in atomize grounding | `mem atomize --evaluate ISSUE` | Implemented |
| **Symmetric Context meld** | Two equal-authority Contexts combined into the current empty result Context | `mem meld LEFT_PEER RIGHT_PEER` | Implemented |
| **Directional Context meld** | A read-only incoming Context melded into an authoritative baseline Context | Canonical: `mem meld [INCOMING] --into BASELINE`; current baseline convenience: `mem meld --from INCOMING` | Implemented |

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

There is no `mem meld --atomic` command and no public command that accepts raw
text strings or individual Memory UIDs as its two frames. The implemented
atomic entry point remains under `mem atomize` because atomize owns the saved
analysis, issue identity, and source evidence.

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

Explicit forms such as `mem meld LEFT RIGHT`,
`mem meld INCOMING --into BASELINE`, and its current-baseline convenience
`mem meld --from INCOMING` retain their existing create-or-resume behavior.
`--sessions` cannot be combined with Context operands or semantic, terminal,
restart, or expansion actions.

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

When the current Context is the incoming source, it can be omitted:

```bash
mem switch test/update/from
mem meld --into ../to
```

Here `../to` is resolved lexically from the current Context name
`test/update/from`, so the exact operation is:

```bash
mem meld test/update/from --into test/update/to
```

The explicit form is useful when the incoming Context is not current:

```bash
mem meld INCOMING --into BASELINE
```

When the Context currently being viewed is the baseline, `--from` supplies
the incoming side instead:

```bash
mem switch task2/advisor1
mem meld --from ../advisor2
```

This is convenience grammar for the same directional operation, not another
Meld mode. The example is normalized to the portable route
`mem meld task2/advisor2 --into task2/advisor1`; saved-session identity,
follow-up guidance, and application receipts use that canonical spelling.
`--from` cannot be combined with `--into` or positional Contexts.

Bare names such as `campus/wiki` remain global Context names. Only `.`, `..`,
`./...`, and `../...` opt into current-relative lookup. They describe the
slash-delimited Context namespace, not shell directories or filesystem paths.
The command snapshots the current Context once and resolves every relative
operand against that same name.

The first invocation performs one bounded semantic analysis, saves a
non-applying relation ledger and proposal, and opens the interactive
workbench in a terminal. Repeating the same resolved incoming–baseline command
resumes without another provider call. Directional roles are ordered:
reversing the two Contexts is a different operation.

The shared issue and whole-set actions use the directional command prefix:

```bash
mem meld INCOMING --into BASELINE \
  --issue 1 \
  --choice 2 \
  --comment "Only vehicle access is closed; keep the stairwell open."

mem meld INCOMING --into BASELINE \
  --comment "Apply this scope to every related parking-access rule."

mem meld INCOMING --into BASELINE --expand 1
mem meld INCOMING --into BASELINE --preserve-all
mem meld INCOMING --into BASELINE --defer-all
mem meld INCOMING --into BASELINE --accept
```

`--preserve-all` respects the authority direction: it keeps the baseline
unless incoming evidence explicitly supports a correction and retains
supported incoming distinctions with their scope. `--defer-all` keeps the
analysis as review-only. Neither action changes either Context.

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
mem meld INCOMING --into BASELINE --restart
```

Both Context-to-Context modes currently accept bounded Contexts containing
direct owned Memories only. Memory references, embedded Contexts, and
query-only references are rejected rather than dereferenced or silently
omitted.

### Why `--into` is not `--to`

`--into` communicates authority and mutation: incoming evidence is considered
against an existing baseline, and explicit acceptance may create that
baseline's next state. It is intentionally not an alias for `--to`.

`--to` is reserved for a different future shape:

```text
mem meld LEFT_PEER RIGHT_PEER --to RESULT_CONTEXT
```

That form would name a distinct result for a symmetric meld and would not make
either peer authoritative. Reusing `--to` for directional mutation now would
make those two contracts indistinguishable. Until explicit symmetric result
selection is implemented, symmetric meld continues to use the current empty
Context as its target.

## Symmetric Context meld: combine two equal-authority Contexts

### 1. Compare the peers in the intended display order

```bash
mem switch LEFT_PEER
mem compare --to RIGHT_PEER
```

This saved `LEFT_PEER → RIGHT_PEER` analysis is the exact read-only basis for
the Meld. The reverse Compare slot is deliberately different and is not used
as a fallback. If either source changes, rerun the command with `--refresh`
before starting or restarting the Meld.

### 2. Create and enter an empty result Context

```bash
mem init RESULT_CONTEXT
```

The current Context is the target. It must be empty. Neither peer source is
mutated.

### 3. Start or resume the symmetric meld

```bash
mem meld LEFT_PEER RIGHT_PEER
```

The first invocation imports the exact Compare overview, relation ledger, and
grounding candidates without another provider call. It preserves their frame,
relation, issue, and option identities in the target-bound Meld session but
does not treat inspection as permission to create target Memories. In a
terminal this opens the interactive workbench. Repeating the same command
resumes the saved session. Outside a terminal it prints the saved snapshot.

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
  --issue 1 \
  --choice 2 \
  --comment "Keep both rules, but state their separate scopes."

mem meld LEFT_PEER RIGHT_PEER \
  --comment "Preserve every source-supported exception."

mem meld LEFT_PEER RIGHT_PEER --expand 1
mem meld LEFT_PEER RIGHT_PEER --preserve-all
mem meld LEFT_PEER RIGHT_PEER --defer-all
mem meld LEFT_PEER RIGHT_PEER --accept
```

`--expand`, resume, defer, and acceptance are provider-free. Issue comments,
whole-set comments, and preserve-all create semantic turns. `--accept` applies
the ready result to the current empty target without mutating either peer.
When Compare reports no grounding candidates, use a whole-set comment or
`--preserve-all` to request the first reviewable target materialization; a
resolved Compare ledger alone is not write authority.

Use `--restart` only when intentionally replacing the saved review session
after rechecking that the target is still empty:

```bash
mem meld LEFT_PEER RIGHT_PEER --restart
```

## Deliberate boundary

The three implemented entry points share a meld reasoning contract but retain
distinct CLI shapes and authority:

```text
one saved atomize issue + clarification
→ mem atomize --evaluate
→ issue-scoped directional meld ("atomic meld" shorthand)

one read-only incoming Context + one authoritative baseline
→ mem meld [INCOMING] --into BASELINE
→ or mem meld --from INCOMING while BASELINE is current
→ Context-wide directional meld

two equal-authority Contexts + empty result Context
→ mem meld LEFT_PEER RIGHT_PEER
→ Context-wide symmetric meld
```

“Atomic” remains a scope shorthand, not `mem meld --atomic`; canonical `--into`
and its current-baseline `--from` convenience remain directional; and the
unimplemented `--to` remains reserved for a distinct symmetric result Context.
