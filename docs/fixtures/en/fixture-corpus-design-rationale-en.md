# Design Rationale for the Three-Task Memory Fixture Corpus

## Decision Summary

The Korean source fixtures use the following scale:

- Task 1: 375 ordinary Memories and 78 query-only Memories
- Task 2: 300 ordinary Memories and 75 query-only Memories
- Task 3: 375 ordinary Memories and 75 query-only Memories
- Total: 1,050 ordinary Memories, 228 query-only Memories, and 1,278 overall

In the original workflow, English translation and installation into actual
Contexts are separate stages after review of the Korean content. Counts are an
outcome, not a target. The corpus provides enough retrieval, comparison,
conflict, and update cases, but first requires every Memory to merit independent
review.

## Atomicity: One Independently Changeable Proposition per Memory

Each candidate contains only one fact or action rule that can be independently
retrieved, verified, modified, and approved. It is split if any of the following
can change independently:

- different states or events;
- different times, locations, or targets;
- actions that can be applied or revoked separately;
- exceptions with a different source or approval boundary; or
- a clause whose truth can change while the rest remains valid.

A condition may remain in the same Memory so the scope of an action is not lost.
Sharing a condition, however, does not justify combining multiple states,
actions, constraints, exceptions, or enumerated items in one Memory. If each can
be judged true or false or modified independently, it is split strictly, with
the conditions needed to understand each child repeated. Independent
reviewability, not punctuation, is the criterion. For example, these are three
separate Memories:

1. The main entrance's general closing time changes from 10 p.m. to 5 p.m.
2. The existing `accessible ramp` is unavailable while it is rebuilt.
3. A temporary `accessible route` beside the main entrance remains available
   throughout construction.

This strict split is not a formal division intended to increase the count. It
makes each independently verifiable component, agent operation, prohibition,
and exception its own unit of modification. An atomic child remains traceable
to its parent's fixture ID or source relationship but is a separate review unit.

### Splitting a verified compound row

`Verified` is the review state of the exact current wording in a particular row.
A checked row that is already atomic is not changed by later automated
normalization. When a user explicitly approves a later instruction to split a
compound proposition, however, that instruction supersedes the fixed boundary
of the existing compound row. New children do not automatically inherit review
of the former compound wording. Each child starts unchecked and is reviewed
again, while the source relationship to the original row is preserved.

Copying the checked state would make new wording the user has not reviewed look
approved. Conversely, ignoring the latest instruction to split would mistake
`Verified` for a lock that blocks an explicit user modification. The chosen
asymmetric rule is therefore: **preserve atomic reviewed rows, and review again
the children of an explicitly approved compound split**. If the user explicitly
requests a change to a checked atomic row itself, the new wording likewise does
not inherit the earlier review, so its check is cleared.

## Separating Hierarchical Memory Location from Purpose

Topic classification is not duplicated in both a separate column and a purpose
code. The intermediate directory in `Memory Location` identifies the topic, and
the leaf identifies a stable item.

```text
dataset/directory/leaf
```

Examples are `construction-updates/building-access/03-hours`,
`campus-wiki/route-changes/17`,
`advisor1/methods/question-evidence-analysis`, and
`personal-memory/2024-06/03`. This structure supports browsing Memories on the
same topic while eliminating a separate `Category` column that would largely
repeat the purpose label.

Purpose is independent of path. One directory may contain facts, policies, a
User Model, and models of other actors. Encoding purpose in the path would turn
a purpose reassessment into a Memory move and couple topic retrieval to use
function, so that design was rejected.

## Six Purpose Codes

The review sidecar assigns each candidate's primary use function one of six
codes:

- `KB` — **Knowledge Base**: facts directly retrieved and verified, such as
  institutions, entities, facilities, rules, current states, definitions, and
  records.
- `PP` — **Procedural Policy**: actions, procedures, prohibitions, and
  confirmation rules the agent should perform or avoid.
- `SM` — **Self Model**: the local agent's own role, capabilities, observation
  and inference limits, authority, uncertainty, and working assumptions.
- `UM` — **User Model**: the current interacting user's expectations,
  preferences, familiarity, discomfort, confusion, experiences, and decision
  tendencies.
- `WM` — **World Model**: structures, dependencies, constraints, causality, and
  expected effects governing how the external environment operates and changes.
- `OM` — **Other Model**: a model of what a relevant actor other than the current
  user expects and prefers and how that actor is likely to judge and respond.

### Purpose-assignment questions

Purpose is determined by the question a Memory answers in downstream reasoning,
not by its grammatical subject or which characters appear in it.

1. Does it directly retrieve a verifiable entity, rule, state, or record? Then
   it is `KB`.
2. Does it say what the agent should do or avoid? Then it is `PP`.
3. Does it say what the agent itself can do and cannot observe, guarantee, or
   infer, or which working assumption it relies on? Then it is `SM`.
4. Does it say what the current user expects or prefers, where the user
   experiences discomfort or confusion, or which choice the user is likely to
   make? Then it is `UM`.
5. Does it describe how the external environment operates through structures,
   dependencies, constraints, or causality independent of minds? Then it is
   `WM`.
6. Does it say what a relevant actor other than the current user expects,
   prefers, judges, or is likely to do? Then it is `OM`.

“Service animals may use the general entrance” mentions a person and an action
but is a verifiable access rule, so it is `KB`. “Most users are enrolled
students” is also `KB` when it states only a flat fact about the user population.
A student carrying only a mobile student card may not expect a physical-card
requirement and may choose the wrong entrance or have to prepare a different
authentication method; that is `UM`. A general statement that an
access-guidance agent answers questions is not by itself a strong `SM`, but the
agent's inability to observe a door's lock state in real time is `SM`. A user
assumption can also be `SM` when the central point is that the agent uses it as
a premise in its own reasoning or recognizes the assumption's limits.

`WM` is not a residual category for flat facts such as location, time, and
current state; those are `KB`. Only content used to predict the external
environment's structure or change belongs in `WM`, such as one entrance closure
changing pedestrian flow through another entrance or one service shutdown
increasing congestion at another facility. Model-purpose statements do not
assert mental states without evidence. They use an observed experience or
strength-calibrated language for an interpretation expected in the synthetic
scenario, such as “expects,” “may prefer,” or “may check again.”

### Other Model boundary

`OM` is not a residual category for external information that does not fit `KB`
or `WM`. It is used when a family member, passerby, reviewer, intake worker,
hospital department, or institution other than the current interacting party is
modeled as an **actor**. Actors unrelated to the actual task are not forced into
the corpus. For example, treating a nearby shop employee or neighborhood
resident who has no reason to use the main building's third floor as an `OM`
actor for the rear-entrance route would be inappropriate.

The role and observation limits of the local guidance agent are `SM`, not `OM`.
An on-site guide is not invented to create `OM` examples. Separate actors who
participate independently in the task are used instead, such as an external
tour leader, contracted operator, delivery company, or mobility-support
companion. Model statements do not reduce every response to “confusion” or
“discomfort”; they record consequences of expectations and preferences for
actual choices, such as choosing a familiar entrance, rechecking intake
conditions, adjusting staffing or inventory, and considering an alternative
route.

The existence or closure of a facility is `KB`. A relationship in which
facilities and routes connect and one closure changes another flow is `WM`. A
verifiable operating fact such as an institution's intake procedure is `KB`,
while what a reviewer looks at first or finds difficult to accept is `OM`. The
current user's own expectations and preferences are `UM`; even when family
appears, a sentence whose primary function is to explain the user's experience
may still be `UM`.

### Expressing Procedural Policy

`PP` does not describe the existence of a rule declaratively. It uses an
imperative that a Memory consumer can apply directly, such as “do,” “do not,” or
“instruct the user to.” Permission remains permission, and optional advice
retains its force rather than becoming an obligation. A state or relationship
with no acting subject or selectable action is not given an imperative ending;
it receives whichever of `KB`, `SM`, `UM`, `WM`, or `OM` matches its actual
function.

Purpose is neither a prefix in Memory content nor a field in current Memory
JSON. It is stored only as a two-letter ticker in a fixture-ID-keyed TSV and the
review sheet. This permits researcher review of classification without
contaminating the content searched as Memory.

## Intended Audience Is Design Intent, Not an ACL

Task 1's `All`, `Visitor`, `Student`, `Staff`, and
`Construction/Building Personnel` fields are review checkboxes for intended
disclosure to those audiences. This designer sidecar provides neither per-Memory user
authentication nor authority enforcement. Ordinary Memories currently perform
no principal-specific disclosure check, so these columns must not be described
as a security mechanism.

The query-only label is likewise a research interaction boundary that requires
a question instead of direct listing. It does not guarantee actual user
authentication, role-based ACLs, legal confidentiality, or operational
security. A real deployment requiring security needs separate authentication,
authorization, and audit boundaries.

## Shared Information Hierarchy in the Review Sheet

Task 1 ordinary tables use this common order:

```text
Verified | Memory Location | All | Visitor | Student | Staff | Construction/Building Personnel | Purpose | Content | Source File
```

Location conveys topic and item identity, the five checkboxes convey intended
disclosure scope, and purpose conveys use function. These three axes are not
mixed. All cells wrap naturally and row height fits their content. Short columns
such as checkboxes and purpose remain narrow, while content, diffs, and
provenance are relatively wide.

Every Memory data sheet uses a shared two-row visible header that shows only a
summary title and column headers at the top of the screen. Rows 2–4, which
contain candidate-count calculations, review formulas, material descriptions,
and native-table markers, are preserved but hidden. Keeping these hidden rows
allows the title's review indicator to be calculated and the descriptions and
table structure to be recovered without moving existing data rows, checkboxes,
or formula references. The overview sheet is a corpus-level dashboard rather
than a Memory list, so the two-row rule does not apply to it.

## Task 1

### Structure and scale

- `construction-updates`: 75
- ordinary `campus-wiki`: 300
- query-only `campus-wiki · construction-details`: 78

The purpose distribution is:

| Dataset | KB | PP | SM | UM | WM | OM | Total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `construction-updates` | 35 | 16 | 8 | 6 | 4 | 6 | 75 |
| `campus-wiki` | 162 | 41 | 41 | 29 | 15 | 12 | 300 |
| `campus-wiki · construction-details` | 34 | 38 | 0 | 0 | 0 | 6 | 78 |

The two ordinary datasets use corresponding directories for building access,
events and spaces, parking, shops and services, facilities and floors, and
routes and accessibility. Each operational area contains `OM` examples genuinely
related to the task, distinguishing expectations and judgments of actors other
than the current user—such as an external tour leader, contracted operator,
delivery company, or mobility-support companion—from facility facts. An on-site
guide is not invented to meet a count, and a surrounding group with no reason to
use the main building is not pulled in. The query-only details likewise contain
`OM` examples in each directory for work, dependencies, reporting, materials,
verification, and disclosure scope.

The update packet is limited to 75 so participants can focus attention on the
units of change they must actually judge. The baseline wiki, in contrast, is
expanded to 300 so it provides not only existing information that directly
conflicts with construction but also ample public-campus-information-style
background: floor-by-floor facilities, public operating hours, event and space
reservations, parking and transportation, shops and food services, visitor
support, and accessible routes. The asymmetry between a small change packet and
a larger organizational knowledge base is intentional and reproduces a
realistic update task.

“Public-information-style” does not mean copied from real public material. The
university, buildings, facilities, shops, stops, and relative locations are all
pseudonymous synthetic information created for research; they do not correspond
to a real school, city, address, phone number, business, or existing place.
Detailed construction work, inspections, materials, and internal reporting are
not copied into this expansion and remain only behind the
`campus-wiki · construction-details` query-only boundary.

### Change-only update packet

`construction-updates` contains only states, routes, policies, and information
needs that actually differ from the baseline. Ordinary facts, general usage
habits, and the agent's existing capabilities or limitations remain only in the
larger `campus-wiki`; they are not duplicated in the update packet. Every update
source must produce at least one actual `edit` or `add` patch. `retain`, a no-op
whose before and after text match, and a semantically duplicate addition of an
existing Memory are disallowed. `UM` and `OM` do not restate a changed
destination or route as fact. They record task-relevant experiences and
anticipated behavior caused by the change: who may choose a familiar route
again because pre-construction expectations differ from construction-period
reality, which information someone may recheck, or how someone may change a
plan.

### Accessible terminology and advance guidance

Accessibility-related wording is standardized as `accessible ramp`,
`accessible route`, `accessible entrance`, and `accessible restroom`. Unfamiliar
new Korean compounds are not used because they could make the same facility
look like a different concept.

If only the closure of the route connecting the third-floor rear entrance to
the central library is stored, a student who ordinarily uses that route cannot
respond until reaching the blocked point. A separate `PP` therefore requires
advance notice that the route is unavailable when a student is about to head
that way. A verified alternative is provided only when one exists; an
unsupported west entrance is not invented. The closed state is `KB`, advance
guidance is `PP`, and the possibility that a student expecting the usual route
may reach the closure and turn back or look again for an alternative is `UM`.

### Update locations and inline diffs

The `construction-updates` table places these columns to the right of the common
columns:

```text
Update Location | Target Memory | Operation | − Existing Content | + Applied Content
```

Putting update results in a separate table would require moving back and forth
between each source Memory and its actual patch, making correspondence easy to
miss after sorting or filtering. Edit and add results therefore appear directly
to the right of each source. The red `−` and green `+` retain their colors and
symbols, while the `Operation` column keeps the meaning accessible without
color. When one source changes multiple targets, numbered corresponding patches
are listed in the same cell. The authoritative normalized sidecar for the 1:N
relationship and complete before/after content remains
`task-1-update-actions-en.tsv`. The current 75 sources produce 77 actual patches,
and every operation is `edit` or `add`.

`campus-wiki` uses the same hierarchical Memory Location and five audience
checkboxes, allowing update and baseline material to be compared on the same
location, audience, and purpose axes.

### Query-only construction details

`construction-details` is not a separate ordinary Context. It is the direct
query-only source attached to the ordinary `campus-wiki` Context. The review
view displays it as `campus-wiki · construction-details` so its affiliation is
clear, but the current explicit query form is
`mem query construction-details ... --context campus-wiki`. A middle dot is
used because a slash in the review label could be mistaken for an ordinary
Context namespace. Detailed construction content is not copied into ordinary
`campus-wiki` Memories to circumvent the query-only boundary.

## Task 2

### Equal advisors and relationship groups

`advisor1` and `advisor2` each contain 150 Memories and use the same
16-directory order. The advisors have equal authority; neither is constructed
as an answer key or distractor. The added items enable more granular,
independent review of the user problem, design contribution, prototype, methods,
evaluation, and design or operational decisions in an HCI master's research
proposal. They are not intended to create a hierarchy of authority or amount of
information. All 16 directories include `OM` examples capturing anticipated
judgments by actors other than the current user, including reviewers,
participants, operators, and financial reviewers.

The two advisors are co-advisors for master's research in the same HCI lab.
Rather than repeating shared external guidelines, they interpret in HCI terms
how to frame the user problem, what counts as a design contribution, which
prototype and user research support the claims, and which design or operational
decisions the results would change. Advisor 1 places somewhat more weight on
controlled formative evaluation and conceptual design knowledge, while Advisor
2 places somewhat more weight on field deployment and actionable design and
operational guidance. Their authority remains equal.

The purpose distribution is:

| Dataset | KB | PP | SM | UM | WM | OM | Total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `advisor1` | 10 | 95 | 8 | 8 | 8 | 21 | 150 |
| `advisor2` | 10 | 95 | 8 | 8 | 8 | 21 | 150 |
| `proposal-submission-guidelines` | 2 | 57 | 2 | 2 | 2 | 10 | 75 |

Even after strict atomization, semantic correspondence is preserved as stable
relationship groups. `pair_id` is an existing compatibility name in the
sidecar; `left_fixture_ids` and `right_fixture_ids` are the actual group-member
lists. If one original piece of advice is split into multiple Memories, their
Fixture IDs are recorded as a semicolon-separated list in the corresponding
field of the same group. A relationship band applies to the two member sets; it
does not mean that every possible left–right ID combination is an independent
pair.

Most groups are `Near Duplicate`, `Same-Principle Variant`, or
`Context-Dependent Variant`. Even after expansion, actual conflicts remain at
only 3 relationship points and explicit complements at only 2. This helps
participants distinguish duplication, contextual variation, and genuine
conflict rather than treating every difference as disagreement. Relationship
bands are a golden sidecar, not Memory content or advisor priority. If a fully
atomic pairwise answer key is later needed, it must be created separately from
this group sidecar.

The three conflicts are limited to authoring choices that a participant without
research-methods training can understand and decide:

- `T2-009`: whether a branching procedure should use a flow diagram that makes
  alternate outcomes visible at once or a sequence table that is faster to
  update during drafting;
- `T2-014`: whether independently reviewable claims should be split into short
  sentences or connected thoughts should retain a longer reading rhythm; and
- `T2-026`: whether em dashes should be avoided because they can trigger
  suspicion of AI-generated prose or allowed conditionally for a deliberate
  interruption or contrast.

The surrounding Advisor Memories retain observations, user preferences, and
costs that make each recommendation intelligible. They do not serialize a
separate rule/benefit/cost explanation. A parent-scoped Rationale can infer the
relationship from readable descendant Memories, while provenance remains a
separate access decision.

Existing differences about using subheadings, first-person versus impersonal
style, and placing a budget in the body versus an appendix can be combined or
selected based on sentence function or official format. They remain contextual
or same-principle variants. The former conflicts about question paradigm,
evaluation setting, and contribution form were removed because they require
domain expertise and are largely determined by the proposal's research context
rather than an ordinary participant's authoring judgment.

### Detailed two-page submission guidance

The query-only `proposal-submission-guidelines` contains 75 Memories in 10
directories, with an `OM` example in every directory. An abstract rule to
“write a good proposal” cannot establish whether the final artifact satisfies
the requirements. The following are therefore atomized:

- one searchable PDF, file size, deadline time, and submission criterion;
- two-page limit, font, type size, page format, and margins;
- required content for summary, background, objectives, methods, outcomes,
  schedule, budget, and ethics;
- specific word ranges for each section;
- trace relationships from question to data to analysis, risk to mitigation,
  and cost to activity; and
- post-submission administrative review and the local agent's limit in
  guaranteeing acceptance.

These guidelines are not evaluation criteria for a particular subfield. They
are a domain-neutral submission contract for compressing an application-oriented
master's research project into two pages. Here, domain-neutral means that the
guidelines do not presume HCI; it does not mean they cover purely theoretical
research. Two pages is document length, not a two-week research duration. The
external guidelines determine what must be submitted, while the two advisors
propose how to express it in HCI. Adding interpretations such as prototypes,
field deployments, or a particular design contribution to the external
guidelines would effectively create a third advisor and resolve the intended
differences prematurely, so that alternative was rejected. Human-subject
research, artifact development, field application, budget, and ethics items
apply only to research for which they are relevant.

## Task 3

### Monthly personal-memory

The 300 `personal-memory` Memories retain stable source keys in 30 monthly
buckets from `2024-01` through `2026-06`, with ten Memories per month. Generated
Study Profiles place those same records under three materialized year Contexts,
so the runtime path is `personal-memory/2024/01` rather than
`personal-memory/2024-01`. The source key remains unchanged to preserve fixture
and Memory identity across this topology-only refinement. Topic categories were
rejected because they would erase how daily-life records accumulate over time
and require a separate time axis to recover when the user learned something.

Content centers on nonclinical daily life such as family gatherings, household
tasks, utilities, administrative work, living expenses, mobility, reading, and
travel; only a small number of healthcare-related Memories remain. Research,
demos, paper writing, and friendships are excluded. Specific synthetic family
roles—mother, father, older sister, younger brother, maternal aunt, and maternal
uncle—are used, and the maternal aunt is explicitly the keeper of the spare key.
Traumatic family history is not invented.

Each month centers `UM`, producing 184 User Models. `UM` states events, actions,
and preferences directly, without restating the source of a memory through
phrases such as “wrote that” or “recorded that.” When keeping a photograph or
entering something in a calendar is itself the event, however, that verb remains.

The dataset neither insists on specific events alone nor immediately compresses
every event into a stable profile. It may contain an event in which conversation
was impossible in a noisy restaurant, a quiet-location preference derived from
repeated experiences, and a personal policy to check noise when proposing a
location. The event → inference → policy connection allows observation of which
evidence and compression level a downstream agent selects for a sharing
candidate. The fixture author does not predetermine the correct level of
anecdotal detail or the point at which it should be compressed into a preference
or policy. This balance is itself a qualitative research question in the
selective-sharing task.

The base monthly composition includes one `KB` and one `OM`; the other two
positions rotate among `PP`, `SM`, and `WM` by month. In some months where the
model boundaries were reapplied, flat facts were reclassified as `KB` and user
expectations or friction as `UM`, producing additional `KB` or `UM` and fewer
rotating positions. The sentence's actual function takes priority over
mechanical monthly balance, while all six purposes remain represented across the
complete dataset. Personal-record status alone does not make every Memory `UM`.

This dataset neither copies nor closely paraphrases source text from the local
IdeenKasten. Only recurring semantic types informed synthetic rewrites from
which names, institutions, projects, real locations and dates, third-party
statements, rare event combinations, diagnoses, and node IDs were removed. It
is therefore not a complete or authoritative profile of any real person.

### Guardrails and healthcare information-request specification

The ordinary `guardrails` dataset contains 75 Memories. It covers the purpose
and scope of selective sharing, protection of third parties, evidence and
uncertainty, approval and delivery, and retention and revocation, as well as
recipient authority, minimization and redaction, channel and format, downstream
use, and auditing and recovery. The guardrails contain no `UM`. Predetermining a
preference such as “the user wants to review personally” inside the guardrails
would present one behavior as the right answer before a participant forms their
own sharing criteria. Because that could prime experimental behavior, external
conditions such as copies, transmission, and synchronization are modeled as
`WM`, and anticipated recipient or organization interpretations as `OM`, in
place of user preferences.

The canonical locator of the query-only external Context is
`government/healthcare-agent/information-request`, which contains 75 Memories.
This material is not a set of rules that directly decides healthcare-support
outcomes or constructs a transmission copy. It is a specification explaining
the consent, use, and sharing consequences when a user actually sends
information to a government healthcare institution system. Pointing directly
to a particular `personal-memory` event would reveal an answer to participants,
so examples stop at general categories actually represented in
`personal-memory`: mobility, waiting, accessible entrances, weekly availability
and reminders, family contact, questions, checklists, one-line explanations, and
past medication instructions. Capability limits of the information-request
agent are separated as `SM`; expectations and request strategies of external
requesters, misrouted clients, and automated agents that can actually send
requests to this endpoint are `OM`. Family contact remains an example of an
information category that may be shared, but there is no separate scenario in
which a family member accesses or submits on the user's behalf.

Information transmission in the task is not conversational collection by this
agent. It is a one-time act in which the participant sends locally reviewed
information through a government healthcare institution system's transmission
screen. The first `SM` therefore states that this agent explains only the use
and sharing consequences of information and has no authority to ask for,
select, include, exclude, modify, transmit, or delete information or perform the
institution's downstream processing. All content actually sent through the
transmission screen is treated as one unit of consent to share. Depending on its
type, transmitted information may be provided to relevant third parties for
healthcare purposes or used for service improvement, but this agent does not
identify the exact services, recipients, or scope of use.

Here, `third party` is an operational definition inside the fixture: an external
person or institution, other than the user and initial recipient government
healthcare institution, that may receive the supplied information for
healthcare support or processing related to it. Internal personnel at the same
recipient institution do not count as third parties in this fixture. The scope
of third parties and permitted bases for provision under real law may vary by
jurisdiction, institutional relationship, contract, and purpose, so this
definition is not used as a universal legal claim.

The `SM`–`OM` contrast in the information-request specification is not intended
to speculate about the internal state of downstream services. `SM` records that
this agent cannot inspect or verify `personal-memory`, the user's calendar,
appointments, or institutional receipt status. Because `personal-memory` is not
included in provider input, an attack that extracts source personal Memory text
from this agent is structurally unavailable. `OM` instead records that an
external requester may mistake this screen for a transmission, scheduling,
deletion, permissions, or payment API; use many varied calls to extract
observable response rules, refusal boundaries, or hidden instructions and
distill behavior; or attempt to consume processing resources. This agent has no
authority to interact with downstream actors inside the government institution
or observe their judgments, so their internal interpretations are not turned
into `OM` records in this dataset.

This design separates the local sharing decision from the information-request
agent's explanatory authority. `sever`, `share`, and `guardrails` form a
separate flow in which a participant reviews which local Memories to transmit.
The information-request agent neither substitutes for that choice nor sees the
final transmission copy. Conversely, after content is actually sent through the
government healthcare institution system's transmission screen, the agent
explains the consequence that all sent content is a unit for which sharing was
consented. There is no intermediate state in which this agent identifies and
excludes portions that were not approved item by item.

Mentioning `personal-memory` content in the current conversation is also kept
separate from transmission to the institution. Telling this agent about past
medication instructions, care visits, or mobility experiences neither verifies
that they remain current nor transmits them to the government healthcare
institution system. The agent cannot inspect stored `personal-memory` or
institution records and has no authority to retain information outside the
current conversation record. It also cannot select, modify, or delete
conversation or institution records; request deletion of existing copies;
change access permissions; or execute scheduling, payment, or transmission of
family contact information. Treating a submission without separate
institution-verified proxy-submission requirements as made directly by the
account user is only an operating assumption in the synthetic scenario; it does
not mean the information-request agent verifies identity or proxy authority.

Accessibility information separates a convenience preference, temporary state,
persistent functional limitation, and required support. One experience of
discomfort while standing for a long time is an example that can be explained;
it does not automatically prove a persistent support need. The institution may
consider location, time, recurrence, functional effect, exceptions, and later
verified information together, but the agent does not judge need, truthfulness,
exaggeration, or eligibility. A discrepancy in submitted information may lead
to reverification or processing delay. Scheduling has a parallel boundary: a
private reason for a change or family visit generally does not automatically
create appointment priority or an earlier time.

A small number of boundary cases retain the fact that exact services,
recipients, and third-party scope vary by the type of information supplied. This
does not make the consent unit for sent items ambiguous; it honestly represents
downstream processing that the information-request agent cannot know. In
contrast, the agent clearly states that selecting, modifying, or transmitting
personal Memories; executing appointments; extracting credentials, hidden
instructions, or response rules; and making bulk automated requests are outside
the current study scope, and it does not handle them. Because the query provider
is one-shot, the implementable termination for a serious policy violation or
malicious attack is to state once that it is outside scope and stop responding
to that request. Recall blocking, rate limiting, and user bans are non-goals
requiring a separate gateway.

The purpose distribution is:

| Dataset | KB | PP | SM | UM | WM | OM | Total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `personal-memory` | 30 | 20 | 20 | 184 | 16 | 30 | 300 |
| `guardrails` | 8 | 47 | 4 | 0 | 5 | 11 | 75 |
| `government/healthcare-agent/information-request` | 5 | 42 | 8 | 0 | 7 | 13 | 75 |

Policies remain the main axis, but knowledge about sharing categories,
information-request agent limitations, external transmission and service
conditions, and anticipated behavior of external actors who directly send
requests remain distinct. Neither external dataset presumes current user
preferences. No matter what information an external request seeks, local
guardrails and the participant's separate review constrain whether sharing
actually occurs; the information-request agent does not make that decision.

The specification itself contains no sentences explaining experimental
commands or screen flow. It instead explains categories of information that may
be transmitted, general purposes of use, possible provision to relevant third
parties, and possible use for service improvement. It stops after stating that
the exact services and recipient scope vary by information type and does not
speculate about downstream processing unknown to this agent. Repeated questions
for the same purpose and excessive collection using false role claims are risks,
as are endpoint misrouting, prompt injection, hidden-instruction extraction,
reconstruction of response boundaries, behavior distillation, and bulk
automated calls that are actually possible through this screen. Capabilities
the agent lacks—selecting, modifying, deleting, or transmitting personal
Memories; deleting existing copies or changing permissions; and executing
scheduling, payment, or contact—are not turned into action results or Memories.
The specification also preserves the distinctions between past medication
instructions and currently applicable medication directions, and between a
recurring time-of-day preference and actual availability in a particular week.
These boundaries are not hints that make the research task easy; they model the
actions and misuse possibilities of real information-sharing guidance.

## Synthetic and De-identification Boundary

- Task 1 and 2 institutions, people, construction, and policies, and the Task 3
  guardrails and healthcare information-request specification, are synthetic
  material created for user research.
- Task 1 spaces draw only shallowly on facility relationships possible in a
  multi-building urban comprehensive university. They do not use a real school
  name, building name, city, address, business name, phone number, construction
  project, or inspection outcome.
- The two Task 2 advisors are fictional roles with equal authority.
- Task 3 personal Memories are de-identified semantic reconstructions. They do
  not retain real sentences, names, institutions, projects, locations, real
  dates, third-party statements, rare event combinations, diagnoses, or source
  node IDs.

This boundary should be preserved at dataset level in installation-manifest
provenance, rather than repeating a synthetic marker in every Memory and
contaminating retrieval content.

## Query-Only Boundary

Task 1 detailed construction material, Task 2 proposal-submission guidance, and
the Task 3 government healthcare information-request specification assume a
research condition in which the required scope is obtained through questions
rather than by reading a direct list.

1. Answer only content explicitly supported by the material within an allowed
   topic.
2. Do not infer or invent facts absent from the material.
3. State when an out-of-scope question cannot be answered from the material.
4. Do not copy source text into ordinary Memories to circumvent the interaction
   boundary.

This does not provide actual user authentication, role-based ACLs, legal
confidentiality, or operational security.

## Remaining Non-Goals and Next Validation

The fixture-design stage described by the Korean source does not itself
implement:

- installation of Markdown into actual Contexts and Memories;
- per-Memory role-based access control and user authentication;
- operational security for query-only material;
- the English translation stage; or
- final golden outcomes for `compare`, `impact`, `meld`, and `sever`.

The next stage should create ID-based sidecars for expected duplicate,
conflict, modification, retention, and exclusion outcomes for each task. Those
sidecars should permit algorithm results to be reviewed without changing the
Korean content.
