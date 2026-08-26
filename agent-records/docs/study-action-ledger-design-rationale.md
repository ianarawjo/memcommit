# Study action ledger design rationale

## Problem and scope

The generic command-attempt ledger proves that a `mem` command started and how
it ended, but it cannot reconstruct an interactive Study run. In particular,
it does not say which arrow, Enter, Tab, or back-navigation keys were used,
whether a provider connection or turn failed, or whether a final review was
shown and accepted. Those distinctions matter when a person follows only a
task description and visible terminal state and the resulting interaction is
later used to debug the research prototype.

Detailed recording is therefore enabled only for the two Profiles created by
current `mem init-study`: the participant Profile and its run-private
granted-memory Profile. Ordinary, baseline, imported, and legacy split Study
Profiles retain only the generic command-attempt ledger. The discriminator is
the validated immutable `ProfileEntry.source` Study UID and role, never a
display-name prefix. Renaming either Profile does not silently disable or
broaden recording.

Within the detailed Study ledger, content-bearing events are narrower again.
Only the Participant duplicates the reconstructed full command and retains
focused Help lookup wording/results. The granted-memory Study action ledger
keeps content-free phases and interactions. Its generic command-attempt ledger,
like every Profile's, still retains the complete command.

## Storage and correlation

Each eligible Profile keeps append-only JSON Lines files under:

```text
ledger/study-actions/ATTEMPT_UID.jsonl
```

Every event carries a random event UID, a strictly increasing sequence within
the command attempt, the generic command-attempt UID, Study UID/name, Profile
UID/role, UTC occurrence time, optional monotonic elapsed time, one allowlisted
action, and action-specific allowlisted data. Files and directories use private
permissions, reject symbolic links and unexpected directory entries, and are
fsynced after append. Readers require complete newline-terminated JSON,
strictly increasing sequence numbers beginning at one, and exact stable
Study/Profile identity. The Study name is the historical display label observed
when the event was written: `mem profile rename-study` does not rewrite the
append-only files, and readers continue to bind events by Study UID, Profile
UID, and role. A gap left by an earlier recorder build remains readable and is
reported as unavailable telemetry; duplicate or decreasing sequence numbers
still fail closed. The current recorder advances its in-memory sequence only
after a durable append, so a rejected event cannot create a new gap.

The participant and granted-memory Profile each receive `STUDY_CREATED` under
the `init-study` attempt UID. The participant additionally receives
`PROFILE_ENTERED`; a Study Profile that was active when another Profile was
selected receives `PROFILE_LEFT`, and an entered Study destination receives
`PROFILE_ENTERED`. A switching command's normal command lifecycle remains in
the Profile that was active when the process started, matching the generic
ledger's frozen-root rule.

## Captured actions

An eligible command records:

- command start and finish, terminal presence and available terminal size;
- for the Participant only, the complete entered argv reconstructed as one
  safely POSIX-quoted `mem ...` command after shell expansion;
- exact non-printable prompt-toolkit input such as Up, Down, Left, Right,
  Enter, Escape, Tab, Shift-Tab, Backspace, control keys, and paste boundaries;
- stable names for non-text key variants whose prompt-toolkit wire value is not
  a ledger-safe token; terminal protocol responses such as CPR continue to the
  renderer unchanged but are not recorded as person actions;
- printable input and pasted text only as character count, line-break count,
  paste flag, and focused control class;
- provider connection and completion phases, provider/operation identity,
  schema presence, input/output character counts, elapsed time, and coarse
  exception class;
- explicit semantic actions emitted by shared surfaces, initially Resolution
  workbench return actions, final approval presentation/acceptance, and the
  distinct local auto-accept used when a reversible proposal has no required
  person decision;
- content-free waiting Help actions, including opening/closing the shared
  inventory, the public command identifier whose forms were inspected, and
  whether the original result or error became ready while Help remained open.
- for Participant focused Help, the normalized natural-language request and,
  after successful validation, the exact three public operation IDs in their
  visible rank order.

The terminal recorder wraps the prompt-toolkit application session at the root
command boundary, so existing TUIs do not need parallel arrow-key machinery.
The exact focused control is sampled when input is read. Semantic surfaces add
events when a key's meaning matters more than its physical spelling; this is
why a reviewed Apply can be distinguished from an Enter that merely opens a
detail. Provider work moved to a responsive executor inherits the active
recording context. Because its provider events can overlap foreground Help
navigation, one recorder lock serializes both sources into the same durable,
gap-free attempt sequence.

## Privacy boundary

The Participant action ledger is deliberately no longer content-free. Its
`COMMAND_ENTERED` event can contain Memory text, query text, names, paths, or a
credential if the person supplied that value as an argv operand. This is why
event is restricted to immutable current-Study Participant provenance; the
generic all-Profile command-attempt record now retains the same canonical
command independently. The canonical string preserves argv values and
boundaries, not the person's original quote spelling, aliases expanded by the
shell, pre-expansion variables, or shell redirections.

Focused Help additionally retains the normalized request as a typed event so
the Study can relate participant wording to the exact ranked suggestions. It
does not retain the complete catalog prompt or raw provider response.

Printable input delivered later through prompt-toolkit remains redacted to
character and line-break counts. At that shared input boundary a printable
`q`, `f`, or `p` could be either a shortcut or private text already buffered
before a focus transition, and the recorder cannot safely infer its meaning.
Provider prompts and responses, stdout/stderr, environment values, stdin,
clipboard contents, and terminal protocol responses are not retained. Surfaces
that know a shortcut's semantic result may still publish an allowlisted
`TUI_ACTION` instead.

Provider character counts describe envelope size, not token usage or content.
Exception classes are retained, while exception messages are not. Event data
uses a closed schema rather than an arbitrary metadata dictionary so a caller
cannot accidentally add private payloads.

## Inspection and failure behavior

`mem log --actions` reads only the active current-Study Profile, prints recent
events first (including Participant `COMMAND_ENTERED` and focused Help text),
and omits its own in-flight attempt. `mem log --operations`
continues to show the smaller ledger available in every Profile. `mem profile`
groups a current Study pair under its immutable Study name and labels the two
live Profiles `Participant` and `Granted memory`.

If Study recording cannot start, command dispatch fails instead of silently
running an unrecorded Study command. If a normal command completes but its
final Study event cannot be appended, the generic attempt is finalized as a
logging failure. When `init-study` or Profile selection has already published
its atomic registry mutation and destination logging then fails, the CLI says
that the Profiles were created or the selection changed; it does not claim a
rollback that did not occur. A command's original failure remains primary if
ledger finalization also fails.

## Alternatives and limitations

- Duplicating raw commands into the granted-memory detailed action log remains
  unnecessary because its generic command-attempt ledger already retains them.
  The Participant duplicate is deliberate event-timeline evidence beside Help,
  provider, input-count, review, and approval events.
- Storing one combined Study log was rejected because the participant and
  authority are independently selectable store roots. Shared attempt and Study
  UIDs provide correlation without creating a third mutable store.
- Duplicating a granted mutation as an authority-side semantic action was
  rejected. The participant command records its action; normal grant/checkpoint
  receipts identify the authority effect. The authority Study log records only
  commands actually entered while that Profile is active, plus pair creation.
- The ledger records terminal input delivered through prompt-toolkit. Input
  consumed before application construction, OS-level mouse gestures, signals
  not represented as keys, and a hard process kill between two appends cannot
  be reconstructed. A retained `COMMAND_STARTED` without `COMMAND_FINISHED`
  remains the evidence for abrupt loss.
- This is durable research telemetry, not a cryptographically chained or
  tamper-evident audit system.
