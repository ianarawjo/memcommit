# Editable proposed command composition

## Problem

Interactive setup screens and explicit CLI syntax describe the same operation,
but the final `PROPOSED COMMAND` was previously a one-way rendering. A person
could change a checked Context, Memory, mode, or placement and see the command
update, yet could not use the compact command itself to revise those controls.
Long UUIDs also made the most useful part of the receipt harder to scan even
where the CLI already accepts an unambiguous prefix.

The desired interaction is bidirectional without turning a shell string into
a second application service:

```text
visible controls -> proposed argv -> editable command form -> visible controls
```

Editing or synchronizing the command is not approval and must not publish
durable state. `RUNNABLE` means Enter can approve the current line, not that it
has already run.

## Shared component contract

`memcommit.adapters.console.terminal.components.command_editor` owns three new
operation-neutral pieces beside the existing immutable review and renderer:

- `CommandForm` and `CommandFormField` describe one operation prefix
  and its operation-owned grammar metadata.
- `CommandDraft` owns shell-like one-line parsing and live validity.
- `CommandEditorControl` owns the always-visible writable field, fixed
  operation prompt, bidirectional argument synchronization hooks, compact
  validity-colored frame, and writable-input protection.

The component does not know a Typer command, Context, Memory, provider, Store,
plan, or Apply action. Each operation supplies a parser/adapter that validates
the whole command against its frozen catalogs and only then updates its
process-local controls. The adapter must be all-or-none at the visible
selection boundary. Every complete valid buffer change updates those controls
immediately; every incomplete or invalid intermediate buffer turns the command
box red and leaves the preceding checked state intact. After synchronization, the
ordinary review factory rebuilds argv and effects from those controls; the raw
draft is never dispatched to a shell.

The form's operation prefix, such as `mem edit` or `mem embed`, is rendered as
a fixed `TextArea` prompt outside the writable buffer. Only the arguments are
editable. `Ctrl-U`, Backspace, selection deletion, and pasted text therefore
cannot remove or replace the operation being reviewed. Validation still
reconstructs and parses the complete command, so the fixed prompt is a UI
boundary rather than a weaker substitute for form-prefix validation.

Catalog adapters accept the terminal-safe escaped spelling already produced by
the exact-command renderer and map it back to one unambiguous raw identity, so
opening and saving an unchanged command cannot require rendering unsafe text.

Synchronization is not approval: it changes only process-local setup state.
The compact title says `COMMAND · RUNNABLE` when the synchronized command can
be approved and `COMMAND · INVALID` otherwise. The same field is the final
approval surface, so one Enter on a runnable line freezes the exact request.
Enter is blocked while the box is red. Escape cancels the
operation. Backspace remains normal text deletion inside the argument buffer;
it and other destructive editing keys cannot change the fixed operation
prefix.

The reverse direction is immediate as well. A retained change to Link Type,
Source/Child, Target, or Position rebuilds the canonical command in the field.
Cursor or hover movement does not count as a retained semantic change. If an
upper choice is temporarily incomplete—for example, Memory mode before a
direct Memory is checked—the red box shows an editable command seed until the
upper form becomes complete.

## Vertical uses: Embed and Edit

Embed exposes the complete editable form because every supported explicit
operand maps to an existing visible setup control:

```text
mem embed ITEM [--from SOURCE] --into TARGET
          [--before ITEM | --after ITEM]
```

The operation adapter owns the semantic mapping:

- presence of `--from` chooses Memory rather than Context link mode;
- `ITEM` selects the exact Child or an unambiguous directly owned Memory;
- `--from` and `--into` must name exact rows in the frozen Source/Target
  catalogs;
- `--before` or `--after` resolves inside the newly selected Target's frozen
  direct-item order; omission selects append;
- a Context Child must remain distinct from its Target; Memory Source/Target
  equality may be staged for inspection, but the normal frozen-plan boundary
  still rejects the recursive self-link before application.

Parsing, catalog checks, read-only Source/Target loading, and anchor resolution
finish before mode, Source, Target, and gap selections move together. The
normal Embed freeze then revalidates canonical identities, full UIDs, digests,
authority, and the exact gap before any mutation.

Edit adopts the same component for
`mem edit MEMORY_SELECTOR CONTENT --context CONTEXT`. Upper direct-Memory and
multiline-content changes rebuild the editable arguments, while a complete
valid argument edit updates both controls atomically. Its fixed `mem edit`
prompt prevents the final approval surface from being repurposed as Delete or
another operation.

## Short identifier display

Only fields whose CLI grammar already accepts UID prefixes opt into
abbreviation. Embed starts at seven characters, as requested, and extends the
prefix only when another identifier in the relevant frozen Source or Target
catalog collides. Arbitrary arguments and opaque plan digests are never
shortened by the shared renderer merely because they resemble a UUID.

The visible prefix is the actual argv spelling in the proposed command, not a
cosmetic replacement applied after shell quoting. The frozen plan still keeps
and revalidates the full canonical UID. The frozen typed review retains the
complete effects even though the compact command box does not repeat them.

## Endpoint Setup rollout

Branch, Meld, Update, and Sever now use the same editor at the bottom of their
unchanged upper setup interfaces. `EndpointCommandBinding` couples one
operation-owned `CommandForm`, canonical review projection, and complete argv
decoder. The common Endpoint Setup shell resolves decoded Context spellings
against its frozen role catalogs, infers existing-versus-new placement,
validates operation rules and direct-Memory identity, and only then replaces
mode, endpoint, reach, Memory, and new-name controls together.

The command editor tracks the last canonical review signature. A valid buffer
edit may therefore update upper controls without the next repaint rewriting
the person's still-focused spelling or argument order. Invalid text retains
that signature and remains visible in red. A later retained upper-control
change produces a new signature and intentionally replaces the stale command.
Entering the command surface also performs this conditional synchronization,
so queued terminal keys cannot approve an older command before a repaint.

Approval reparses the visible buffer and returns the resulting typed Endpoint
Setup draft. It does not rebuild a different request from stale upper fields,
spawn a child shell, connect a provider, or publish durable state. Branch,
Meld, Update, and Sever own codecs beside their command adapters; the shared
terminal component no longer contains operation-named projection modules.

## Remaining rollout boundary

The model also enables bidirectional argument editing for Embed, Edit, Memory
Transfer, and retained-history selection. Another setup flow may adopt it when
its complete explicit argv can be mapped back into visible process-local
controls without provider work, hidden persistence, or semantic loss.

Frozen-plan reviews such as Merge and Replace cannot safely adopt the editor by
only changing their displayed argv: an edit may require recomputing a complete
plan, issue set, digest, or authority snapshot. Those screens need an explicit
operation-owned replan transition before becoming editable. Ground also keeps
its existing allowlisted command and separate exact approval rules. Shared
visual chrome is not permission to weaken those boundaries.

## Evidence

Pure tests cover immutable operation-prefix isolation, shell quoting,
immediate all-or-none updates, reverse canonical projection, red invalid-box
styling, and collision-safe seven-character prefixes. Embed tests cover Context
and Memory grammar plus command-to-gap synchronization before freeze. The ordered
`180x52` color-PTY record under
[`screenshots/mem-embed-placement-20260813/`](screenshots/mem-embed-placement-20260813/README.md)
captures the compact blue runnable box, a red incomplete command box,
upper controls changing before Enter, invalid-command rejection, final
approval, success, and read-only durable verification.
The ordered Edit record under
[`screenshots/direct-memory-selector-actions-20260820/`](screenshots/direct-memory-selector-actions-20260820/edit-interaction-log.md)
additionally captures an attempted cross-operation argument paste while the
fixed `mem edit` prompt remains intact, followed by a valid bidirectional edit.
The ordered Endpoint Setup record under
[`screenshots/editable-endpoint-commands-20260830/`](screenshots/editable-endpoint-commands-20260830/README.md)
captures upper-to-command projection, a direct command edit, the resulting
upper-field reprojection, exact Enter approval, and the returned setup receipt.
