# English Memory Fixtures for User Research

## Status

This directory contains the **English translations of the Korean design
sources** for three tasks. These documents do not yet install actual Contexts or
Memories; installation happens in a separate stage after content review and
translation review. Every institution, person, construction project, policy,
schedule, and personal event is synthetic or a de-identified semantic
reconstruction for user research.

## Count Contract

| Task | Ordinary material | Query-only material | Total |
| --- | ---: | ---: | ---: |
| Task 1 | `description` 2 + `construction-updates` 75 + `campus-wiki` 300 = 377 | `campus-wiki · construction-details` 78 | 455 |
| Task 2 | `description` 2 + `advisor1` 150 + `advisor2` 150 = 302 | `proposal-submission-guidelines` 75 | 377 |
| Task 3 | `description` 2 + `local/personal-memory` 300 + `local/guardrails` 75 + public healthcare guidance 25 = 402 | `remote/government/healthcare-agent/info-request/questions-and-answers` 75 | 477 |
| Total | 1,081 | 228 | 1,309 |

`Ordinary material` and `Query-only material` describe participant
interaction. Physically, all 1,309 records are ordinary Memories: task-local
records live in task Profiles, and granted material lives in task-specific
authority Profiles. A `QUERY` grant, rather than a special source file,
enforces the query-only view in the generated study packages.

The counts are not targets for mechanically fragmenting sentences. Each Memory
candidate contains one proposition or action rule that can be independently
retrieved, verified, modified, and approved. If time, location, target, exception,
or outcome can change independently, each belongs in a separate Memory.
Conditions, actions, and exceptions may remain together only when they define a
single decision rule.

## Shared Structure

### Memory locations and atomicity

`Memory Location` is a hierarchical locator sidecar of the form
`dataset/directory/leaf`. The intermediate directory in this path provides topic
classification, so there is no separate `Category` column. Purpose codes are an
independent axis. Memories with different purposes can appear in the same
directory, and the same purpose can appear across multiple directories.

When a compound candidate is split, the existing fixture ID and source
relationship remain traceable, but each resulting child is treated as a new
Memory candidate. Even if children share a condition, period, or target, states,
actions, constraints, exceptions, and enumerated items are split whenever they
can be verified independently. The conditions needed to understand each child
on its own are repeated. For example, a change to main-entrance hours, closure
of an existing `accessible ramp`, and provision of a temporary
`accessible route` are three Memories because each can change independently.

### Six purpose codes

| Code | Name | Decision criterion |
| --- | --- | --- |
| `KB` | Knowledge Base | Facts directly retrieved and verified, such as institutions, entities, facilities, rules, states, and records |
| `PP` | Procedural Policy | Actions, procedures, prohibitions, and confirmation rules the agent should perform or avoid |
| `SM` | Self Model | The local agent's own role, capabilities, observation and inference limits, authority, and working assumptions |
| `UM` | User Model | The current user's expectations, preferences, familiarity, discomfort, confusion, and decision tendencies |
| `WM` | World Model | Structures, dependencies, constraints, and expected effects governing how the external environment operates and changes |
| `OM` | Other Model | Expectations, preferences, judgments, and anticipated responses of relevant actors other than the current user |

A model purpose is not assigned merely because a person or agent appears in a
sentence. “Service animals may use the general entrance” is a verifiable rule
and therefore `KB`. A flat fact about user-population composition, such as
“most users are enrolled students,” is also `KB` by itself. In contrast, a
student who carries only a mobile student card may not expect a physical-card
requirement and may choose the wrong entrance or have to prepare another
authentication method; that is `UM`. A sentence that mentions a third party but
only states a facility condition or operational fact is `KB`; it is `OM` only
when it models what that actor expects, prefers, judges, or is likely to do.

The role performed by a local guidance agent, or an on-site condition it cannot
inspect in real time, is `SM`, not `OM`. We do not invent an on-site guide to
fill an `OM` quota. Only separate actors genuinely relevant to the task are
modeled, such as an external tour leader, contracted operator, delivery company,
or mobility-support companion. `UM` and `OM` records do not repeat every
response as “confusion” or “discomfort”; they also capture actions such as
choosing a familiar route again, rechecking information, and changing a plan.

`SM` is not a catch-all for every sentence about an agent. A general statement
that an access-guidance agent answers questions is closer to a flat fact unless
it specifies the role. By contrast, knowing that the agent cannot observe a
door's lock state in real time, cannot guarantee a completed reservation from
the current material, or relies on an assumption that many users know the route
is `SM`. An assumption about users may itself be `UM`, but it becomes `SM` when
the main content is **that the agent uses the assumption as a premise in its own
reasoning or recognizes the assumption's limits**.

`WM` is not another name for flat facts such as locations and operating hours;
those belong in `KB`. Only models used to predict the external environment's
structure, dependencies, causality, and change belong in `WM`, such as one
entrance closure redirecting pedestrian flow to another entrance or one service
closure increasing congestion at another facility. These six purposes are a
review axis for separating different kinds of reasoning evidence in common
grounding.

`PP` content is written as an imperative that an acting agent can apply
directly—for example, “do,” “do not,” or “instruct the user to.” It preserves
the original conditions and force without turning permission or discretion into
an obligation. A purpose code is an authoring and review sidecar, not part of
Memory content or a field in the current schema.

### Verified state and intended audience

The `Verified` checkbox in the review sheet is a designer sidecar indicating
that the exact current wording of that row has been reviewed. A checked row that
is already atomic remains unchanged. When the user explicitly approves a later
instruction to split a compound proposition, however, that approval supersedes
the compound row's fixed boundary. Newly created child rows do not automatically
inherit the earlier review and must all be reviewed again from an unchecked
state. By the same principle, if the user explicitly directs a wording change
to a checked row, `Verified` is cleared on the changed row so the new wording can
be reviewed.

Task 1's `All`, `Visitor`, `Student`, `Staff`, and
`Construction/Building Personnel` checkboxes identify the **intended disclosure
scope**. They are neither per-Memory ACLs nor user
authentication, and the current prototype does not enforce them as authority.
Likewise, query-only is a research interaction boundary that requires querying
instead of listing; it does not provide operational security or legal
confidentiality.

## File List

- Task 1
  - [Participant description](task-1-description-en.md)
  - [75 `construction-updates`](task-1-construction-updates-en.md)
  - [300 `campus-wiki` Memories](task-1-campus-baseline-en.md)
  - [78 query-only `construction-details` in `campus-wiki`](task-1-campus-wiki-construction-details-en.md)
  - [Update locations, targets, and before/after content](task-1-update-actions-en.tsv)
  - [Purpose sidecar](task-1-memory-purpose-en.tsv)
- Task 2
  - [Participant description](task-2-description-en.md)
  - [150 `advisor1` Memories](task-2-advisor1-en.md)
  - [150 `advisor2` Memories](task-2-advisor2-en.md)
  - [75 query-only `proposal-submission-guidelines`](task-2-proposal-submission-guidelines-en.md)
  - [Advisor relation groups](task-2-pair-relations-en.tsv)
  - [Purpose sidecar](task-2-memory-purpose-en.tsv)
- Task 3
  - [Participant description](task-3-description-en.md)
  - [Participant brief draft](task-3-study-brief-en.md)
  - [300 `local/personal-memory` Memories](task-3-personal-memory-en.md)
  - [75 ordinary `local/guardrails`](task-3-guardrails-en.md)
  - [25 ordinary `remote/government/healthcare-agent/info-request/transmission-guidance` Memories](task-3-healthcare-public-guidance-en.md)
  - [75 query-only `remote/government/healthcare-agent/info-request/questions-and-answers` Memories](task-3-healthcare-information-request-en.md)
  - [Purpose sidecar](task-3-memory-purpose-en.tsv)
- [Complete design rationale](fixture-corpus-design-rationale-en.md)

## Per-Task Contracts

### Task 1

`construction-updates` and `campus-wiki` use the same six operational
directories. The review table's base order is:

`Verified | Memory Location | All | Visitor | Student | Staff | Construction/Building Personnel | Purpose | Content | Source File`

The 75 `construction-updates` focus on the change packet participants will
actually review and apply. The 300 `campus-wiki` Memories provide not only the
update target baseline but also public campus-guidance background, including
floor-by-floor guidance, public operating hours, event and space reservations,
parking and transportation, shops and food services, visitor services, and
`accessible route` information. This public-information-style material is also
entirely synthetic: institution, building, facility, shop, stop, and relative
location names are research pseudonyms. They must not be interpreted as
corresponding to any real university, city, address, phone number, or business.

Every `construction-updates` candidate must be a change to a state, route,
policy, or information need caused by construction. Candidates that merely
repeat ordinary facts, general usage tendencies, or the agent's existing
capabilities are disallowed, as are `retain` no-ops. Content corresponding to an
existing wiki Memory is connected to an actual `edit` patch; only a
construction-period change absent from the baseline is `added` as a new Memory.

The following update evidence appears immediately to the right in
`construction-updates`:

`Update Location | Target Memory | Operation | − Existing Content | + Applied Content`

This avoids moving between a separate diff table to match sources and results.
Edits retain a red `−` and green `+`; additions retain a marker that no existing
Memory exists and a green `+`. When one source changes multiple targets,
numbered patches appear to its right in the same row, while the source 1:N
relationship remains preserved in the TSV. `campus-wiki` uses the same
hierarchical location and five audience checkboxes.

Accessibility terminology is standardized as `accessible ramp`,
`accessible route`, `accessible entrance`, and `accessible restroom`, rather
than newly coined Korean terms. When a student ordinarily uses or is heading
toward the third-floor rear-entrance route connecting to the library, a separate
Memory requires advance notice that the route is unavailable and, when a
verified alternative exists, guidance to that alternative.

`task-1-campus-authority` owns ordinary `campus-wiki` and
`campus-wiki/construction-details` Context trees. The task receives a readable
and editable wiki view plus a narrower query-only details view. Its explicit
query form is `mem query campus-wiki/construction-details ...`. Detailed
construction content is not copied into the task Profile.

### Task 2

The two advisors have equal authority, each providing 150 Memories in the same
16-directory order. The added items provide more granular advice for independent
review of an HCI master's research proposal; they do not indicate a difference
in authority or rank between advisors. All 16 directories include `OM` examples
for the behavior of reviewers, operators, participants, and other actors who are
not the current user. The two stores are not duplicate copies of generic writing
guidance. They are internal advice from co-advisors in the same HCI lab who
interpret domain-neutral external requirements in the language of user problems,
design contributions, prototypes, user research, evaluation, and design or
operational decisions.

Semantic correspondence is preserved as relationship **groups**. After
expansion, actual `Conflict` remains limited to 8 relationship points and
explicit `Compatible Complement` to 2; added advice is mapped as
`Near Duplicate`, `Same-Principle Variant`, or `Context-Dependent Variant`.
Relationships are a golden sidecar, not a marker of advisor superiority or of
correct answers in the content. When one semantic unit has been split across
multiple atomic Memories, semicolon-separated member lists are recorded in
`left_fixture_ids` and `right_fixture_ids`.

The eight actual conflicts are authoring and planning choices accessible
without research-methods training: two- versus three-sentence problem framing,
flow diagram versus sequence table, short one-claim sentences versus connected
rhythm, descriptive subheadings versus continuous paragraph flow, first-person
responsibility versus action-first procedure prose, one exact target versus a
bounded range, budget rationale in the main text versus a separate table, and
avoiding em dashes versus deliberate conditional use. Supporting Memories
retain ordinary observations, preferences, update costs, and author habits from
which Rationale can reconstruct each advisor's position; they do not encode a
separate rule/benefit/cost explanation.

The 75 query-only submission-guideline Memories are divided across 10
directories, each containing an `OM` example. They form a general submission
contract for compressing an application-oriented master's research project into
two pages, not criteria for a particular subfield. Domain-neutral means that the
guidelines do not presume HCI; it does not mean that they cover purely
theoretical research. Two pages is document length, not an instruction to
complete the research in two weeks. The guidelines specify a single searchable
PDF, font and margin rules, required summary, background, objectives, methods,
outcomes, schedule, and applicable budget and ethics content, word ranges,
submission deadline, and review boundaries. The external guidance determines
what to submit, while advisor Memories interpret how to express it in HCI.
Accordingly, the external guidance is neither a third advisor that resolves the
two advisors' differences nor an answer key.

### Task 3

The 300 `local/personal-memory` Memories retain source keys for ten Memories per month
from `2024-01` through `2026-06`, rather than using topic keys. Generated Study
Profiles expose them through year/month Contexts such as
`local/personal-memory/2024/01`, including the structural `local/personal-memory/2024`
parent. Concrete
user experiences dominate the `UM` purpose, producing 184 User Models overall.
Memories state events, actions, and preferences directly instead of explaining
their provenance with phrases such as “wrote that” or “recorded that.” An actual
act of keeping a photograph or entering something in a calendar remains because
the recording act is itself the event. The data include different compression
levels together: an event in which conversation was impossible in a noisy
restaurant, an inferred preference for a quiet meal, and a personal policy to
check noise when proposing a location. How much event detail to retain and how
much to compress into a preference or policy is a qualitative research question
for which this fixture does not fix the correct answer.

Family members are identified by synthetic roles such as mother, father, older
sister, younger brother, maternal aunt, and maternal uncle; the maternal aunt
keeps the spare key. The data exclude research and demo content, friendships,
traumatic family history, and identifiable real events. Every month also
contains one `OM` describing the expectations, preferences, judgments, or
anticipated responses of a person or institution other than the current user,
and the complete set contains all six purposes.

The 75 `local/guardrails` form an ordinary Context covering purpose limitations for
selective sharing, protection of third parties, uncertainty, approval, delivery,
and revocation, as well as recipient authority, minimization and redaction,
channel and format, downstream use, auditing, and recovery. Neither the
guardrails nor the connected query-only Context contains `UM` statements that
predetermine a participant's sharing preference. Such statements could steer
choices during the experiment; they are replaced with `WM` statements about
external data-flow conditions and `OM` statements about anticipated recipient
or organization interpretations.

The ordinary Context `remote/government/healthcare-agent/info-request/transmission-guidance` contains 25
distributable public transmission-guidance Memories, including its own role,
review policies, and Self, User, World, and recipient-facing Other Models. Its grant permits reading,
derivation, combination, export, and retained analysis, so it can serve as the
one Criteria Context of Sever or be combined with another criterion through
Meld. The connected query-only Context has canonical locator
`remote/government/healthcare-agent/info-request/questions-and-answers`. Its 75 Memories explain the
consent, use, and sharing consequences when categories of personal Memory are
actually transmitted to a government healthcare institution system. They do not
identify particular events in the personal record as correct answers or request
information directly; they explain general categories and examples such as
functional support, scheduling, environment, and explanation preferences in one
pass. All content actually sent through the transmission screen is treated as
one unit of consent to share. Depending on the information supplied, it may be
provided to relevant third parties for healthcare purposes or used for service
improvement. The agent does not identify the exact services, recipients, or
scope of third parties.

Alongside the healthcare Q&A agent's capability limits, `OM` covers
external clients that mistake this endpoint for a transmission, scheduling,
deletion, permissions, or payment API; excessive requesters; and automated
requesters attempting prompt injection, hidden-instruction extraction, behavior
distillation, or repeatedly varied queries. Downstream actors inside the
government institution neither interact with nor are observed by this agent, so
they are not made `OM` actors in this dataset.

The healthcare Q&A agent does not access stored personal Memories or
institution records and does not retain information outside the current
conversation record. It cannot select, include, exclude, modify, transmit, or
delete information; control the institution's receipt, retention, internal
sharing, downstream processing, or access permissions; or execute scheduling,
payment, or transmission of family contact information. Mentioning personal
Memory content in the current conversation is neither institution transmission
nor physical deletion. Actual sharing candidates are reviewed through the local
guardrails and the participant's `sever` and `share` flow. Accessibility
information distinguishes convenience preferences, temporary states, persistent
functional limitations, and required support; the agent does not determine
need, truthfulness, or eligibility. For a serious attack, it ends only the
response to that one-shot request and does not assume recall blocking or rate
limiting is implemented.

## Synthetic, De-identification, and Query Boundaries

- The Task 1 and 2 people, institutions, construction, and policies, and the
  Task 3 guardrails and healthcare healthcare Q&A specification, are
  entirely synthetic research material.
- Task 1 spaces draw only shallowly on facility relationships possible at an
  urban comprehensive university; they do not use a real school name, building
  name, city, address, business name, phone number, or construction outcome.
- The two Task 2 advisors are fictional roles with equal authority.
- Task 3 personal Memories do not directly copy recurring topics from the local
  IdeenKasten; they reconstruct them as de-identified, generalized meanings.
  Names, institutions, projects, locations, source dates, third-party statements,
  rare event combinations, diagnoses, and source node IDs are not retained.
- Query-only material answers only content explicitly supported by the material
  within allowed topics, does not infer absent facts, and states when an
  out-of-scope question cannot be answered.

## Next Steps

1. Review the Korean content and `Verified` state with the user.
2. Create ID-based golden sidecars for duplicates, conflicts, ambiguity,
   omissions, and expected outcomes by task.
3. Review the approved Korean source and English translation for semantic
   preservation.
4. Import the generated packages with `mem profile import-study`, which imports
   task and authority Context baselines, translation catalogs, and grant
   templates into one editable `study-baseline` without changing `authoring`.
   Use `mem init-study NAME` to make one complete clean Profile copy after
   reviewing that merged topology. Authoring checkpoints and other run
   artifacts stay outside both the baseline and initialized copy.
