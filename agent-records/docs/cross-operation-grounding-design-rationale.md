# 오퍼레이션 전반의 Grounding과 향후 Update 해소 과정

## 2026-08-29 Atomize 경계 수정

이 문서의 공통 Grounding 구상은 향후 오퍼레이션 설계를 위한 연구
맥락으로 남긴다. 그러나 Atomize는 더 이상 그 구상의 실행 주체가
아니다. Atomize는 ambiguity/conflict를 finding과 적용 receipt로 기록할
뿐, 대화를 시작하거나 reading을 선택하거나 resolution을 적용하지
않는다. 기존 Atomize Grounding 실행 경로와 Atomize-to-Meld projection은
제거되었으며, 과거 record model과 복구 경로만 호환성 용도로 남는다.

따라서 아래의 Atomize 다회차 clarification 설명은 역사적 설계 기록이며
현재 callable contract가 아니다. 현재 경계는
[`atomize-read-only-findings-design-rationale.md`](atomize-read-only-findings-design-rationale.md)에
정리되어 있다.

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
| Context-to-Context directional Meld | direct `INCOMING → BASELINE`의 `EDIT`/`ADD` 및 zero-change acceptance 구현 |
| 독립적인 `compare` 명령 | 읽기 전용 peer comparison으로 구현 |
| 독립적인 `reconcile` 명령 | **미구현 TODO** |
| atomize의 다회차 clarification | **현재 Atomize 범위 밖**; 과거 record만 읽기/복구 호환 |
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
| `MEMORIES` | 현재 Goal과 Rules를 시험하는 구체적인 Memories, findings, readings, 관계 묶음 또는 변경 제안 |

오퍼레이션은 네 번째 Ground 계층이 아니다. 각 오퍼레이션은 위 세
계층을 자신의 source arity, evidence, target, mutation 경계에 맞게
해석하는 어댑터를 제공한다. 또한 어떤 아티팩트를 검토하거나
변경했다는 사실만으로 그 아티팩트가 승인된 Ground Memory나 golden
Ground Memory가
되는 것은 아니다.

반복되는 정당화 흐름은 다음과 같다.

```text
하나의 구체적인 아티팩트 또는 중요한 finding을 제시
→ 현재 Goal과 Rules에 따라 판단
→ 제안된 reading, 관계 또는 변경과 그 영향을 표시
→ 근거가 부족하면 실제 판단을 바꿀 수 있는 후속 질문을 제시
→ 사용자가 확인·확장·수정·철회·보류하거나 추가 맥락을 제공
→ 관련된 Ground Memory, Rule 또는 Goal을 수정
→ 영향을 받는 findings와 기존에 승인된 Ground Memories를 다시 검토
→ 실제 변경 전 명시적인 허가를 요청
```

이 구조는 인간 대화에서의 common grounding과도 대응한다. 사람들은
첫 문장을 완성된 명세로 취급하지 않는다. 상대가 어떻게 이해했는지,
그 이해가 어떤 결과를 만드는지, 빠진 조건이 무엇인지 확인하고
오해를 수정한 뒤 행동을 허가한다. 이 프로젝트의 Grounding은 그
과정을 관찰 가능한 상태와 승인 경계로 보존하려는 시도다.

## Ground와 Meld의 관계

Ground와 Meld는 동일한 장기적 상호작용의 서로 다른 측면을 설명한다.

- **Ground**는 행동을 정당화하는 공통 Goal, Rules, Memories, 수정 사항과
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

사용자의 clarification은 하나의 ambiguity를 해소하거나 예상 결과를
바꿀 수 있지만, 그 처리는 Atomize의 책임이 아니다. 현재 Atomize는
Source Memories, proposed readings, split 결과, ambiguity/conflict를
불변 evidence로 보존하고 적용 receipt에 모두 표시한다. 대화, resolution,
Memory update는 별도의 후속 오퍼레이션이 자기 계약으로 맡아야 하며,
Atomize는 그 소비자를 자동 호출하거나 handoff schema를 만들지 않는다.

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
clarification을 재사용 가능한 Rule이나 golden Ground Memory로 승격하는 과정은
별도로 명시되고 승인되어야 한다.

현재 `compare`는 독립적인 읽기 전용 public command이며 Meld가 그 저장된
분석을 seed로 사용할 수 있다. `reconcile`은 여전히 향후 계약이다. 이
절의 Reconcile 설명은 현재 사용 가능한 완성 기능을 뜻하지 않는다.

### Update

방향성 update의 Goal은 검증된 source Context A를 target Context B에
반영하면서 B의 관련 없는 기존 지식을 보존하는 것이다. Update Rules는
source의 권위와 범위, 변경 가능한 target의 소유권, provenance,
근거 없는 정보 생성 금지, 관련 없는 target 정보 보존, stale input과
승인 경계를 규정한다. 제안된 각각의 edit, addition, 또는 removal은
구체적인 아티팩트에 연결된 candidate Case로 볼 수 있다.

현재 구현은 이 큰 계약의 좁은 부분으로, `--goal`에 공통
Context/Memory/text Goal focus를 받을 수 있다. 이 frame은 provider의
relevance 및 output-selection 기준이고 session과 Apply freshness에
결합되지만 `source_id` 근거가 아니며 named Ground 전체와의 자동
동기화도 아니다. 이 경계는
[`goal-focus-operand-design-rationale.md`](goal-focus-operand-design-rationale.md)에
기록한다.

Task 1에서 B는 읽고 수정할 수 있는 ordinary `campus-wiki`다. 표준
이름은 [`task-1-naming-contract.md`](task-1-naming-contract.md)를 따른다.
공사 상세는 그 안의 query-only `construction-details` 포인터로 분리된다.
`impact`와 `update`는 ordinary wiki만 대상으로 삼으며, 상세 정보에
질문할 수 있다는 사실은 그 내용을 traverse하거나 수정할 권한을
뜻하지 않는다.

ordinary wiki의 범위는 impact 결과를 미리 알고 선택한 "바뀔 페이지 목록"이
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
> 지금의 `UpdateSession`은 source, target, fingerprints, edit/add/remove
> operations와 로컬 적용 receipt를 저장한다. Ground identity나
> revision, Rules, Ground Memories, unresolved issues, Meld turns를 저장하지
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
→ 쓰기 가능한 ordinary campus wiki에 대한 impact preview
→ 선택적인 provenance 검토
→ update가 campus wiki에 실제 적용
→ wiki baseline과 적용 결과의 diff
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

- 모든 대화 turn이 Memory, Rule 또는 golden Ground Memory가 되는 것은 아니다.
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
- query-only `construction-details`는 impact/update의 mutation target이 될 수 없고,
  query 권한은 write 권한으로 승격되지 않는다.
- update가 실제로 변경하는 B는 ordinary `campus-wiki`다.
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
7. 국소적인 clarification이 재사용 가능한 Rule이나 golden Ground Memory가
   되기 전에 별도의 명시적 승격과 승인을 요구한다.
8. 해결되지 않은 `REQUIRED` issue가 있으면 staging을 차단한다.
9. Ground 변경 이후 기존 update proposal과 관련 Ground Memories를 다시
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
- atomize clarification을 Ground Rule이나 Ground Memory로 자동 승격하는 기능
- update issue를 실제 semantic turn으로 해소하고 전체 계획을 재분석하는
  durable resolution session
- update proposal에 대한 selective per-proposal acceptance
- Ground 변경에 따른 자동 semantic regression
- 다중 Context local update를 위한 process-crash recovery journal
- remote `push`, PR, access-control 또는 조직 publication

이 항목들은 이 설계 방향의 후속 작업이다. Task 1의 제한된 경로가
작동한다는 사실을 근거로 완성된 cross-operation Grounding 시스템이
존재한다고 설명해서는 안 된다.

## 관련 문서

- [`mem-ground-design-rationale.md`](mem-ground-design-rationale.md):
  named Goal–Rules–Memories Ground와 Task 1 fixture co-design
- [`mem-review-conversational-grounding-design-rationale.md`](mem-review-conversational-grounding-design-rationale.md):
  atomize에서 시작된 다회차 human grounding과 일반화 경계
- [`memory-refinement-pipeline-design-rationale.md`](memory-refinement-pipeline-design-rationale.md):
  atomize, finder, reconcile, audience, normalize, place의 분리
- [`memory-review-shell-design-rationale.md`](memory-review-shell-design-rationale.md):
  공통 interaction grammar와 operation-specific evidence 경계
- [`semantic-resolution-workbench-design-rationale.md`](semantic-resolution-workbench-design-rationale.md):
  Meld·Atomize·Update·향후 Reconcile의 공통 동적 list/detail/comment
  presentation과 operation-owned semantic 경계
- [`mem-impact-update-design-rationale.md`](mem-impact-update-design-rationale.md):
  현재 방향성 impact/update의 제한된 local-application 계약
