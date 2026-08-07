# Retiring `mem integrate`

## Decision

`mem integrate` is no longer a public CLI command. Its registration, Help
entry, command adapter, and granted-mutation route are removed together so the
inventory cannot advertise a semantic mutation path that the current workflow
has superseded.

The command accepted one free-text value, treated it as an assumed Memory, and
classified existing Memories as duplicate, update, or unrelated before a
small confirmation loop. That is the narrow middle of a directional Meld, but
it bypassed Meld's explicit INCOMING and BASELINE roles, saved relation ledger,
ambiguity/conflict review, shared provider contract, and common session UI.
Maintaining both surfaces would give nearly identical user intent two different
authority, provenance, and review guarantees.

## Compatibility boundary

Retirement does not rewrite history:

- Existing checkpoints whose command is `integrate` retain that exact command
  identity. Trace, restoration, Undo, and Redo may still render
  `mem integrate <INFO>` as a privacy-preserving reconstruction of the
  historical action; that text is not a currently executable suggestion.
- The frozen Integrate fixtures, scoring function, low-level semantic pipeline,
  and developer evaluation route remain available as research artifacts. Their
  names and digests are preserved so prior model results remain comparable.
- No historical Integrate record is relabeled as Meld. Doing so would falsely
  claim the stronger source-role, relation, and approval contract added later.

The retained low-level pipeline is evaluation-only. It must not be imported by
a new public mutation adapter or treated as a granted Context route.

## Alternatives considered

Keeping `integrate` as a direct alias for directional Meld was rejected. A raw
text operand has no durable source Context, source identity, or reviewed
INCOMING frame, so silently adapting it would make the alias appear stronger
than the supplied evidence. A deprecation period was also unnecessary for this
research prototype: preserving recorded history and frozen evaluation evidence
provides the needed compatibility without leaving an ambiguous live command.

If free-text convenience returns, it should explicitly construct a temporary
INCOMING frame and enter the common directional Meld review flow. It should not
revive a separate inference, permission, or persistence path.
