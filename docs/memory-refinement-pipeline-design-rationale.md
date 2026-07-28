# Memory refinement pipeline

## Decision history

### Initial order

처음에는 정리 전 원문 Memory를 다음 순서로 다듬기로 했다.

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

### Revised order: atomize before deduplication

Task 1 원문을 검토하면서, 하나의 Memory 안에 폐쇄 사실, 대체 위치,
운영 시간, 이유가 함께 들어 있는 경우가 많다는 점을 확인했다. 이러한
복합 Memory를 먼저 dedup하면 일부만 같은 두 Memory를 통째로 중복으로
오판하거나, 내부에 숨어 있는 실제 중복을 찾지 못한다.

따라서 primary pipeline을 다음과 같이 수정한다.

```text
원문 intake
→ atomize
→ 기계적 dedup
→ 의미론적 dedup
→ reconcile
→ audience
→ normalize
→ dedup 재검증
→ place
```

초기 순서를 덮어 지우지 않고 decision history로 남기는 이유는, raw
line을 Memory 하나로 보는 intake 관점에서 atomic claim을 정제하는
관점으로 설계가 바뀐 근거를 이후 연구 기록에서 추적할 수 있게 하기
위해서다.

## Intent

`mem add --paste` preserves raw notes without trying to understand them. The
refinement pipeline turns that intake into explainable, audience-appropriate,
rule-conforming Memories without hiding semantic decisions inside a single
opaque cleanup step.

The primary order is intentional:

1. **Atomize** explicit multi-claim Memories while preserving order and source
   lineage.
2. **Deduplicate mechanically** using only meaning-preserving comparison
   normalization.
3. **Deduplicate semantically** only when two atomic claims are mutually
   substitutable without information loss.
4. **Reconcile conflict and ambiguity together** to identify what the current
   knowledge cannot yet explain.
5. **Classify audiences** so differences caused by applicability, recipient,
   or disclosure purpose become explicit.
6. **Normalize** only after meaning and scope are sufficiently clear.
7. **Verify deduplication again** because later qualification and normalization
   can expose new equivalence.
8. **Place by category** after the Memory contents have stable semantics.

These are separable operations with distinct previews, reasons, provenance,
and checkpoints. A single `clean up everything` command would make it hard to
tell whether a Memory disappeared because it was a duplicate, was classified
for an audience, was normalized, or was moved to another category.

## Atomization before deduplication

`atomize` is a source-preserving semantic split, not sentence tokenization and
not stylistic rewriting. It separates only explicit multi-claim Memories. The
ordered children must collectively preserve the parent's information without
adding a decision that belongs to reconciliation, audience classification, or
normalization.

If the scope of a qualifier is uncertain, atomization reports the uncertainty
instead of guessing which children inherit it. A heading, question, or process
note is classified and retained rather than silently deleted for not being an
atomic operational fact.

The existing `mem chunk` provides a useful structural primitive but is not the
Task 1 atomizer:

- it splits one Memory by Markdown headers, paragraphs, or an approximate
  English sentence boundary;
- against the current 51 Memories, header and paragraph modes split none, and
  sentence mode splits only one Memory into an operational clause plus the
  incomplete fragment `Main building cafe`;
- it replaces the original with fresh UIDs and preserves child order at the
  original position;
- its checkpoint records the source UID and method, but not source-to-child
  lineage;
- it does not scan for inbound `memory_ref` values before removing the source.

The first `atomize` contract should therefore:

- inspect directly owned Memories as one previewable batch;
- label each item `atomic`, `composite`, `uncertain`, or
  `non-propositional`;
- return an ordered child-content list only for a clear composite;
- bind the plan to the Context UID, source UID, source-content fingerprint,
  and source position;
- allocate fresh UIDs to all confirmed children and replace the source at its
  original position;
- record `source_uid → ordered child UIDs and contents` in the staged plan and
  checkpoint metadata while keeping the base Memory schema at `uid + content`;
- block v1 application when any Context contains an inbound reference to the
  source, because a one-to-many split has no single safe retarget;
- apply every approved split in one Context-level checkpoint;
- perform no deduplication itself.

The previous checkpoint preserves recoverability, while the explicit mapping
provides operation provenance. If lineage later needs to be queried without
history traversal, that requirement should motivate a separate schema change
rather than silently adding fields during atomization.

## Deduplication in two trust layers

Both mechanical and semantic deduplication are necessary, but they should be
two phases of one public `mem dedup` operation with visibly different trust
levels.

### Mechanical dedup

Mechanical detection has no model dependency. It reports:

- `EXACT`: stored content is identical;
- `SURFACE_EQUIVALENT`: a conservative comparison key is identical after
  line-ending normalization, Unicode NFC, outer trimming, and horizontal
  whitespace normalization that preserves paragraph boundaries.

Comparison normalization never rewrites stored content. It must not remove
negation, question marks, numbers, dates, modality, list markers, or other
potentially meaningful symbols. Case folding, punctuation tolerance,
translation, typo correction, and synonym expansion may produce candidates
for review, but they are not mechanically applicable equivalence.

### Semantic dedup

Semantic detection considers only atomic Memories that remain after the
mechanical phase. Two claims are eligible only when they are mutually
substitutable without information loss under the same:

- subject and applicability;
- predicate or operational state;
- object and place;
- audience and time;
- modality and uncertainty;
- access method, exception, and relevant causal scope.

If one Memory entails the other but contains additional information, the
result is `OVERLAP`, not a removable duplicate. Missing qualifiers or
uncertain scope produce `UNKNOWN` and are handed to `reconcile`. The model
acts as a classifier and reason generator, not as a canonical-text author.
Application keeps a stable existing survivor UID and existing survivor
wording; later normalization owns rewriting.

Both phases are previewed before mutation because even an exact removal changes
UID availability, provenance, order, and references. The shared apply path
must check inbound references, bind the plan to a Context fingerprint, reject
stale plans, and record every absorbed UID in one checkpoint.

An optional byte-exact scan can run before atomization as a cheap read-only
diagnostic, but it cannot replace the post-atomization passes. The current
Task 1 intake has zero exact full-record duplicates.

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

`normalize` conforms each atomic Memory to explicit wording and scope rules
while preserving its resolved meaning. It is not another opportunity for
semantic invention.

Candidate rules include:

- use a complete declarative sentence;
- state the affected audience, place, and time when they are necessary;
- replace vague references such as `앞서`, `적절히`, and `등등`;
- use consistent building, entrance, and service names;
- express times and date ranges in an unambiguous format;
- verify that one operational fact remains per Memory, handing residual
  composites back to `atomize`;
- preserve an unresolved placeholder rather than inventing a missing value.

Normalization follows reconciliation and audience classification because a
sentence cannot be made fully explicit until its applicability, intended
recipient, and scope are known. Early atomization establishes the claim
boundaries; normalization later makes the resolved scope explicit without
changing those identities.

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
| 1 | `mem atomize` | atomic/composite classifications and ordered split proposals with lineage | preview first; confirmed direct-item batch applies as one checkpoint |
| 2 | `mem dedup` | mechanical and semantic equivalence groups, survivor UIDs, absorbed UIDs, reasons | preview by trust tier; confirmed groups share one stale-safe apply path |
| 3 | `mem reconcile` | jointly unexplained groups, missing dimensions, clarifying questions | read-only first; edits require a separate confirmed plan |
| 4 | `mem audience` | applicability, recipient, purpose, and disclosure assignments | preview first; storage representation must be explicit |
| 5 | `mem normalize` | named rule violations and full replacement proposals | confirmed batch applies as one checkpoint |
| 6 | `mem dedup --check` | post-normalization exact scan and deferred semantic reclassification | read-only verification; any removal requires a newly confirmed plan |
| 7 | `mem place` | destination Context plan and multi-category references | staged plan in v1; apply requires a recoverable multi-Context boundary |

### `atomize`

- Identifies clear composite Memories without resolving ambiguous modifier
  scope.
- Proposes ordered child contents without normalizing their wording.
- Gives every child a fresh UID and records the ordered source-to-child mapping
  in plan and checkpoint provenance.
- Replaces each source at its original position and blocks sources with inbound
  references in v1.
- Does not perform deduplication, reconciliation, audience inference, or
  deletion of non-propositional notes.

### `dedup`

- Runs deterministic `EXACT`/`SURFACE_EQUIVALENT` detection before semantic
  classification and shows the tiers separately.
- Semantic duplicate detection distinguishes `SEMANTIC_EQUIVALENT`,
  `OVERLAP`, `UNKNOWN`, and `DISTINCT`.
- A group is applicable only when its Memories make the same operational
  claim under the same scope. If either Memory contains a unique fact,
  constraint, or exception, `OVERLAP` is reported but nothing is absorbed.
- `UNKNOWN` is not a dedup outcome to apply; missing scope is handed to
  `reconcile`.
- Dedup keeps one stable survivor UID and its existing wording, and names every
  absorbed source UID. Canonical rewriting belongs to `normalize`; combining
  unique facts is a different integration operation.
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

Early atomization exposes the claims that the primary dedup pass should
compare. Later reconciliation and audience classification can supply a missing
qualifier that proves a deferred candidate equivalent or distinct.
Normalization can also make two previously different surface forms
mechanically identical. The pipeline therefore includes a deliberate
read-only verification pass:

```text
atomize
→ mechanical dedup
→ semantic dedup
→ reconcile
→ audience
→ normalize
→ dedup verification
→ place
```

An `uncertain` atomization is not sent through dedup as if it were atomic.
It remains intact and goes to `reconcile`; after the missing scope is supplied,
that item returns to `atomize` and then enters the dedup phases. This is a
targeted retry, not permission for atomization to guess during the first pass.

The verification does not silently apply previously deferred candidates. Any
new removal is a new previewed plan. This check does not collapse the
operations or change their primary order.

## Current Task 1 implications

The 51 Memories in `temp/task-1` are raw intake, not final fixture data.
Immediate examples are:

- rear-door closure and staff-entrance availability each contain semantic
  dedup candidates, but their instruction-versus-fact and scope differences
  still require review;
- physical-card versus app access is a `reconcile` case, not safe dedup;
- restroom directions differ by visitor and accessibility audience;
- public closure guidance and internal construction reasons need different
  audiences and detail levels;
- long store, restroom, and parking Memories need atomization and
  normalization;
- the final facts belong in the six `construction-updates/*` Contexts.

The first implementation should therefore be `mem atomize`, preview-first. It
should be run on a branch or otherwise preserve the raw paste checkpoint.
Mechanical and semantic phases of `mem dedup` should follow, then
`reconcile`, `audience`, `normalize`, dedup verification, and `place`, one at
a time so their contracts remain observable in the study.
