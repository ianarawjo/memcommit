# Study Task 3 agent-driven terminal debug log

## Purpose and evidence boundary

This note records the agent-driven Task 3 exercise so the workflow can be
repeated without relying on conversation history. The task-solving portions of
the run used the CLI as a black box:

- use only `mem help`, command `--help`, the Task description, and information
  visibly rendered by the terminal;
- do not inspect fixture source, a solution, an answer key, or scoring data;
- operate interactive screens through literal keyboard input, including arrow
  keys;
- use a TTY for interactive screens and non-TTY output only where the public
  command contract calls for it; and
- report ambiguous behavior rather than silently infer a hidden command or
  answer.

The first run was performed from the repository root on 2026-08-09 in Study
Profile `study-20260809T215815Z-03fed00a`. The worktree already contained many
unrelated in-progress changes, so this is an observational debug record rather
than a clean-baseline benchmark.

The report distinguishes three evidence types:

1. terminal output retained in the conversation;
2. durable public CLI state reconstructed later through `mem profile`,
   `mem contexts`, `mem show`, and `mem log`; and
3. source-guided implementation work that occurred only after the black-box
   run exposed a product question.

The first run did not retain one byte-complete raw PTY transcript. Exact key
sequences are recorded only where the conversation preserved them; missing
keys are not reconstructed from inference.

## Visible Task and initial navigation friction

The visible Task description said that a government AI healthcare agent had
requested access to broad personal Memory and required the participant to
decide what to provide, exclude everything else, and transfer only the selected
information.

The first usability failure occurred while trying to read the description.
`mem contexts` displayed the exact public Context name, but passing that name as
the positional operand in:

```text
mem show task-3/description
```

treated it as a direct item selector inside the current Context. The command
therefore failed even though the name had just been shown by `mem contexts`.
`mem show --help` disclosed the actual grammar: the positional operand is a
Memory/reference/embed selector, while the parent Context belongs in
`--context`. The reliable public forms are:

```text
mem show --context task-3/description
```

or:

```text
mem switch task-3/description
mem show
```

This was a command-model mismatch, not a missing Context. Operand-free
`mem show` is useful because it shows the current Context and avoids forcing a
person to guess whether a displayed Context name is also a positional selector.

## Early curation failure and interpretation

The first curation attempt reached Forget/Sever behavior before the contents
needed to define a concrete disclosure purpose had been read. The resulting
logic proposed removing everything. The run did not treat an all-drop result as
proof that no information should be shared.

The important semantic observation was that selective curation answers the
criterion it is actually given. If the criterion effectively asks whether each
Memory has a concrete purpose, recipient, or necessity, but none has yet been
supplied, every item can consistently fail that test. In that case an all-drop
proposal is not necessarily a decoder or mutation failure; it can be the
literal consequence of an underspecified criterion.

The Source remained conceptually distinct from the result: Sever determines
which content survives into a new derived Context, while leaving Source
unchanged. It is therefore a keep/transform/drop projection, not an operation
that deletes selected fields from the Source in place.

This first failure changed the next-run policy. A normal participant should
read the available Memory and recipient guidance, state a specific purpose and
recipient, minimize disclosure, preserve uncertainty, and only then execute
selective curation. A visible error or surprising proposal should be recorded,
but the full safe workflow should continue unless the error prevents further
progress.

## First-run criteria and reviewed draft

The eventual ordinary Criteria Context was:

```text
task-3/local/healthcare-sharing-criteria
```

The public Context state later showed eight direct Criteria Memories and one
live embedded Context, `task-3/local/guardrails`. The eight direct items froze:

- the intended receiver endpoint and unknown downstream recipients;
- the healthcare-arrangement purpose and possible service-improvement use;
- the requested accessibility, environmental, explanation, support-contact,
  scheduling, and continuity categories;
- exclusion of private causes behind preferences or limitations;
- exclusion of unrelated life details and unnecessary third-party data;
- staleness treatment for medication, availability, contact, and functional
  history;
- a requirement that the result remain a local review draft until exact
  recipient, purpose, channel, and content were reviewed together; and
- uncertainty about downstream use, routing, retention, and deletion.

The same eight Memories and embed were retained in
`task-3/local/healthcare-sharing-criteria/branch2`. The public state alone does
not preserve the exact command-by-command construction order, so this report
does not claim whether each item was added individually or through a batch.

The resulting reviewed local Context was:

```text
task-3/local/healthcare-sharing-draft
```

`mem show` later confirmed `116 memories`, no references, no query-only
Contexts, and no embeds. Its contents were ordinary copied/derived Memories,
not a live selection view. The draft included accessibility and environment
observations, communication preferences, scheduling safeguards, historical
healthcare facts with explicit current-confirmation boundaries, and limited
support information. It also retained some arguably broad environmental and
travel history, which is a useful review question for an alternative run.

## External transfer

The endpoint was visible through `mem contexts` as:

```text
task-3/government/healthcare-agent  [view share ...]
```

`mem share --help` identified Share as the operation that sends one ordinary
Context through a grant-backed receiver endpoint. Sever alone only created the
local review result; it did not satisfy the Task's explicit transfer clause.

The completed command attempt took approximately 22.2 seconds. The authority
Profile later exposed the received ordinary Context:

```text
task-3/remote/government/healthcare-agent/received-shares/
743073b8-47f0-54bb-94c4-026abb7cf301
```

`mem show` confirmed that the receiver stored `116 memories`, matching the
reviewed local draft. The received items had fresh Memory UIDs, consistent with
a transferred copy rather than a live reference to the participant store.

## Timing and trace limitations

The retained Profile operation list later showed:

- one provider-backed Find attempt: approximately `459.2s`;
- one long Query attempt: approximately `1663.8s`, ending after a visible
  `Ctrl-C` key event;
- Share: approximately `22.2s`; and
- several immediate read-only Find, Log, Status, Profile, and Reference calls.

The operation ledger's recent window had already dropped earlier events, and
the content-free Study action ledger warned that 226 earlier sequence positions
were unavailable. These values therefore establish timings and operation
presence, not a complete chronological keystroke trace. The approximately
seven-and-a-half-minute delay discussed during the run aligns with the recorded
459.2-second provider-backed Find attempt.

## Product change motivated by the run

The run exposed a missing inverse to Forget/Sever in Find. Search could identify
relevant Memories, but it could not preserve the checked result set as a durable
review input. The implemented interactive Find flow now supports:

```text
MATERIALIZE AS
[ COPY ] [ REFERENCE ]

SAVE LOCATION
task-3/local/results/accessibility
```

`COPY` creates independent new Memories; `REFERENCE` creates read-only live
pointers with the same semantics as `mem reference`. Both require an explicit
fresh local Save Location and leave Source and the current Context unchanged.
History, query-only, and artifact results remain evidence-only. The design,
authority, freshness, and compatibility boundaries are recorded in
`agent-records/docs/mem-find-search-workbench-design-rationale.md` and commit `1420abb`.

An actual isolated 80-column by 24-row PTY exercise sent literal keys through
search, two result checks, COPY/REFERENCE selection, Save Location editing, and
To Do creation. It then changed Source and confirmed that REFERENCE updated,
COPY remained unchanged, and the current Context did not move. The ten captured
states are under `agent-records/outputs/find-materialization-screens/`.

## Alternative-run method

The next run should use a fresh Study Profile and preserve the same black-box
boundary, but deliberately choose a different information architecture:

1. read the Task and public command grammar first;
2. use interactive Profile-wide Find to retrieve narrowly phrased candidate
   classes;
3. check only visibly relevant current-Memory results and materialize them as
   `REFERENCE` Contexts under a local `task-3/local/results/...` namespace;
4. treat those references as auditable, live candidate collections rather than
   immediately copying a broad semantic projection;
5. build one concrete Criteria Context from the visible purpose, recipient,
   minimization, uncertainty, and existing guardrails;
6. use Sever to create a fresh ordinary reviewed share Context from the
   personal Source against that Criteria; and
7. use Share only after inspecting the exact result count and representative
   contents.

This path tests whether Find can reduce discovery and review burden without
turning search results themselves into the transmitted artifact. It also tests
the current limitation that a granted result can be copied but not referenced,
and whether an 80×24 materialization layout remains usable in a real Study
Profile rather than only the isolated harness.

## Alternative-run execution record

The alternative run used fresh Study Profile
`study-20260810T000728Z-54da735c`. A manually driven 120-column by 40-row PTY
reported `40 120` through `stty size`. Every interactive transition was sent as
terminal key input; ordinary inspection commands used their documented
non-TTY form. The run did not inspect fixture, answer, or scoring files.

### Discovery references

After reading the description, `mem contexts`, all ten direct guardrail
categories, and the readable 25-Memory public transmission guidance, the run
switched to `task-3/local/personal-memory` and opened operand-free interactive
Find.

The first query was:

```text
healthcare accessibility needs, noise, seating, entrances, and communication preferences
```

It returned five current-Memory results. Each was opened by moving the Results
cursor with Down and was checked with Enter. Right changed Materialize from
COPY to REFERENCE; Tab moved to the exact Save Location; `Ctrl-U` replaced the
generated name with:

```text
task-3/local/results/accessibility-communication
```

The command created five read-only live references and explicitly reported
that Source was unchanged.

The second query was:

```text
healthcare scheduling availability, reminders, preparation, and current contact information
```

Four of five results were checked. The unchecked result described the user's
older sister and a historical contact-list update; retaining that third-party
event was unnecessary for the discovery purpose. The second materialization
created:

```text
task-3/local/results/scheduling-preparation
```

with four live references. Both semantic searches completed in approximately
30 seconds during the manually observed run. The generated Save Location was
longer than the visible one-line field, so only its tail remained visible while
editing. `Ctrl-U` plus a known exact name worked, but the field did not show the
whole reviewed locator at once.

The two result Contexts were deliberately not embedded into Criteria and were
not transmitted. Their role was to preserve auditable discovery evidence and
make overbroad or stale candidates visible before whole-frame curation.

### Alternative Criteria

The run created:

```text
task-3/local/healthcare-sharing-criteria-find
```

Eight direct Memories defined the exact grant-backed receiver, a healthcare
arrangement and explanation purpose, the smallest useful support categories,
third-party exclusion, stale-history treatment, the non-approval status of the
Find references, unknown downstream behavior, and the final joint review
boundary. `mem embed` then added the existing
`task-3/local/guardrails` Context as one live embed.

Public inspection confirmed `8 memories`, `1 embedded context`, and no
references. The executable Sever criterion frame contained those eight direct
Memories plus the 75 guardrail descendants, for 83 Criteria Memories total.

### Sever review and application

The public explicit command was:

```text
mem sever \
  --source task-3/local/personal-memory \
  --criteria task-3/local/healthcare-sharing-criteria-find \
  --save-as task-3/local/healthcare-sharing-draft-find \
  --source-descendants \
  --criteria-descendants
```

The progress screen froze and analyzed `300 SOURCE × 83 CRITERIA` as one whole
frame. The provider analysis screen changed to the review workbench after
approximately 242 seconds. The operation ledger later reported 617.1 seconds
for the complete command, including manual review and final application; its
provider configuration displayed a 600-second timeout, but no timeout occurred.

The complete report proposed 97 result Memories from 300 Source Memories. The
review sampled:

- item 1: the user's mother's birthday, recommended `FORGET` because it was
  unrelated to healthcare support;
- item 2: a private family-meal noise event, recommended `SUMMARIZE` as the
  minimal historical fact that noisy environments had made conversation nearly
  impossible; and
- item 300: a parent-owned yard and time-of-day heat observation, recommended
  `SUMMARIZE` with ownership removed and current conditions explicitly requiring
  confirmation.

End moved the Items cursor to decision 300. Backspace returned to the complete
report. One navigation attempt appeared to leave the last opened treatment
unselected and changed To Do from `APPLY is available` to
`Resolve 1 required item`; moving to Responses with Tab and pressing Enter on
the first `Use recommendation · SUMMARIZE` row restored the selection. This
record states the observed transition but does not infer whether it was a
focus-count error or a state bug.

The final review showed `RESPONSES · 300/300 ANSWERED`, `OPEN REVIEWS · NONE`,
and `Nothing changes until the final action below is confirmed.` Enter on
Review and Apply presented that receipt without applying. Three Tab events
moved from Viewer through the visible surfaces back to To Do, and a separate
Enter accepted the exact action. The terminal then reported:

```text
SEVER · APPLIED · SOURCE UNCHANGED
OUTPUT · task-3/local/healthcare-sharing-draft-find · CREATED LOCALLY
```

The local result contained 97 ordinary Memories, no references, no query-only
Contexts, and no embeds. The current Context remained the Criteria Context.

### Transfer and receiver verification

The exact outbound command was:

```text
mem share task-3/local/healthcare-sharing-draft-find \
  --to task-3/government/healthcare-agent
```

It returned:

```text
Shared Context.
Share: 675fa52f-9c7f-57aa-831e-6b36a8654984
Memories: 97
Consent digest: 2d316e225557a9d26509783639974d6931d20d13129edd6962758b593c764aae
```

The authority Profile exposed the matching receiver Context at:

```text
task-3/remote/government/healthcare-agent/received-shares/
675fa52f-9c7f-57aa-831e-6b36a8654984
```

`mem show` confirmed 97 receiver Memories with fresh UIDs. The participant
Profile was selected again after this read-only verification.

### Comparison and remaining concern

| Observation | First run | Find-first alternative |
|---|---:|---:|
| Discovery collections | none durable | 5 + 4 live references |
| Direct Criteria Memories | 8 | 8 |
| Embedded guardrails | 75 | 75 |
| Whole-frame Source Memories | 300 | 300 |
| Reviewed ordinary result | 116 | 97 |
| Receiver copy | 116 | 97 |

The alternative sent 19 fewer Memories and removed more private event and
third-party context. The discovery references made individual candidate
quality inspectable without becoming the outbound artifact.

The 97-Memory result is still arguably broad. It generalized several
non-healthcare observations about coffee and sleep, reading concentration,
footwear, heat, water, and administrative documents into possible healthcare
support guidance. That is safer than copying their private event context, but
it may still exceed a strict necessity interpretation. A future variant should
test a hard allowlist materialized directly from multiple reviewed Find result
sets, or run a second Sever pass whose criterion requires explicit connection
to a current requested support category rather than merely possible usefulness.

## Alternative-run captures

The durable contact sheet and its nine individual 120×40 terminal-state images
are under:

```text
agent-records/outputs/study-task-3-alternative-screens/
```

They cover the visible Task, both reference collections, Criteria, first and
last Sever decisions, the 97-Memory result, the Share receipt with receiver
verification, and the first-run comparison. The rendering script stores the
exact backing text beside each PNG so later layout changes can be distinguished
from semantic-output changes.
