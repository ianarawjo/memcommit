# Task 1 fixture grounding TODO

## Status and boundary

This note records the current Ground material for building the Task 1 study
fixture. It is a planning artifact only. No Task 1 Context or Memory should be
populated merely because a requirement appears here.

The current local store was inspected before writing this note:

- `temp/task-1-atomized-en` contains 54 provisional English Memories;
- the legacy `construction-updates` root embeds the six intended child
  Contexts, but all six children are empty; and
- the legacy ordinary `campus-wiki` Context is empty.

The intended writable objects under
[the Task 1 naming contract](task-1-naming-contract.md) are
`participant/construction-updates` and top-level `campus-wiki`. The ordinary
wiki directly carries an opaque `construction-details` query pointer.

## Goal

Create a fictional but operationally coherent Task 1 dataset in which a
participant uses six categories of verified local construction updates to
update the corresponding six parts of a larger writable campus wiki,
without exposing protected construction details or implying that the
fictional university is a real institution.

## Working rules

### 1. Mirrored six-part structure

The verified update source must be divided into exactly these six child
Contexts:

1. `building-access`
2. `event-relocations`
3. `temporary-parking`
4. `shop-updates`
5. `facility-updates`
6. `route-changes`

The writable campus wiki must initially contain exactly the same six
task-relevant sections. Every source section must therefore have a
corresponding target section. The initial fixture should not add unrelated
top-level wiki departments merely to make the wiki appear large.

The ordinary wiki may additionally contain a direct query-only
`construction-details` pointer. That source is not a seventh ordinary
wiki section, is not participant-visible Context structure, and does not
change the six-part correspondence above.

### 2. Required memory perspectives in every wiki section

Each of the six wiki sections must contain at least one agent Memory serving
each of these semantic roles:

- **knowledge-base knowledge**: a stable reference fact;
- **agent policy**: a rule for answering, routing, disclosing, or acting;
- **user model**: a fact about the relevant users, visitors, students, staff,
  or their recurring needs;
- **agent model**: a fact about the campus agent's own abilities, limits, or
  escalation boundary; and
- **world model**: a fact about the surrounding environment, spatial
  relationships, or likely consequences of a change.

The five roles are a fixture coverage rule, not yet a storage-schema change.
A later grounding step must decide whether roles remain implicit in ordinary
Memory content, use visible content prefixes, or require metadata support.

### 3. Coverage and relative scale

- All six source categories must be represented in the wiki baseline.
- The wiki must contain more Memories than the verified update source.
- The extra wiki Memories should supply the stable background needed to
  interpret and apply the updates, not arbitrary trivia.
- The target should contain a deliberate mix of stale affected facts, missing
  affected facts, already-correct facts, and unaffected baseline facts so
  `impact`, `update`, and `diff` have meaningful work.
- The dataset must not introduce deliberate semantic errors into the expected
  Task 1 update result.

### 4. Fiction boundary

The setting is a fictional comprehensive university:

- it has an urban location while retaining a distinct, walkable campus;
- the Main Building is comparatively recent but has reached the point where
  coordinated maintenance is reasonable; and
- no real university, address, or geographic identity should be inferable.

If asked for the university's real name, city, address, or real-world
location, the campus agent must state that the study setting is fictional
rather than inventing a location or mapping it to an actual university.

### 5. Query-only construction-details information

Public operational consequences may appear in the writable wiki, but
detailed construction scope and internal reporting information must not be
directly readable there. Protected material includes the precise maintenance
and replacement work, inspection findings, and which components were
reported.

The fixture routes that material into the opaque query-only
`construction-details` source attached to `campus-wiki`. It is not held in a
`PROTECTED` bucket in `task1/participant`, and it must not be copied into
ordinary participant-visible Memories, ordinary provider prompts, `mem ls`
output, or update material merely to make the scenario more detailed. The
writable wiki exposes only its direct `QueryContextRef` named
`construction-details`.

The concealed construction-details material consists of the 12 internal
construction and reporting entries routed from the raw Task 1 intake plus one
agent-policy entry:

> Answer only questions about the Main Building improvement construction
> plan and its internal inspection or reporting scope. For any question
> outside that scope, answer that the available material cannot answer it,
> and do not supply other wiki information or speculation.

This scope guard is part of the query source, not an ordinary wiki Memory.
The current provider already receives only that concealed source and is told
to refuse unsupported questions. The source policy makes the narrower
construction-details boundary explicit, but it remains prototype prompt
enforcement rather than a production authorization mechanism.

### 6. Parking and unaffected alternatives

The scenario must distinguish the Main Building's construction-affected
parking connection from other campus parking:

- the underground garage and any directly connected access route may be
  affected by construction; and
- a separate outdoor parking area remains available, so parking on campus is
  still possible and the agent can answer questions about alternative
  parking.

This distinction prevents “the affected parking area is closed” from being
misread as “all university parking is closed.” The exact lot names and route
will be grounded later.

### 7. Audience intent and access-specific wording

Every Task 1 update preview must show intended disclosure separately for:

- everyone or public access;
- visitors;
- students;
- faculty and staff; and
- construction or building personnel.

This matrix must not conflate who may read a statement with who the statement
applies to. For example, everyone may need to see that the rear entrance is
closed, while only authorized construction or building personnel may use its
exception. The current Task 1 wording also establishes these fixture facts:

- the rear entrance is closed to everyone except authorized construction or
  building personnel;
- the underground garage is closed to ordinary parking and vehicle entry;
- its pedestrian door is locked, but faculty and staff may enter with a
  physical access credential;
- a general statement that the garage is used for temporary construction
  material staging is intended for faculty/staff and construction/building
  personnel;
- the first-floor Innovation Hub contains a faculty/staff-only coffee machine;
  this location and restriction are stable wiki baseline knowledge, while its
  availability during the café closure is an update; and
- cooling may be interrupted occasionally for 5–10 minutes for inspection,
  and this operational notice is intended for faculty and staff.

The current runtime does **not** enforce this matrix. `Memory` persists only
`uid` and `content`, and ordinary traversal and update planning do not
authenticate a campus role. Query-only is a coarse Context-wide concealment
prototype, not a role ACL. The matrix therefore belongs in a designer
sidecar, not in current `context.json` records or visible Memory prefixes.
The complete non-applied specimen is
[`examples/task-1-wiki-update-access-preview-ko.md`](examples/task-1-wiki-update-access-preview-ko.md).

## Fixture frame: stable campus and building model

The wiki baseline should make the following fictional spatial model
recoverable without requiring knowledge of a real campus.

### Main Building

- The building has a front entrance and an opposite rear entrance.
- Because the site rises toward the library, the rear entrance opens at the
  third-floor level.
- Escalators connect floors 1 through 3.
- Floors 1 through 3 are air-conditioned and are commonly used as a cool
  indoor summer route.
- The accessible ramp is frequently used and is operationally
  important.
- The building connects to an underground parking garage.
- Offices occupy much of the middle and upper portions of the building.
- A research wing occupies part of the middle-to-upper floors.
- Middle floors contain offices and seminar rooms; some seminar rooms are
  also scheduled for courses.
- The first floor and the top floor include conference or event facilities.
  Their exact names and division of functions remain to be grounded.
- The wiki must eventually describe what is located on every floor at the
  level needed for access, routing, and facility-update decisions.

### Surroundings and routes

- From the front entrance, a parking area lies to the left.
- An ATM and a bank building are beside that parking area.
- The Humanities Building lies to the right of the front entrance.
- The rear entrance is effectively connected to the Central Library route.
- The Student Centre is behind the Central Library.
- The indoor Main Building route is commonly used by people travelling to the
  library during summer.

These are stable world facts. Construction updates may change availability or
routing temporarily without rewriting the underlying campus geometry.

## Context relocation capability retained after fixture work

Task 1 fixture construction exposed a need for an explicit Context rename or
namespace-migration operation. The existing empty roots used legacy names,
while the naming contract now gives the ordinary wiki the exact top-level
name `campus-wiki`.

The store's internal Context relocation plan provides the graph migration that
was needed for that fixture work. It moves the exact slash-delimited source
root and all lexical descendants, preserves Context and Memory UIDs, rewrites
typed ordinary references and current state, keeps existing checkpoint
identity while repairing future-restorable pointer locators, and records an
automatic checkpoint for every changed live owner. Named Ground frames and
translation artifacts have explicit UID-bound continuity rules; unrelated
semantic caches retain their own freshness boundaries. This is no longer the
public `mem rename` command; that spelling now changes a Profile display name.

An owning internal operation supplies exact canonical old and new names,
freezes the complete graph plan, and requires the applied graph to equal that
plan. Occupied or overlapping destinations, unsafe or inconsistent storage,
identity/name disagreement, and ambiguous ordinary/query selectors fail
closed.

The operation does not open or rename query-only sources and does not rewrite
`QueryContextRef`. Fixture provisioning must therefore create the separate
`construction-details` source through its opaque-source path. Exception
rollback is implemented, but a durable crash-recovery journal remains a
prototype limitation. The complete decision record is
[`mem-rename-design-rationale.md`](mem-rename-design-rationale.md).

“Rename a Memory” is a separate question because the current atomic Memory
record has content but no independent name. Changing its text belongs to
editing unless a future named-Memory schema is introduced.

## Sort and placement capability discovered during fixture work

The flat 54-Memory source also exposes a need for a bulk semantic placement
operation. In this Task 1 usage, **sort** does not mean lexical ordering. It
means classifying each source Memory and placing it in the most appropriate
one of the six child Contexts or routing internal construction-details material
to the query-only `construction-details` source.

Earlier refinement notes used `place` as the semantic stage name. The current
working CLI vocabulary is:

- `place`: the underlying semantic concept and pipeline stage;
- `mem impact sort`: a read-only bulk placement preview; and
- a future `mem sort`: the separately confirmed structural mutation.

The name remains provisional until its behavior is tested against other
sorting expectations. A help entry must explicitly say “classify and place”
so users do not mistake it for alphabetical or chronological ordering.

The placement contract should preserve these invariants:

- every direct source Memory receives exactly one owning destination or one
  explicit disposition: an ordinary destination, the query-only
  construction-details route, `UNRESOLVED`, or `NON_OPERATIONAL`;
- no Memory disappears because the classifier cannot place it;
- a legitimate relationship with several categories uses one owning Context
  plus `memory_ref` links rather than drifting content copies;
- structural movement preserves the Memory UID, source lineage, and relative
  source order within each proposed destination where possible;
- internal construction details are routed to the query-only
  construction-details boundary, never to an ordinary participant-visible child
  Context or a participant-side hold bucket; and
- an applied multi-Context sort needs one shared operation identity and an
  explicit checkpoint/rollback contract across every touched Context.

### `mem impact sort`

The preview operation should accept a flat source Context and an explicit set
of allowed destination Contexts or a reviewed Ground frame. It must show:

- all 54 source Memories exactly once;
- the proposed owning destination and a short placement reason;
- held and cross-category items separately;
- projected counts for all six destinations;
- source categories or wiki sections that remain uncovered;
- Goal and Rule fit for each unit; and
- the exact structural changes a later `mem sort` would make.

The preview is read-only. It does not move or copy a Memory, change a Context,
create a Context checkpoint, or silently turn a proposed classification into
authority. A Korean preview may translate text for presentation, but the
translation is not a replacement Memory and must not change the source
artifact.

A complete non-applied screen specimen is recorded in
[`examples/task-1-impact-sort-preview-ko.txt`](examples/task-1-impact-sort-preview-ko.txt).
It accounts for all 54 source occurrences, routes 12 of them to the concealed
construction-details source, adds one query scope-guard entry, and drafts 60
ordinary wiki Memories without creating any artifact.

## Artifact, judgment, and fit model

The Ground for this fixture starts from one raw intake and produces three
authority-separated artifact lanes:

```text
RAW INPUT
  temp/task-1-atomized-en
  54 provisional direct Memories

PARTICIPANT UPDATE ARTIFACT
  participant/construction-updates
  42 routed items: 36 placed, 5 unresolved, and 1 non-operational

WRITABLE WIKI ARTIFACT
  campus-wiki
  60 ordinary baseline Memories across six corresponding sections
  plus one opaque QueryContextRef named construction-details

QUERY-ONLY CONSTRUCTION SOURCE
  construction-details
  construction-details collection: 12 routed entries plus 1 scope guard
```

In the Ground workbench, the person-facing artifact lanes may be displayed as
`task1/participant` and `task1/campus-wiki`. These are compact view aliases,
not persisted Context identifiers. The receipt or detail view must still show
the backing canonical names so the display convention cannot silently replace
the naming and authority contract.

The full Contexts are artifacts rather than single Ground Memories. A
**placement judgment** is the reviewable unit that connects them:

```text
one source Memory
→ one proposed owner section or hold disposition
→ zero or more relevant baseline wiki Memories
→ the Goal and Rules used to judge the proposal
```

Reviewed representative, boundary, or disputed placement judgments may later be
saved as durable Ground Memories. Automatically copying all source and wiki
Memories into the Ground Memory registry would confuse working data with
approved examples and make the Ground unnecessarily large.

Every placement judgment and every drafted wiki Memory needs a unit-level
responsiveness check:

- `YES`: it supports the Goal and satisfies the applicable Rules;
- `MAY`: its destination, semantic role, scope, or rule applicability needs
  clarification; or
- `NO`: it conflicts with the Goal, violates a Rule, exposes protected
  material, or adds irrelevant fixture content.

The judgment must cite the specific applicable Rules. Whole-fixture counts are
useful summaries, but they cannot prove that each Memory coheres with the
Goal or that the five required semantic perspectives are actually present in
every wiki section. A later Ground workbench should therefore be able to show
the two artifact sets, navigate their unit judgments, and alternate between
source placement coverage and target-rule coverage.

Destination and semantic role are orthogonal axes. A Memory has exactly one
owning placement, while one wiki Memory may contribute to one or more
coverage roles. A sort plan must not turn a role label into another
destination or duplicate content merely to satisfy the role matrix.

Some Rules are corpus-level invariants rather than unit judgments. The preview
therefore needs both:

1. an exhaustive unit matrix for every source placement and drafted target
   Memory; and
2. a separate aggregate report for six-section existence, target count,
   five-role coverage in every section, absence of internal construction
   details from ordinary material, and presence of the query scope guard.

A passing set of unit rows does not by itself prove these aggregate
properties.

### Current implementation boundary

The current Ground schema cannot yet render both artifacts as one live Memory
registry. It permits one `WORKING_CANDIDATES` frame, and a Ground Memory refers
to one direct source Memory from that frame. The Korean specimen is therefore
a manual multi-lane mock, not output from an implemented command.

An implementation needs either a sort-plan adapter with two artifact lanes or
a later Ground schema extension. Even then, preview rows remain candidate
judgments; promoting a representative or boundary row to a durable Ground
Memory requires its own explicit approval. Neither `impact sort` nor `sort`
automatically creates or accepts Ground Memories.

## Ordered TODO

1. If fixture roots still require relocation, run a focused internal migration
   using the stored Context relocation plan; do not use the Profile-oriented
   public `mem rename` command.
2. Verify the resulting Context UIDs, descendants, references, current state,
   and rename checkpoints before fixture population.
3. Specify `mem impact sort` and the eventual UID-preserving `mem sort`
   mutation contract.
4. Add a multi-lane sort-plan or Ground adapter that can show the 54 raw
   source Memories, the participant-routed subset, the larger ordinary wiki
   artifact, and the opaque query-only route without treating an entire
   Context as one Ground Memory.
5. Ground the exact verified source Memories for each of the six update
   sections from `temp/task-1-atomized-en`.
6. Preview all 54 placement judgments, verify that the 12 construction-details
   entries route only to query-only storage, and resolve every remaining
   held, cross-category, or Goal/Rule-misaligned item before applying
   anything.
7. Ground the fictional university, Main Building floor plan, and stable
   surrounding-route facts.
8. Ground at least one knowledge-base, agent-policy, user-model, agent-model,
   and world-model Memory for every wiki section.
9. Check every drafted wiki Memory against the Goal and applicable Rules, then
   run the separate aggregate invariant report.
10. Provision the query-only `construction-details` source with the 12 internal
    construction-details entries and one out-of-scope refusal policy; expose only
    its `QueryContextRef` in the writable wiki and verify it through
    `mem query`.
11. Populate the six source sections and the six corresponding wiki sections
   through normal `mem` commands.
12. Verify that the wiki has more Memories than the updates and that every
   source section has a corresponding target.
13. Exercise `mem ls`, `find`, `impact`, `update`, and `diff` against the
   completed fixture before preparing the study image.

## Open grounding questions

- What are the exact floor numbers and names for the research wing,
  office/seminar levels, first-floor conference facility, and top-floor event
  facility?
- Which separate outdoor lot is the approved alternative, and what route
  should each audience follow?
- How should the five semantic memory roles be represented without turning
  research metadata into participant-facing prose?
- Within the approved construction-details scope, which audiences may ask which
  questions, and does the study need an authorization check beyond the
  current query-only prompt boundary?
- Which wiki entries should begin stale, absent, already correct, or
  unaffected so the expected update plan remains deterministic?
- Should the public command remain `sort`, use the earlier semantic name
  `place`, or expose both as preview and apply vocabulary?
- Which placement and target-coverage judgments should become durable Ground
  Memories rather than remaining transient artifact judgments?
