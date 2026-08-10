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
strictly increasing sequence numbers beginning at one, and exact Study/Profile
identity. A gap left by an earlier recorder build remains readable and is
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
- exact non-printable prompt-toolkit input such as Up, Down, Left, Right,
  Enter, Escape, Tab, Shift-Tab, Backspace, control keys, and paste boundaries;
- printable input and pasted text only as character count, line-break count,
  paste flag, and focused control class;
- provider connection and completion phases, provider/operation identity,
  schema presence, input/output character counts, elapsed time, and coarse
  exception class;
- explicit semantic actions emitted by shared surfaces, initially Resolution
  workbench return actions and final approval presentation/acceptance.

The terminal recorder wraps the prompt-toolkit application session at the root
command boundary, so existing TUIs do not need parallel arrow-key machinery.
The exact focused control is sampled when input is read. Semantic surfaces add
events when a key's meaning matters more than its physical spelling; this is
why a reviewed Apply can be distinguished from an Enter that merely opens a
detail.

## Privacy boundary

The detailed ledger still does not store raw argv, printable keystrokes,
Memory/query/composer text, provider prompts or responses, stdout/stderr,
environment values, credentials, or query-only material. At the shared input
boundary a printable `q`, `f`, or `p` could be either a shortcut or private
text already buffered before a focus transition. Recording every printable
key exactly would copy answers and authored Memories into a second durable
surface. The shared recorder therefore redacts all printable input to counts;
surfaces that know a shortcut's semantic result may publish an allowlisted
`TUI_ACTION` instead.

Provider character counts describe envelope size, not token usage or content.
Exception classes are retained, while exception messages are not. Event data
uses a closed schema rather than an arbitrary metadata dictionary so a caller
cannot accidentally add private payloads.

## Inspection and failure behavior

`mem log --actions` reads only the active current-Study Profile, prints recent
events first, and omits its own in-flight attempt. `mem log --operations`
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

- Expanding the generic ledger for every Profile was rejected because ordinary
  authoring does not need interaction telemetry and should keep the smaller
  privacy surface.
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
