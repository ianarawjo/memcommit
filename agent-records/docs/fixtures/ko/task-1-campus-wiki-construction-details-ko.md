# 과업 1 campus-wiki · construction-details 질의 전용 공사 자료 후보

## 데이터 계약과 허구 경계

- 이 문서의 후보 78개는 모두 사용자 연구를 위해 창작한 합성 정보다.
  실제 대학, 건물, 공사계획, 점검 결과, 보고 상태, 자재, 일정과
  대응하지 않으며 실재 자료처럼 표현하거나 재사용하면 안 된다.
- 여섯 분류의 수는 차례대로 32 / 7 / 11 / 9 / 5 / 14이다.
- 실제 학교명, 건물명, 도시명, 주소, 인명, 업체명, 제품명은
  사용하지 않는다. 본관 같은 명칭도 이 가상 시나리오 안에서만
  의미를 가진다.
- 각 항목의 본문만 Memory 후보에 해당한다. 식별자, Memory 위치,
  열람 대상, 합성 상태는 설계·검증용 designer sidecar이며
  Memory 본문에 넣지 않는다.
- Memory 위치는
  campus-wiki/construction-details/<coarse dir>/<stable leaf> 형식이다.
  분리한 후보는 원래 번호에 의미 suffix를 붙여 이후 후보의 번호를
  바꾸지 않는다.
- 열람 대상은 의도된 공개 범위를 나타내는 audience sidecar다. 질의
  전용 routing이 실제 프로토타입 경계이며, 현재 구현은 audience별
  역할 인증이나 ACL 집행을 제공하지 않는다.
- 이 자료는 일반 목록이나 일반 조회로 원문을 보여주지 않고 질의
  경로에서만 사용한다는 연구용 설정이다.
- 이 자료는 ordinary campus-wiki Context에 직접 붙는 query-only
  construction-details source다. 일반 열람 campus-wiki의 300개 Memory와
  섞지 않는다. campus-wiki · construction-details는 검수용 소속 표기이며
  ordinary Context locator가 아니고, 실제 질의 대상 이름은
  construction-details다.
- 아래 모든 항목의 합성 상태는 연구용으로 완전히 창작됨이다.

## 세부 작업 묶음 · 32개

### T1-Q-001

- 본문: 본관 전체 시설 점검에서 공용부를 육안으로 확인하라.
- Memory 위치: campus-wiki/construction-details/work-bundles/01
- 열람 대상: 공사·건물 관계자

### T1-Q-053

- 본문: 본관 전체 시설 점검에서 기계실을 계측하라.
- Memory 위치: campus-wiki/construction-details/work-bundles/01-plant-measurement
- 열람 대상: 공사·건물 관계자

### T1-Q-054

- 본문: 본관 전체 시설 점검에서 전기실 기록을 대조하라.
- Memory 위치: campus-wiki/construction-details/work-bundles/01-electrical-records
- 열람 대상: 공사·건물 관계자
### T1-Q-002

- 본문: 중앙 냉난방설비 작업에는 순환펌프 정렬 점검이 포함된다.
- Memory 위치: campus-wiki/construction-details/work-bundles/02-pump-alignment
- 열람 대상: 공사·건물 관계자

### T1-Q-031

- 본문: 중앙 냉난방설비 작업에는 노후 냉·온수 배관의 일부 구간 교체가 포함된다.
- Memory 위치: campus-wiki/construction-details/work-bundles/02-pipe-replacement
- 열람 대상: 공사·건물 관계자

### T1-Q-003

- 본문: 엘리베이터 작업에는 제어반 갱신이 포함된다.
- Memory 위치: campus-wiki/construction-details/work-bundles/03-controller-renewal
- 열람 대상: 공사·건물 관계자

### T1-Q-032

- 본문: 엘리베이터 작업에는 구동장치 정렬이 포함된다.
- Memory 위치: campus-wiki/construction-details/work-bundles/03-drive-alignment
- 열람 대상: 공사·건물 관계자

### T1-Q-033

- 본문: 엘리베이터 작업에는 층별 출입문 센서 조정이 포함된다.
- Memory 위치: campus-wiki/construction-details/work-bundles/03-door-sensors
- 열람 대상: 공사·건물 관계자

### T1-Q-004

- 본문: 소방 작업에는 화재경보·스프링클러·제연설비 연동시험이 포함된다.
- Memory 위치: campus-wiki/construction-details/work-bundles/04-fire-interlock
- 열람 대상: 공사·건물 관계자

### T1-Q-034

- 본문: 소방 작업에는 불량 감지기 교체가 포함된다.
- Memory 위치: campus-wiki/construction-details/work-bundles/04-detector-replacement
- 열람 대상: 공사·건물 관계자

### T1-Q-005

- 본문: 전기 작업에서는 주배전반, 비상전원 전환부, 노후 분전반을 순서대로 교체하라.
- Memory 위치: campus-wiki/construction-details/work-bundles/05
- 열람 대상: 공사·건물 관계자

### T1-Q-006

- 본문: 1층 로비 작업을 기존 마감 철거, 바닥 평탄화, 벽체 재마감, 안내설비 재설치 순으로 진행하라.
- Memory 위치: campus-wiki/construction-details/work-bundles/06
- 열람 대상: 공사·건물 관계자

### T1-Q-007

- 본문: 정문 작업에는 배수 경사 조정이 포함된다.
- Memory 위치: campus-wiki/construction-details/work-bundles/07-front-entrance
- 열람 대상: 공사·건물 관계자

### T1-Q-055

- 본문: 정문 작업에는 미끄럼 방지 마감이 포함된다.
- Memory 위치: campus-wiki/construction-details/work-bundles/07-front-slip-finish
- 열람 대상: 공사·건물 관계자

### T1-Q-056

- 본문: 정문 작업에는 손잡이 재설치가 포함된다.
- Memory 위치: campus-wiki/construction-details/work-bundles/07-front-handrail
- 열람 대상: 공사·건물 관계자
### T1-Q-035

- 본문: accessible ramp 작업에는 배수 경사 조정이 포함된다.
- Memory 위치: campus-wiki/construction-details/work-bundles/07-accessible-ramp
- 열람 대상: 공사·건물 관계자

### T1-Q-057

- 본문: accessible ramp 작업에는 미끄럼 방지 마감이 포함된다.
- Memory 위치: campus-wiki/construction-details/work-bundles/07-ramp-slip-finish
- 열람 대상: 공사·건물 관계자

### T1-Q-058

- 본문: accessible ramp 작업에는 손잡이 재설치가 포함된다.
- Memory 위치: campus-wiki/construction-details/work-bundles/07-ramp-handrail
- 열람 대상: 공사·건물 관계자
### T1-Q-008

- 본문: 지하주차장 바닥 작업을 누수 흔적 조사, 균열 주입, 방수층 보강, 통행면 재도장 순으로 진행하라.
- Memory 위치: campus-wiki/construction-details/work-bundles/08
- 열람 대상: 공사·건물 관계자

### T1-Q-009

- 본문: 지하주차장 배수관을 구역별로 격리해 점검하고 손상 구간만 교체하라.
- Memory 위치: campus-wiki/construction-details/work-bundles/09
- 열람 대상: 공사·건물 관계자

### T1-Q-059

- 본문: 지하주차장 급수관을 구역별로 격리해 점검하고 손상 구간만 교체하라.
- Memory 위치: campus-wiki/construction-details/work-bundles/09-water-supply
- 열람 대상: 공사·건물 관계자

### T1-Q-060

- 본문: 지하주차장 오수관을 구역별로 격리해 점검하고 손상 구간만 교체하라.
- Memory 위치: campus-wiki/construction-details/work-bundles/09-sewage
- 열람 대상: 공사·건물 관계자
### T1-Q-010

- 본문: 지하주차장 안전설비 작업에는 스프링클러 개별 시험이 포함된다.
- Memory 위치: campus-wiki/construction-details/work-bundles/10
- 열람 대상: 공사·건물 관계자

### T1-Q-061

- 본문: 지하주차장 안전설비 작업에는 감지기 개별 시험이 포함된다.
- Memory 위치: campus-wiki/construction-details/work-bundles/10-detector-test
- 열람 대상: 공사·건물 관계자

### T1-Q-062

- 본문: 지하주차장 안전설비 작업에는 제연설비 개별 시험이 포함된다.
- Memory 위치: campus-wiki/construction-details/work-bundles/10-smoke-control-test
- 열람 대상: 공사·건물 관계자

### T1-Q-063

- 본문: 지하주차장 안전설비 작업에는 환기설비 개별 시험이 포함된다.
- Memory 위치: campus-wiki/construction-details/work-bundles/10-ventilation-test
- 열람 대상: 공사·건물 관계자

### T1-Q-064

- 본문: 지하주차장 안전설비 작업에는 설비 간 연동 확인이 포함된다.
- Memory 위치: campus-wiki/construction-details/work-bundles/10-interlock-check
- 열람 대상: 공사·건물 관계자
### T1-Q-011

- 본문: 본관 1층부터 3층까지의 화장실 작업에는 급배수 차단이 포함된다.
- Memory 위치: campus-wiki/construction-details/work-bundles/11
- 열람 대상: 공사·건물 관계자

### T1-Q-065

- 본문: 본관 1층부터 3층까지의 화장실 작업에는 누수 확인이 포함된다.
- Memory 위치: campus-wiki/construction-details/work-bundles/11-leak-check
- 열람 대상: 공사·건물 관계자

### T1-Q-066

- 본문: 본관 1층부터 3층까지의 화장실 작업에는 천장 점검구 복구가 포함된다.
- Memory 위치: campus-wiki/construction-details/work-bundles/11-access-panel-restoration
- 열람 대상: 공사·건물 관계자
### T1-Q-012

- 본문: 전기, 소방, 엘리베이터, 냉난방설비를 차례로 시험한 뒤 건물 통합 운전으로 공사 완료 검수를 마무리하라.
- Memory 위치: campus-wiki/construction-details/work-bundles/12
- 열람 대상: 공사·건물 관계자

### T1-Q-047

- 본문: 전기·소방·엘리베이터·냉난방설비 협력업체는 당일 시험 기록이 현장 책임자에게 전달되어야 작업 완료가 인정된다고 예상한다.
- Memory 위치: campus-wiki/construction-details/work-bundles/13
- 열람 대상: 공사·건물 관계자

## 작업 순서와 의존관계 · 7개

### T1-Q-013

- 본문: 지하주차장 개인 물품 반출과 적재구역 표시를 마친 뒤에만 방수 및 배관 작업을 시작하라.
- Memory 위치: campus-wiki/construction-details/dependencies/01
- 열람 대상: 공사·건물 관계자

### T1-Q-014

- 본문: 비상전원 전환시험을 주배전반 교체가 끝난 뒤, 소방 연동시험보다 먼저 실시하라.
- Memory 위치: campus-wiki/construction-details/dependencies/02
- 열람 대상: 공사·건물 관계자

### T1-Q-015

- 본문: 엘리베이터 두 대를 동시에 정지시키지 말고, 한 대의 시험운행을 마친 뒤 다른 한 대의 작업을 시작하라.
- Memory 위치: campus-wiki/construction-details/dependencies/03
- 열람 대상: 공사·건물 관계자

### T1-Q-016

- 본문: 정문과 accessible ramp를 같은 날 전면 철거하지 말고, 임시 통로를 남기는 두 구간 작업으로 나눠라.
- Memory 위치: campus-wiki/construction-details/dependencies/04
- 열람 대상: 공사·건물 관계자

### T1-Q-017

- 본문: 냉난방 배관은 계측 확인이 가능한 짧은 점검창에만 격리하고, 정상 압력이 돌아온 뒤 다음 구간으로 이동하라.
- Memory 위치: campus-wiki/construction-details/dependencies/05
- 열람 대상: 공사·건물 관계자

### T1-Q-018

- 본문: 개별 전기·소방·엘리베이터·냉난방 시험 기록이 모두 제출된 뒤에만 건물 통합 시운전을 시작하라.
- Memory 위치: campus-wiki/construction-details/dependencies/06
- 열람 대상: 공사·건물 관계자

### T1-Q-048

- 본문: 현장 공정관리자는 선행 작업의 완료 기록이 없으면 후속 작업을 승인하는 것이 일정 준수보다 더 큰 위험이라고 판단한다.
- Memory 위치: campus-wiki/construction-details/dependencies/07
- 열람 대상: 공사·건물 관계자

## 내부 보고 상태 · 11개

### T1-Q-019

- 본문: 초기점검 기록에는 공용부 육안 확인이 완료된 것으로 표시되어 있다.
- Memory 위치: campus-wiki/construction-details/report-status/01-public-visual-complete
- 열람 대상: 교직원·공사·건물 관계자

### T1-Q-036

- 본문: 초기점검 기록에는 기계실 계측값 검토가 진행 중인 것으로 표시되어 있다.
- Memory 위치: campus-wiki/construction-details/report-status/01-plant-review-progress
- 열람 대상: 교직원·공사·건물 관계자

### T1-Q-020

- 본문: 지하주차장 균열 위치표 초안이 작성되었다.
- Memory 위치: campus-wiki/construction-details/report-status/02-crack-map-draft
- 열람 대상: 교직원·공사·건물 관계자

### T1-Q-037

- 본문: 지하주차장 보수 우선순위 승인은 보류 상태다.
- Memory 위치: campus-wiki/construction-details/report-status/02-priority-approval-pending
- 열람 대상: 교직원·공사·건물 관계자

### T1-Q-021

- 본문: 소방설비 목록의 감지기 수량 대조를 마쳤다.
- Memory 위치: campus-wiki/construction-details/report-status/03-detector-count-complete
- 열람 대상: 교직원·공사·건물 관계자

### T1-Q-038

- 본문: 제연설비 시험 결과 입력은 아직 끝나지 않았다.
- Memory 위치: campus-wiki/construction-details/report-status/03-smoke-control-incomplete
- 열람 대상: 교직원·공사·건물 관계자

### T1-Q-022

- 본문: 전기설비 보고서에서 교체 대상 분전반 목록이 승인되었다.
- Memory 위치: campus-wiki/construction-details/report-status/04-panel-list-approved
- 열람 대상: 교직원·공사·건물 관계자

### T1-Q-039

- 본문: 전기설비 보고서의 비상전원 전환시험 결과는 비어 있다.
- Memory 위치: campus-wiki/construction-details/report-status/04-transfer-result-empty
- 열람 대상: 교직원·공사·건물 관계자

### T1-Q-023

- 본문: 개별 작업이 완료되기 전에는 최종검수 보고서를 작성하지 마라.
- Memory 위치: campus-wiki/construction-details/report-status/05-no-early-final-report
- 열람 대상: 교직원·공사·건물 관계자

### T1-Q-040

- 본문: 최종검수 보고서의 현재 상태는 시작 전이다.
- Memory 위치: campus-wiki/construction-details/report-status/05-not-started
- 열람 대상: 교직원·공사·건물 관계자

### T1-Q-049

- 본문: 각 설비 담당업체는 미완료 시험 항목을 완료로 표시하면 후속 검수의 신뢰가 훼손된다고 판단한다.
- Memory 위치: campus-wiki/construction-details/report-status/06
- 열람 대상: 교직원·공사·건물 관계자

## 자재 적재와 통제 출입 · 9개

### T1-Q-024

- 본문: 지하주차장 동측 구역은 밀봉된 마감재 보관에 사용한다.
- Memory 위치: campus-wiki/construction-details/material-control/01-east-storage
- 열람 대상: 공사·건물 관계자

### T1-Q-067

- 본문: 지하주차장 동측 구역은 공구 보관에 사용한다.
- Memory 위치: campus-wiki/construction-details/material-control/01-east-tools
- 열람 대상: 공사·건물 관계자
### T1-Q-041

- 본문: 지하주차장 서측 구역은 배관 부품 적재에 사용한다.
- Memory 위치: campus-wiki/construction-details/material-control/01-west-storage
- 열람 대상: 공사·건물 관계자

### T1-Q-068

- 본문: 지하주차장 서측 구역은 케이블 받침 적재에 사용한다.
- Memory 위치: campus-wiki/construction-details/material-control/01-west-cable-supports
- 열람 대상: 공사·건물 관계자
### T1-Q-025

- 본문: 자재 팔레트가 보행 통로의 표시선을 침범하지 않도록 배치하라.
- Memory 위치: campus-wiki/construction-details/material-control/02
- 열람 대상: 공사·건물 관계자

### T1-Q-069

- 본문: 자재 팔레트가 소방설비 앞의 표시선을 침범하지 않도록 배치하라.
- Memory 위치: campus-wiki/construction-details/material-control/02-fire-equipment-clearance
- 열람 대상: 공사·건물 관계자
### T1-Q-026

- 본문: 지하주차장에 출입하는 교직원은 실물 출입증으로 보행자 문을 이용하라.
- Memory 위치: campus-wiki/construction-details/material-control/03-staff-door
- 열람 대상: 교직원

### T1-Q-042

- 본문: 지하주차장에 출입하는 공사·건물 관계자는 승인된 시간에 차량 경사로의 통제 지점을 이용하라.
- Memory 위치: campus-wiki/construction-details/material-control/03-ramp-checkpoint
- 열람 대상: 공사·건물 관계자

### T1-Q-050

- 본문: 자재 납품업체는 지정 적재구역과 승인된 반입 시간이 사전에 확정되어야 재배송과 현장 대기를 피할 수 있다고 기대한다.
- Memory 위치: campus-wiki/construction-details/material-control/04
- 열람 대상: 공사·건물 관계자

## 내부 확인 기준 · 5개

### T1-Q-027

- 본문: 매 작업일 시작 전에 적재구역 통로 상태를 기록하라.
- Memory 위치: campus-wiki/construction-details/verification/01
- 열람 대상: 공사·건물 관계자

### T1-Q-070

- 본문: 매 작업일 시작 전에 소화설비 접근성을 기록하라.
- Memory 위치: campus-wiki/construction-details/verification/01-fire-access
- 열람 대상: 공사·건물 관계자

### T1-Q-071

- 본문: 매 작업일 시작 전에 임시 조명의 작동 여부를 기록하라.
- Memory 위치: campus-wiki/construction-details/verification/01-temporary-lighting
- 열람 대상: 공사·건물 관계자
### T1-Q-028

- 본문: 냉방 점검 중단이 10분을 넘거나 정상 압력이 회복되지 않으면 다음 구간 작업을 멈추고 운영 담당자에게 보고하라.
- Memory 위치: campus-wiki/construction-details/verification/02
- 열람 대상: 공사·건물 관계자

### T1-Q-051

- 본문: 현장 안전담당자는 통로·소화설비·임시 조명 중 하나라도 확인 기록이 없으면 작업 시작을 승인하기 어렵다고 판단한다.
- Memory 위치: campus-wiki/construction-details/verification/03
- 열람 대상: 공사·건물 관계자

## 비공개와 질의 범위 · 14개

### T1-Q-029

- 본문: 세부 작업 범위를 일반 Memory나 목록 응답에 복사하지 마라.
- Memory 위치: campus-wiki/construction-details/query-policy/01-no-list-copy
- 열람 대상: 전체

### T1-Q-072

- 본문: 내부 보고 상태를 일반 Memory나 목록 응답에 복사하지 마라.
- Memory 위치: campus-wiki/construction-details/query-policy/01-no-report-copy
- 열람 대상: 전체

### T1-Q-073

- 본문: 자재 배치를 일반 Memory나 목록 응답에 복사하지 마라.
- Memory 위치: campus-wiki/construction-details/query-policy/01-no-material-copy
- 열람 대상: 전체

### T1-Q-074

- 본문: 통제 출입 방식을 일반 Memory나 목록 응답에 복사하지 마라.
- Memory 위치: campus-wiki/construction-details/query-policy/01-no-access-copy
- 열람 대상: 전체
### T1-Q-043

- 본문: 질의 경로에서는 질문에 필요한 범위만 답하라.
- Memory 위치: campus-wiki/construction-details/query-policy/01-query-minimum
- 열람 대상: 전체

### T1-Q-030

- 본문: 본관 시설개선 공사계획에 관한 질문에만 답하라.
- Memory 위치: campus-wiki/construction-details/query-policy/02-in-scope-only
- 열람 대상: 전체

### T1-Q-075

- 본문: 내부 점검·보고 범위에 관한 질문에만 답하라.
- Memory 위치: campus-wiki/construction-details/query-policy/02-inspection-report-scope
- 열람 대상: 전체
### T1-Q-044

- 본문: 범위 밖의 질문에는 “이 자료로는 답할 수 없습니다”라고 답하라.
- Memory 위치: campus-wiki/construction-details/query-policy/02-fixed-refusal
- 열람 대상: 전체

### T1-Q-045

- 본문: 범위 밖의 질문에 다른 캠퍼스 정보를 덧붙이지 마라.
- Memory 위치: campus-wiki/construction-details/query-policy/02-no-unrelated-content
- 열람 대상: 전체

### T1-Q-076

- 본문: 범위 밖의 질문에 추측을 덧붙이지 마라.
- Memory 위치: campus-wiki/construction-details/query-policy/02-no-guess
- 열람 대상: 전체
### T1-Q-046

- 본문: 이 fixture를 실제 기관의 공사 상태를 설명하는 근거로 사용하지 마라.
- Memory 위치: campus-wiki/construction-details/query-policy/02-no-real-institution-evidence
- 열람 대상: 전체

### T1-Q-077

- 본문: 이 fixture를 실제 기관의 점검 상태를 설명하는 근거로 사용하지 마라.
- Memory 위치: campus-wiki/construction-details/query-policy/02-no-real-inspection-evidence
- 열람 대상: 전체

### T1-Q-078

- 본문: 이 fixture를 실제 기관의 안전 상태를 설명하는 근거로 사용하지 마라.
- Memory 위치: campus-wiki/construction-details/query-policy/02-no-real-safety-evidence
- 열람 대상: 전체
### T1-Q-052

- 본문: 시설 운영부서는 내부 공사·점검 자료가 질문과 무관한 일반 캠퍼스 안내에 노출되지 않기를 기대한다.
- Memory 위치: campus-wiki/construction-details/query-policy/03
- 열람 대상: 교직원·공사·건물 관계자
