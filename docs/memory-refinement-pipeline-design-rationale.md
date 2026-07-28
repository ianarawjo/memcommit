# Memory refinement pipeline

## Original decision

정리 전 원문 Memory는 다음 순서로 다듬는다.

```text
중복 제거
→ 충돌·모호성 통합 검토
→ 대상 분류
→ 정규화
→ 범주별 배치
```

여기서 `충돌`과 `모호성`은 서로 다른 operation으로 나누지 않는다.
현실의 장면에서는 모순처럼 보이는 두 설명이 대상, 시간, 장소, 접근
방법, 예외 조건에 따라 모두 참일 수 있다. 따라서 이 프로토타입에서는
현실적인 충돌을 곧바로 어느 한쪽이 거짓이라는 뜻으로 보지 않고, 현재
지식만으로 두 설명을 함께 설명할 수 없다는 상태로 먼저 다룬다. 이는
보편적 사실 주장이 아니라 이 refinement pipeline의 open-world 설계
가정이다.

또한 `비공개 분리`를 단순한 공개/비공개 이진 분류로 보지 않는다.
학생, 교직원, 방문자, 시설 담당자처럼 정보를 전달받을 대상과 목적에
따라 필요한 설명과 세부 수준을 정하는 `대상 분류`로 다룬다.

## Intent

`mem add --paste` preserves raw notes without trying to understand them. The
refinement pipeline turns that intake into explainable, audience-appropriate,
rule-conforming Memories without hiding semantic decisions inside a single
opaque cleanup step.

The primary order is intentional:

1. **Deduplicate** first to reduce repeated evidence and review volume.
2. **Reconcile conflict and ambiguity together** to identify what the current
   knowledge cannot yet explain.
3. **Classify audiences** so differences caused by applicability, recipient,
   or disclosure purpose become explicit.
4. **Atomize and normalize** only after meaning and scope are sufficiently
   clear.
5. **Place by category** after the Memory contents have stable semantics.

These are separable operations with distinct previews, reasons, provenance,
and checkpoints. A single `clean up everything` command would make it hard to
tell whether a Memory disappeared because it was a duplicate, was rewritten
for an audience, or was moved to another category.

## Why conflict and ambiguity are one operation

Classical logical contradiction asks whether both `P` and `not P` can be true
under the same interpretation. Operational campus knowledge rarely arrives
with a complete interpretation. Its missing coordinates commonly include:

- audience: student, staff, member, visitor, or facilities operator;
- time: public hours, after hours, a construction phase, or an emergency;
- place: main entrance, rear entrance, parking pedestrian door, or stairwell;
- access method: vehicle, pedestrian, physical card, app, or staff credential;
- exception: accessibility need, urgent use, delivery, or construction work.

For example, these can all be valid at once:

```text
Staff entrances remain open.
The underground-parking stairwell is closed even to staff.
The parking pedestrian door is available only to staff.
```

The statements become contradictory only if they are assumed to describe the
same entrance and conditions. The operation should therefore ask:

> What missing distinction, condition, or evidence would make these Memories
> jointly explainable?

This document calls such a case an **explainability gap**: the current
qualifiers and evidence are insufficient to explain a set of Memories
together. This is an open-world stance. Lack of a current explanation is not
treated as proof that one statement is false.

The working operation name is `reconcile`. It replaces the planned conceptual
role of a narrow `find-conflicts` command. `direct conflict` and `ambiguous`
may remain useful result labels, but they are severity or evidence labels
inside one operation, not separate workflows.

`reconcile` must not silently choose a winner. Its first responsibility is to
surface the unexplained relationship and the smallest clarifying question.
A later confirmed edit can add the missing scope, preserve both scoped facts,
or mark one statement as superseded when evidence actually supports that
decision.

## Audience classification is not merely privacy separation

The Korean design concept is `대상 분류`. The working command name is
`audience`, rather than `target`, because target already means several things
in update and reference operations. Audience classification keeps four
questions distinct:

- **subject/applicability:** who or what the fact applies to;
- **intended recipient:** who needs to receive the explanation;
- **purpose/detail:** why they need it and which details support that purpose;
- **disclosure:** who may be allowed to see it.

Initial audience classes for the campus scenario include:

- students;
- staff and faculty;
- authorized members;
- visitors and the general public;
- service-desk and event staff;
- facilities and construction operators.

One underlying event can require different explanations. A visitor needs an
available entrance and public hours. A staff member needs credential and
exception rules. A facilities operator may need the reason for a closure and
its reopening dependency.

Audience classification can inform disclosure decisions, but it is not access
control. A normal Context or `context_ref` does not become confidential merely
because it is labelled for facilities staff. Content that must be technically
hidden still requires a query-only or future access-controlled storage
boundary.

The storage representation remains an implementation decision. Candidate
representations include Memory metadata, audience-specific Contexts, or a
derived audience plan. The first `audience` implementation should not commit
to one representation without testing how multi-audience Memories and
references behave.

## Normalization

The normalization phase contains two explicit operations.

`atomize` is the structural operation that splits a composite Memory into
atomic operational facts. It is separate because one-to-many identity and
provenance changes are not merely wording cleanup. A split requires new UIDs,
ordered outputs, and lineage back to the original UID. The current Memory
schema has no lineage field, so the implementation must define that
representation before applying splits.

`normalize` conforms each atomic Memory to explicit wording and scope rules
while preserving its resolved meaning. It is not another opportunity for
semantic invention.

Candidate rules include:

- use a complete declarative sentence;
- state the affected audience, place, and time when they are necessary;
- replace vague references such as `앞서`, `적절히`, and `등등`;
- use consistent building, entrance, and service names;
- express times and date ranges in an unambiguous format;
- keep one operational fact per Memory;
- preserve an unresolved placeholder rather than inventing a missing value.

Atomization and normalization follow audience classification because a
sentence cannot be made fully explicit until its applicability, intended
recipient, and scope are known. They follow reconciliation because polishing
two unexplained statements too early can make uncertainty less visible
without resolving it.

## Category placement

The working operation name is `place`. It assigns a normalized Memory to its
organizational Context. The Task 1 destination categories are:

```text
construction-updates/building-access
construction-updates/event-relocations
construction-updates/temporary-parking
construction-updates/shop-updates
construction-updates/facility-updates
construction-updates/route-changes
```

Placement is structural, not a rewrite. A deterministic `move` primitive will
likely be required beneath the semantic placement operation. Moving should
preserve the Memory UID, provenance, and relative order where possible. If one
Memory legitimately belongs in several categories, prefer one owning Context
plus `memory_ref` values over copied Memories that can drift apart.

## Proposed operation contracts

The command names below are working names. Their semantic boundaries are more
important than final CLI spelling.

| Stage | Working operation | Primary output | Mutation boundary |
|---|---|---|---|
| 1 | `mem dedup` | equivalent groups, survivor UID, canonical content, reasons | preview by default; confirmed groups apply as one checkpoint |
| 2 | `mem reconcile` | jointly unexplained groups, missing dimensions, clarifying questions | read-only first; edits require a separate confirmed plan |
| 3 | `mem audience` | applicability, recipient, purpose, and disclosure assignments | preview first; storage representation must be explicit |
| 4a | `mem atomize` | composite violations and ordered split proposals with lineage | preview first; lineage representation must exist before apply |
| 4b | `mem normalize` | named rule violations and full replacement proposals | confirmed batch applies as one checkpoint |
| 5 | `mem place` | destination Context plan and multi-category references | staged plan in v1; apply requires a recoverable multi-Context boundary |

### `dedup`

- Exact duplicate detection is deterministic.
- Semantic duplicate detection must distinguish `equivalent`, `overlap`, and
  `distinct`.
- A group is applicable only when its Memories make the same operational
  claim under the same scope. If either Memory contains a unique fact,
  constraint, or exception, `overlap` is reported but nothing is absorbed.
- `conflict` is not a dedup outcome to apply; it is handed to `reconcile`.
- Dedup keeps one stable survivor UID, chooses a meaning-equivalent canonical
  wording, and names every absorbed source UID. Combining unique facts is a
  different integration operation and is outside dedup.
- Referenced Memories cannot be removed until inbound references have been
  checked and safely migrated or the group has been blocked.

### `reconcile`

- Operates on relationships among Memories, not only one new statement against
  the Context.
- Treats missing scope as the default hypothesis, not proof that one statement
  is false.
- Records the dimension that could explain the difference and the evidence
  still required.
- Can conclude that two statements are already jointly explainable and need no
  edit.

### `audience`

- Supports several audiences for one Memory.
- Separates applicability, recipient, purpose/detail, and disclosure.
- Distinguishes intended recipient from enforced visibility.
- Records why each audience needs the information and which details they need.
- Must not remove facts merely because one audience should not see them.

### `atomize`

- Identifies composite Memories by a named atomicity rule.
- Proposes ordered child contents without rewriting their resolved meaning.
- Defines new-UID and source-lineage policy before any split is applied.
- Does not silently delete the relationship to the original Memory.

### `normalize`

- Uses a named, inspectable rule set.
- Preserves meaning and does not resolve missing facts by guessing.
- Reports which rule caused each proposed edit.
- Operates on atomic Memory contents rather than performing identity-changing
  splits itself.

### `place`

- Chooses among existing organizational Contexts.
- Uses movement for ownership and references for legitimate multi-placement.
- Does not create duplicate content copies as a shortcut.
- Preflights every source and target before any Context is written.
- Updates or blocks every inbound `memory_ref` whose owner locator would change
  when the Memory moves.

The current store writes one Context at a time and does not provide a
multi-Context transaction. Therefore the first `place` implementation must not
claim crash-atomic movement across Contexts. It should remain a staged plan
until a recovery manifest or equivalent transaction boundary exists, or
clearly checkpoint every affected Context with a recoverable partial-failure
procedure.

## Cross-operation invariants

Every refinement operation should:

- be previewable without changing Contexts or checkpoints;
- show source UIDs, proposed result, and a human-readable reason;
- bind its plan to the Context UID and content fingerprint;
- refuse to apply a stale plan;
- record one operation-level history event; a multi-Context operation requires
  linked checkpoints carrying one shared operation ID;
- preserve the raw intake through history or an explicit working branch;
- avoid opening query-only sources or treating model output as trusted IDs;
- make no silent deletion, conflict resolution, audience inference, or move.

The operations should be idempotent at their intended stage. Re-running an
operation on unchanged, already-processed input should report no work.

## Initial graph scope

Version 1 of every refinement operation should inspect only Memories directly
owned by the selected Context. A `memory_ref` is a view of a logical Memory,
not another content candidate, and must not be reported as a duplicate of its
target.

Recursive refinement is deferred until graph traversal has a canonical
logical identity such as `(owner_context_uid, memory_uid)`, visits shared or
cyclic Contexts once, preserves owner information, and folds references into
their target instead of counting them as copied contents.

## Iteration without changing the primary order

Atomization can split a composite Memory and reveal a duplicate that was not
visible during the first dedup pass. Audience classification can also supply
the missing distinction that explains a reconcile finding. The pipeline
therefore allows read-only verification passes:

```text
dedup → reconcile → audience → atomize → normalize → place
   ↑                                                   |
   └──────────── final dedup/reconcile check ──────────┘
```

This feedback check does not collapse the operations or change their primary
order. It verifies that later structural improvements did not expose new work.

## Current Task 1 implications

The 51 Memories in `temp/task-1` are raw intake, not final fixture data.
Immediate examples are:

- rear-door closure and staff-entrance availability contain semantic
  duplicates suitable for `dedup`;
- physical-card versus app access is a `reconcile` case, not safe dedup;
- restroom directions differ by visitor and accessibility audience;
- public closure guidance and internal construction reasons need different
  audiences and detail levels;
- long store, restroom, and parking Memories need atomization and
  normalization;
- the final facts belong in the six `construction-updates/*` Contexts.

The first implementation should therefore be `mem dedup`, preview-first. It
should be run on a branch or otherwise preserve the raw paste checkpoint.
`reconcile`, `audience`, `atomize`, `normalize`, and `place` should follow one
at a time so their contracts remain observable in the study.
