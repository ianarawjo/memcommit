# Shared Goal focus operand design rationale

## Motivating scenario

The same reviewed outcome may already exist as an ordinary Context, as one
ordinary Memory, or only as text entered for the current command. These forms
must have the same semantic role:

```text
mem makemore --from coffee-advice --to coffee-advice \
  --goal coffee-advice/goal
mem distill --from coffee-advice --to coffee-advice \
  --goal coffee-advice/goal:<memory-uid>
mem update --from new-advice --to coffee-advice \
  --goal "Help a friend's café operate reliably."
```

Previously, `--from` used the migrating Context/Memory/text operand family,
while operation-specific `--goal` parameters were plain strings or rejected a
Context supplied beside `--from`. That made an existing name such as
`coffee-advice/goal` ambiguous at the wrong layer and caused Makemore to reject
the motivating command as if the Goal were a second generative Source.

## Contract

`FrozenGoalFocus` is the operation-neutral value. It contains an ordered frame
of `GoalFocusItem` values and records whether the operand was process-local
`INLINE`, one durable `MEMORY`, a direct-Memory `CONTEXT`, or a physical
`GROUND` `/goals` projection. Durable items retain Context UID, Memory UID,
content digest, and complete Context digest; inline text receives no fabricated
durable provenance.

`freeze_goal_focus_operand` shares the existing operand classifiers and direct
Memory resolvers used by the Context-targeting migration:

- an existing exact Context wins;
- `CONTEXT:UID`, a UUID, or an unambiguous short UID selects one direct Memory;
- unambiguous natural language is process-local text;
- `text:` forces literal text when it otherwise resembles a locator; and
- a missing relative or portable-looking Context fails closed, so a typo is
  never silently disclosed to a provider as Goal text.

A Context Goal may contain several direct ordinary Memories for operations
whose relevance criterion is a frame. Stable `g000001` aliases preserve their
boundaries in prompts and receipts. Operations that own a single durable Goal,
notably physical Ground creation and `/goals` replacement, request exactly one
item and continue enforcing the 40-word durable Goal limit.

## Semantic invariant: focus is not Source

A Goal focus selects, constrains, and helps assess supported output. It cannot
support a Distill Rule, satisfy a Makemore Rule check, serve as an Update
`source_id`, or authorize a fact absent from the operation's Source frame.
Consequently `--from SOURCE --goal FOCUS` is valid: Source and focus are
different roles even when both operands happen to locate ordinary Contexts.

- Distill retains its exhaustive post-generation Goal Fit judgment and carries
  the exact focus frame into proposal and publication receipts.
- Makemore includes the focus frame in generation identity for both
  Goal-to-Rules and Rules-to-Cases. In the standalone `--goal`-only form, the
  one Goal item is also the generative Goal Source for compatibility; beside
  `--rule` or `--from`, it is only auxiliary focus.
- Update stores the focus in its session, exposes it separately from Source and
  Target payloads, retains it through revision, and revalidates its durable
  pre-image while holding the Apply locks. This is a narrow relevance binding,
  not the still-future multi-turn Update issue-resolution adapter.

## Physical Ground

A physical Ground does not gain a scalar Goal field. Its durable Goal remains
an ordinary Memory in `<ground>/goals`; the shared focus value is only an exact
semantic projection of that lane. Creation and `--set-goal` may copy one
Context/Memory/text operand into that lane and record the operand provenance in
the Ground checkpoint.

Distill, Makemore, and Fit consume the same physical Goal Memory. Distill and
Makemore remain proposal-only by default. `--adopt` is the separate explicit
effect boundary for a physical Ground: it adds the complete proposal to
`/rules` or `/examples`, advances the manifest once, records the semantic
analysis digest, and publishes one Ground-local command unit that local Undo
can reverse. Proposal generation revalidates only its consumed frame; adoption
additionally requires the reviewed whole-Ground revision and destination lane
pre-image. The retired JSON Ground session has no adoption or compatibility
path.

## Freshness and publication

Durable Goal focus identity participates in cache keys, session records,
checkpoints, and Source bindings. It is revalidated before provider disclosure,
after inference where applicable, and at the relevant write boundary. Generated
Memories publish all-or-none. A changed Goal, consumed Source, Ground revision,
or destination lane rejects publication rather than silently reinterpreting a
reviewed proposal.

An inline Goal is intentionally process-local and therefore has content
identity but no Store lock. Copying an external Goal into physical `/goals`
creates a new ordinary Memory; the checkpoint retains where the copied content
came from, but the new Memory does not become an alias or live synchronization
link.

## Compatibility and limitations

Legacy application calls that pass a plain Distill or Makemore Goal remain
readable and are normalized to an inline focus internally. Existing Update
session schemas remain readable; the Goal-aware schemas are used only when a
focus is present. Public Python adapters have not yet added a polymorphic
string operand parser because their callers already pass typed values or plain
content; CLI operand interpretation remains an interface concern.

This change does not make a named Ground automatically coordinate every
semantic operation, promote every clarification into a Rule, or implement the
documented multi-turn directional Update grounding lifecycle. Those require
their own issue, response, recomputation, and approval contracts.
