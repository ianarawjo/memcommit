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

- T2-L-001 — `structure/problem` — PP — 독자가 배경 설명보다 먼저 제안서의 핵심 쟁점에 도달하도록 첫 두 문장 안에 문제 설명을 완결하라.
- T2-L-070 — `structure/two-sentence-opening-reserve` — PP — 첫 문장에는 구체적인 문제를, 둘째 문장에는 그 결과를 쓰고 이후 문장은 제안할 대응을 위해 남겨라.
- T2-L-002 — `structure/research-question-position` — PP — 주된 HCI 연구 질문에 사용자, 사용 맥락, 탐구할 상호작용을 명시하라.
- T2-L-011 — `structure/interaction-step-visual` — PP — 낯선 상호작용 절차를 제안할 때는 한 장의 간결한 시각 자료로 요약하라.
- T2-L-071 — `structure/interaction-transition-visual` — PP — 낯선 상호작용 절차가 한 단계에서 다음 단계로 넘어가는 조건을 시각 자료에 표시하라.
- T2-L-015 — `structure/masters-timeline-phases` — PP — 석사 연구 일정을 탐색, 설계, 시제품 제작, 사용자 평가의 단계별 시기로 제시하라.
- T2-L-072 — `structure/masters-timeline-deliverables` — PP — 석사 연구의 각 단계에 검토 가능한 산출물을 하나씩 연결하라.
- T2-L-017 — `structure/gap-contribution-link` — PP — HCI 관련 연구가 남긴 공백과 제안한 설계·경험적 기여를 인접하게 배치하라.
- T2-L-018 — `structure/descriptive-subheadings` — PP — 두 쪽 제안서를 짧고 설명적인 소제목으로 나누어 독자가 문제, 제안할 대응, 다음 단계로 바로 이동할 수 있게 하라.
- T2-L-083 — `structure/subheading-problem-response` — PP — 문단 전환에만 의존하지 말고 문제와 제안할 대응에 각각 설명적인 소제목을 붙여라.
- T2-L-084 — `structure/subheading-next-steps` — PP — 다시 찾아볼 때 쉽게 보이도록 다음 단계와 요청할 지원에 별도 소제목을 붙여라.
- T2-L-024 — `structure/preliminary-result-placement` — PP — 파일럿 관찰이나 초기 시제품 결과는 실행 가능성 주장을 뒷받침하는 문장 가까이에 배치하라.
- T2-L-054 — `structure/reviewer-two-sentence-scan` — OM — 이 advisor는 독자가 나머지 페이지를 훑기 전에 첫 두 문장으로 제안서의 주제를 판단하는 모습을 반복해서 보았다.
- T2-L-080 — `structure/late-problem-scan-cost` — OM — 설정 설명이 둘째 문장을 넘어가면 훑어 읽는 독자는 배경 주제는 기억하지만 제안하려는 정확한 문제를 놓치는 경우가 많다.
- T2-L-095 — `structure/subheading-return-path` — PP — 논의할 때도 같은 짧은 소제목을 다시 사용해 독자가 페이지 전체를 뒤지지 않고 해당 부분으로 돌아갈 수 있게 하라.
- T2-L-096 — `structure/subheading-omission-signal` — PP — 눈에 보이는 소제목을 완결성 점검표로 사용해 비었거나 빠진 부분이 즉시 드러나게 하라.
- T2-L-097 — `structure/advisor-heading-scan-observation` — SM — 이 advisor는 독자가 어느 문단을 자세히 읽을지 정하기 전에 먼저 소제목을 훑는 모습을 반복해서 보았다.
- T2-L-003 — `emphasis/contribution-count` — PP — 주된 HCI 기여는 두 가지를 넘기지 마라.
- T2-L-051 — `emphasis/contribution-naming` — PP — 각 설계 또는 경험적 기여에 이름을 붙여 한 문장으로 제시하라.
- T2-L-013 — `emphasis/recruitment-primary-constraint` — PP — 지역사회 참가자를 모집하는 연구에서는 참여에 따르는 시간 부담을 강조하라.
- T2-L-073 — `emphasis/recruitment-secondary-constraint` — PP — 지역사회 참가자를 모집하는 연구에서는 참여에 따르는 이동 부담을 강조하라.
- T2-L-026 — `style/em-dash-avoidance` — PP — 제안서에서는 em dash를 피하고 문장을 나누거나 더 일반적인 문장부호를 사용하라.
- T2-L-055 — `emphasis/reviewer-contribution-capacity` — OM — HCI 심사자는 이름 붙은 설계·경험적 기여가 두 개를 넘으면 주된 기여를 파악하기 어려워한다.
- T2-L-098 — `emphasis/formative-decision-priority` — PP — 완성도 높은 제품 시연보다 형성 평가가 바꿀 핵심 설계 결정을 우선 강조하라.
- T2-L-099 — `emphasis/transferable-knowledge-priority` — PP — 특정 시제품의 성능보다 다른 유사 상호작용에 이전할 수 있는 설계 원리를 주된 기여로 강조하라.
- T2-L-100 — `emphasis/formative-evaluation-function` — KB — 형성 평가는 설계 대안의 우열을 최종 확정하기보다 다음 반복에서 수정할 근거를 만든다.
- T2-L-101 — `style/author-compound-sentence-tendency` — UM — 이 제안서를 작성하는 사용자는 서로 따로 검토할 수 있는 주장 여러 개를 한 문장에 넣는 경향이 있다.
- T2-L-004 — `claim-evidence/evidence-adjacency` — PP — 사용자 행동이나 기술 효과에 관한 검증 가능한 주장에는 인접한 근거나 인용을 붙여라.
- T2-L-005 — `claim-evidence/observation-prediction-status` — PP — 파일럿에서 관찰한 결과와 본 사용자 연구에서 확인할 예상을 서로 다른 표현으로 구분하라.
- T2-L-009 — `expression/flow-diagram-choice` — PP — 절차의 갈림길에 따라 결과가 달라질 때는 순서표보다 흐름 그림을 사용하라.
- T2-L-085 — `expression/flow-diagram-branches` — PP — 독자가 갈림길과 그 결과를 한눈에 비교할 수 있도록 같은 흐름 그림에 함께 그려라.
- T2-L-010 — `claim-evidence/causal-language` — PP — 설계가 인과 추론을 뒷받침하지 않으면 인과를 입증한다는 동사를 사용하지 마라.
- T2-L-012 — `claim-evidence/source-priority` — PP — HCI 연구 근거가 충분히 축적된 주제라면 개별 사례 나열보다 최신 종합 연구를 우선 인용하라.
- T2-L-027 — `claim-evidence/design-rationale` — PP — 각 설계 선택이 어떤 사용자 필요를 해결하도록 도출되었는지 설명하라.
- T2-L-041 — `claim-evidence/direct-evidence` — PP — 핵심 주장에는 그 주장을 직접 검토한 근거를 간접적인 요약보다 우선 붙여라.
- T2-L-056 — `claim-evidence/reviewer-evidence-order` — OM — 심사자는 핵심 주장과 가장 가까운 곳에 놓인 직접 근거를 먼저 확인한다.
- T2-L-102 — `claim-evidence/conceptual-claim-observation-chain` — PP — 제안하는 개념적 설계 원리를 최소 하나의 관찰 가능한 사용자 행동과 연결하라.
- T2-L-103 — `claim-evidence/formative-finding-decision` — PP — 형성 평가에서 얻을 각 근거가 유지·수정·폐기 중 어떤 설계 판단을 지원하는지 밝혀라.
- T2-L-104 — `claim-evidence/formative-evidence-limit` — KB — 통제된 형성 연구의 결과는 실제 장기 사용에서의 효과를 직접 입증하지 않는다.
- T2-L-105 — `claim-evidence/advisor-claim-threshold` — SM — the agent는 관찰 가능한 자료로 반증할 수 없는 설명을 개념적 기여로 승인할 수 없다.
- T2-L-019 — `style/first-person-responsibility` — PP — 제안서 작성자가 맡는 선택과 약속은 1인칭 능동태로 써서 작업 계획 전체에서 책임 주체를 분명히 하라.
- T2-L-020 — `style/confirmed-procedure-status` — PP — 이미 구현해 확인한 시제품 동작은 관찰된 상태로 써라.
- T2-L-052 — `style/unconfirmed-procedure-status` — PP — 아직 구현하거나 평가하지 않은 시제품 동작은 계획 또는 예상으로 써라.
- T2-L-057 — `style/reviewer-first-person-responsibility` — OM — 이 advisor는 문장이 누가 선택했고 무엇을 전달하거나 수정할지 1인칭 능동태로 밝힐 때 독자가 책임을 더 정확히 배정하는 모습을 보았다.
- T2-L-106 — `style/first-person-choice-boundary` — PP — 저자가 통제하는 결정과 약속에만 “우리”를 쓰고 외부 사실이나 다른 주체의 행동에는 쓰지 마라.
- T2-L-107 — `style/first-person-accountability-effect` — KB — 저자를 행위자로 밝히면 의도적인 약속과 단지 존재하는 조건을 더 쉽게 구별할 수 있다.
- T2-L-108 — `style/author-passive-commitment-tendency` — UM — 이 제안서를 작성하는 사용자는 확정되지 않은 약속을 “검토될 것이다”나 “예상된다” 같은 수동 표현 뒤에 숨기는 경향이 있다.
- T2-L-006 — `terminology/term-consistency` — PP — 같은 상호작용 개념이나 인터페이스 요소에는 제안서 전체에서 같은 용어를 사용하라.
- T2-L-021 — `terminology/abbreviation-eligibility` — PP — 반복되는 세 단어 이상의 명칭에만 약어를 사용하라.
- T2-L-082 — `terminology/abbreviation-definition` — PP — 약어를 처음 사용할 때 전체 명칭과 약어를 함께 제시하라.
- T2-L-042 — `terminology/participant-role-language` — PP — 사람을 지칭할 때는 진단명이나 결핍보다 연구에서의 역할을 앞세워라.
- T2-L-058 — `terminology/reviewer-undefined-abbreviation` — OM — 세부 분야가 다른 심사자는 처음에 정의되지 않은 약어를 문맥만으로 복원하기 어려워한다.
- T2-L-109 — `terminology/formative-summative-distinction` — PP — 설계 수정 근거를 얻는 연구에는 형성 평가라는 용어를 사용하고 최종 효과 판정과 구분하라.
- T2-L-110 — `terminology/advisor-contribution-term-check` — SM — the agent는 원리, 모형, 지침이라는 기여 명칭이 실제 산출물의 추상화 수준과 맞아야 승인할 수 있다.
- T2-L-111 — `terminology/design-principle-scope` — KB — 설계 원리는 하나의 화면 배치를 그대로 복제하는 지시가 아니라 조건과 결과의 관계를 서술한다.
- T2-L-033 — `expression/prototype-fidelity-separation` — KB — 시제품의 시각적 충실도와 기능적 충실도는 서로 다른 수준일 수 있다.
- T2-L-081 — `expression/interaction-state-change` — KB — 흐름 그림은 절차의 갈림길과 서로 다른 결과를 한 화면에서 보여줄 수 있다.
- T2-L-059 — `expression/reviewer-caption-scan` — OM — HCI 심사자는 시제품 화면과 상호작용 흐름 그림을 본문보다 먼저 훑는 경우가 많다.
- T2-L-112 — `expression/flow-diagram-overview` — KB — 독자는 행을 하나씩 읽는 표보다 흐름 그림에서 절차의 전체 갈림 구조를 더 빠르게 이해할 수 있다.
- T2-L-113 — `expression/flow-diagram-redraw-cost` — KB — 절차가 바뀔 때 갈림 구조의 흐름 그림을 다시 그리는 일은 표의 한 행을 고치는 일보다 대체로 오래 걸린다.
- T2-L-114 — `expression/advisor-visual-scan-observation` — SM — 이 advisor는 심사자가 절차 설명을 전부 읽기 전에 제안서의 핵심 시각 자료부터 살펴보는 경우를 반복해서 보았다.
- T2-L-007 — `methods/question-evidence-analysis` — PP — 각 HCI 연구 질문을 대응하는 사용자 자료와 분석 절차에 직접 연결하라.
- T2-L-014 — `style/short-sentence-rule` — PP — 한 문장에 서로 따로 검토할 수 있는 주장이 둘 이상 들어가면 짧은 문장으로 나누어라.
- T2-L-074 — `style/one-claim-sentences` — PP — 심사자가 빠르게 찾아 판단할 수 있도록 문장마다 핵심 주장 하나만 담아라.
- T2-L-016 — `methods/preregistration-change-condition` — PP — 사전등록 연구에서는 계획에서 벗어날 수 있는 조건을 밝혀라.
- T2-L-075 — `methods/preregistration-change-record` — PP — 사전등록 연구에서는 계획에서 벗어난 내용을 기록하는 방식을 밝혀라.
- T2-L-022 — `methods/exact-target` — PP — 일정, 작업량, 예산을 같은 수량에 맞춰 확인할 수 있도록 참가자 목표 수를 하나의 정확한 값으로 확정하라.
- T2-L-028 — `methods/data-collection-tool` — PP — 각 사용자 자료를 수집할 인터뷰 질문지, 기록 장치 또는 로그 도구를 구체적으로 적어라.
- T2-L-076 — `methods/data-collection-timing` — PP — 각 사용자 자료를 상호작용 전·중·후 어느 시점에 수집할지 적어라.
- T2-L-034 — `methods/exact-target-review` — SM — 이 advisor는 제안서의 여러 부분이 서로 다른 목표 수를 암시하면 일정과 예산이 일치하는지 판단할 수 없다.
- T2-L-036 — `methods/prototype-error-observation` — WM — 형성 평가용 시제품에서는 설계 선택 외에도 실행 불안정성이 독립적인 과업 실패 원인으로 존재한다.
- T2-L-086 — `methods/prototype-instability-safety` — WM — 형성 평가 중 시제품 안전 신호가 발생하면 기관의 기존 안전 절차가 계획된 자료 수집보다 우선한다.
- T2-L-060 — `methods/reviewer-answerability-trace` — OM — 심사자는 각 연구 질문에서 자료와 분석까지 이어지는 경로를 따라 답변 가능성을 판단한다.
- T2-L-069 — `methods/author-feature-contribution-assumption` — UM — 이 제안서를 작성하는 사용자는 구현한 기능 목록을 설계 기여로 바로 제시하는 경향이 있다.
- T2-L-115 — `methods/exact-target-resource-fit` — PP — 필요한 세션 수, 진행자 시간, 참가자 지급액을 서로 다른 대략치가 아니라 같은 정확한 목표 수에서 계산하라.
- T2-L-116 — `methods/exact-target-shortfall` — PP — 모집 수가 정확한 목표보다 적으면 부족분을 명시하고 영향을 받는 일정이나 산출물을 수정하라.
- T2-L-117 — `methods/author-range-deferral` — PP — 제안서의 다른 부분이 뒷받침해야 할 수량 선택을 미루기 위해 넓은 범위를 사용하지 마라.
- T2-L-118 — `style/author-em-dash-tendency` — UM — 이 제안서를 작성하는 사용자는 이미 절이 여러 개인 문장에서 em dash를 반복해서 쓰는 경향이 있다.
- T2-L-119 — `style/em-dash-authorship-suspicion` — WM — em dash가 반복되면 심사자의 관심이 제안서의 논리에서 AI가 생성한 문장인지에 대한 의심으로 옮겨갈 수 있다.
- T2-L-043 — `evaluation/primary-measure` — PP — 비교한 설계 대안을 유지·수정·폐기할 기준이 되는 대표 측정값 하나를 지정하라.
- T2-L-061 — `evaluation/panel-primary-measure` — OM — HCI 심사 패널은 선언된 대표 측정값으로 설계 대안의 판단 기준이 분명한지 확인한다.
- T2-L-120 — `evaluation/formative-diagnostic-measures` — PP — 대표 결과지표와 함께 문제가 발생한 상호작용 단계를 진단할 과정 측정값을 수집하라.
- T2-L-121 — `evaluation/design-alternative-contrast` — PP — 평가 결과를 단일 시제품의 성공 여부가 아니라 비교한 설계 대안 사이의 차이로 해석하라.
- T2-L-122 — `evaluation/conceptual-transfer-check` — PP — 도출한 설계 원리가 비교하지 않은 인접 상황에도 설명력을 갖는지 경계 사례로 점검하라.
- T2-L-123 — `evaluation/lab-behavior-boundary` — WM — 통제된 평가 환경에는 일상 사용의 시간 압박, 동료 개입, 자발적 중단 조건이 모두 재현되지 않는다.
- T2-L-008 — `ethics/burden-mitigation` — PP — 각 사용자 연구 과업에서 예상되는 참가자 부담과 그 완화책을 연결하라.
- T2-L-029 — `ethics/accessibility-accommodation` — PP — 참가자가 시제품과 연구 과업에 접근하는 데 필요한 편의를 명시하라.
- T2-L-077 — `ethics/accommodation-delivery` — PP — 접근성 편의를 사용자 연구 세션에서 제공하는 방식을 명시하라.
- T2-L-030 — `ethics/identifier-separation` — PP — 수집 직후 개인 식별자를 연구자료에서 분리하는 방법을 적어라.
- T2-L-037 — `ethics/equipment-loan` — PP — 참가자에게 필요한 장비가 없을 때 대여할 장비를 적어라.
- T2-L-078 — `ethics/equipment-return` — PP — 참가자에게 대여한 장비의 반환 절차를 적어라.
- T2-L-062 — `ethics/ethics-reviewer-mitigation` — OM — HCI 윤리 검토자는 사용자 연구 과업마다 예상 부담과 완화책이 대응하는지 확인한다.
- T2-L-124 — `ethics/formative-prototype-disclosure` — PP — 형성 평가용 시제품이 완성된 서비스가 아님을 참가자에게 설명하라.
- T2-L-125 — `ethics/iteration-burden-limit` — PP — 같은 참가자에게 반복 평가를 요청할 때 누적 과업 부담의 상한을 정하라.
- T2-L-126 — `ethics/author-benefit-emphasis` — UM — 이 제안서를 작성하는 사용자는 참가자 부담보다 시제품의 예상 이점을 먼저 설명하는 경향이 있다.
- T2-L-127 — `ethics/authority-demand-effect` — WM — 지도자나 기관 관계자가 모집을 맡는 조직에서는 모집 권한과 학업·업무 평가 권한이 같은 역할에 결합될 수 있다.
- T2-L-025 — `scope/generalization-boundary` — PP — 설계 지식이 적용되지 않는 사용자 집단과 사용 맥락을 한 문장으로 경계 지어라.
- T2-L-063 — `scope/reviewer-generalization-boundary` — OM — 심사자는 명시적으로 제외된 대상과 상황을 통해 결과의 일반화 경계를 판단한다.
- T2-L-128 — `scope/conceptual-transfer-conditions` — PP — 제안한 설계 지식이 이전될 수 있는 사용자 목표, 상호작용 조건, 기술 제약을 명시하라.
- T2-L-129 — `scope/analytic-generalization` — KB — 소규모 형성 연구도 결과를 설계 조건과 메커니즘으로 표현하면 통계적 대표성과 다른 분석적 일반화를 지원할 수 있다.
- T2-L-130 — `scope/author-population-expansion-tendency` — UM — 이 제안서를 작성하는 사용자는 접근 가능한 표본에서 얻을 설계 지식을 더 넓은 사용자 집단에 적용하려는 경향이 있다.
- T2-L-038 — `safety/escalation-order` — PP — 연구 중 심각한 불편이 보고되면 누구에게 어떤 순서로 알릴지 적어라.
- T2-L-064 — `safety/staff-escalation-reliance` — OM — 현장 담당자는 심각한 불편이 보고되면 사전에 정한 연락 순서에 의존한다.
- T2-L-131 — `safety/formative-stop-rule` — PP — 형성 평가 중 반복되는 심각한 오류가 나타나면 해당 설계 대안의 사용을 중단할 기준을 정하라.
- T2-L-132 — `safety/unsafe-iteration-exclusion` — PP — 안전 문제로 중단된 설계 대안을 수정 없이 다음 평가 반복에 포함하지 마라.
- T2-L-133 — `safety/prototype-recovery-limit` — WM — 통제 환경에서도 시제품 복구 절차가 늦으면 세션 중단 시간이 늘고 동일 과업의 자료 수집 조건이 달라진다.
- T2-L-039 — `feasibility/unverified-schedule-assumption` — PP — 아직 검증되지 않은 일정 가정은 가정이라고 표시하라.
- T2-L-087 — `feasibility/unverified-recruitment-assumption` — PP — 아직 검증되지 않은 모집 가정은 가정이라고 표시하라.
- T2-L-088 — `feasibility/unverified-technical-assumption` — PP — 아직 검증되지 않은 기술 가정은 가정이라고 표시하라.
- T2-L-044 — `feasibility/resource-traceability` — PP — 요청하는 각 자원이 시제품 제작이나 사용자 연구의 어느 단계에 쓰이는지 밝혀라.
- T2-L-065 — `feasibility/operations-staff-check` — OM — 운영 검토자는 각 절차에 배정된 인력을 보고 실행 가능성을 판단한다.
- T2-L-089 — `feasibility/operations-equipment-check` — OM — 운영 검토자는 각 절차에 배정된 장비를 보고 실행 가능성을 판단한다.
- T2-L-090 — `feasibility/operations-time-check` — OM — 운영 검토자는 각 절차에 배정된 시간을 보고 실행 가능성을 판단한다.
- T2-L-134 — `feasibility/iteration-count-resource-fit` — PP — 계획한 형성 평가 반복 횟수가 시제품 수정 시간과 모집 자원 안에서 가능한지 검증하라.
- T2-L-135 — `feasibility/minimum-testable-prototype` — PP — 주된 설계 가정을 비교하는 데 필요한 최소 기능만 형성 평가용 시제품 범위에 포함하라.
- T2-L-136 — `feasibility/advisor-iteration-evidence` — SM — the agent는 각 반복 사이에 시제품을 수정할 시간과 담당자가 배정되어야 반복 설계 계획을 실행 가능하다고 판단할 수 있다.
- T2-L-137 — `feasibility/recruitment-turnaround` — WM — 참가자 모집 지연은 형성 평가 사이의 시제품 수정 시간을 압축할 수 있다.
- T2-L-035 — `reproducibility/software-version-assessability` — OM — HCI 심사자는 평가에 사용한 시제품 버전이 드러나지 않으면 결과의 재현 가능성을 평가하기 어렵다.
- T2-L-138 — `reproducibility/design-alternative-specification` — PP — 비교한 설계 대안의 조작 요소와 고정 요소를 다른 연구자가 재구성할 수 있게 기록하라.
- T2-L-139 — `reproducibility/formative-decision-trail` — KB — 형성 평가의 결정 기록은 원자료, 해석, 설계 수정 사이의 연결을 재구성하게 한다.
- T2-L-140 — `reproducibility/advisor-iteration-trace` — SM — the agent는 각 시제품 버전이 어느 관찰을 반영했는지 추적할 수 있어야 설계 지식의 도출 과정을 검토할 수 있다.
- T2-L-023 — `budget/main-text-rationale` — PP — 제안서를 벗어나지 않고 자원 논리를 이해할 수 있도록 총액, 주요 비용 범주, 한 줄의 산정 근거를 본문에 유지하라.
- T2-L-031 — `budget/main-text-activity-link` — PP — 주요 비용을 그 비용이 가능하게 하는 활동이나 산출물 바로 옆의 본문에 배치하라.
- T2-L-079 — `budget/main-text-estimate-basis` — PP — 각 주요 비용의 수량과 단가 근거를 그 비용을 요청하는 같은 문단에 적어라.
- T2-L-066 — `budget/reviewer-inline-cost-reading` — OM — 이 advisor는 주장한 이점과 같은 페이지에서 비용을 확인할 수 없을 때 독자가 제안한 우선순위를 의심하는 모습을 보았다.
- T2-L-141 — `budget/main-text-revision-consistency` — PP — 관련 활동이 바뀔 때마다 비용 문장도 갱신해 서술과 요청 금액이 어긋나지 않게 하라.
- T2-L-142 — `budget/main-text-space-cost` — PP — 요청이 적절한지 결정하는 데 산정 근거가 중요하다면 본문 문단이 더 빽빽해지는 비용을 감수하라.
- T2-L-143 — `budget/author-detached-table-omission` — UM — 이 제안서를 작성하는 사용자는 주요 금액이 활동 옆에도 반복되지 않으면 작업 계획을 고치고도 떨어져 있는 예산표 갱신을 잊는 경향이 있다.
- T2-L-046 — `compensation/base-hourly-rate` — PP — 사용자 연구 보상 예산은 세션 시간과 준비 부담을 합친 예상 참여 부담을 기준으로 산정하라.
- T2-L-047 — `compensation/modality-burden` — PP — 대면 사용자 연구에서 요구하는 필수 이동 시간도 보상하라.
- T2-L-053 — `compensation/participation-time` — PP — 연구 방식과 관계없이 세션에 실제로 참여한 시간을 보상하라.
- T2-L-048 — `compensation/payment-method` — PP — 대면 연구에서는 현금 지급을 사용할 수 있는 보상 방식으로 남겨 두어라.
- T2-L-049 — `compensation/payment-method-finality` — PP — 예산의 동등성이 설명되었다면 제안서 단계에서 지급 방식을 확정하도록 요구하지 마라.
- T2-L-050 — `compensation/modality-rate` — PP — 과업 부담이 같다면 대면 연구와 원격 연구에 같은 기본 시급을 적용하라.
- T2-L-067 — `compensation/participant-fairness` — OM — 참가자는 세션 시간과 필수 이동·준비 시간을 합친 부담으로 보상의 공정성을 판단한다.
- T2-L-144 — `compensation/repeated-session-burden` — PP — 같은 참가자가 여러 형성 평가 세션에 참여하면 반복 일정 조정과 재방문의 부담을 보상에 반영하라.
- T2-L-145 — `compensation/partial-session-payment` — PP — 시제품 오류로 세션을 조기 종료해도 참가자가 이미 들인 시간은 보상하라.
- T2-L-146 — `compensation/author-session-only-estimate` — UM — 이 제안서를 작성하는 사용자는 반복 연구의 보상을 계산할 때 세션 사이의 준비 부담을 빼는 경향이 있다.
- T2-L-032 — `review/substantive-pass` — PP — 제출 전 한 차례는 사용자 문제, 설계 개입, 평가 논리의 타당성만 따로 검토하라.
- T2-L-040 — `review/question-prototype-consistency` — PP — 연구 질문과 시제품의 핵심 기능이 서로 일치하는지 대조하라.
- T2-L-091 — `review/task-measure-consistency` — PP — 평가 과업과 대표 측정값이 서로 일치하는지 대조하라.
- T2-L-092 — `review/evidence-decision-consistency` — PP — 수집할 근거와 바꾸려는 설계·운영 결정이 서로 일치하는지 대조하라.
- T2-L-045 — `review/logic-consistency` — PP — 사용자 문제, 설계 개입, 사용자 연구, 기대 기여가 같은 논리적 흐름을 이루는지 마지막에 점검하라.
- T2-L-068 — `review/reviewer-question-prototype-confidence` — OM — HCI 심사자는 연구 질문과 시제품 기능이 연결되지 않으면 설계 개입의 타당성을 낮게 본다.
- T2-L-093 — `review/reviewer-task-measure-confidence` — OM — HCI 심사자는 평가 과업이 대표 측정값을 만들지 못하면 평가 계획의 타당성을 낮게 본다.
- T2-L-094 — `review/reviewer-evidence-decision-confidence` — OM — HCI 심사자는 수집할 근거가 설계·운영 결정을 바꾸지 못하면 기여의 실용성을 낮게 본다.
- T2-L-147 — `review/formative-decision-trace` — PP — 각 연구 질문, 형성 평가 자료, 설계 수정 판단이 끊김 없이 이어지는지 마지막에 대조하라.
- T2-L-148 — `review/conceptual-transfer-boundary` — PP — 제안한 설계 원리의 적용 조건과 실패할 경계 사례가 함께 제시되었는지 검토하라.
- T2-L-149 — `review/advisor-contribution-separation` — SM — the agent는 시제품 결과와 그 결과에서 도출한 이전 가능한 설계 지식이 분리되어야 기여를 검토할 수 있다.
- T2-L-150 — `review/reviewer-lab-transfer-risk` — WM — 통제된 형성 평가의 관찰 범위에는 실제 사용 맥락의 장기 적응과 운영 변화가 포함되지 않는다.
