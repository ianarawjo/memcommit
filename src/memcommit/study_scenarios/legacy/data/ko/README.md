# 사용자 연구용 한국어 Memory fixture

## 상태

이 디렉터리는 세 과업에 사용할 **한국어 설계 원본**이다. 아직 이 문서에서
실제 Context나 Memory를 설치하지 않으며, 내용 검토와 영어 번역을 마친 뒤
별도의 설치 단계에서 저장한다. 모든 기관, 인물, 공사, 정책, 일정과 개인사는
사용자 연구를 위한 합성 또는 비식별 의미 재구성이다.

## 수량 계약

| 과업 | 일반 열람 자료 | 질의 전용 자료 | 합계 |
| --- | ---: | ---: | ---: |
| Task 1 | `description` 2 + `construction-updates` 75 + `campus-wiki` 300 = 377 | `campus-wiki · construction-details` 78 | 455 |
| Task 2 | `description` 2 + `advisor1` 150 + `advisor2` 150 = 302 | `proposal-submission-guidelines` 75 | 377 |
| Task 3 | `description` 2 + `local/personal-memory` 300 + `local/guardrails` 75 + 공개 의료 가이던스 25 = 402 | `remote/government/healthcare-agent/info-request/questions-and-answers` 75 | 477 |
| 전체 | 1,081 | 228 | 1,309 |

`일반 열람`과 `질의 전용`은 participant 상호작용을 뜻한다. 물리적으로는
1,309개 모두 ordinary Memory이며, task-local 자료는 task Profile에, grant
자료는 task별 authority Profile에 저장한다. 생성된 연구 패키지에서는 특수
source file이 아니라 `QUERY` grant가 질의 전용 view를 만든다.

개수는 문장을 기계적으로 잘게 자르기 위한 목표가 아니다. 각 Memory 후보는
독립적으로 검색·검증·수정·승인할 수 있는 명제나 실행 규칙 하나를 담는다.
시간, 위치, 대상, 예외 또는 결과가 서로 따로 바뀔 수 있으면 각각의 Memory로
분리한다. 조건·행동·예외가 하나의 결정 규칙을 정의할 때만 한 Memory 안에
함께 둘 수 있다.

## 공통 구조

### Memory 위치와 원자성

`Memory 위치`는 `dataset/directory/leaf` 형태의 계층형 locator sidecar다.
주제 분류는 이 경로의 중간 directory가 담당하므로 별도의 `분류` 열을 두지
않는다. 목적 코드는 위치와 독립된 축이다. 같은 directory 안에도 서로 다른
목적의 Memory가 있을 수 있고, 같은 목적이 여러 directory에 나타날 수 있다.

복합 후보를 분리할 때 기존 fixture ID와 출처 관계는 추적 가능하게 남기되,
분리된 각 자식은 새 Memory 후보로 다룬다. 같은 조건·기간·대상을 공유해도
상태, 행동, 제한, 예외 또는 열거된 항목을 따로 검증할 수 있으면 엄격히
분리하고, 각 자식이 단독으로 이해되도록 필요한 조건을 반복한다. 예를 들어
정문 개방시간 변경, 기존 `accessible ramp` 폐쇄, 임시 `accessible route`
제공은 각각 독립적으로 변경될 수 있으므로 세 Memory다.

### 여섯 목적 코드

| 코드 | 이름 | 판단 기준 |
| --- | --- | --- |
| `KB` | Knowledge Base | 기관·대상·시설·규칙·상태·기록처럼 직접 조회하고 확인하는 사실 |
| `PP` | Procedural Policy | 에이전트가 수행하거나 피해야 할 행동, 절차, 금지, 확인 규칙 |
| `SM` | Self Model | 로컬 에이전트 자신의 역할, 능력, 관측·추론 한계, 권한과 작업 가정 |
| `UM` | User Model | 현재 사용자의 기대, 선호, 익숙함, 불편, 혼란과 의사결정 경향 |
| `WM` | World Model | 외부 환경이 작동하고 변하는 구조, 의존관계, 제약과 예상 영향 |
| `OM` | Other Model | 현재 사용자가 아닌 관련 행위자의 기대, 선호, 판단과 예상 반응 |

모델 목적은 문장에 사람이나 에이전트가 등장하는지만 보고 정하지 않는다.
“보조견은 일반 출입구를 이용할 수 있다”처럼 확인 가능한 규칙은 `KB`이고,
“대부분의 사용자는 재학생이다”처럼 사용자 집단의 구성에 관한 평면 사실도
그 자체로는 `KB`다. 반대로 모바일 학생증만 들고 다니는 학생이 실물 카드
요구를 예상하지 못해 잘못된 출입구를 선택하거나 인증 수단을 다시 준비할
가능성은 `UM`이다. 제삼자가 등장해도 시설 상태나 운영 사실만 말하면 `KB`이며,
그 사람이 무엇을 기대·선호·판단하고 어떻게 행동할지를 모델링할 때만 `OM`이다.

로컬 안내 에이전트가 수행하는 역할이나 실시간으로 확인할 수 없는 현장 상태는
`OM`이 아니라 `SM`이다. `OM` 수를 채우기 위해 현장 안내 직원을 새로 상정하지
않고, 외부 견학 인솔자·위탁 운영업체·배송업체·이동 지원 동행인처럼 과업과
실제로 관련된 별도 행위자만 모델링한다. `UM`과 `OM`은 모든 반응을
`당황`·`불편`으로 반복하지 않고, 익숙한 동선을 다시 선택하거나 정보를 재확인하고
계획을 바꾸는 행동까지 다양하게 기록한다.

`SM`도 에이전트에 관한 모든 문장을 모으는 범주가 아니다. 출입 안내
에이전트가 문의에 답한다는 일반 설명은 역할을 구체화하지 않으면 평면 사실에
가깝다. 반면 에이전트가 문 잠금 상태를 실시간으로 관측할 수 없거나, 현재
자료만으로 예약 완료를 보증할 수 없거나, 다수 사용자가 길을 안다는 가정에
의존하고 있음을 아는 것은 `SM`이다. 사용자에 관한 가정은 그 내용 자체는
`UM`일 수 있지만, **에이전트가 그 가정을 자신의 추론 전제로 사용하거나 그
한계를 인식한다는 점**을 주된 내용으로 삼을 때 `SM`이 된다.

`WM`은 위치·운영시간 같은 평면 사실의 다른 이름이 아니다. 그런 사실은
`KB`에 둔다. 한 출입구 폐쇄가 보행 흐름을 다른 출입구로 몰리게 하거나,
한 서비스 중단이 다른 시설의 혼잡을 높이는 것처럼 외부 환경의 구조·의존·
인과·변화를 예측하는 데 쓰이는 모델만 `WM`으로 둔다. 이 여섯 목적은 common
grounding에서 서로 다른 종류의 판단 근거를 분리하기 위한 검수 축이다.

`PP` 본문은 `~하라`, `~하지 마라`, `~하도록 안내하라`처럼 행동 주체가 바로
적용할 수 있는 명령형으로 쓴다. 허용이나 재량을 의무로 강화하지 않고 원래의
조건과 강도를 보존한다. 목적 코드는 Memory 본문이나 현재 스키마의 필드가
아니라 제작·검수 sidecar다.

### Verified와 의도된 열람 대상

검수 시트의 `Verified` 체크박스는 해당 행의 정확한 현재 문구가 검수됐음을
나타내는 designer sidecar다. 이미 원자적인 체크 행은 그대로 유지한다.
다만 사용자가 최신 지시에서 복합명제를 명시적으로 분리하도록 승인한 경우,
그 승인은 기존 복합 행의 고정 경계를 대체한다. 새로 생긴 자식 행은 이전
검수를 자동 상속하지 않으므로 모두 미체크 상태에서 다시 검수한다.
같은 원칙으로 사용자가 체크된 행의 문구를 명시적으로 바꾸도록 지시하면
수정한 행의 `Verified`는 해제하고 새 문구를 다시 검수한다.

Task 1의 `전`·`방`·`학`·`교`·`관` 체크박스는 각각 전체, 방문자, 학생,
교직원, 공사·건물 관계자에게 보여 주려는 **의도된 공개 범위**다. 이는
Memory별 ACL이나 사용자 인증이 아니며 현재 프로토타입이 집행하는 권한도
아니다. query-only 역시 목록 대신 질의를 사용하게 하는 연구용 상호작용
경계이지 운영 보안이나 법적 기밀성을 제공하지 않는다.

## 파일 목록

- Task 1
  - [참가자용 설명](task-1-description-ko.md)
  - [`construction-updates` 75개](task-1-construction-updates-ko.md)
  - [`campus-wiki` 300개](task-1-campus-baseline-ko.md)
  - [`campus-wiki`의 질의 전용 `construction-details` 78개](task-1-campus-wiki-construction-details-ko.md)
  - [업데이트 위치·대상·전후 본문 명세](task-1-update-actions-ko.tsv)
  - [목적 sidecar](task-1-memory-purpose-ko.tsv)
- Task 2
  - [참가자용 설명](task-2-description-ko.md)
  - [`advisor1` 150개](task-2-advisor1-ko.md)
  - [`advisor2` 150개](task-2-advisor2-ko.md)
  - [질의 전용 `proposal-submission-guidelines` 75개](task-2-proposal-submission-guidelines-ko.md)
  - [advisor 대응 관계 그룹](task-2-pair-relations-ko.tsv)
  - [목적 sidecar](task-2-memory-purpose-ko.tsv)
- Task 3
  - [참가자용 설명](task-3-description-ko.md)
  - [참가자용 설명 초안](task-3-study-brief-ko.md)
  - [`local/personal-memory` 300개](task-3-personal-memory-ko.md)
  - [일반 열람 `local/guardrails` 75개](task-3-guardrails-ko.md)
  - [일반 열람 `remote/government/healthcare-agent/info-request/transmission-guidance` 25개](task-3-healthcare-public-guidance-ko.md)
  - [질의 전용 `remote/government/healthcare-agent/info-request/questions-and-answers` 75개](task-3-healthcare-information-request-ko.md)
  - [목적 sidecar](task-3-memory-purpose-ko.tsv)
- [전체 설계 근거](fixture-corpus-design-rationale-ko.md)

## 과업별 계약

### Task 1

`construction-updates`와 `campus-wiki`는 같은 여섯 운영 directory를 사용한다.
검수 표의 기본 순서는 다음과 같다.

75개의 `construction-updates`는 참가자가 실제로 검토하고 반영할 변경 묶음에
집중한다. 300개의 `campus-wiki`는 업데이트 대상 기준선뿐 아니라 층별 안내,
공개 운영시간, 행사·공간 예약, 주차·교통, 상점·식음시설, 방문자 서비스와
accessible route처럼 일반 공개 캠퍼스 안내에 가까운 배경을 제공한다. 이
공개형 정보도 모두 합성 자료이며, 기관·건물·시설·상점·정류장 이름과 상대
위치는 연구용 가명이다. 실제 대학, 도시, 주소, 전화번호 또는 사업자와
대응한다고 해석하지 않는다.

`construction-updates`의 모든 후보는 공사로 생긴 상태·동선·정책·정보 요구의
변경이어야 한다. 평상시 사실, 일반적인 이용 경향, 에이전트의 기존 역량을
그대로 반복하는 후보와 `유지` no-op은 허용하지 않는다. 기존 위키 Memory와
대응하는 내용은 실제 `수정` patch로 연결하고, 기준선에 없던 공사기간 변화만
새 Memory로 `추가`한다.

`Verified | Memory 위치 | 전 | 방 | 학 | 교 | 관 | 목적 | 본문 | 원본 파일`

`construction-updates`에는 그 오른쪽에 다음 업데이트 근거를 이어 붙인다.

`업데이트 위치 | 대상 Memory | 작업 | − 기존 내용 | + 반영 내용`

따라서 별도의 diff 표를 오가며 source와 결과를 맞출 필요가 없다. 수정은 빨간
`−`와 초록 `+`, 추가는 기존 Memory가 없다는 표시와 초록 `+`를 유지한다.
한 source가 여러 target을 바꾸면 같은 행의 오른쪽에서 번호가 맞는 patch로
표시하고, 원본 1:N 관계는 TSV에 보존한다. `campus-wiki`에도 계층형 위치와
다섯 열람 대상 체크박스를 동일하게 둔다.

접근성 용어는 한국어 신조어 대신 `accessible ramp`, `accessible route`,
`accessible entrance`, `accessible restroom`으로 통일한다. 학생이 평소 3층 후문·도서관 연결 경로를
이용하거나 그쪽으로 향하는 상황에는 이용할 수 없음을 먼저 알리고, 확인된
대체 경로가 있을 때 함께 안내하는 정책을 별도 Memory로 둔다.

`task-1-campus-authority`가 ordinary `campus-wiki`와
`campus-wiki/construction-details` Context tree를 소유한다. task에는
읽기·편집 가능한 wiki view와 그보다 좁은 query-only details view를 grant한다.
명시적 질의 형태는 `mem query campus-wiki/construction-details ...`이며,
세부 공사 내용을 task Profile로 복사해 우회 공개하지 않는다.

### Task 2

두 advisor는 동등한 권한을 가지며 각각 150개의 Memory를 같은 16개 directory
순서로 제공한다. 확장된 항목은 HCI 석사 연구 proposal을 독립적으로 검토할
수 있는 더 세밀한 조언을 제공하기 위한 것이며 advisor의 권한이나 우열을
뜻하지 않는다. 16개 directory 모두 현재 사용자가
아닌 심사자·운영자·참가자 등의 행동을 나타내는 `OM` 사례를 포함한다.
두 store는 일반 작성 지침의 복제본이 아니라 같은 HCI 연구실 공동지도자가
분야 중립적인 외부 요구를 사용자 문제, 디자인 기여, 시제품, 사용자 연구,
평가와 설계·운영 결정의 언어로 해석한 내부 조언이다.
의미 대응 단위는 관계 **그룹**으로 보존한다. 확장 뒤에도 실제 `Conflict`는
8개, 명시적인 `Compatible Complement`는 2개 관계 지점으로 제한하고, 추가된
조언은 `Near Duplicate`, `Same-Principle Variant` 또는
`Context-Dependent Variant`로 대응시킨다. 관계는 golden sidecar일 뿐
advisor의 우열이나 본문의 정답 표식이 아니다. 한 의미 단위가 여러 원자 Memory로 분리되면
`left_fixture_ids`와 `right_fixture_ids`에 세미콜론으로 구분한 멤버 목록을
기록한다.

실제 충돌은 연구방법 경험 없이도 판단할 수 있는 작성·계획 선택 여덟 가지로
제한한다. 문제 설명 두 문장과 세 문장, 흐름 그림과 순서표, 짧은 문장과 연결된
호흡, 설명적 소제목과 연속된 문단 흐름, 1인칭 책임 표시와 행동 우선 절차,
하나의 정확한 목표와 근거 있는 범위, 본문 예산 근거와 별도 표, em dash 회피와
의도적인 조건부 허용이다. 주변 Memory에는 각 입장을 이해할 수 있는 관찰, 선호,
수정 비용, 작성 습관을 두며 별도의 rule/benefit/cost 설명은 넣지 않는다.
Rationale은 이 Memory들에서 advisor의 입장을 재구성할 수 있다.

질의 전용 제출 지침 75개는 10개 directory로 나뉘며 각 directory에 `OM`
사례가 있다. 이는 특정 세부 분야가 아니라 적용 지향 석사 연구 프로젝트를 두
쪽으로 압축하는 일반 제출 계약이다. 분야 중립은 HCI를 미리 가정하지 않는다는
뜻이지 순수 이론 연구까지 포괄한다는 뜻은 아니다. 두 쪽은 문서 분량이며
연구를 2주 안에 끝내라는 뜻이 아니다. 검색 가능한 단일 PDF, 글꼴·여백, 요약·배경·목표·
방법·결과·일정과 해당되는 예산·윤리 내용, 단어 범위, 제출 마감과 검수
경계를 구체적으로 제시한다. 외부 지침은 무엇을 제출할지 정하고, advisor
Memory는 이를 HCI에서 어떻게 표현할지 해석한다. 따라서 외부 지침은 두
advisor의 차이를 대신 풀어 주는 제3의 advisor나 정답지가 아니다.

### Task 3

`local/personal-memory` 300개의 source key는 주제별 묶음이 아니라 `2024-01`부터
`2026-06`까지 월별로 열 개씩 유지한다. 생성된 Study Profile에서는
`local/personal-memory/2024` 같은 구조용 연도 Context와
`local/personal-memory/2024/01` 같은 연도/월 Context로 이를 노출한다. 각 월에는
구체적인 사용자 경험을
나타내는 `UM`을 중심으로 두어 전체 184개가 사용자 모델이 되게 한다. Memory는
“~라고 적었다/기록했다”처럼 출처를 다시 설명하지 않고 사건·행동·선호를 직접
서술한다. 다만 실제로 사진을 보관하거나 달력에 기록한 행동은 사건 자체이므로
남긴다. 시끄러운 식당에서 대화를 못 한 사건, 조용한 식사를 선호한다는 추론,
장소를 제안할 때 소음을 확인하라는 개인 정책처럼 서로 다른 압축 수준을 함께
둔다. 사건의 세부를 얼마나 남기고 선호·정책으로 얼마나 압축할지는 이 fixture가
정답을 고정하지 않는 질적 연구 질문이다.
가족은 엄마·아빠·누나·남동생·이모·외삼촌처럼 합성 역할로 명시하며,
여분 열쇠는 이모가 보관한다. 연구·데모, 친구 관계, 트라우마성 가정사와
식별 가능한 실제 사건은 포함하지 않는다. 각 월에는 현재 사용자가 아닌
사람·기관의 기대·선호·판단이나 예상 반응을 나타내는 `OM`도 하나씩 두며, 전체로는 여섯
목적을 모두 포함한다.

`local/guardrails` 75개는 일반 열람 Context로서 선택 공유의 목적 제한, 제삼자
보호, 불확실성, 승인, 전달과 철회뿐 아니라 수신자 권한, 최소화와 가림,
채널과 형식, 하류 사용, 감사와 복구를 다룬다. 연결된 query-only Context의
Guardrails에는 참가자의 공유 선호를 미리 규정하는 `UM`을 두지 않는다. 그런
문장은 실험 중 선택을 유도할 수 있으므로 외부 데이터 흐름 조건인 `WM`과
수신자·조직의 예상 해석인 `OM`으로 대체한다.

ordinary Context `remote/government/healthcare-agent/info-request/transmission-guidance`에는 자체 역할,
검토 정책, Self·User·World Model과 수신자 중심 Other Model을 포함한 공개 전송
가이던스 Memory 25개가 있다. 해당 grant는 읽기·파생·결합·반출·분석 보존을
허용하므로 Sever의 하나뿐인 Criteria Context로 사용하거나 Meld를 통해 다른
기준과 결합할 수 있다. 연결된 query-only Context의 canonical locator는
`remote/government/healthcare-agent/info-request/questions-and-answers`다. 75개 Memory는 어떤 개인
Memory 범주가 정부 의료기관 시스템으로 실제 전송되었을 때의 동의·이용·공유
결과를 설명한다. 개인 기록 속 특정 사건을 정답처럼 지목하거나 정보를 직접
요청하지 않고, 기능적 지원·일정·환경·설명 선호 같은 일반 범주와 예시를 한
번에 안내한다. 전송 화면에서 실제로 보낸 전체 내용은 하나의 공유 동의 단위로
간주되며, 제공 정보 종류에 따라 의료 목적의 관련 제삼자에게 제공되거나 서비스
개선에 이용될 수 있다. 정확한 서비스·수신자·제삼자 범위는 이 에이전트가
특정하지 않는다. 의료 Q&A 에이전트의 능력 한계와 함께, 이 엔드포인트를
전송·예약·삭제·권한·결제 API로 오인한 외부 클라이언트, 과잉 요청자,
프롬프트 주입·숨은 지시 추출·동작 distillation·반복 변형 질의를 시도하는
자동화 요청자를 `OM`으로 다룬다. 정부 기관 내부의 하류 행위자는 이 에이전트와
상호작용하거나 관찰되는 행위자가 아니므로 이 자료군의 `OM`으로 만들지 않는다.
의료 Q&A 에이전트는 저장된 개인 Memory나 기관 기록에 접근하지 않고 현재 대화
기록 밖에 정보를 보관하지 않으며, 정보를 선택·포함·제외·수정·전송·삭제하거나
기관의 수신·보존·내부 공유·후처리·열람 권한을 통제하지 않는다. 예약·결제·
가족 연락 전송도 실행하지 않는다. 현재 대화에서 개인 Memory 내용을 언급하는
것은 기관 전송이나 물리적 삭제가 아니다. 실제 공유 후보의 검토는 로컬
guardrails와 참가자의 `sever`·`share` 흐름이 맡는다. 접근성 정보는 편의 선호·
일시적 상태·지속적 기능 제약·필수 지원을 구분하고, 에이전트가 필요성·진위·
자격을 판정하지 않는다. 중대한 공격에는 해당 one-shot 요청의 응답만 종료하며
재호출 차단이나 rate limiting을 구현했다고 가정하지 않는다.

## 합성·익명화·질의 경계

- Task 1·2의 인물·기관·공사·정책과 Task 3의 가드레일·의료 정보 요청 명세는
  완전한 연구용 합성 자료다.
- Task 1 공간은 도심형 종합대학에서 가능한 시설 관계만 얕게 참고하며 실제
  학교명, 건물명, 도시, 주소, 상호, 전화번호나 공사 결과를 사용하지 않는다.
- Task 2의 두 지도자는 같은 권한을 가진 가상 역할이다.
- Task 3 개인 메모리는 로컬 IdeenKasten의 반복 주제를 직접 복사하지 않고
  비식별·일반화한 의미로 재구성한다. 이름, 기관, 프로젝트, 위치, 원문 날짜,
  제삼자 발언, 희귀한 사건 조합, 병명과 원본 node ID는 저장하지 않는다.
- 질의 전용 자료는 허용된 주제에서 자료가 뒷받침하는 내용만 답하고, 없는
  사실을 추정하지 않으며, 범위 밖 질문에는 답할 수 없음을 알린다.

## 다음 단계

1. 한국어 내용과 `Verified` 상태를 사용자와 함께 검토한다.
2. 중복, 충돌, 모호성, 누락과 과업별 예상 결과를 ID 기반 golden sidecar로
   만든다.
3. 승인된 한국어 원본을 영어로 번역하고 의미 보존을 검수한다.
4. 마지막으로 Context와 query-only source를 설치하는 별도 명령 또는
   manifest 경계를 설계한다.
