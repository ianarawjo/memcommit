# Task 2 제안서 제출 지침 질의 전용 맥락

이 문서의 75개 항목은 사용자 연구를 위해 완전히 창작한 합성 자료이며 실제
기관, 연구비 공고, 제출 양식 또는 심사 절차와 대응하지 않는다. 이 맥락은
`advisor1`과 `advisor2`가 동등하게 참조하는 외부 제안서 제출 지침이며,
어느 지도자의 조언을 정답으로 삼거나 두 지도자 사이의 충돌을 대신 해결하는
내부 문답지가 아니다.

이 자료는 특정 세부 분야의 평가 기준이 아니라, 적용 지향 석사 연구 프로젝트를
두 쪽으로 압축해 제안할 때의 분야 중립적인 형식·필수 구성·제출 절차를
정의한다. 여기서 분야 중립적이라는 말은 HCI를 미리 가정하지 않는다는
뜻이며, 순수 이론 연구까지 포괄하는 보편 계약이라는 뜻은 아니다. 두 쪽이라는
제한은 문서 분량을 뜻하며 연구를 2주 안에 끝내라는 뜻이 아니다. 사람 대상
연구, 산출물 개발, 현장 적용, 예산 또는 윤리에 관한 항목은 해당되는 연구에만
적용한다. HCI에서 시제품·상호작용·사용자 연구·배포·디자인 기여를 어떻게
표현할지는 두 advisor의 Memory가 해석한다.

질의 전용이라는 표시는 사용자가 질문을 통해 필요한 제출 요건을 확인하게
하는 연구 프로토타입의 상호작용 경계이며, 사용자 인증이나 접근 제어
목록(ACL)을 뜻하지 않는다. 각 레코드는
`Fixture ID — Memory 위치 — 목적 — 본문` 순서다. `Memory 위치`는
`directory/slug` 형식의 상대 locator이며, 실제 Memory 본문은 마지막 긴
줄표 오른쪽 문장만을 가리킨다. 목적 코드는 `KB`, `PP`, `SM`, `UM`,
`WM`, `OM`을 사용한다. `KB`는 검증 가능한 연구·제안서 지식, `PP`는
에이전트가 따라야 할 명령형 절차, `SM`은 로컬 에이전트 자신의 역할·능력·
인식 한계, `UM`은 현재 제안서 작성자의 기대·선호·익숙함·혼란,
`OM`은 심사자·접수 담당자 등 다른 행위자의 기대·선호·판단,
`WM`은 사람의 마음과 독립된 기관·마감·포털·자원 환경의 제약을 뜻한다.

- T2-Q-001 — `submission/pdf-upload` — PP — 제출 포털에 PDF 파일 한 개를 업로드하라.
- T2-Q-065 — `submission/pdf-searchability` — PP — 제출할 PDF의 텍스트를 검색 가능하게 유지하라.
- T2-Q-002 — `submission/file-size` — PP — 업로드 파일의 크기를 10MB 이하로 유지하라.
- T2-Q-004 — `submission/deadline` — PP — 공고에 표시된 마감일의 북미 동부시간 오후 5시 전에 제출하라.
- T2-Q-005 — `submission/administrator-timestamp-check` — OM — 접수 담당자는 작성자가 업로드를 시작한 시각보다 포털 서버 타임스탬프를 제출 완료 여부의 권위 있는 근거로 간주한다.
- T2-Q-075 — `submission/requirements-may-change` — WM — 제출 포털의 양식과 공고 요구는 제출 회차에 따라 바뀔 수 있다.
- T2-Q-006 — `format/body-page-limit` — PP — 제안서 본문을 최대 두 쪽으로 제한하라.
- T2-Q-007 — `format/reference-page-count` — KB — 참고문헌은 본문 두 쪽 제한에 포함되지 않는다.
- T2-Q-072 — `format/figure-table-page-count` — KB — 본문에 배치한 그림과 표는 본문 두 쪽 제한에 포함된다.
- T2-Q-008 — `format/font-size` — PP — 본문 글자 크기를 11포인트 이상으로 유지하라.
- T2-Q-009 — `format/page-size` — PP — 모든 페이지를 US Letter 크기로 작성하라.
- T2-Q-010 — `format/typeface` — PP — 본문 글꼴은 Arial을 사용하라.
- T2-Q-011 — `format/margins` — PP — 모든 페이지의 네 방향 여백을 1인치 이상으로 유지하라.
- T2-Q-012 — `format/reviewer-figure-scan` — OM — 심사자는 그림과 표를 본문과 별도로 먼저 훑는 경우가 많다.
- T2-Q-013 — `summary/word-budget` — PP — 프로젝트 요약을 80~100단어로 작성하라.
- T2-Q-014 — `summary/problem` — PP — 프로젝트 요약에 해결할 문제를 한 문장으로 제시하라.
- T2-Q-015 — `summary/objective` — PP — 프로젝트 요약에 주된 연구 목표를 한 문장으로 제시하라.
- T2-Q-016 — `summary/approach` — PP — 프로젝트 요약에 사용할 연구 접근을 한 문장으로 제시하라.
- T2-Q-017 — `summary/expected-outcome` — PP — 프로젝트 요약에 예상 결과를 한 문장으로 제시하라.
- T2-Q-018 — `summary/reviewer-fit-decision` — OM — 심사자는 프로젝트 요약을 바탕으로 제안서가 공모 범위에 맞는지 처음 판단한다.
- T2-Q-019 — `background/word-budget` — PP — 배경과 관련 연구를 합쳐 170~210단어로 작성하라.
- T2-Q-020 — `background/unresolved-problem` — PP — 아직 해결되지 않은 연구 문제를 구체적으로 특정하라.
- T2-Q-021 — `background/urgency` — PP — 해당 문제를 지금 다뤄야 하는 이유를 설명하라.
- T2-Q-022 — `background/related-evidence` — PP — 제안한 연구 문제나 접근과 가장 직접 관련된 최신 근거를 제시하라.
- T2-Q-023 — `background/research-gap` — PP — 기존 연구가 남긴 공백을 한 문장으로 명시하라.
- T2-Q-024 — `background/nonspecialist-reading` — OM — 세부 분야가 다른 심사자는 처음 정의되지 않은 핵심 개념을 같은 의미로 해석하기 어렵다.
- T2-Q-003 — `objectives/word-budget` — PP — 연구 목표와 질문을 합쳐 60~80단어로 작성하라.
- T2-Q-025 — `objectives/primary-objective` — PP — 주된 연구 목표를 한 문장으로 작성하라.
- T2-Q-026 — `objectives/author-question-scope` — UM — 이 제안서를 작성하는 사용자는 제한된 두 쪽에 맞추기 위해 연구 질문을 세 개 이하로 좁히려 한다.
- T2-Q-073 — `objectives/author-advice-reconciliation` — UM — 이 제안서를 작성하는 사용자는 서로 다른 내부 조언을 공식 제출 지침과 대조해 최종 구성을 결정하려 한다.
- T2-Q-027 — `objectives/success-criterion` — PP — 주된 연구 목표가 달성되었다고 판단할 기준을 명시하라.
- T2-Q-028 — `objectives/panel-comparison` — OM — 심사 패널은 명시된 연구 목표와 성공 기준을 대응시켜 제안서의 초점을 비교한다.
- T2-Q-029 — `methods/word-budget` — PP — 방법과 평가 계획을 합쳐 300~340단어로 작성하라.
- T2-Q-030 — `methods/question-data-link` — PP — 각 연구 질문에 답하기 위해 수집할 자료 유형을 연결하라.
- T2-Q-031 — `methods/collection-tool` — PP — 각 자료 유형을 수집할 도구를 명시하라.
- T2-Q-033 — `methods/analysis-procedure` — PP — 각 자료 유형에 적용할 분석 절차를 명시하라.
- T2-Q-034 — `methods/sample-rationale` — PP — 사람·사례·자료 표본이 필요한 연구라면 목표 규모와 산정 근거를 제시하라.
- T2-Q-035 — `methods/feasibility-criterion` — PP — 제안한 방법을 주어진 기간과 자원 안에서 수행할 수 있는지 판단할 기준을 명시하라.
- T2-Q-036 — `methods/execution-constraints` — PP — 예상되는 주요 실행 제약과 그 대응 계획을 명시하라.
- T2-Q-037 — `methods/reviewer-answerability` — OM — 심사자는 연구 질문에서 자료와 분석까지 이어지는 경로를 따라 답변 가능성을 판단한다.
- T2-Q-038 — `outcomes/word-budget` — PP — 예상 결과와 기여를 합쳐 80~100단어로 작성하라.
- T2-Q-039 — `outcomes/decision-contribution` — PP — 연구 결과가 바꿀 수 있는 설계 또는 운영 결정을 하나 이상 특정하라.
- T2-Q-040 — `outcomes/reviewer-evidence-status` — OM — 심사자는 예상 결과를 이미 확인된 효과와 구분해 읽는다.
- T2-Q-041 — `workplan-budget/timeline-word-budget` — PP — 석사 연구 프로젝트의 전체 실행 일정을 60~80단어로 작성하라.
- T2-Q-032 — `workplan-budget/budget-word-budget` — PP — 비용이 발생하거나 별도 예산이 요구되면 예산 설명을 40~60단어로 작성하라.
- T2-Q-042 — `workplan-budget/recruitment-milestone` — PP — 모집의 주요 이정표를 표시하라.
- T2-Q-066 — `workplan-budget/data-collection-milestone` — PP — 자료 수집의 주요 이정표를 표시하라.
- T2-Q-067 — `workplan-budget/analysis-milestone` — PP — 분석의 주요 이정표를 표시하라.
- T2-Q-043 — `workplan-budget/dependencies` — PP — 선행 작업이 끝나야 시작할 수 있는 이정표의 의존성을 표시하라.
- T2-Q-044 — `workplan-budget/budget-appendix-limit` — PP — 별도 예산표가 요구되면 최대 한 쪽의 부록으로 제출하라.
- T2-Q-045 — `workplan-budget/participant-compensation-row` — PP — 참가자 보상 비용이 적용되면 별도 행에 기재하라.
- T2-Q-068 — `workplan-budget/travel-cost-row` — PP — 이동 비용이 적용되면 별도 행에 기재하라.
- T2-Q-069 — `workplan-budget/equipment-cost-row` — PP — 장비 비용이 적용되면 별도 행에 기재하라.
- T2-Q-070 — `workplan-budget/software-cost-row` — PP — 소프트웨어 비용이 적용되면 별도 행에 기재하라.
- T2-Q-071 — `workplan-budget/external-service-cost-row` — PP — 외부 서비스 비용이 적용되면 별도 행에 기재하라.
- T2-Q-046 — `workplan-budget/calculation-basis` — PP — 각 주요 예산 항목에 금액의 산정 근거를 적어라.
- T2-Q-047 — `workplan-budget/activity-link` — PP — 각 주요 예산 항목이 지원하는 연구 활동을 명시하라.
- T2-Q-048 — `workplan-budget/finance-review` — OM — 재무 검토자는 각 비용이 어떤 연구 활동에 필요한지 추적해서 예산의 타당성을 판단한다.
- T2-Q-049 — `ethics-data-access/ethics-status` — PP — 윤리 심의가 필요한 연구라면 현재 심의 상태를 명시하라.
- T2-Q-050 — `ethics-data-access/word-budget` — PP — 해당되는 윤리, 위험, 데이터 관리, 접근성 설명을 합쳐 90~120단어로 작성하라.
- T2-Q-051 — `ethics-data-access/approval-dependency` — WM — 윤리 심의가 필요한 연구에서는 승인이 관련 연구 활동을 시작하기 위한 선행 조건이다.
- T2-Q-052 — `ethics-data-access/eligibility-scope` — PP — 사람·조직·사례를 모집하는 연구라면 포함 기준을 연구 질문에 필요한 특성으로만 설명하라.
- T2-Q-053 — `ethics-data-access/sensitive-data-minimization` — PP — 연구 목적에 필요하지 않은 민감한 개인정보를 요구하지 마라.
- T2-Q-054 — `ethics-data-access/accommodation-options` — PP — 사람 대상 연구라면 참가자가 요청할 수 있는 접근성 편의를 제안서에 명시하라.
- T2-Q-055 — `ethics-data-access/accommodation-request` — PP — 사람 대상 연구라면 접근성 편의를 요청하는 절차를 제안서에 명시하라.
- T2-Q-056 — `ethics-data-access/risk-mitigation` — PP — 예상되는 각 위험에 대응하는 완화 조치를 연결하라.
- T2-Q-057 — `ethics-data-access/storage-location` — PP — 수집 자료의 저장 위치를 명시하라.
- T2-Q-058 — `ethics-data-access/access-scope` — PP — 수집 자료에 접근할 수 있는 역할을 명시하라.
- T2-Q-059 — `ethics-data-access/retention-period` — PP — 수집 자료의 보존 기간을 명시하라.
- T2-Q-060 — `ethics-data-access/disposal-method` — PP — 보존 기간이 끝난 자료의 폐기 방식을 명시하라.
- T2-Q-061 — `ethics-data-access/ethics-reviewer-trace` — OM — 윤리 검토자는 예상되는 위험마다 대응하는 완화 조치가 있는지 확인한다.
- T2-Q-062 — `review/official-priority` — PP — 내부 조언이 공식 공고나 제출 양식과 충돌하면 공식 요구를 우선 적용하라.
- T2-Q-063 — `review/agent-acceptance-limit` — SM — 로컬 에이전트는 포털의 실제 접수 성공을 보증할 수 없다.
- T2-Q-074 — `review/agent-rule-invention-limit` — SM — 로컬 에이전트는 공식 공고에 없는 제출 요건을 확정할 수 없다.
- T2-Q-064 — `review/administrator-completeness` — OM — 행정 검토자는 필수 섹션이 빠졌는지 먼저 확인한다.
