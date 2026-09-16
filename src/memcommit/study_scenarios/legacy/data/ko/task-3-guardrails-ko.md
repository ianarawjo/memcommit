# 과제 3 일반 선택 공유 가드레일

이 문서는 Task 3의 향후 `sever` 단계에서 로컬 발신 공유 후보에 적용할
사전 검토 가드레일 75개를 담은 완전한 합성 자료다. `local/guardrails`는 일반 열람
Context이며, 연결된 의료 안내 에이전트의 질의 전용 자료와 분리한다. 기존의
목적·프라이버시·근거·승인·보존 경계를 유지하면서 수신자 권한, 최소화,
전달 채널, 후속 이용, 감사와 복구까지 검토 범위를 확장한다. Guardrails에는
사용자의 공유 선호를 미리 가정하는 User Model을 두지 않는다. 그런 가정은
참가자의 선택을 유도해 연구 행동을 오염시킬 수 있기 때문이다. 그 자리는 외부
데이터 흐름 조건인 World Model과 수신자·조직의 예상 해석인 Other Model로
채운다. `mem sever`는 pass마다 ordinary Criteria Context 하나를 받는다. 이
guardrails를 그 기준으로 사용하거나, 먼저 `mem meld`로 권한이 있는 다른 기준과
결합할 수 있다.

각 `directory/NN` 표시는 `local/guardrails` 아래의 계층형 Memory 위치다. 대괄호의
두 글자 목적 ticker는 제작·검수용 sidecar이며 실제 Memory 본문이 아니다.
실제 Memory 후보는 ticker 뒤의 문장뿐이다. `PP`는 에이전트가 취할 행동을
명령형으로 표현한다. `KB`는 확인된 공유·보안 지식, `SM`은 로컬 에이전트의
역할·능력·관찰 한계, `OM`은 수신자·제삼자·운영자가 무엇을 기대·판단하거나
어떻게 반응할지에 대한 모델, `WM`은 마음과 독립적인 매체·사본·시간·제도
환경의 상태와 제약을 서술한다. 목적 분포는 KB 8, PP 47, SM 4, UM 0,
WM 5, OM 11이다.

Memory 본문은 아래 Context JSON 파일에서 관리한다. 이 문서는 데이터 계약과 탐색용 인덱스다.

- [`local/guardrails/purpose-and-scope`](../native/task-3/task-3/ko/local/guardrails/purpose-and-scope/context.json)
- [`local/guardrails/privacy-and-others`](../native/task-3/task-3/ko/local/guardrails/privacy-and-others/context.json)
- [`local/guardrails/evidence-and-uncertainty`](../native/task-3/task-3/ko/local/guardrails/evidence-and-uncertainty/context.json)
- [`local/guardrails/approval-and-delivery`](../native/task-3/task-3/ko/local/guardrails/approval-and-delivery/context.json)
- [`local/guardrails/retention-and-revocation`](../native/task-3/task-3/ko/local/guardrails/retention-and-revocation/context.json)
- [`local/guardrails/recipient-and-authority`](../native/task-3/task-3/ko/local/guardrails/recipient-and-authority/context.json)
- [`local/guardrails/minimization-and-redaction`](../native/task-3/task-3/ko/local/guardrails/minimization-and-redaction/context.json)
- [`local/guardrails/channel-and-format`](../native/task-3/task-3/ko/local/guardrails/channel-and-format/context.json)
- [`local/guardrails/downstream-use`](../native/task-3/task-3/ko/local/guardrails/downstream-use/context.json)
- [`local/guardrails/audit-and-recovery`](../native/task-3/task-3/ko/local/guardrails/audit-and-recovery/context.json)
