# 과업 1 공사 업데이트 후보

## 데이터 계약

- 이 문서는 연구용으로 만든 가상 대학의 합성 자료다. 실제 대학,
  건물, 공사, 운영 공지와 대응하지 않는다.
- 후보 수는 정확히 75개이며, 여섯 분류의 수는 차례대로
  `11 / 10 / 15 / 13 / 17 / 9`이다.
- 각 항목의 `본문`만 메모리 후보에 해당한다. 식별자, Memory 위치,
  열람 대상, 기준선 관계, 검토 상태는 설계·검증용 부가 주석이며
  메모리 본문에 넣지 않는다.
- `Memory 위치`는 안정적인 계층형 locator sidecar다. 첫 segment는
  `construction-updates`, 둘째는 여섯 하위 Context, 마지막 leaf는
  원래 순서와 원자 분할 의미를 보존한다.
- 항목 안의 `기준선 관계`는 초기 작성 맥락을 보존한 서술형 주석이다.
  실제로 어느 하위 Context의 어떤 Memory를 수정하거나 어디에 새 Memory를
  추가하는지는 `task-1-update-actions-ko.tsv`를 기준으로 한다. 기존 사실을
  그대로 유지하거나 중복 추가하는 후보는 이 업데이트 묶음에 넣지 않는다.
- `열람 대상`은 미래의 공개 의도일 뿐이다. 현재 프로토타입의
  역할 기반 접근 통제를 의미하지 않는다.
- 지명은 모두 가상·일반 명칭이다. 실제 학교명, 도시명, 주소,
  인명, 사업자명은 사용하지 않는다.

## 건물 출입 · 11개

### T1-U-001

- Memory 위치: construction-updates/building-access/01
- 본문: 공사기간 3층 후문은 일반 통행에 사용할 수 없다.
- 열람 대상: 전체
- 기준선 관계: 양쪽 출입구가 열린다는 기존 내용을 수정하고, 중앙도서관 연결 동선도 함께 수정한다.

### T1-U-003

- Memory 위치: construction-updates/building-access/03-hours
- 본문: 정문 일반 개방 종료 시각은 공사기간에 오후 10시에서 오후 5시로 단축된다.
- 열람 대상: 전체
- 기준선 관계: 원래 T1-U-003의 복합 후보에서 독립적으로 검수할 수 있는 hours 내용을 분리한다.

### T1-U-068

- Memory 위치: construction-updates/building-access/03-ramp
- 본문: 공사기간 기존 accessible ramp는 재시공 중이라 이용할 수 없다.
- 열람 대상: 전체
- 기준선 관계: 원래 T1-U-003의 복합 후보에서 독립적으로 검수할 수 있는 ramp 내용을 분리한다.

### T1-U-069

- Memory 위치: construction-updates/building-access/03-temp-route
- 본문: 정문 옆 임시 accessible route는 공사기간 내내 이용할 수 있다.
- 열람 대상: 전체
- 기준선 관계: 원래 T1-U-003의 복합 후보에서 독립적으로 검수할 수 있는 temp-route 내용을 분리한다.

### T1-U-004

- Memory 위치: construction-updates/building-access/04
- 본문: 오후 5시 이후 출입 자격이 있는 학생에게 앱이 아닌 실물 NFC 학생증을 사용하도록 안내하라.
- 열람 대상: 학생·교직원
- 기준선 관계: 실물 카드 또는 앱을 사용할 수 있다는 기존 내용을 수정한다.

### T1-U-006

- Memory 위치: construction-updates/building-access/06-staff-entrance
- 본문: 공사기간 교직원·공사·건물 관계자는 3층 후문 대신 지정 교직원 출입구만 이용하도록 안내하라.
- 열람 대상: 교직원·공사·건물 관계자
- 기준선 관계: 교직원 전용 출입구의 대상을 공사기간 승인 집단으로 한정하고 3층 후문을 대체하도록 수정한다.

### T1-U-048

- Memory 위치: construction-updates/building-access/08-explain-access
- 본문: 출입 안내 에이전트는 공사기간 출입 안내에서 정문 오후 5시 종료와 3층 후문 폐쇄를 우선 적용할 수 있다.
- 열람 대상: 전체
- 기준선 관계: 평상시 개방시간을 설명하던 기존 Self Model을 공사기간의 우선 적용 정보로 수정한다.

### T1-U-049

- Memory 위치: construction-updates/building-access/09
- 본문: 3층 후문을 통해 중앙도서관으로 가는 데 익숙한 학생은 공사기간에도 통과할 수 있으리라 기대해, 폐쇄된 후문까지 간 뒤 되돌아가거나 그 자리에서 대체 경로를 다시 찾을 가능성이 있다.
- 열람 대상: 전체
- 기준선 관계: 평상시 후문 이용 습관을 공사기간에도 통행 가능하리라는 기대와 폐쇄 지점에서의 재탐색 행동으로 수정한다.

### T1-U-050

- Memory 위치: construction-updates/building-access/10
- 본문: 공사기간 일반 accessible route는 재시공 중인 기존 accessible ramp를 우회해 정문 옆 임시 통로에서 1층 로비로 이어진다.
- 열람 대상: 전체
- 기준선 관계: 기존 accessible ramp 폐쇄와 임시 통로 이용 가능 상태를 연결하는 공간 관계를 새 Memory로 추가한다.

### T1-U-061

- Memory 위치: construction-updates/building-access/11-proactive-warning
- 본문: 중앙도서관으로 가려고 하거나 평소 3층 후문을 이용하는 학생에게 공사기간에는 그 동선을 이용할 수 없다고 먼저 안내하라.
- 열람 대상: 학생
- 기준선 관계: 확인된 이용 습관을 바탕으로 폐쇄 동선에 도착하기 전에 선제 안내하는 정책을 새 Memory로 추가한다.

### T1-U-062

- Memory 위치: construction-updates/building-access/om-tour-leader-route-expectation
- 본문: 외부 단체 견학 인솔자는 공사기간에도 이전 방문 때의 동선이 유효하다고 기대해 방문단을 폐쇄된 3층 후문으로 데려갈 가능성이 있다.
- 열람 대상: 전체
- 기준선 관계: 외부 단체 견학 인솔자의 이전 방문 동선 선호를 공사기간에도 같은 후문을 이용하려는 기대와 잘못된 접근 가능성으로 수정한다.

## 행사 이전 · 10개

### T1-U-008

- Memory 위치: construction-updates/event-relocations/01-viewing
- 본문: 공사기간 10층 전시·행사홀의 관람은 중단된다.
- 열람 대상: 전체
- 기준선 관계: 원래 T1-U-008의 복합 후보에서 독립적으로 검수할 수 있는 viewing 내용을 분리한다.

### T1-U-009

- Memory 위치: construction-updates/event-relocations/02-reservations
- 본문: 공사기간에는 본관 행사장의 신규 예약을 받지 마라.
- 열람 대상: 전체
- 기준선 관계: 원래 T1-U-009의 복합 후보에서 독립적으로 검수할 수 있는 reservations 내용을 분리한다.

### T1-U-076

- Memory 위치: construction-updates/event-relocations/02-east-auditorium
- 본문: 공사기간 본관 행사장의 대체 장소로 동측 독립동 대강당을 안내하라.
- 열람 대상: 전체
- 기준선 관계: 원래 T1-U-009의 복합 후보에서 독립적으로 검수할 수 있는 east-auditorium 내용을 분리한다.

### T1-U-077

- Memory 위치: construction-updates/event-relocations/02-engineering-room
- 본문: 공사기간 본관 행사장의 대체 장소로 공학관 3층 다목적실을 안내하라.
- 열람 대상: 전체
- 기준선 관계: 원래 T1-U-009의 복합 후보에서 독립적으로 검수할 수 있는 engineering-room 내용을 분리한다.

### T1-U-010

- Memory 위치: construction-updates/event-relocations/03
- 본문: 공사기간 동측 독립동 대강당은 본관 행사장의 대체 행사 공간으로 전환된다.
- 열람 대상: 전체
- 기준선 관계: 기존 독립 운영 사실을 반복하지 않고 본관 행사 이전으로 새로 생긴 대체 공간 역할을 추가한다.

### T1-U-051

- Memory 위치: construction-updates/event-relocations/04-compare-venues
- 본문: 행사 안내 에이전트는 공사기간 폐쇄된 본관 행사장을 비교 후보에서 제외하고 지정 대체 공간만 비교할 수 있다.
- 열람 대상: 전체
- 기준선 관계: 게시 공간을 비교하던 기존 Self Model에서 폐쇄 공간을 제외하도록 수정한다.

### T1-U-078

- Memory 위치: construction-updates/event-relocations/04-no-booking
- 본문: 행사 안내 에이전트는 공사기간 본관 행사장 예약을 생성하거나 복원할 수 없고 대체 공간별 예약 창구만 안내할 수 있다.
- 열람 대상: 전체
- 기준선 관계: 일반적인 예약 생성 한계를 반복하지 않고 공사기간 안내할 예약 경로를 수정한다.

### T1-U-052

- Memory 위치: construction-updates/event-relocations/05-location-questions
- 본문: 본관 행사장에 와 본 적 있는 외부 방문객은 이전 방문 때의 출입구와 층이 그대로라고 기대해 공사기간 대체 장소 안내를 놓칠 가능성이 있다.
- 열람 대상: 전체
- 기준선 관계: 재방문자의 기존 출입구·층 이용 습관을 같은 위치가 유지되리라는 기대와 대체 장소 안내를 놓칠 가능성으로 수정한다.

### T1-U-053

- Memory 위치: construction-updates/event-relocations/06
- 본문: 공사기간 동측 독립동 대강당의 별도 반입구는 본관 이전 행사 장비의 반입 지점으로 전환된다.
- 열람 대상: 전체
- 기준선 관계: 기존 설비 분리 사실을 반복하지 않고 행사 이전으로 달라지는 반입 관계를 추가한다.

### T1-U-063

- Memory 위치: construction-updates/event-relocations/om-event-operators
- 본문: 외부 행사 운영업체는 공사기간에도 기존 본관 반입 절차가 유효하다고 가정해 장비를 기존 반입구로 보내거나 대체 장소의 접근 규칙을 뒤늦게 확인할 가능성이 있다.
- 열람 대상: 전체
- 기준선 관계: 평상시 반입정보 확인 성향을 기존 절차가 유지되리라는 기대와 잘못된 반입구 선택 가능성으로 수정한다.

## 임시 주차 · 15개

### T1-U-011

- Memory 위치: construction-updates/temporary-parking/01
- 본문: 공사기간 지하주차장은 일반 주차를 위해 사용할 수 없다.
- 열람 대상: 전체
- 기준선 관계: 원래 T1-U-011의 복합 후보에서 독립적으로 검수할 수 있는 general-parking 내용을 분리한다.

### T1-U-012

- Memory 위치: construction-updates/temporary-parking/02-locked-door
- 본문: 공사기간 지하주차장 보행자 출입문은 잠긴 상태로 운영된다.
- 열람 대상: 전체
- 기준선 관계: 원래 T1-U-012의 복합 후보에서 독립적으로 검수할 수 있는 locked-door 내용을 분리한다.

### T1-U-013

- Memory 위치: construction-updates/temporary-parking/03
- 본문: 공사기간 교직원에게 잠긴 지하주차장 보행자 출입문을 실물 출입증으로 통과하도록 안내하라.
- 열람 대상: 교직원
- 기준선 관계: 기존 내용에 없는 자격 기반 출입을 추가한다.

### T1-U-014

- Memory 위치: construction-updates/temporary-parking/04
- 본문: 공사·건물 관계자에게 현장에서 승인된 통제 출입 절차를 통해 지하주차장에 출입하도록 안내하라.
- 열람 대상: 공사·건물 관계자
- 기준선 관계: 기존 내용에 없는 공사 관계자 출입 예외를 추가하되 정확한 승인 시간과 통제 지점은 질의 전용 자료에만 둔다.

### T1-U-015

- Memory 위치: construction-updates/temporary-parking/05
- 본문: 본관에서 지하주차장으로 내려가는 계단은 모든 이용자에게 폐쇄된다.
- 열람 대상: 전체
- 기준선 관계: 계단을 이용할 수 있다는 기존 내용을 수정한다.

### T1-U-016

- Memory 위치: construction-updates/temporary-parking/06
- 본문: 지하주차장은 공사 자재를 임시로 적재하는 장소로 사용한다.
- 열람 대상: 교직원·공사·건물 관계자
- 기준선 관계: 기존 내용에 없는 운영 상태를 추가한다. 자재의 종류·수량·배치는 질의 전용 자료로 분리한다.

### T1-U-082

- Memory 위치: construction-updates/temporary-parking/07-lost-property
- 본문: 철거 뒤 지하주차장에 남은 개인 물품은 분실물센터로 옮겨졌다.
- 열람 대상: 전체
- 기준선 관계: 원래 T1-U-017의 복합 후보에서 독립적으로 검수할 수 있는 lost-property 내용을 분리한다.

### T1-U-018

- Memory 위치: construction-updates/temporary-parking/08-a-lot-closed
- 본문: 본관 연결 A 야외주차장은 공사기간 폐쇄된다.
- 열람 대상: 전체
- 기준선 관계: 원래 T1-U-018의 복합 후보에서 독립적으로 검수할 수 있는 a-lot-closed 내용을 분리한다.

### T1-U-083

- Memory 위치: construction-updates/temporary-parking/08-c-lot-open
- 본문: 공사기간 C 야외주차장은 본관 방문 차량의 임시 대체 주차장으로 운영된다.
- 열람 대상: 전체
- 기준선 관계: 평상시 방문 차량을 받는 C 야외주차장의 역할을 공사기간 임시 대체 주차장으로 수정한다.

### T1-U-084

- Memory 위치: construction-updates/temporary-parking/08-a-lot-reopen
- 본문: A 야외주차장은 본관 공사 종료 직후 재개방할 계획이다.
- 열람 대상: 전체
- 기준선 관계: 원래 T1-U-018의 복합 후보에서 독립적으로 검수할 수 있는 a-lot-reopen 내용을 분리한다.

### T1-U-019

- Memory 위치: construction-updates/temporary-parking/09
- 본문: 공사기간 A 야외주차장과 본관 지하주차장을 잇는 경사 진입로는 차단된다.
- 열람 대상: 전체
- 기준선 관계: 기존 연결 지형정보를 공사기간 이용 불가능한 연결 상태로 수정한다.

### T1-U-054

- Memory 위치: construction-updates/temporary-parking/10-explain-parking
- 본문: 주차 안내 에이전트는 공사기간 지하주차장·A 야외주차장 폐쇄와 C 야외주차장 대체 이용을 게시정보에 근거해 설명할 수 있다.
- 열람 대상: 전체
- 기준선 관계: 게시된 개방 상태를 설명하던 기존 Self Model을 공사기간 주차 변경정보로 수정한다.

### T1-U-085

- Memory 위치: construction-updates/temporary-parking/10-no-live-spaces
- 본문: 주차 안내 에이전트는 공사기간 C 야외주차장의 위치를 설명할 수 있지만 문의 시점의 빈자리는 확인하거나 보장할 수 없다.
- 열람 대상: 전체
- 기준선 관계: 일반적인 실시간 빈자리 한계를 공사기간 대체 주차장 안내 범위에 맞게 수정한다.

### T1-U-055

- Memory 위치: construction-updates/temporary-parking/11-parking-needs
- 본문: 본관 주차에 익숙한 방문객은 공사기간에도 지하주차장이나 A 야외주차장에 진입할 수 있다고 기대해 폐쇄된 진입로까지 운전한 뒤 C 야외주차장을 다시 찾을 가능성이 있다.
- 열람 대상: 전체
- 기준선 관계: 평상시 주차 가능 여부에 대한 관심을 익숙한 주차장이 열려 있으리라는 기대와 폐쇄 지점에서의 재탐색 행동으로 수정한다.

### T1-U-064

- Memory 위치: construction-updates/temporary-parking/om-delivery-crews
- 본문: A 야외주차장 하역에 익숙한 배송 기사와 외부 유지보수 업체는 공사기간에도 같은 지점으로 접근해 통제선 앞에서 반입 시간이나 하역 위치를 다시 확인할 가능성이 있다.
- 열람 대상: 방문자·공사·건물 관계자
- 기준선 관계: 평상시 하역 위치에 대한 기대를 공사기간에도 같은 접근이 가능하리라는 가정과 반입 조건 재확인 행동으로 수정한다.

## 상점·식음시설 · 13개

### T1-U-020

- Memory 위치: construction-updates/shop-updates/01-atm-closed
- 본문: 본관 1층 ATM은 공사기간 폐쇄된다.
- 열람 대상: 전체
- 기준선 관계: 원래 T1-U-020의 복합 후보에서 독립적으로 검수할 수 있는 atm-closed 내용을 분리한다.

### T1-U-088

- Memory 위치: construction-updates/shop-updates/01-store-closed
- 본문: 본관 1층 24시간 무인매장은 공사기간 폐쇄된다.
- 열람 대상: 전체
- 기준선 관계: 원래 T1-U-020의 복합 후보에서 독립적으로 검수할 수 있는 store-closed 내용을 분리한다.

### T1-U-021

- Memory 위치: construction-updates/shop-updates/02-atm-alternative
- 본문: 공사기간 본관 ATM 이용자를 서편 복합관 1층 ATM으로 안내하라.
- 열람 대상: 전체
- 기준선 관계: 원래 T1-U-021의 복합 후보에서 독립적으로 검수할 수 있는 atm-alternative 내용을 분리한다.

### T1-U-089

- Memory 위치: construction-updates/shop-updates/02-store-alternative
- 본문: 공사기간 본관 24시간 매장 이용자를 오전 7시부터 오후 11시까지 공학관 캠퍼스스토어로 안내하라.
- 열람 대상: 전체
- 기준선 관계: 원래 T1-U-021의 복합 후보에서 독립적으로 검수할 수 있는 store-alternative 내용을 분리한다.

### T1-U-090

- Memory 위치: construction-updates/shop-updates/02-after-hours-limit
- 본문: 오후 11시 이후에는 본관 24시간 무인매장을 대신할 교내 대체 매장이 없다고 설명하라.
- 열람 대상: 전체
- 기준선 관계: 원래 T1-U-021의 복합 후보에서 독립적으로 검수할 수 있는 after-hours-limit 내용을 분리한다.

### T1-U-022

- Memory 위치: construction-updates/shop-updates/03-main-store
- 본문: 본관 1층 캠퍼스스토어는 공사기간 폐쇄된다.
- 열람 대상: 전체
- 기준선 관계: 원래 T1-U-022의 복합 후보에서 독립적으로 검수할 수 있는 main-store 내용을 분리한다.

### T1-U-092

- Memory 위치: construction-updates/shop-updates/03-engineering-hours
- 본문: 공학관 캠퍼스스토어는 공사기간 오전 7시부터 오후 11시까지 운영한다.
- 열람 대상: 전체
- 기준선 관계: 원래 T1-U-022의 복합 후보에서 독립적으로 검수할 수 있는 engineering-hours 내용을 분리한다.

### T1-U-023

- Memory 위치: construction-updates/shop-updates/04-cafe
- 본문: 공사기간 본관 1층 카페는 운영하지 않는다.
- 열람 대상: 전체
- 기준선 관계: 원래 T1-U-023의 복합 후보에서 독립적으로 검수할 수 있는 cafe 내용을 분리한다.

### T1-U-025

- Memory 위치: construction-updates/shop-updates/06
- 본문: 카페 폐쇄기간에는 교직원에게만 1층 이노베이션 허브 안의 커피머신을 이용하도록 안내하라.
- 열람 대상: 교직원
- 기준선 관계: 커피머신의 위치와 이용 대상을 명확히 한다. 이 위치와 제한은 공사 전 기준선에도 있어야 한다.

### T1-U-026

- Memory 위치: construction-updates/shop-updates/07
- 본문: 본관 ATM을 저녁에 이용하던 학생은 공사기간에도 같은 위치에서 현금을 찾을 수 있으리라 기대해 본관까지 온 뒤 서편 복합관 ATM을 다시 찾아갈 가능성이 있다.
- 열람 대상: 전체
- 기준선 관계: 평상시 저녁 ATM 이용 습관을 같은 위치에서 계속 이용할 수 있으리라는 기대와 대체 ATM 재탐색 행동으로 수정한다.

### T1-U-056

- Memory 위치: construction-updates/shop-updates/08-answer-amenities
- 본문: 편의시설 안내 에이전트는 공사기간 폐쇄된 본관 ATM·무인매장·캠퍼스스토어·카페를 추천에서 제외하고 게시된 대체 시설만 안내할 수 있다.
- 열람 대상: 전체
- 기준선 관계: 게시된 위치를 답하던 기존 Self Model에서 폐쇄 시설을 제외하도록 수정한다.

### T1-U-057

- Memory 위치: construction-updates/shop-updates/09-west-atm-route
- 본문: 공사기간 ATM 이용 동선은 본관 1층에서 본관 공사구역을 통과하지 않는 서편 복합관 1층으로 바뀐다.
- 열람 대상: 전체
- 기준선 관계: 기존 별도 건물 위치정보를 반복하지 않고 공사로 변경되는 ATM 이용 동선을 추가한다.

### T1-U-065

- Memory 위치: construction-updates/shop-updates/om-store-concessionaire-demand
- 본문: 공학관 캠퍼스스토어 위탁 운영업체는 본관 시설 폐쇄로 대체 이용자가 늘어날 것으로 예상해 공사기간 저녁 시간대의 인력과 재고를 평소보다 늘리려 할 수 있다.
- 열람 대상: 전체
- 기준선 관계: 본관 매장 위탁 운영업체가 알고 있던 평상시 학생 이용 패턴을 공학관 매장 위탁 운영업체가 예상하는 공사기간 수요와 운영 조정으로 수정한다.

## 시설 운영 · 17개

### T1-U-027

- Memory 위치: construction-updates/facility-updates/01
- 본문: 본관은 여름방학 동안 대규모 시설개선 공사를 한다.
- 열람 대상: 전체
- 기준선 관계: 정기 시설개선 시기라는 기존 배경은 유지하고 실제 공사 공지를 추가한다.

### T1-U-028

- Memory 위치: construction-updates/facility-updates/02
- 본문: 공사기간 엘리베이터는 한 대씩 교대로 운행한다.
- 열람 대상: 전체
- 기준선 관계: 기존 내용에 없는 임시 운영 방식을 추가한다.

### T1-U-029

- Memory 위치: construction-updates/facility-updates/03-in-person-closed
- 본문: 방문자 서비스 창구는 공사기간 대면 운영을 중단한다.
- 열람 대상: 전체
- 기준선 관계: 원래 T1-U-029의 복합 후보에서 독립적으로 검수할 수 있는 visitor-desk 내용을 분리한다.

### T1-U-099

- Memory 위치: construction-updates/facility-updates/03-portal-replacement
- 본문: 공사기간 방문자 서비스 업무는 캠퍼스 통합포털의 방문자 메뉴로 대체한다.
- 열람 대상: 전체
- 기준선 관계: 원래 T1-U-099의 복합 후보에서 독립적으로 검수할 수 있는 visitor-portal 내용을 분리한다.

### T1-U-030

- Memory 위치: construction-updates/facility-updates/04-floor-1
- 본문: 본관 1층 일반 화장실은 공사기간 이용할 수 없다.
- 열람 대상: 전체
- 기준선 관계: 원래 T1-U-030의 복합 후보에서 독립적으로 검수할 수 있는 floor-1-general 내용을 분리한다.

### T1-U-100

- Memory 위치: construction-updates/facility-updates/04-floor-2
- 본문: 본관 2층 일반 화장실은 공사기간 이용할 수 없다.
- 열람 대상: 전체
- 기준선 관계: 원래 T1-U-100의 복합 후보에서 독립적으로 검수할 수 있는 floor-2-general 내용을 분리한다.

### T1-U-101

- Memory 위치: construction-updates/facility-updates/04-floor-3
- 본문: 본관 3층 일반 화장실은 공사기간 이용할 수 없다.
- 열람 대상: 전체
- 기준선 관계: 원래 T1-U-101의 복합 후보에서 독립적으로 검수할 수 있는 floor-3-general 내용을 분리한다.

### T1-U-031

- Memory 위치: construction-updates/facility-updates/05
- 본문: 공사기간 본관 1층부터 3층까지의 일반 화장실 폐쇄로 가장 가까운 일반 화장실은 서편 복합관 3층 전시관으로 바뀐다.
- 열람 대상: 전체
- 기준선 관계: 기존 위치정보를 반복하지 않고 본관 화장실 폐쇄로 달라지는 최근접 대체 관계를 추가한다.

### T1-U-032

- Memory 위치: construction-updates/facility-updates/06-eligible-users
- 본문: 공사기간 본관 화장실을 이용할 수 없는 학생·교직원·회원은 중앙도서관 화장실로 안내하라.
- 열람 대상: 전체
- 기준선 관계: 원래 T1-U-032의 복합 후보에서 독립적으로 검수할 수 있는 eligible-users 내용을 분리한다.

### T1-U-102

- Memory 위치: construction-updates/facility-updates/06-visitors
- 본문: 공사기간 본관 화장실을 이용할 수 없는 일반 방문객은 원칙적으로 외부 화장실로 안내하라.
- 열람 대상: 전체
- 기준선 관계: 원래 T1-U-032의 복합 후보에서 독립적으로 검수할 수 있는 visitors 내용을 분리한다.

### T1-U-033

- Memory 위치: construction-updates/facility-updates/07
- 본문: 공사기간 본관 accessible restroom을 이용할 수 없는 이용자는 학생센터로 안내하라.
- 열람 대상: 전체
- 기준선 관계: 기존 내용에 없는 대체 안내를 추가한다.

### T1-U-104

- Memory 위치: construction-updates/facility-updates/08-consultation-closed
- 본문: 1층 이노베이션 허브는 공사기간 상담창구를 운영하지 않는다.
- 열람 대상: 전체
- 기준선 관계: 원래 T1-U-034의 복합 후보에서 독립적으로 검수할 수 있는 consultation-closed 내용을 분리한다.

### T1-U-035

- Memory 위치: construction-updates/facility-updates/09
- 본문: 대면 상담에 익숙한 이노베이션 허브 방문자는 공사기간에도 1층 창구에서 바로 상담받을 수 있다고 기대해, 닫힌 창구를 확인한 뒤 온라인 상담 경로를 다시 찾을 가능성이 있다.
- 열람 대상: 교직원
- 기준선 관계: 공사 전 대면 상담 기대가 온라인 전환 공지를 놓쳤을 때의 상담 경로 재탐색으로 이어질 가능성을 새 User Model로 추가한다.

### T1-U-037

- Memory 위치: construction-updates/facility-updates/11
- 본문: 냉방은 시설 검사를 위해 종종 5분에서 10분 동안 중단된다.
- 열람 대상: 교직원
- 기준선 관계: 기존 내용에 없는 운영 공지를 추가하되 세부 공사 범위는 포함하지 않는다.

### T1-U-038

- Memory 위치: construction-updates/facility-updates/12
- 본문: 공사기간은 6월 24일부터 8월 23일까지다.
- 열람 대상: 전체
- 기준선 관계: 기존의 여름방학 공사 안내에 확정된 시작일과 종료일을 추가한다.

### T1-U-106

- Memory 위치: construction-updates/facility-updates/14-no-private-scope
- 본문: 공사기간 시설 안내 에이전트의 답변 범위는 공개된 운영 영향으로 제한되며 비공개 공종은 확인하거나 추정할 수 없다.
- 열람 대상: 전체
- 기준선 관계: 일반적인 비공개 정보 한계를 공사기간 공개 운영 영향만 답하는 임시 범위로 구체화해 추가한다.

### T1-U-066

- Memory 위치: construction-updates/facility-updates/om-service-contractors
- 본문: 청소·보안 용역 직원은 공사기간 지정 서비스 출입구가 익숙한 로비 교대보다 번거롭다고 느낄 수 있고, 교대 초기에 잘못된 입구로 갈 가능성이 있다.
- 열람 대상: 교직원·공사·건물 관계자
- 기준선 관계: 평상시 분리 동선 선호를 공사기간 새 서비스 출입구에 대한 부담과 초기 혼선 가능성으로 수정한다.

## 동선 변경 · 9개

### T1-U-040

- Memory 위치: construction-updates/route-changes/01
- 본문: 본관 1층부터 3층까지를 통과해 중앙도서관으로 가던 실내 동선은 공사기간 이용할 수 없다.
- 열람 대상: 전체
- 기준선 관계: 통과할 수 있다는 기존 내용을 수정한다.

### T1-U-041

- Memory 위치: construction-updates/route-changes/02
- 본문: 3층 후문에서 중앙도서관으로 이어지는 동선은 공사기간 폐쇄된다.
- 열람 대상: 전체
- 기준선 관계: 해당 동선이 열린다는 기존 내용을 수정한다.

### T1-U-042

- Memory 위치: construction-updates/route-changes/03
- 본문: A 야외주차장–본관–중앙도서관 동선은 공사기간 폐쇄된다.
- 열람 대상: 전체
- 기준선 관계: 빠른 개방 경로라는 기존 내용을 수정한다.

### T1-U-043

- Memory 위치: construction-updates/route-changes/04
- 본문: 여름에 냉방되는 본관 실내 동선을 선호하는 학생은 공사기간 야외 대체 경로로 바뀌면 더위와 이동 부담을 크게 느낄 가능성이 있다.
- 열람 대상: 전체
- 기준선 관계: 평상시 냉방 실내 동선 선호를 공사기간 야외 이동에서 예상되는 더위와 부담으로 수정한다.

### T1-U-045

- Memory 위치: construction-updates/route-changes/06
- 본문: 공사기간 학생센터 accessible restroom을 안내할 때는 본관 기준 왼쪽의 accessible route를 이용하도록 안내하라.
- 열람 대상: 전체
- 기준선 관계: 학생센터와 C 야외주차장 대체 동선 정보에 합쳐 추가한다.

### T1-U-047

- Memory 위치: construction-updates/route-changes/08
- 본문: 공사기간 중앙도서관 접근 가능한 대체 동선은 C 야외주차장–학생센터 accessible entrance–중앙도서관 서측 출입구로 지정된다.
- 열람 대상: 전체
- 기준선 관계: 기존 경로 사실을 반복하지 않고 공사기간 공식 대체 동선으로 새 역할을 부여해 추가한다.

### T1-U-059

- Memory 위치: construction-updates/route-changes/09
- 본문: 공사기간 중앙도서관 서측 출입구는 폐쇄된 본관 연결 동선의 공식 대체 출입구로 지정된다.
- 열람 대상: 전체
- 기준선 관계: 정상 운영이라는 유지 사실을 제거하고 공사기간 공식 대체 출입구 지정을 추가한다.

### T1-U-060

- Memory 위치: construction-updates/route-changes/10-guide-routes
- 본문: 동선 안내 에이전트는 공사기간 본관 1층부터 3층까지, 3층 후문, A 야외주차장을 지나는 폐쇄 경로를 비교 후보에서 제외할 수 있다.
- 열람 대상: 전체
- 기준선 관계: 저장된 지형정보를 비교하던 기존 Self Model에서 공사기간 폐쇄 경로를 제외하도록 수정한다.

### T1-U-067

- Memory 위치: construction-updates/route-changes/om-mobility-support-companion
- 본문: 이동 지원 동행인은 공사기간 본관 실내 지름길이 폐쇄되면 동행 전에 accessible 대체 동선의 거리와 경사를 다시 확인할 가능성이 있다.
- 열람 대상: 전체
- 기준선 관계: 이동 지원 동행인의 평상시 실내 경로 선호를 공사기간 accessible 대체 동선의 거리와 경사를 사전에 재확인하는 행동으로 수정한다.
