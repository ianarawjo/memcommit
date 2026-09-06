# 과제 3 개인 메모리 후보

이 문서는 Task 3의 선택 공유 과업에 사용할 비식별 합성 개인 메모리 300개를
담는다. 2024년 1월부터 2026년 6월까지 30개월에 월별 10개씩 배치했다.
User Model에는 식사, 이동, 집안일, 행정, 여가 같은 구체적 사건과 그 사건들에서
도출된 선호·개인 규칙을 함께 둔다. 한 사건을 안정적인 성향으로 과장하지 않고,
관찰된 반응이나 그 상황에서의 선택으로 한정한다. 사건의 세부를 얼마나 남기고
얼마나 압축된 선호·정책으로 바꿀지는 이 fixture가 미리 고정하지 않는 질적 연구
질문이다. Other Model은 현재 사용자가 아닌 가족이나
직원이 무엇을 기대·선호·판단하거나 어떻게 반응할지를, Self Model은 로컬
에이전트가 무엇을 관찰·비교할 수 있고 무엇을 확인할 수 없는지를 담는다.
World Model은 사람의 마음과 독립적인 물리·제도·환경 조건만 담는다.
가족 관계는 엄마, 아빠, 누나, 남동생, 이모, 외삼촌처럼 명시하되 실제 이름,
기관, 주소, 병명은 포함하지 않는다. 모든 날짜와 사건은 연구용 합성 자료다.

`YYYY-MM/NN`은 `local/personal-memory` Context 아래의 계층형 Memory 위치다. 각
위치는 월 단위 Context와 월 안의 개별 Memory를 나타낸다. 생성된 Study
Profile은 이 source locator를 안정적인 fixture key로 보존하면서, ordinary
Context는 구조용 `YYYY` 부모를 포함한 `YYYY/MM` 경로로 노출한다. 대괄호의 두
글자 목적 ticker는 검수용 sidecar이며 실제 Memory 본문에 포함하지 않는다. 실제
Memory 후보는 ticker 뒤의 문장뿐이다. 목적 분포는 KB 30, PP 20, SM 20,
UM 184, WM 16, OM 30이다.

Memory 본문은 아래 Context JSON 파일에서 관리한다. 이 문서는 데이터 계약과 탐색용 인덱스다.

- [`local/personal-memory/2024/01`](../native/task-3/task-3/ko/local/personal-memory/2024/01/context.json)
- [`local/personal-memory/2024/02`](../native/task-3/task-3/ko/local/personal-memory/2024/02/context.json)
- [`local/personal-memory/2024/03`](../native/task-3/task-3/ko/local/personal-memory/2024/03/context.json)
- [`local/personal-memory/2024/04`](../native/task-3/task-3/ko/local/personal-memory/2024/04/context.json)
- [`local/personal-memory/2024/05`](../native/task-3/task-3/ko/local/personal-memory/2024/05/context.json)
- [`local/personal-memory/2024/06`](../native/task-3/task-3/ko/local/personal-memory/2024/06/context.json)
- [`local/personal-memory/2024/07`](../native/task-3/task-3/ko/local/personal-memory/2024/07/context.json)
- [`local/personal-memory/2024/08`](../native/task-3/task-3/ko/local/personal-memory/2024/08/context.json)
- [`local/personal-memory/2024/09`](../native/task-3/task-3/ko/local/personal-memory/2024/09/context.json)
- [`local/personal-memory/2024/10`](../native/task-3/task-3/ko/local/personal-memory/2024/10/context.json)
- [`local/personal-memory/2024/11`](../native/task-3/task-3/ko/local/personal-memory/2024/11/context.json)
- [`local/personal-memory/2024/12`](../native/task-3/task-3/ko/local/personal-memory/2024/12/context.json)
- [`local/personal-memory/2025/01`](../native/task-3/task-3/ko/local/personal-memory/2025/01/context.json)
- [`local/personal-memory/2025/02`](../native/task-3/task-3/ko/local/personal-memory/2025/02/context.json)
- [`local/personal-memory/2025/03`](../native/task-3/task-3/ko/local/personal-memory/2025/03/context.json)
- [`local/personal-memory/2025/04`](../native/task-3/task-3/ko/local/personal-memory/2025/04/context.json)
- [`local/personal-memory/2025/05`](../native/task-3/task-3/ko/local/personal-memory/2025/05/context.json)
- [`local/personal-memory/2025/06`](../native/task-3/task-3/ko/local/personal-memory/2025/06/context.json)
- [`local/personal-memory/2025/07`](../native/task-3/task-3/ko/local/personal-memory/2025/07/context.json)
- [`local/personal-memory/2025/08`](../native/task-3/task-3/ko/local/personal-memory/2025/08/context.json)
- [`local/personal-memory/2025/09`](../native/task-3/task-3/ko/local/personal-memory/2025/09/context.json)
- [`local/personal-memory/2025/10`](../native/task-3/task-3/ko/local/personal-memory/2025/10/context.json)
- [`local/personal-memory/2025/11`](../native/task-3/task-3/ko/local/personal-memory/2025/11/context.json)
- [`local/personal-memory/2025/12`](../native/task-3/task-3/ko/local/personal-memory/2025/12/context.json)
- [`local/personal-memory/2026/01`](../native/task-3/task-3/ko/local/personal-memory/2026/01/context.json)
- [`local/personal-memory/2026/02`](../native/task-3/task-3/ko/local/personal-memory/2026/02/context.json)
- [`local/personal-memory/2026/03`](../native/task-3/task-3/ko/local/personal-memory/2026/03/context.json)
- [`local/personal-memory/2026/04`](../native/task-3/task-3/ko/local/personal-memory/2026/04/context.json)
- [`local/personal-memory/2026/05`](../native/task-3/task-3/ko/local/personal-memory/2026/05/context.json)
- [`local/personal-memory/2026/06`](../native/task-3/task-3/ko/local/personal-memory/2026/06/context.json)
