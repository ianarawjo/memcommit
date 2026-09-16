# advisor1 메모리 후보

> 설계자 전용 안내: 두 공동지도자는 동등한 권한을 가진다. 각 레코드는
> `Fixture ID — Memory 위치 — 목적 — 본문` 순서다. `Memory 위치`는
> `directory/slug` 형식의 상대 locator이며, 실제 Memory 본문은 마지막 긴
> 줄표 오른쪽 문장만을 가리킨다. 목적 코드는 `KB`, `PP`, `SM`, `UM`,
> `WM`, `OM`을 사용한다. `KB`는 검증 가능한 연구·제안서 지식, `PP`는
> 에이전트가 따라야 할 명령형 절차, `SM`은 이 advisor 자신의 역할·능력·
> 검토 한계, `UM`은 현재 제안서 작성자의 기대·선호·익숙함·혼란,
> `OM`은 심사자·참가자·운영자 등 다른 행위자의 기대·선호·판단,
> `WM`은 사람의 마음과 독립된 기관·일정·자원·평가 환경의 제약을 뜻한다.
>
> 이 store는 분야 중립적인 두 쪽짜리 석사 연구 제안서 제출 지침을 HCI
> 연구실의 작성 관행으로 해석한 내부 지도 조언이다. 두 쪽은 문서 분량이며
> 연구기간이 2주라는 뜻이 아니다. 외부 지침은 무엇을 제출할지 정하고,
> 이 Memory는 사용자 문제, 설계 기여, 시제품, 사용자 연구와 평가를 HCI에서
> 어떻게 표현할지 정한다.
>
> 두 advisor는 같은 의미 범주의 대응쌍 순서로 제시하지만, 원자화 결과에
> 따라 개별 Memory 위치와 개수는 다를 수 있다. 관계 밴드 sidecar는
> `pair_id`, `left_fixture_ids`, `right_fixture_ids`, `relationship_band`
> 순서다. 원자화로 한쪽 조언이 여러 Memory가 된 경우에는 세미콜론으로
> 구분한 여러 Fixture ID가 같은 대응쌍에 함께 연결된다. 이 파일에는
> 정확히 150개의 독립 검토 가능한
> 후보가 있다.

Memory 본문은 아래 Context JSON 파일에서 관리한다. 이 문서는 데이터 계약과 탐색용 인덱스다.

- [`advisor1/structure`](../native/task-2/task-2-proposal-authority/ko/advisor1/structure/context.json)
- [`advisor1/emphasis`](../native/task-2/task-2-proposal-authority/ko/advisor1/emphasis/context.json)
- [`advisor1/style`](../native/task-2/task-2-proposal-authority/ko/advisor1/style/context.json)
- [`advisor1/claim-evidence`](../native/task-2/task-2-proposal-authority/ko/advisor1/claim-evidence/context.json)
- [`advisor1/expression`](../native/task-2/task-2-proposal-authority/ko/advisor1/expression/context.json)
- [`advisor1/terminology`](../native/task-2/task-2-proposal-authority/ko/advisor1/terminology/context.json)
- [`advisor1/methods`](../native/task-2/task-2-proposal-authority/ko/advisor1/methods/context.json)
- [`advisor1/evaluation`](../native/task-2/task-2-proposal-authority/ko/advisor1/evaluation/context.json)
- [`advisor1/ethics`](../native/task-2/task-2-proposal-authority/ko/advisor1/ethics/context.json)
- [`advisor1/scope`](../native/task-2/task-2-proposal-authority/ko/advisor1/scope/context.json)
- [`advisor1/safety`](../native/task-2/task-2-proposal-authority/ko/advisor1/safety/context.json)
- [`advisor1/feasibility`](../native/task-2/task-2-proposal-authority/ko/advisor1/feasibility/context.json)
- [`advisor1/reproducibility`](../native/task-2/task-2-proposal-authority/ko/advisor1/reproducibility/context.json)
- [`advisor1/budget`](../native/task-2/task-2-proposal-authority/ko/advisor1/budget/context.json)
- [`advisor1/compensation`](../native/task-2/task-2-proposal-authority/ko/advisor1/compensation/context.json)
- [`advisor1/review`](../native/task-2/task-2-proposal-authority/ko/advisor1/review/context.json)
