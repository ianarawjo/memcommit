# Focused Memory semantic operations

## Motivation

Atomize, Compare, Directional Meld, and Update often need to act on one
Memory without discarding the local meaning supplied by its containing
Context. Projecting only the selected text makes references and scope harder
to interpret. Treating the whole Context as actionable, however, lets an
operation report or mutate Memories the person did not select.

The selected Memory is therefore the **actionable frame**, while the other
Memories in the already frozen Context projection are **context-only
evidence**. The provider may use the latter to interpret local meaning,
preserve unrelated facts, or detect duplication and conflict. Context-only
evidence must never become a visible relation member, proposal source,
provenance source, edit target, removal target, or newly materialized result.

This distinction is internal. Ordinary reports show the selected work and its
outcomes, not a second list explaining which neighboring Memories were sent as
context.

The shared application implementation names this boundary `MemoryScope` and
owns it at `memcommit.application.capabilities.semantic.memory_scope`.
Canonical Memory UID-shape recognition remains a core locator rule in
`memcommit.core.context_targeting.uid_locator`. Existing Endpoint Setup wording
and Meld's `memory_focus` provider marker are separate presentation and wire
contracts; this internal relocation does not rename or reinterpret them.

## Selection contract

The explicit command form accepts one UID or unambiguous UID prefix per role:

- `mem atomize --memory UID_OR_PREFIX`
- `mem compare --reference-memory UID_OR_PREFIX --compared-memory UID_OR_PREFIX`
- `mem meld INCOMING --into BASELINE --incoming-memory UID_OR_PREFIX --baseline-memory UID_OR_PREFIX`
- `mem update --from SOURCE --to TARGET --source-memory UID_OR_PREFIX --target-memory UID_OR_PREFIX`

Each binary flag is independently optional. An unselected side retains its
existing whole-frame behavior. A Memory selector cannot be combined with that
side's descendant-scope flag because a single ambiguous selector must not
silently acquire a broader public namespace.

The common new-session endpoint TUI exposes the same exact target without
requiring a UID to be copied. `m` reveals direct Memory rows; `Enter` or
`Space` checks one when the active operation role supports focus. The setup
receipt carries the exact selected UID into the same command boundary used by
the explicit flag. Atomize Input, Compare A/B, Update A/B, and Directional
Meld A/B opt in. Symmetric Meld and the whole-frame curation operations do not.
There is no persisted cross-launch default: tree cursor, checked Memory, and
setup receipt remain process-local until the operation freezes its normal
saved artifact.

With no Memory flag, the provider payload, saved behavior, and whole-Context
semantics remain compatible with the existing operation.

## Frozen selection and evidence

The command loads its normal Context projection and resolves the UID prefix
before provider connection. Resolution returns one exact selected UID, an
ordered actionable set, and an ordered context-only set. Missing and ambiguous
prefixes fail locally.

Provider aliases for actionable Memories are admitted to the operation's
output schema. Context-only aliases are deliberately absent from that schema.
This makes the evidence boundary structural rather than relying only on a
prompt instruction or filtering an already-visible result afterward.

The complete containing Context remains part of freshness validation. A
neighbor that changes after inference makes the result stale even though that
neighbor was not actionable, because it may have affected interpretation.
Application still uses the operation's existing Context/owner CAS boundary.

## Operation-specific meaning

### Atomize

Only the focused Memory is classified and only it may be split. Neighboring
Memories may resolve an ordinary referent or shared scope during judgment, but
they are not source evidence for a child. Every child must still cite literal
spans from the focused source, plus an explicitly reviewed declared frame when
the existing reviewed-frame contract permits it. This prevents a contextual
fact from being copied into a new child with fabricated lineage.

The saved analysis binds two different digests: the actionable Memory frame
and the complete ordered direct-Memory evidence frame. Apply replaces only a
selected composite source and preserves every unselected direct Memory.

### Compare

Only actionable Memories enter exhaustive source assignments and the visible
relation ledger. Neighbors on either side may help decide whether the selected
claims are equivalent, scoped, conflicting, or distinct, but they cannot
appear as one-sided findings. The full Context digest remains bound to each
focused frame.

### Directional Meld

Memory focus is supported only for Directional Meld. INCOMING context-only
Memories cannot ground results. BASELINE context-only Memories cannot be
edited. When a BASELINE Memory is selected, `ADD` is also unavailable because
it would create an out-of-scope sibling; the operation may edit the selected
Memory or surface an unresolved issue. A whole BASELINE still retains the
existing ADD/EDIT behavior. Each focused frame persists its exact selected UID
independently of the context-only list, so this boundary still holds when the
containing Context has only one Memory and therefore no neighboring evidence.

Focused Directional Meld does not reuse a whole-Context Compare or prewarm as
its relation basis. It runs one bounded Meld turn whose actionable ledger is
constructed directly from the selected roles and whose complete Context
snapshots remain freshness and CAS evidence.

### Update

Only an actionable Source Memory can be cited in `source_refs`. Only an
actionable Target Memory can be edited or removed. A focused Target exposes no
Target Context alias for additions, so the structured schema permits no ADD.
Unselected Target Memories remain available for preservation, duplicate, and
conflict judgment but cannot become operations.

The saved Update session records exact selected UIDs. Reuse, review revision,
application, Undo/Redo validation, and stale checks reconstruct the same focus
against the current full Context frames.

## Intentionally unsupported operations

Forget and Sever remain whole-frame selective-curation operations. Their
semantic invariant requires one complete Source frame and one complete
criterion frame in a single provider turn, followed by exactly one decision
for every Source Memory. They therefore expose no Memory-focus flag and do not
reuse this selection model. Adding per-Memory selection there would change the
meaning of omission and the complete-coverage safety guarantee, not merely
reduce input size.

## Limits and follow-up

This version selects at most one Memory per role. Context-only evidence is
still subject to each operation's existing one-shot provider budget; focus is
a semantic boundary, not permission to truncate or secretly batch the
surrounding frame. A future multi-select design must preserve the same
actionable/context-only alias separation and define exact checked-set identity
in every saved artifact before the common selector is widened.
