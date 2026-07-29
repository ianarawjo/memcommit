# 오퍼레이션 전반의 Grounding과 향후 Update 해소 과정

## 상태와 범위

이 문서는 여러 semantic memory 오퍼레이션에 반복해서 나타나는
정당화 구조를 기록한다. 핵심 결정은 Grounding을 작업 시작 전에 한 번
끝내는 준비 단계나 공통 TUI 모양으로만 보지 않는 것이다. Grounding은
사람과 에이전트가 오퍼레이션의 Goal, Rules, 그리고 구체적인
아티팩트에 연결된 Cases를 계속 검토하고 수정하며 행동의 근거를
형성하는 과정이다.

> **중요한 프로토타입 경계**
>
> 이 문서는 완성된 공통 실행 엔진을 설명하지 않는다. 현재 구현에는
> 같은 정당화 패턴을 사용하는 여러 독립적인 오퍼레이션별 세션이
> 있지만, 하나의 named Ground가 atomize, reconcile, meld, update를
> 동시에 지배하거나 자동으로 동기화하는 계약은 없다.

현재 상태를 과장하지 않기 위해 다음 경계를 명시한다.

| 영역 | 현재 상태 |
| --- | --- |
| Task 1 방향성 `impact → update` | 검증된 source와 사용자 소유 local wiki fork를 전제로 계획을 preview하고 로컬 적용하는 경로 구현 |
| update 중 ambiguity/conflict 해소 | **미구현 TODO** |
| update와 named Ground의 UID/revision/digest binding | **미구현 TODO** |
| Context-to-Context directional Meld | **미구현 TODO** |
| 독립적인 `compare` 또는 `reconcile` 명령 | **미구현 TODO** |
| atomize의 다회차 clarification | 별도 atomize grounding session으로 구현 |
| local working-copy 적용 | **구현**; 다중 Context 예외 rollback은 제공하지만 crash journal은 없음 |
| `push`/PR와 원격 publication | **미구현 TODO** |

따라서 Task 1의 해소 없는 경로는 의도된 **시나리오 경계**지만,
일반적인 update 해소 기능의 부재는 여전히 **프로토타입의 한계**다.
두 사실을 같은 의미로 해석해서는 안 된다.

## 결정

의미를 다루는 메모리 오퍼레이션들은 다음의 안정적인 Grounding 계층을
각자의 증거와 판단 단위에 맞게 반복해서 사용한다.

| Ground 계층 | 오퍼레이션 전반에서의 의미 |
| --- | --- |
| `GOAL` | 현재 오퍼레이션이 실현하려는 결과와 완료 여부를 판단하는 기준 |
| `RULES` | 근거를 해석하고 관계와 결과를 판단하며 무엇을 적용할 수 있는지 결정하는 검토 가능한 제약 |
| `CASES` | 현재 Goal과 Rules를 시험하는 구체적인 Memories, findings, readings, 관계 묶음 또는 변경 제안 |

오퍼레이션은 네 번째 Ground 계층이 아니다. 각 오퍼레이션은 위 세
계층을 자신의 source arity, evidence, target, mutation 경계에 맞게
해석하는 어댑터를 제공한다. 또한 어떤 아티팩트를 검토하거나
변경했다는 사실만으로 그 아티팩트가 승인된 Case나 golden Case가
되는 것은 아니다.

반복되는 정당화 흐름은 다음과 같다.

```text
하나의 구체적인 아티팩트 또는 중요한 finding을 제시
→ 현재 Goal과 Rules에 따라 판단
→ 제안된 reading, 관계 또는 변경과 그 영향을 표시
→ 근거가 부족하면 실제 판단을 바꿀 수 있는 후속 질문을 제시
→ 사용자가 확인·확장·수정·철회·보류하거나 추가 맥락을 제공
→ 관련된 Case, Rule 또는 Goal을 수정
→ 영향을 받는 findings와 기존에 승인된 Cases를 다시 검토
→ 실제 변경 전 명시적인 허가를 요청
```

이 구조는 인간 대화에서의 common grounding과도 대응한다. 사람들은
첫 문장을 완성된 명세로 취급하지 않는다. 상대가 어떻게 이해했는지,
그 이해가 어떤 결과를 만드는지, 빠진 조건이 무엇인지 확인하고
오해를 수정한 뒤 행동을 허가한다. 이 프로젝트의 Grounding은 그
과정을 관찰 가능한 상태와 승인 경계로 보존하려는 시도다.

## Ground와 Meld의 관계

Ground와 Meld는 동일한 장기적 상호작용의 서로 다른 측면을 설명한다.

- **Ground**는 행동을 정당화하는 공통 Goal, Rules, Cases, 수정 사항과
  명시적인 결정을 유지한다.
- **Meld**는 승인된 하나의 memory-bearing contribution이 명시적인
  source, authority, target, provenance 제약 아래 경계가 정해진 대상에
  어떤 변화를 만드는지 판단한다.

따라서 하나의 사용자 발화가 두 과정에 참여할 수 있다. 사용자의
설명은 현재 Ground의 이해를 명확하게 만드는 한편, issue-scoped
directional Meld의 근거가 될 수 있다. 그 Meld 결과가 새로운 질문을
드러내면 다시 Grounding이 필요할 수 있다.

```text
하나의 reading을 Ground
→ 해당 reading의 Meld 영향을 preview
→ 빠진 조건이나 영향을 받는 아티팩트를 발견
→ 그 조건을 다시 Ground
→ 경계가 정해진 전체 제안을 다시 계산
→ 최종 Meld를 승인하거나 보류
```

이는 여러 오퍼레이션이 동일한 list/detail/comment 화면을 사용할 수
있다는 주장보다 강하고, 하나의 generic session으로 모든 오퍼레이션을
합쳐도 된다는 주장보다 약하다. 재사용되는 것은 정당화와 turn의
구조이며, operation-specific evidence와 mutation 계약은 유지된다.

## 오퍼레이션별 적용

### Atomize와 disambiguation

Atomize의 Goal은 누락된 범위를 임의로 만들어내지 않으면서 원문에
근거한 atomic claims를 만드는 것이다. Atomize Rules는 atomicity,
source grounding, scope attachment, 정보 보존과 같은 경계를 정의한다.
구체적인 source Memories, 제안된 readings, 예상되는 split 결과는
candidate Cases가 된다.

사용자의 clarification은 하나의 ambiguity를 해소하거나, 선택된
Memory의 예상 결과를 바꾸거나, 동일한 reading에 의존하는 다른
Memories를 드러낼 수 있다. 기존 atomicity Rule이나 적용 범위가
잘못되었음을 보여줄 수도 있다. 현재 구현은 이 중 한 issue에 대한
다회차 대화를 별도의 atomize grounding session으로 제공한다.

그러나 이 세션은 named Ground가 아니다. 승인된 atomize clarification은
자동으로 named Ground의 Rule이나 golden Case가 되지 않으며, named
Ground 역시 자동으로 atomize evidence가 되지 않는다. 이 분리는 현재의
의도적인 provenance 경계다.

### Compare와 reconcile

Compare는 구체적인 아티팩트들이 어떤 관계에 있는지 판단하기 위한
근거를 만든다. Compare 결과만으로 실제 변경 권한이 생기지는 않는다.
한 Memory에 관한 ambiguity finding과 두 Memories에 관한 conflict
finding은 서로 다른 source arity를 유지해야 한다.

Reconcile은 이러한 findings를 함께 검토하여 다음과 같은 질문을
다루는 하위 단계다.

- 두 내용을 함께 설명하기 위해 어떤 구분이 빠져 있는가?
- 시간, 장소, 대상, 접근 방식 또는 예외 조건이 필요한가?
- 현재 판단을 뒷받침하기 위해 어떤 추가 근거가 필요한가?

Grounding은 이 과정에서 필요한 사람–에이전트 clarification protocol을
제공한다. 승인된 해소 결과는 현재 Case에만 적용되는 국소적인 판단일
수도 있고 여러 Cases에 재사용할 Rule을 정당화할 수도 있다. 국소적인
clarification을 재사용 가능한 Rule이나 golden Case로 승격하는 과정은
별도로 명시되고 승인되어야 한다.

현재 `compare`는 독립적인 public command가 아니라 finder나 Meld 내부의
비교 단계에 가깝고, `reconcile`은 향후 계약이다. 이 절은 현재 사용
가능한 완성 기능을 설명하지 않는다.

### Update

방향성 update의 Goal은 검증된 source Context A를 target Context B에
반영하면서 B의 관련 없는 기존 지식을 보존하는 것이다. Update Rules는
source의 권위와 범위, 변경 가능한 target의 소유권, provenance,
근거 없는 정보 생성 금지, 관련 없는 target 정보 보존, stale input과
승인 경계를 규정한다. 제안된 각각의 edit 또는 addition은 구체적인
아티팩트에 연결된 candidate Case로 볼 수 있다.

Task 1에서 B는 조직의 공유 원본 자체가 아니라 참가자에게 미리 제공된
쓰기 가능한 local fork다. 표준 이름은
[`task-1-naming-contract.md`](task-1-naming-contract.md)를 따른다. 조직
원본 `campus-wiki`는 query-only이고, 참가자의 담당 범위는
`participant/campus-wiki-fork`라는 local Context graph로 존재한다.
`impact`와 `update`는 이 local fork만 대상으로 삼는다. 조직 원본에
질문할 수 있다는 사실은 그 내용을 traverse하거나 수정할 권한을
뜻하지 않으며, 실제 조직 원본으로의 기여는 향후 `push` 또는 PR라는
별도의 승인 경계가 담당한다.

현재 구현은 query-only origin pointer를 표현하고 이미 provision된
fork에 update를 로컬 적용할 수 있지만, scoped fork 생성, origin
revision binding, refresh, publication은 구현하지 않았다. 따라서 이
구분은 Task 1 fixture와 향후 update/push가 따라야 할 권한 계약이며,
현재 remote access-control 기능이 완성됐다는 주장이 아니다.

현재 Task 1 fixture는 시작 시점에 `participant/campus-wiki-fork`가
참가자 담당 범위의 최신 승인 snapshot이고, 과업 동안 그 원격 범위에
동시 변경이 없다고 가정한다. query-only adapter는 이 조건을 검증할 수
없다. 이는 연구 시나리오를 단순화하기 위한 가정이며, 향후 publication
adapter의 upstream base revision과 remote divergence 검사로 대체해야
한다.

local fork의 범위는 impact 결과를 미리 알고 선택한 "바뀔 페이지 목록"이
아니라 참가자의 책임과 권한으로 정한 candidate scope다. 따라서 관련될
가능성이 있는 페이지와 실제로는 변경되지 않을 비교 항목도 포함해야
하며, 그중 실제 변경 subset을 찾는 일은 여전히 `impact`의 책임이다.
fixture 검토는 모든 잠재적 영향 페이지가 이 권한 범위에 들어 있는지
별도로 확인해야 한다.

일반적인 update에서는 다음과 같은 미해결 문제가 발생할 수 있다.

- 하나의 source 또는 target에 여러 가능한 reading이 존재한다.
- source와 target이 충돌하는 것처럼 보인다.
- 어느 target Context에 배치해야 하는지 불명확하다.
- 시간, 장소, 대상 또는 예외 범위가 빠져 있다.
- 사용자가 새 의견이나 추가 조건을 제공한다.

완성된 일반 update라면 이런 경우 곧바로 stage하거나 적용해서는 안
된다. 해당 update는 해소가 필요한 상태에서 멈추고, bound Ground의
통제를 받는 issue-scoped directional Meld로 들어가야 한다. 사용자의
답변은 하나의 target Memory를 즉시 수정하는 명령이 아니라, 경계가
정해진 전체 update 제안을 다시 계산하기 위한 semantic turn이 된다.

> **현재 구현 주의**
>
> 지금의 `UpdateSession`은 source, target, fingerprints, edit/add
> operations와 로컬 적용 receipt를 저장한다. Ground identity나
> revision, Rules, Cases, unresolved issues, Meld turns를 저장하지
> 않는다. 현재 planner는 이러한 해소 루프를 수행하지 않으며
> `update`는 conflict-free validated plan을 로컬 fork에 적용한다.

## Task 1의 경계

Task 1 참가자에게 제공되는 local memory는 이미 수집과 검증이 끝난
자료로 규정된다. Task 1의 impact 결과는 합리적이고 conflict-free인
것으로 기대된다. 참가자는 provenance를 추가로 확인하거나 결과를
신뢰할 수 있지만 clarification 또는 reconcile turn을 반드시 거칠
필요는 없다.

```text
검증된 local Context
→ 쓰기 가능한 사용자 local wiki fork에 대한 impact preview
→ 선택적인 provenance 검토
→ update가 local fork에 실제 적용
→ fork baseline과 적용 결과의 diff
→ 향후 query-only 조직 원본에 push 또는 PR
```

Task 1에 인위적인 ambiguity나 conflict를 추가하면 참가자에게 결과가
신뢰하기 어렵다는 신호를 줄 수 있다. 이는 provenance의 가용성,
책임감에 대한 인식, 시스템에 대한 신뢰를 관찰하려는 연구 조건을
변경할 수 있다. 따라서 Task 1 참가자 흐름에서 update 해소 과정이
없는 것은 의도된 시나리오 경계다.

Task 1 이전의 fixture 제작 과정은 구분해야 한다. Raw intake를
atomize하고 ambiguity/conflict를 검토하며 wiki와 local destination의
내용을 정당화하는 과정은 참가자 runtime 이전에 수행될 수 있다.
참가자가 받는 verified Context는 그 사전 과정을 통과한 결과다.

다시 말해 다음 두 문장은 동시에 참이다.

1. Task 1 참가자 경로는 update-resolution dialogue를 요구하지 않는다.
2. 실제 환경의 일반 update에는 Grounding과 directional Meld를 통한
   해소 경로가 필요하며, 이는 아직 구현되지 않았다.

## 불변 조건

- 모든 대화 turn이 Memory, Rule 또는 golden Case가 되는 것은 아니다.
- 하나의 Case에만 적용되는 clarification은 자동으로 전역 Rule이 되지
  않는다.
- 오퍼레이션별 source arity, evidence, target, mutation 계약은 계속
  유지된다.
- 하나의 issue에 관한 turn이라도 경계가 정해진 전체 operation frame의
  결과를 다시 계산할 수 있다.
- Ground revision, operation input, target state는 fingerprint로
  고정되어야 한다.
- Ground 또는 Context가 바뀌면 기존 proposal은 stale 상태가 되어야
  한다.
- query-only 조직 원본은 impact/update의 mutation target이 될 수 없고,
  query 권한은 write 권한으로 승격되지 않는다.
- update가 실제로 변경하는 B는 사용자 소유 local fork이며, 조직
  publication은 별도의 push/PR 승인 경계다.
- proposal, semantic acceptance, local materialization, publication은
  서로 다른 동의 경계로 유지한다.
- 해결되지 않은 `REQUIRED` issue는 stage 또는 bulk acceptance로
  우회할 수 없어야 한다.
- provider는 사용자 승인이나 source authority를 대신 결정할 수 없다.
- operation-specific artifact와 named Ground 사이의 승격·가져오기는
  자동 동기화가 아니라 명시적 provenance 동작이어야 한다.

## TODO: 해소가 필요한 방향성 Update

향후 update-grounding 어댑터는 다음을 지원해야 한다.

1. 구조화된 `REQUIRED` 및 `HELPFUL` update issues를 정의한다.
2. update session을 관련 Ground UID, revision, digest에 연결한다.
3. 제안된 edit와 addition을 아티팩트에 연결된 candidate Cases로
   표현한다.
4. 모든 dialogue turn에서 source와 target fingerprints를 유지한다.
5. 사용자의 해소 답변을 directional Meld turn으로 기록한다.
6. 각 turn 이후 경계가 정해진 전체 update proposal을 다시 계산한다.
7. 국소적인 clarification이 재사용 가능한 Rule이나 golden Case가
   되기 전에 별도의 명시적 승격과 승인을 요구한다.
8. 해결되지 않은 `REQUIRED` issue가 있으면 staging을 차단한다.
9. Ground 변경 이후 기존 update proposal과 관련 Cases를 다시
   검사한다.
10. local working-copy 적용과 publication을 서로 별도로 승인되는
    오퍼레이션으로 유지한다.
11. 실제 ambiguity, conflict, placement uncertainty를 포함하는
    Task 1 외부의 golden scenarios를 추가한다.

Task 1에는 검증되고 conflict-free인 update가 이 미래의 resolution
branch에 들어가지 않고 로컬 적용까지 도달한다는 regression case를
유지한다.

## 현재 단계의 의도적인 비목표

이 문서는 현재 단계에서 다음 기능이 존재한다고 주장하지 않는다.

- 하나의 named Ground가 모든 semantic operation을 자동 조율하는 기능
- atomize clarification을 Ground Rule이나 Case로 자동 승격하는 기능
- update issue를 대화로 해소하는 TUI
- update proposal에 대한 selective per-proposal acceptance
- non-empty baseline을 수정하는 public directional Meld
- Ground 변경에 따른 자동 semantic regression
- 다중 Context local update를 위한 process-crash recovery journal
- remote `push`, PR, access-control 또는 조직 publication

이 항목들은 이 설계 방향의 후속 작업이다. Task 1의 제한된 경로가
작동한다는 사실을 근거로 완성된 cross-operation Grounding 시스템이
존재한다고 설명해서는 안 된다.

## 관련 문서

- [`mem-ground-design-rationale.md`](mem-ground-design-rationale.md):
  named Goal–Rules–Cases Ground와 Task 1 fixture co-design
- [`mem-review-conversational-grounding-design-rationale.md`](mem-review-conversational-grounding-design-rationale.md):
  atomize에서 시작된 다회차 human grounding과 일반화 경계
- [`memory-refinement-pipeline-design-rationale.md`](memory-refinement-pipeline-design-rationale.md):
  atomize, finder, reconcile, audience, normalize, place의 분리
- [`memory-review-shell-design-rationale.md`](memory-review-shell-design-rationale.md):
  공통 interaction grammar와 operation-specific evidence 경계
- [`mem-impact-update-design-rationale.md`](mem-impact-update-design-rationale.md):
  현재 방향성 impact/update의 제한된 local-application 계약
