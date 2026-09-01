# Context-or-inline-Memory operand rationale

## Status

Update and Meld accept an unambiguously non-Context string as one exact,
process-local Source Memory. Their new-session TUIs additionally expose the
Source shape as an explicit three-way choice: `CONTEXT`, `STORED MEMORY`, or
`INLINE MEMORY`. The shared application classifier lives in
`memcommit.application.capabilities.context_operand_classification`; each
operation retains its own frame, session, authority, provider, review, and
Apply semantics. Console-only arbitration between positional and named
endpoint spellings lives separately in
`memcommit.adapters.console.coordination.endpoint_operand`, so application
code does not depend on CLI grammar.

The same low-level classifier and direct-Memory resolver now back `--goal`
without making Goal a Source. The separate typed projection and role contract
are documented in
[`goal-focus-operand-design-rationale.md`](goal-focus-operand-design-rationale.md).

## Motivation

Directional semantic work often starts with one idea that has not earned a
durable Context yet. Requiring a temporary Context for that idea adds storage
and cleanup without adding authority. For example, both of these should start
an Update against `practice/rules`:

```text
mem update "want to make all the last word as fruits" --to practice/rules
mem update --from "want to make all the last word as fruits" --to practice/rules
```

The same Source shape is useful for a directional Meld. The raw string is
evidence to reconcile with the target; it is not a generic provider
instruction and it never becomes a named Context.

## Shared classification contract

The command snapshots the current Context once, then classifies each
Context-or-inline operand in this order:

1. If the resolved existing-Context locator exists, it is a Context.
2. Relative locators (`.`, `..`, `./...`, and `../...`) remain Context
   locators even when absent.
3. A value that satisfies the portable Context-name grammar remains a Context
   locator even when absent.
4. Only a value that cannot be a portable Context name becomes inline Memory
   content.

This deliberately does not implement “storage miss means text.” A misspelled
portable name such as `pratice/rules` must still fail as a missing Context
rather than silently reaching the provider as different evidence. Existing
legacy Context names also retain Context meaning because existence is checked
before portable-name validation. Ambiguous short text such as `apple` requires
the explicit `--memory apple` spelling.

Shell tokenization remains outside this contract. Multiword content must be
quoted so that it arrives as one operand; without quotes, Click receives
multiple positional operands and reports the command's ordinary arity error.

## Operation mappings

Update treats one positional Source plus `--to TARGET`, or `--from SOURCE`
plus `--to TARGET`, as `SOURCE -> TARGET`. When Target is omitted, the current
Context is used. `--memory TEXT` forces the Source to be inline content.
Inline Source descendants and Source-Memory focus are invalid because the
temporary frame already contains exactly one Memory.

Two positional Update operands always retain the published `SOURCE TARGET`
order. Inline text is supported only in the Source role, so
`mem update practice/rules "all should be fish names"` must not be guessed as
a reversed request: the second operand is the Target and cannot be inline
text. The diagnostic names both roles and points to
`mem update --memory TEXT --to CONTEXT`. This preserves typo safety while
making the asymmetric string support visible at the point of failure.

Meld uses operand shape to interpret `--to`:

- with fewer than two positional Source Contexts, `--to` names the
  authoritative directional baseline;
- with two positional peer Contexts, `--to` names the distinct symmetric
  Result Context.

Thus `mem meld --from "sentence" --to practice/rules` is directional, while
`mem meld PEER_A PEER_B --to RESULT_C` remains symmetric. Saved directional
receipts use `--into` as their canonical authority-bearing spelling even when
the accepted input used the shape-compatible `--to` alias.

## Persistence and application boundary

Neither operation writes the synthetic Source to the Memory store, makes it
current, lists it, or checkpoints it independently. Meld retains its existing
schema-9 inline frame. Update emits schema 8 only for inline Source sessions
without Goal focus; unchanged whole-Context and focused sessions retain
schemas 6 and 7. A stored Goal focus uses schema 9, or schema 10 when combined
with inline Source, so its durable pre-image can be retained and revalidated
without changing older records.

Update derives deterministic process identities from the exact inline
content. This allows the exact command to resume the same target-bound staged
session without creating a Context. Apply reconstructs and validates that
synthetic Source while locking and compare-and-swap validating only durable
target Contexts. The reviewed target mutation, checkpoint, Undo, and Redo
boundaries are otherwise unchanged.

For this rollout, inline Update and Meld targets must be ordinary local
Contexts. In each setup TUI, selecting `INLINE MEMORY` replaces the Source
Context controls with one process-local text field and constructs the same
canonical `--memory TEXT` command used at the CLI boundary. Selecting `STORED
MEMORY` retains an owner Context and requires one exact direct Memory UID;
selecting `CONTEXT` retains exact-or-descendant Context reach. Switching types
never interprets a missing Context name as inline text. Directional Meld
exposes the choice only for its incoming Source; symmetric Meld remains two
Context peers. Impact Update retains its existing saved/Context endpoint
grammar. Supporting granted inline targets or wider operation rollout requires
a separate authority and interaction review.
