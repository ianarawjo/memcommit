# advisor2 메모리 후보

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

- T2-R-001 — `structure/problem` — PP — 도입부 세 문장 안에 실제 사용 환경에서 아직 풀리지 않은 상호작용 문제를 제시하라.
- T2-R-070 — `structure/problem-urgency` — PP — 도입부 세 문장 안에 그 상호작용 문제가 현재 사용자나 운영에 주는 부담을 제시하라.
- T2-R-002 — `structure/research-question-position` — PP — 주된 HCI 연구 질문에 사용자, 운영 이해관계자, 실제 사용 환경을 명시하라.
- T2-R-011 — `structure/interaction-step-visual` — PP — 낯선 상호작용 절차를 제안할 때는 단계 순서를 한 장의 순서표로 요약하라.
- T2-R-071 — `structure/interaction-transition-visual` — PP — 낯선 상호작용 절차의 단계 사이 전환 조건을 순서표에 표시하라.
- T2-R-015 — `structure/masters-timeline-phases` — PP — 석사 연구 일정을 현장 이해, 시스템 구현, 사용자 연구, 분석의 단계별 이정표로 제시하라.
- T2-R-072 — `structure/masters-timeline-deliverables` — PP — 석사 연구의 각 이정표에 다음 단계 진입을 판단할 산출물을 연결하라.
- T2-R-017 — `structure/gap-contribution-link` — PP — 실제 사용 맥락의 공백과 제안한 설계·운영 기여를 한 흐름 안에서 직접 연결하라.
- T2-R-018 — `structure/two-page-heading-ban` — PP — 제출 템플릿이 정해진 소제목만 허용하면 추가 소제목을 만들지 마라.
- T2-R-083 — `structure/two-page-continuous-argument` — PP — 정해진 소제목 안에서는 사용자 문제, 설계 개입, 평가 논리를 하나의 연속된 흐름으로 연결하라.
- T2-R-024 — `structure/preliminary-result-placement` — PP — 현장 관찰이나 기술 검증 결과는 실행 가능성 주장을 뒷받침하는 문장 가까이에 배치하라.
- T2-R-054 — `structure/reviewer-opening-problem` — OM — HCI 심사자는 도입부의 첫 세 문장에서 사용자와 실제 사용 환경의 문제를 찾아 초기 논점을 형성한다.
- T2-R-080 — `structure/reviewer-opening-urgency` — OM — HCI 심사자는 도입부의 첫 세 문장에서 그 문제가 현재 사용자나 운영에 주는 부담을 판단한다.
- T2-R-003 — `emphasis/contribution-count` — PP — 독자가 기억해야 할 주된 HCI 기여는 두 가지를 넘기지 마라.
- T2-R-051 — `emphasis/contribution-naming` — PP — 각 설계 또는 운영 기여를 이름 붙인 한 문장으로 제시하라.
- T2-R-013 — `emphasis/recruitment-primary-constraint` — PP — 조직 구성원을 모집하는 연구에서는 업무 흐름 제약을 강조하라.
- T2-R-073 — `emphasis/recruitment-secondary-constraint` — PP — 조직 구성원을 모집하는 연구에서는 관리자 승인 제약을 강조하라.
- T2-R-026 — `emphasis/contribution-type` — PP — 제안서의 주된 HCI 디자인 기여는 개념적 모형이 아니라 실무자가 적용할 수 있는 설계 지침으로 제시하라.
- T2-R-055 — `emphasis/reviewer-contribution-capacity` — OM — HCI 심사자는 이름 붙은 설계·운영 기여가 두 개를 넘으면 주된 기여를 파악하기 어려워한다.
- T2-R-004 — `claim-evidence/evidence-adjacency` — PP — 사용자 요구나 현장 효과에 관한 주장 바로 옆에 관찰 근거나 출처를 두어라.
- T2-R-005 — `claim-evidence/observation-prediction-status` — PP — 현장에서 이미 확인한 사실과 사용자 연구가 검토할 예상을 문장 수준에서 구별하라.
- T2-R-009 — `claim-evidence/study-directionality` — PP — 제안서의 주된 연구 질문을 방향성 가설이 없는 탐색적 질적 질문으로 표현하라.
- T2-R-010 — `claim-evidence/causal-language` — PP — 설계가 인과 추론을 뒷받침하지 않으면 인과를 입증한다는 동사를 사용하지 마라.
- T2-R-012 — `claim-evidence/source-priority` — PP — 빠르게 바뀌는 HCI 주제에서는 최신 시스템과 현장 연구를 우선 인용하라.
- T2-R-027 — `claim-evidence/design-rationale` — PP — 각 설계 선택이 해결하려는 사용자나 운영 이해관계자의 필요를 설명하라.
- T2-R-041 — `claim-evidence/direct-evidence` — PP — 중요한 결론에는 그 결론을 직접 검토한 가장 가까운 근거를 우선 인용하라.
- T2-R-056 — `claim-evidence/reviewer-evidence-order` — OM — 심사자는 중요한 결론과 가장 가까운 곳에 놓인 직접 근거를 먼저 확인한다.
- T2-R-019 — `style/research-team-voice` — PP — 반복 가능한 사용자 연구 절차는 사람보다 과업과 단계가 먼저 나오도록 써라.
- T2-R-020 — `style/confirmed-procedure-status` — PP — 실제 사용 환경에서 확인한 시스템 동작은 관찰된 상태로 써라.
- T2-R-052 — `style/unconfirmed-procedure-status` — PP — 아직 현장에서 확인하지 않은 시스템 동작은 조건부 계획으로 써라.
- T2-R-057 — `style/reviewer-voice-interpretation` — OM — HCI 심사자는 과업과 단계가 먼저 나오는 문장에서 반복 가능한 사용자 연구 절차를 쉽게 식별한다.
- T2-R-006 — `terminology/term-consistency` — PP — 같은 사용자 역할, 시스템 기능, 운영 단계를 가리키는 명칭은 중간에 바꾸지 마라.
- T2-R-021 — `terminology/abbreviation-eligibility` — PP — 두 쪽짜리 제안서에서는 반복되는 긴 명칭에만 약어를 사용하라.
- T2-R-082 — `terminology/abbreviation-definition` — PP — 약어를 처음 사용할 때 전체 명칭과 약어를 함께 제시하라.
- T2-R-042 — `terminology/participant-role-language` — PP — 참가자는 상태가 아니라 연구에서 수행하는 역할을 중심으로 지칭하라.
- T2-R-058 — `terminology/reviewer-undefined-abbreviation` — OM — 세부 분야가 다른 심사자는 처음에 정의되지 않은 약어를 문맥만으로 복원하기 어려워한다.
- T2-R-033 — `expression/prototype-fidelity-separation` — KB — 시제품의 시각적 충실도와 실제 데이터·서비스 연결 수준은 서로 다를 수 있다.
- T2-R-081 — `expression/interaction-state-change` — KB — 서비스 흐름 그림은 개별 화면만으로 드러나지 않는 사람·시스템 간 전환을 나타낸다.
- T2-R-059 — `expression/reviewer-caption-scan` — OM — HCI 심사자는 시스템 구조와 서비스 흐름 그림을 본문보다 먼저 훑는 경우가 많다.
- T2-R-007 — `methods/question-evidence-analysis` — PP — 모든 HCI 연구 질문에 대응하는 현장·사용자 자료원과 분석 절차를 지정하라.
- T2-R-014 — `methods/primary-evaluation-setting` — PP — 제안서의 주 평가를 실제 사용 환경의 현장 배포 연구로 설계하라.
- T2-R-074 — `methods/lab-evaluation-scope` — PP — 주된 기여가 실제 운영 결정을 바꾸는 것이라면 통제된 실험실 평가만으로 판단하지 마라.
- T2-R-016 — `methods/preregistration-change-condition` — PP — 사전등록 연구에서는 계획 변경의 판단 기준을 밝혀라.
- T2-R-075 — `methods/preregistration-change-record` — PP — 사전등록 연구에서는 계획 변경의 기록 위치를 밝혀라.
- T2-R-022 — `methods/sample-size-form` — PP — 모집 가능성의 근거에 따라 목표 참가자 수를 하나의 수치나 정당화된 범위로 제시하라.
- T2-R-028 — `methods/data-collection-tool` — PP — 각 현장·사용자 자료를 수집할 관찰 기록, 시스템 로그 또는 인터뷰 도구를 구체적으로 적어라.
- T2-R-076 — `methods/data-collection-timing` — PP — 각 현장·사용자 자료를 배포 전·중·후 어느 시점에 수집할지 적어라.
- T2-R-034 — `methods/recruitment-funnel-visibility` — SM — the agent는 연락 대상에서 최종 참여자까지의 예상 이탈 단계가 없으면 모집 계획의 현실성을 검토할 수 없다.
- T2-R-036 — `methods/deployment-failure-observation` — WM — 현장 배포에서는 설계 선택 외에도 네트워크와 서비스 불안정성이 독립적인 과업 실패 원인으로 존재한다.
- T2-R-084 — `methods/deployment-safety-signal` — WM — 현장 시스템에서 안전 신호가 발생하면 해당 기관의 기존 안전 절차가 연구 일정과 자료 수집 계획보다 우선한다.
- T2-R-060 — `methods/reviewer-answerability-trace` — OM — 심사자는 각 연구 질문에서 자료원과 분석 절차까지 이어지는 경로를 따라 답변 가능성을 판단한다.
- T2-R-069 — `methods/author-feature-contribution-assumption` — UM — 이 제안서를 작성하는 사용자는 구현한 기능 목록을 설계 기여로 바로 제시하는 경향이 있다.
- T2-R-043 — `evaluation/primary-measure` — PP — 배포한 설계를 유지·수정·중단할 운영 결정을 좌우할 대표 측정값 하나를 지정하라.
- T2-R-061 — `evaluation/panel-primary-measure` — OM — HCI 심사 패널은 선언된 대표 측정값으로 운영 결정을 내릴 수 있는지 확인한다.
- T2-R-008 — `ethics/burden-mitigation` — PP — 각 현장 사용자 연구 과업에서 예상되는 참가자 부담과 그 완화책을 연결하라.
- T2-R-029 — `ethics/accessibility-accommodation` — PP — 참가자가 현장 시스템과 연구 과업에 접근하는 데 필요한 편의를 명시하라.
- T2-R-077 — `ethics/accommodation-delivery` — PP — 접근성 편의를 현장 사용자 연구에서 제공하는 방식을 명시하라.
- T2-R-030 — `ethics/identifier-separation` — PP — 수집 직후 개인 식별자를 연구자료에서 분리하는 방법을 적어라.
- T2-R-037 — `ethics/equipment-loan` — PP — 참가자에게 필요한 장비가 없을 때 대여할 장비를 적어라.
- T2-R-078 — `ethics/equipment-return` — PP — 참가자에게 대여한 장비의 반환 절차를 적어라.
- T2-R-062 — `ethics/ethics-reviewer-mitigation` — OM — HCI 윤리 검토자는 현장 사용자 연구 과업마다 예상 부담과 완화책이 대응하는지 확인한다.
- T2-R-025 — `scope/generalization-boundary` — PP — 설계 지식을 적용하려는 사용자 집단과 실제 사용 환경을 한 문장으로 특정하라.
- T2-R-063 — `scope/reviewer-generalization-boundary` — OM — 심사자는 명시된 대상 집단과 환경을 통해 결과의 일반화 경계를 판단한다.
- T2-R-038 — `safety/escalation-order` — PP — 연구 중 심각한 불편이 보고되면 누구에게 어떤 순서로 알릴지 적어라.
- T2-R-064 — `safety/staff-escalation-reliance` — OM — 현장 담당자는 심각한 불편이 보고되면 사전에 정한 연락 순서에 의존한다.
- T2-R-039 — `feasibility/unverified-schedule-assumption` — PP — 아직 검증되지 않은 일정 가정은 가정이라고 표시하라.
- T2-R-085 — `feasibility/unverified-recruitment-assumption` — PP — 아직 검증되지 않은 모집 가정은 가정이라고 표시하라.
- T2-R-086 — `feasibility/unverified-technical-assumption` — PP — 아직 검증되지 않은 기술 가정은 가정이라고 표시하라.
- T2-R-044 — `feasibility/resource-traceability` — PP — 각 핵심 시제품 기능과 현장 연구 절차에 필요한 자원을 역으로 확인하라.
- T2-R-065 — `feasibility/operations-staff-check` — OM — 운영 검토자는 각 절차에 필요한 사람을 보고 실행 가능성을 판단한다.
- T2-R-087 — `feasibility/operations-equipment-check` — OM — 운영 검토자는 각 절차에 필요한 장비를 보고 실행 가능성을 판단한다.
- T2-R-088 — `feasibility/operations-time-check` — OM — 운영 검토자는 각 절차에 필요한 시간을 보고 실행 가능성을 판단한다.
- T2-R-035 — `reproducibility/software-version-assessability` — OM — HCI 심사자는 현장 배포에 사용한 시스템 버전이 드러나지 않으면 결과의 재현 가능성을 평가하기 어렵다.
- T2-R-023 — `budget/body-detail-placement` — PP — 본문에는 현장 HCI 연구 단계와 주요 비용 범주의 대응만 요약하라.
- T2-R-031 — `budget/personnel-work-time` — PP — 인건비에는 현장 배포와 사용자 연구 역할별 작업 시간을 적어라.
- T2-R-079 — `budget/personnel-rate-basis` — PP — 인건비에는 현장 배포와 사용자 연구 역할별 단가의 산정 근거를 붙여라.
- T2-R-066 — `budget/finance-activity-trace` — OM — 재무 검토자는 전체 예산과 세부 비용이 어떤 HCI 연구 단계에 연결되는지 추적해 예산의 타당성을 판단한다.
- T2-R-046 — `compensation/base-hourly-rate` — PP — 사용자 연구 보상 예산은 세션 시간과 필수 기술·이동 준비를 합친 예상 참여 부담을 기준으로 산정하라.
- T2-R-047 — `compensation/modality-burden` — PP — 연구를 중도 종료한 참가자에게도 실제 참여 시간을 보상하라.
- T2-R-053 — `compensation/participation-time` — PP — 연구 방식과 관계없이 세션에 실제로 참여한 시간을 보상하라.
- T2-R-048 — `compensation/payment-method` — PP — 원격 연구에서 전자송금을 사용할 수 없는 참가자에게 같은 가치의 상품권 지급을 허용하라.
- T2-R-049 — `compensation/payment-method-finality` — PP — 지급 방식이 미정이라고 확인되었다면 이를 제안서 단계의 결함으로 취급하지 마라.
- T2-R-050 — `compensation/modality-rate` — PP — 이동이나 기술 준비로 참여 부담이 달라지면 대면 연구와 원격 연구의 보상액을 다르게 산정하는 것을 허용하라.
- T2-R-067 — `compensation/participant-fairness` — OM — 참가자는 세션 시간과 필수 기술·이동 준비를 합친 부담으로 보상의 공정성을 판단한다.
- T2-R-032 — `review/substantive-pass` — PP — 제출 전 한 차례는 사용자 문제, 시스템 개입, 현장 평가 논리의 타당성만 따로 검토하라.
- T2-R-040 — `review/question-prototype-consistency` — PP — 연구 질문과 시스템의 핵심 기능이 서로 일치하는지 대조하라.
- T2-R-089 — `review/task-measure-consistency` — PP — 현장 과업과 대표 측정값이 서로 일치하는지 대조하라.
- T2-R-090 — `review/evidence-decision-consistency` — PP — 수집할 근거와 바꾸려는 설계·운영 결정이 서로 일치하는지 대조하라.
- T2-R-045 — `review/logic-consistency` — PP — 사용자 문제, 시스템 개입, 현장 평가, 기대 기여가 같은 논리적 흐름을 이루는지 최종 확인하라.
- T2-R-068 — `review/reviewer-question-prototype-confidence` — OM — HCI 심사자는 연구 질문과 시스템 기능이 연결되지 않으면 설계 개입의 타당성을 낮게 본다.
- T2-R-091 — `review/reviewer-task-measure-confidence` — OM — HCI 심사자는 현장 과업이 대표 측정값을 만들지 못하면 평가 계획의 타당성을 낮게 본다.
- T2-R-092 — `review/reviewer-evidence-decision-confidence` — OM — HCI 심사자는 수집할 근거가 설계·운영 결정을 바꾸지 못하면 기여의 실용성을 낮게 본다.
- T2-R-093 — `structure/decision-chain` — PP — 사용자 문제에서 현장 근거, 설계 개입, 평가 결과, 운영 결정까지의 경로를 끊김 없이 제시하라.
- T2-R-094 — `structure/deployment-handoff` — PP — 연구 단계가 끝난 뒤 시스템을 누가 어떤 조건에서 이어받는지 연구 흐름에 포함하라.
- T2-R-095 — `structure/field-decision-argument` — KB — 현장 배포 연구의 논리는 설계가 작동하는지뿐 아니라 그 결과가 어떤 운영 결정을 뒷받침하는지까지 연결한다.
- T2-R-096 — `structure/advisor-operational-owner-visibility` — SM — the agent는 배포 이후 운영 주체가 드러나지 않으면 제안한 개입의 지속 가능성을 검토할 수 없다.
- T2-R-097 — `emphasis/primary-deployment-decision` — PP — 평가 결과로 바꾸려는 가장 중요한 현장 운영 결정 하나를 중심 주장으로 강조하라.
- T2-R-098 — `emphasis/optional-feature-boundary` — PP — 주된 현장 문제를 검토하는 데 필요하지 않은 시제품 기능은 부차적 범위로 명시하라.
- T2-R-099 — `emphasis/author-novelty-bias` — UM — 이 제안서를 작성하는 사용자는 운영 적합성보다 새로운 상호작용 기능을 먼저 강조하는 경향이 있다.
- T2-R-100 — `claim-evidence/workaround-evidence` — PP — 기존 도구를 우회해 과업을 끝낸 현장 사례를 설계 필요성의 근거로 연결하라.
- T2-R-101 — `claim-evidence/stakeholder-report-observation` — PP — 운영 이해관계자가 보고한 문제와 연구자가 직접 관찰한 문제를 서로 다른 근거로 표시하라.
- T2-R-102 — `claim-evidence/breakdown-log-value` — KB — 현장 장애 기록은 시스템 실패와 사용자의 적응 행동이 발생한 시점과 조건을 함께 보여줄 수 있다.
- T2-R-103 — `claim-evidence/routine-adaptation` — WM — 새 시스템을 도입하는 현장에서는 공식 절차와 기존 수동 절차가 한동안 병행되어 단일 설계 효과를 분리하기 어렵다.
- T2-R-104 — `style/field-actor-action` — PP — 현장 상호작용을 설명할 때 각 단계의 행위자, 행동, 대상 시스템을 구체적으로 써라.
- T2-R-105 — `style/advisor-passive-responsibility` — SM — the agent는 수동태로만 적힌 현장 절차에서 오류 대응 책임자를 판별할 수 없다.
- T2-R-106 — `style/partner-provisional-language` — WM — 현장 파트너가 아직 승인하지 않은 조건부 기능은 운영 절차와 사용자 역할이 확정되지 않아 예상 행동 변화의 메커니즘도 잠정적이다.
- T2-R-107 — `terminology/operational-role-authority` — PP — 운영 역할을 처음 제시할 때 그 역할이 내릴 수 있는 결정과 수행할 수 있는 조치를 함께 정의하라.
- T2-R-108 — `terminology/title-authority-variance` — KB — 같은 직함을 쓰는 사람이라도 배포 현장에 따라 시스템 변경 권한과 자료 접근 권한이 다를 수 있다.
- T2-R-109 — `terminology/author-user-bucket` — UM — 이 제안서를 작성하는 사용자는 서로 다른 현장 역할을 모두 사용자라는 한 명칭으로 묶는 경향이 있다.
- T2-R-110 — `expression/intervention-baseline-figure` — PP — 서비스 흐름 그림에는 설계가 바꾸는 단계와 그대로 유지하는 단계를 구별해 표시하라.
- T2-R-111 — `expression/walkthrough-screen-difference` — KB — 화면 이미지는 인터페이스 상태를 보여주지만 현장 워크스루는 사람과 시스템 사이의 실제 인계 과정을 보여준다.
- T2-R-112 — `expression/advisor-screen-decision-gap` — SM — the agent는 화면 이미지의 나열만으로 현장 운영 결정이 어떻게 달라지는지 추론할 수 없다.
- T2-R-113 — `methods/pilot-main-transition` — PP — 파일럿 배포에서 본 배포로 넘어갈 기능 안정성, 운영 준비도, 안전 조건을 미리 정하라.
- T2-R-114 — `methods/shadow-deployment-fallback` — PP — 실제 업무를 방해할 위험이 있으면 기존 절차를 유지한 채 결과를 비교하는 섀도 배포 단계를 설계하라.
- T2-R-115 — `methods/time-coverage-sampling` — PP — 업무량과 참여자 구성이 달라지는 시간대를 포함하도록 현장 관찰 일정을 배치하라.
- T2-R-116 — `methods/operator-workaround-capture` — PP — 운영자가 시스템을 우회하거나 수동으로 복구한 행동을 기록할 자료 수집 방법을 지정하라.
- T2-R-117 — `methods/interview-observation-complement` — KB — 인터뷰는 참여자가 인식한 이유를 보여주고 현장 관찰은 실제로 수행된 절차와 우회 행동을 보여준다.
- T2-R-118 — `methods/author-convenience-recruitment` — UM — 이 제안서를 작성하는 사용자는 운영 결정과 관련된 역할보다 쉽게 모집할 수 있는 참가자를 먼저 선택하는 경향이 있다.
- T2-R-119 — `methods/organizational-rhythm` — WM — 현장의 업무량, 담당자 구성, 예외 처리 방식은 요일과 시간대에 따라 달라질 수 있다.
- T2-R-120 — `evaluation/decision-threshold` — PP — 대표 측정값이 어느 수준에 도달하면 설계를 유지, 수정, 중단할지 판단 기준을 정하라.
- T2-R-121 — `evaluation/work-redistribution` — PP — 설계가 한 역할의 부담을 줄이는 대신 다른 역할에 새 업무를 만드는지 평가하라.
- T2-R-122 — `evaluation/acceptability-usability-separation` — PP — 사용 가능성과 조직이 실제로 도입할 의향을 서로 다른 평가 결과로 구분하라.
- T2-R-123 — `evaluation/implementation-fidelity` — KB — 구현 충실도는 계획한 기능과 운영 절차가 현장에서 의도한 방식으로 제공되었는지를 나타낸다.
- T2-R-124 — `evaluation/novelty-decay` — WM — 초기 평가와 장기 운영은 시스템 노출 기간과 반복 사용 횟수가 달라 같은 측정 조건이 아니다.
- T2-R-125 — `ethics/safe-fallback` — PP — 연구 참여를 중단해도 참가자가 기존 업무 절차로 안전하게 돌아갈 수 있는 방법을 마련하라.
- T2-R-126 — `ethics/refusal-nonpenalty` — PP — 조직 구성원이 연구 참여를 거절해도 업무 배정이나 평가에서 불이익을 받지 않는다고 명시하라.
- T2-R-127 — `ethics/advisor-fallback-risk` — SM — the agent는 현장 과업의 안전한 대체 절차가 없으면 참여 중단 위험을 충분히 검토할 수 없다.
- T2-R-128 — `ethics/author-short-session-burden` — UM — 이 제안서를 작성하는 사용자는 세션이 짧으면 업무 중단과 관리자 노출에서 생기는 부담도 작다고 가정하는 경향이 있다.
- T2-R-129 — `scope/transfer-conditions` — PP — 설계 지침을 다른 현장에 적용하려면 같아야 하는 업무 흐름, 기술 기반, 운영 권한 조건을 명시하라.
- T2-R-130 — `scope/transfer-boundary-components` — KB — 현장 설계 지식의 전이 가능성은 사용자 특성뿐 아니라 업무 흐름과 기술·조직 기반에도 좌우된다.
- T2-R-131 — `scope/author-overgeneralization` — UM — 이 제안서를 작성하는 사용자는 한 배포 현장에서 확인한 결과를 유사한 모든 조직에 적용하려는 경향이 있다.
- T2-R-132 — `safety/stop-rule` — PP — 참가자 피해, 운영 장애, 데이터 이상이 어느 수준이면 배포와 자료 수집을 중단할지 정하라.
- T2-R-133 — `safety/restoration-plan` — PP — 현장 배포를 중단한 뒤 기존 시스템과 업무 상태를 복구할 절차를 마련하라.
- T2-R-134 — `safety/advisor-recovery-authority` — SM — the agent는 복구 명령을 내릴 권한과 실행 책임자가 없으면 중단 계획의 실행 가능성을 판단할 수 없다.
- T2-R-135 — `safety/blame-reporting` — WM — 오류 보고가 개인 성과평가와 연결된 조직에서는 안전 신호 기록이 연구용 결정 기록과 분리되어 같은 사건의 추적 경로가 끊길 수 있다.
- T2-R-136 — `feasibility/partner-commitment` — PP — 모집, 설치, 운영 지원에 필요한 현장 파트너의 약속과 확인 상태를 각각 적어라.
- T2-R-137 — `feasibility/maintenance-owner` — PP — 배포 기간 중 소프트웨어 업데이트, 장비 점검, 사용자 지원을 맡을 책임자를 지정하라.
- T2-R-138 — `feasibility/advisor-hidden-dependencies` — SM — the agent는 외부 서비스와 현장 인력 의존성이 드러나지 않으면 배포 준비도를 검토할 수 없다.
- T2-R-139 — `feasibility/site-schedule-change` — WM — 현장 일정과 담당 인력은 연구자가 통제할 수 없는 운영 사정으로 바뀔 수 있다.
- T2-R-140 — `reproducibility/config-change-log` — PP — 배포 중 바뀐 시스템 설정, 현장 절차, 자료 수집 도구를 시점과 이유와 함께 기록하라.
- T2-R-141 — `reproducibility/deployment-provenance` — KB — 배포 버전과 설정 변경의 이력은 서로 다른 현장에서 나온 결과를 해석하는 데 필요한 근거다.
- T2-R-142 — `budget/onsite-repair-contingency` — PP — 현장 장비 교체, 긴급 이동, 기술 지원에 쓸 배포 예비비를 별도 비용으로 산정하라.
- T2-R-143 — `budget/operator-onboarding-cost` — PP — 현장 운영자 교육과 초기 지원에 필요한 인력 시간과 자료 제작비를 예산에 반영하라.
- T2-R-144 — `budget/author-postdeployment-support` — UM — 이 제안서를 작성하는 사용자는 설치 비용은 계산하지만 배포 후 지원과 유지보수 비용은 빠뜨리는 경향이 있다.
- T2-R-145 — `compensation/longitudinal-reporting-burden` — PP — 일지 작성과 반복 보고가 필요한 종단 연구에서는 세션 밖 기록 시간도 보상에 포함하라.
- T2-R-146 — `compensation/staff-labor-separation` — PP — 연구 참가 보상과 현장 직원이 업무로 수행하는 설치·운영 지원의 인건비를 구분하라.
- T2-R-147 — `compensation/author-unpaid-preparation` — UM — 이 제안서를 작성하는 사용자는 세션 시간은 계산하지만 참가자의 사전 설정과 후속 보고 시간을 빠뜨리는 경향이 있다.
- T2-R-148 — `review/failure-mode-walkthrough` — PP — 제출 전에 현장 담당자와 함께 설치 실패, 운영 중단, 복구 상황을 순서대로 점검하라.
- T2-R-149 — `review/contribution-decision-test` — PP — 각 제안 기여가 실제로 어떤 설계 또는 운영 결정을 바꿀 수 있는지 한 문장으로 검증하라.
- T2-R-150 — `review/advisor-placeholder-visibility` — SM — the agent는 미확정 현장 파트너와 장비가 확정된 것처럼 쓰이면 남은 실행 위험을 구별할 수 없다.
