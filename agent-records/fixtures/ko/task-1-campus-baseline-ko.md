# 과업 1 캠퍼스 기준선 후보

## 데이터 계약

- 이 문서는 연구용으로 만든 가상 대학의 합성 자료다. 실제 대학,
  건물, 도시, 주소, 인명, 사업자와 대응하지 않는다.
- 후보 수는 정확히 300개이며, 여섯 분류에는 각각 50개가 있다.
- 각 항목의 본문만 Memory 후보에 해당한다. 식별자, Memory 위치,
  열람 대상, 기준선 상태는 설계·검증용 designer sidecar이며
  Memory 본문에 넣지 않는다.
- Memory 위치는 campus-wiki/<하위 Context>/<stable leaf> 형식의
  canonical locator다. 분리한 후보는 원래 번호에 의미 suffix를 붙여
  이후 후보의 번호를 바꾸지 않는다.
- 열람 대상은 의도된 공개 범위를 나타내는 audience sidecar다. 현재
  프로토타입의 역할 인증이나 ACL 집행을 뜻하지 않는다.
- 수정 대상은 공사 업데이트가 실제로 바꾸는 오래된 기준선, 누락 보완은
  업데이트를 해석하는 데 필요하지만 기존 기준선에서 빠진 사실, 영향 판정
  지원은 변경 방향을 판단하는 배경, 비영향은 이번 공사와 무관한 사실을
  뜻한다. 업데이트와 동일한 사실을 뜻하는 `이미 일치` 상태는 사용하지 않는다.
- 공간 배치는 도심형 종합대학의 조밀한 캠퍼스를 느슨하게 참고한
  가상 모델이다. 실제 장소에 관한 사실로 해석해서는 안 된다.
- 본문에 쓰인 대학·건물·시설·주차장·상점·정류장 이름과 상대 위치는
  모두 연구용 가명이다. 실제 기관, 주소, 도시, 전화번호, 사업자 또는
  현존 장소를 식별하거나 재현하지 않는다.

## 건물 출입 · 50개

### T1-W-001

- 본문: 본관 3층 후문은 학기와 방학의 일반 개방시간 안에 일반 통행에 사용할 수 있다.
- Memory 위치: campus-wiki/building-access/01
- 열람 대상: 전체
- 기준선 상태: 수정 대상

### T1-W-002

- 본문: 본관 정문은 1층에 있다.
- Memory 위치: campus-wiki/building-access/02-front-floor
- 열람 대상: 전체
- 기준선 상태: 영향 판정 지원

### T1-W-100

- 본문: 경사진 대지 반대편의 본관 후문은 3층 높이에 있다.
- Memory 위치: campus-wiki/building-access/02-rear-elevation
- 열람 대상: 전체
- 기준선 상태: 영향 판정 지원

### T1-W-003

- 본문: 본관 내부 에스컬레이터는 1층부터 3층까지 연결한다.
- Memory 위치: campus-wiki/building-access/03
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-004

- 본문: 본관 정문의 학기 중 일반 개방 종료 시각은 오후 10시다.
- Memory 위치: campus-wiki/building-access/04
- 열람 대상: 전체
- 기준선 상태: 수정 대상

### T1-W-136

- 본문: 본관 정문의 방학 중 일반 개방 종료 시각은 오후 10시다.
- Memory 위치: campus-wiki/building-access/04-recess
- 열람 대상: 전체
- 기준선 상태: 수정 대상
### T1-W-005

- 본문: 중앙도서관으로 가는 데 익숙한 학생은 3층 후문이 평상시 통행 가능한 연결로라고 기대한다.
- Memory 위치: campus-wiki/building-access/05
- 열람 대상: 전체
- 기준선 상태: 수정 대상

### T1-W-006

- 본문: 출입 안내 에이전트는 게시된 개방시간을 설명할 수 있다.
- Memory 위치: campus-wiki/building-access/06-explain-hours-eligibility
- 열람 대상: 전체
- 기준선 상태: 수정 대상

### T1-W-137

- 본문: 출입 안내 에이전트는 게시된 출입 자격을 설명할 수 있다.
- Memory 위치: campus-wiki/building-access/06-explain-eligibility
- 열람 대상: 전체
- 기준선 상태: 비영향
### T1-W-101

- 본문: 출입 안내 에이전트는 출입증을 발급할 수 없다.
- Memory 위치: campus-wiki/building-access/06-no-credential-issuance
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-102

- 본문: 출입 안내 에이전트는 잠긴 문을 열 수 없다.
- Memory 위치: campus-wiki/building-access/06-no-unlocking
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-007

- 본문: 일반 개방시간 이후 출입 자격이 있는 학생에게 실물 NFC 학생증 또는 등록된 앱을 사용하도록 안내하라.
- Memory 위치: campus-wiki/building-access/07
- 열람 대상: 학생·교직원
- 기준선 상태: 수정 대상

### T1-W-008

- 본문: 출입 인증이 실패하면 게시된 담당 연락처를 확인한 뒤 안내하라.
- Memory 위치: campus-wiki/building-access/08-verified-contact
- 열람 대상: 학생·교직원
- 기준선 상태: 누락 보완

### T1-W-103

- 본문: 확인되지 않은 연락처 번호를 추정하지 마라.
- Memory 위치: campus-wiki/building-access/08-no-unverified-number
- 열람 대상: 학생·교직원
- 기준선 상태: 누락 보완

### T1-W-009

- 본문: 교직원 전용 출입구는 3층 후문과 별개의 통제 출입구다.
- Memory 위치: campus-wiki/building-access/09
- 열람 대상: 교직원·공사·건물 관계자
- 기준선 상태: 수정 대상

### T1-W-010

- 본문: 정문 옆 accessible ramp는 계단을 쓰지 않고 1층 로비로 들어가는 상시 접근로다.
- Memory 위치: campus-wiki/building-access/10
- 열람 대상: 전체
- 기준선 상태: 수정 대상

### T1-W-130

- 본문: 외부 단체 견학 인솔자는 이전 방문에서 사용한 3층 후문 동선을 다음 방문에도 그대로 이용하려는 경향이 있다.
- Memory 위치: campus-wiki/building-access/12
- 열람 대상: 전체
- 기준선 상태: 수정 대상

### T1-W-054

- 본문: 본관 정문의 학기 중 일반 개방 시작 시각은 오전 7시다.
- Memory 위치: campus-wiki/building-access/13-term-opening
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-055

- 본문: 본관 정문의 방학 중 일반 개방 시작 시각은 오전 8시다.
- Memory 위치: campus-wiki/building-access/14-recess-opening
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-056

- 본문: 본관의 주말 일반 개방시간은 주말 운영표에 별도로 게시된다.
- Memory 위치: campus-wiki/building-access/15-weekend-hours
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-057

- 본문: 본관의 공휴일 출입시간은 정규 운영시간과 다를 수 있다.
- Memory 위치: campus-wiki/building-access/16-holiday-hours
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-058

- 본문: 처음 방문하는 사람은 본관 1층 정문이 일반 방문자의 기본 출입구라고 예상하는 경우가 많다.
- Memory 위치: campus-wiki/building-access/17-first-time-visitors
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-059

- 본문: 계단 이용이 어려운 방문객은 계단 없는 접근로가 정문 가까이에 있기를 기대한다.
- Memory 위치: campus-wiki/building-access/18-ramp-demand
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-060

- 본문: 교직원 전용 출입구를 이용하려면 유효한 교직원 출입 자격이 필요하다.
- Memory 위치: campus-wiki/building-access/19-staff-eligibility
- 열람 대상: 교직원
- 기준선 상태: 비영향

### T1-W-061

- 본문: 본관의 서비스 출입구는 사전 등록된 배송과 시설 업무에 사용된다.
- Memory 위치: campus-wiki/building-access/20-service-entrance
- 열람 대상: 교직원·공사·건물 관계자
- 기준선 상태: 비영향

### T1-W-062

- 본문: 어린이를 동반한 방문객은 유모차로 접근 가능한 정문과 accessible ramp가 가까이 연결되기를 선호한다.
- Memory 위치: campus-wiki/building-access/21-family-visitors
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-063

- 본문: 택시·차량 호출 기사는 승객이 별도 출입구를 지정하지 않으면 본관 1층 정문을 기본 하차 지점으로 예상하는 경우가 많다.
- Memory 위치: campus-wiki/building-access/22-rideshare-front-entrance-expectation
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-064

- 본문: 출입 안내 에이전트는 정문과 후문의 평상시 용도를 구분해 설명할 수 있다.
- Memory 위치: campus-wiki/building-access/23-explain-door-roles
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-065

- 본문: 출입 안내 에이전트는 문의 시점의 물리적 잠금 상태를 실시간으로 확인할 수 없다.
- Memory 위치: campus-wiki/building-access/24-no-live-lock-state
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-066

- 본문: 게시된 운영시간과 현장 출입 표지가 다르면 현장 표지를 따르도록 안내하라.
- Memory 위치: campus-wiki/building-access/25-follow-site-signage
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-067

- 본문: 출입 자격이 없는 사람에게 다른 이용자의 인증을 따라 들어가도록 제안하지 마라.
- Memory 위치: campus-wiki/building-access/26-no-tailgating
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-068

- 본문: 비상구는 비상 대피를 위한 문이며 평상시 일반 출입구가 아니다.
- Memory 위치: campus-wiki/building-access/27-emergency-exits
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-069

- 본문: 본관 정문의 자동문은 일반 개방시간에 작동한다.
- Memory 위치: campus-wiki/building-access/28-automatic-door-hours
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-070

- 본문: 보조견은 이용자와 함께 본관의 일반 출입구를 이용할 수 있다.
- Memory 위치: campus-wiki/building-access/29-service-animals
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-071

- 본문: 자전거와 개인형 이동장치는 본관 실내에서 타지 않도록 안내하라.
- Memory 위치: campus-wiki/building-access/30-no-indoor-riding
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-072

- 본문: 유아차를 이용하는 방문객은 정문 옆 accessible ramp를 이용할 수 있다.
- Memory 위치: campus-wiki/building-access/31-stroller-access
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-073

- 본문: 단체 견학 방문자는 인솔자가 1층 정문 로비에서 기다릴 것이라고 기대하는 경우가 많다.
- Memory 위치: campus-wiki/building-access/32-tour-groups
- 열람 대상: 방문자
- 기준선 상태: 비영향

### T1-W-074

- 본문: 외부 작업자는 서비스 출입구의 별도 확인 절차를 일반 방문 절차와 혼동할 수 있다.
- Memory 위치: campus-wiki/building-access/33-contractor-check-in
- 열람 대상: 공사·건물 관계자
- 기준선 상태: 비영향

### T1-W-075

- 본문: 대여한 방문 출입증은 본관을 나가기 전에 안내 창구에 반납해야 한다.
- Memory 위치: campus-wiki/building-access/34-return-visitor-pass
- 열람 대상: 방문자
- 기준선 상태: 비영향

### T1-W-076

- 본문: 출입증을 분실한 이용자에게 게시된 출입지원 창구를 안내하라.
- Memory 위치: campus-wiki/building-access/35-lost-credential
- 열람 대상: 학생·교직원
- 기준선 상태: 비영향

### T1-W-077

- 본문: 정문 옆 accessible entrance에는 자동문이 설치되어 있다.
- Memory 위치: campus-wiki/building-access/36-accessible-automatic-door
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-078

- 본문: 정문 안쪽의 바람막이 공간은 외부와 로비 사이에 있다.
- Memory 위치: campus-wiki/building-access/37-vestibule
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-079

- 본문: 본관의 야간 출입은 일반 개방과 별도의 자격 정책을 따른다.
- Memory 위치: campus-wiki/building-access/38-night-access-policy
- 열람 대상: 학생·교직원
- 기준선 상태: 비영향

### T1-W-080

- 본문: 캠퍼스 발급 출입 자격의 유효 여부는 이용자의 소속 상태에 따라 달라진다.
- Memory 위치: campus-wiki/building-access/39-affiliation-status
- 열람 대상: 학생·교직원
- 기준선 상태: 비영향

### T1-W-081

- 본문: 모바일 출입 인증의 지원 여부는 캠퍼스 건물마다 다를 수 있다.
- Memory 위치: campus-wiki/building-access/40-mobile-support-varies
- 열람 대상: 학생·교직원
- 기준선 상태: 비영향

### T1-W-082

- 본문: 공개 행사의 등록 방문객은 행사 안내에 지정된 출입구를 이용한다.
- Memory 위치: campus-wiki/building-access/41-event-entrance
- 열람 대상: 방문자
- 기준선 상태: 비영향

### T1-W-083

- 본문: 행사 전용 출입구의 이용 가능 시간은 해당 행사 일정에 따른다.
- Memory 위치: campus-wiki/building-access/42-event-entrance-hours
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-084

- 본문: 학생 단체는 대규모 방문 때 정문 로비에서 일행을 바로 만날 수 있기를 기대한다.
- Memory 위치: campus-wiki/building-access/43-group-arrival-notice
- 열람 대상: 학생
- 기준선 상태: 비영향

### T1-W-085

- 본문: 출입구에 남겨진 물품이 통행을 방해하면 시설 신고 에이전트를 통해 신고하라.
- Memory 위치: campus-wiki/building-access/44-obstruction-reporting
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-086

- 본문: 현장 출입 지원이 필요한 방문자에게 1층 안내 창구를 안내하라.
- Memory 위치: campus-wiki/building-access/45-onsite-access-help
- 열람 대상: 전체
- 기준선 상태: 비영향

## 행사·공간 예약 · 50개

### T1-W-011

- 본문: 본관 1층 회의공간은 외부 행사를 위해 예약할 수 있다.
- Memory 위치: campus-wiki/event-relocations/01
- 열람 대상: 전체
- 기준선 상태: 수정 대상

### T1-W-138

- 본문: 본관 1층 회의공간은 교내 회의를 위해 예약할 수 있다.
- Memory 위치: campus-wiki/event-relocations/01-campus-meetings
- 열람 대상: 전체
- 기준선 상태: 수정 대상
### T1-W-012

- 본문: 본관 10층 전시·행사홀은 방학에도 전시 관람을 운영한다.
- Memory 위치: campus-wiki/event-relocations/02-recess-viewing
- 열람 대상: 전체
- 기준선 상태: 수정 대상

### T1-W-104

- 본문: 본관 10층 전시·행사홀은 방학에도 예약 행사를 운영한다.
- Memory 위치: campus-wiki/event-relocations/02-recess-events
- 열람 대상: 전체
- 기준선 상태: 수정 대상

### T1-W-013

- 본문: 본관 동쪽의 독립동 대강당은 본관 행사시설과 설비를 공유하지 않는다.
- Memory 위치: campus-wiki/event-relocations/03-separate-services
- 열람 대상: 전체
- 기준선 상태: 영향 판정 지원

### T1-W-105

- 본문: 본관 동쪽의 독립동 대강당은 본관 행사시설과 출입구를 공유하지 않는다.
- Memory 위치: campus-wiki/event-relocations/03-separate-entrance
- 열람 대상: 전체
- 기준선 상태: 영향 판정 지원

### T1-W-014

- 본문: 운영이 확인된 공간만 행사 대체 장소로 제시하라.
- Memory 위치: campus-wiki/event-relocations/04-confirmed-spaces
- 열람 대상: 전체
- 기준선 상태: 영향 판정 지원

### T1-W-106

- 본문: 빈 시간표를 확인하지 못한 공간을 확정 예약처럼 안내하지 마라.
- Memory 위치: campus-wiki/event-relocations/04-no-unchecked-booking
- 열람 대상: 전체
- 기준선 상태: 영향 판정 지원

### T1-W-015

- 본문: 본관 행사장에 와 본 적 있는 외부 방문객은 이전 방문 때 사용한 출입구와 층을 다음 방문에도 그대로 찾으려는 경향이 있다.
- Memory 위치: campus-wiki/event-relocations/05
- 열람 대상: 전체
- 기준선 상태: 수정 대상

### T1-W-016

- 본문: 행사 안내 에이전트는 게시된 행사 공간을 비교할 수 있다.
- Memory 위치: campus-wiki/event-relocations/06-compare-space-hours
- 열람 대상: 전체
- 기준선 상태: 수정 대상

### T1-W-139

- 본문: 행사 안내 에이전트는 게시된 운영시간을 비교할 수 있다.
- Memory 위치: campus-wiki/event-relocations/06-compare-hours
- 열람 대상: 전체
- 기준선 상태: 비영향
### T1-W-107

- 본문: 행사 안내 에이전트는 예약을 생성할 수 없다.
- Memory 위치: campus-wiki/event-relocations/06-no-reservations
- 열람 대상: 전체
- 기준선 상태: 수정 대상

### T1-W-108

- 본문: 행사 안내 에이전트는 잔여 좌석을 보장할 수 없다.
- Memory 위치: campus-wiki/event-relocations/06-no-seat-guarantee
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-017

- 본문: 본관 5층 일부 세미나실은 정규수업에도 사용된다.
- Memory 위치: campus-wiki/event-relocations/07-class-use
- 열람 대상: 학생·교직원
- 기준선 상태: 누락 보완

### T1-W-140

- 본문: 본관 6층 일부 세미나실은 정규수업에도 사용된다.
- Memory 위치: campus-wiki/event-relocations/07-floor-6-class-use
- 열람 대상: 학생·교직원
- 기준선 상태: 누락 보완
### T1-W-109

- 본문: 본관 5층과 6층 일부 세미나실을 행사 대체실로 제시하기 전에 수업 일정을 확인하라.
- Memory 위치: campus-wiki/event-relocations/07-check-class-schedule
- 열람 대상: 학생·교직원
- 기준선 상태: 누락 보완

### T1-W-131

- 본문: 외부 행사 운영업체는 반입구와 무대 접근 동선이 행사 전날까지 명확히 확정되기를 기대한다.
- Memory 위치: campus-wiki/event-relocations/08
- 열람 대상: 전체
- 기준선 상태: 수정 대상

### T1-W-087

- 본문: 예약 가능한 캠퍼스 공간의 이름과 수용 인원은 공개 공간 목록에 게시된다.
- Memory 위치: campus-wiki/event-relocations/09-public-room-directory
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-088

- 본문: 행사 공간 예약 요청은 캠퍼스 공간예약 포털에서 제출한다.
- Memory 위치: campus-wiki/event-relocations/10-booking-portal
- 열람 대상: 학생·교직원
- 기준선 상태: 비영향

### T1-W-089

- 본문: 행사 주최자는 예상 참석 인원에 맞는 수용 규모를 확인해야 한다.
- Memory 위치: campus-wiki/event-relocations/11-check-capacity
- 열람 대상: 학생·교직원
- 기준선 상태: 비영향

### T1-W-090

- 본문: accessible seating이 필요한 행사는 예약 요청에 그 필요를 표시할 수 있다.
- Memory 위치: campus-wiki/event-relocations/12-accessible-seating
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-091

- 본문: 외부 단체의 캠퍼스 행사 예약에는 교내 주관 부서가 필요하다.
- Memory 위치: campus-wiki/event-relocations/13-campus-sponsor
- 열람 대상: 방문자·교직원
- 기준선 상태: 비영향

### T1-W-092

- 본문: 학생단체의 행사 예약은 등록된 단체 계정으로 신청한다.
- Memory 위치: campus-wiki/event-relocations/14-student-group-account
- 열람 대상: 학생
- 기준선 상태: 비영향

### T1-W-093

- 본문: 공간 예약은 승인 확인서가 발행된 뒤 확정된다.
- Memory 위치: campus-wiki/event-relocations/15-confirmation-receipt
- 열람 대상: 학생·교직원
- 기준선 상태: 비영향

### T1-W-094

- 본문: 반복 행사의 공간 사용은 학기마다 다시 승인받는다.
- Memory 위치: campus-wiki/event-relocations/16-recurring-events
- 열람 대상: 학생·교직원
- 기준선 상태: 비영향

### T1-W-095

- 본문: 예약 시간에는 행사 준비와 철수에 필요한 시간이 포함된다.
- Memory 위치: campus-wiki/event-relocations/17-setup-teardown
- 열람 대상: 학생·교직원
- 기준선 상태: 비영향

### T1-W-096

- 본문: 행사 종료 뒤 이동한 가구를 공간의 기본 배치로 되돌려 놓아라.
- Memory 위치: campus-wiki/event-relocations/18-reset-furniture
- 열람 대상: 학생·교직원
- 기준선 상태: 비영향

### T1-W-097

- 본문: 음식 반입 가능 여부는 공간별 이용 규칙에서 확인하라.
- Memory 위치: campus-wiki/event-relocations/19-check-food-policy
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-098

- 본문: 행사 음향·영상 지원은 공간 예약과 별도로 요청한다.
- Memory 위치: campus-wiki/event-relocations/20-av-support-request
- 열람 대상: 학생·교직원
- 기준선 상태: 비영향

### T1-W-099

- 본문: 행사 임시 표지는 통행과 비상구를 가리지 않도록 설치하라.
- Memory 위치: campus-wiki/event-relocations/21-signage-safety
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-167

- 본문: 행사 안내 에이전트는 공개 목록에 있는 공간별 수용 인원을 비교할 수 있다.
- Memory 위치: campus-wiki/event-relocations/22-compare-capacity
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-168

- 본문: 행사 안내 에이전트는 비공개 참가자 명단을 열람할 수 없다.
- Memory 위치: campus-wiki/event-relocations/23-no-participant-list
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-169

- 본문: 행사 안내 에이전트는 심사 중인 예약의 승인 시점을 보장할 수 없다.
- Memory 위치: campus-wiki/event-relocations/24-no-approval-guarantee
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-170

- 본문: 당일 공간 운영 여부는 공식 행사 일정과 시설 공지를 함께 확인하라.
- Memory 위치: campus-wiki/event-relocations/25-check-calendar-notices
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-171

- 본문: 임시로 보류된 공간을 확정된 예약 공간으로 안내하지 마라.
- Memory 위치: campus-wiki/event-relocations/26-no-tentative-confirmation
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-172

- 본문: 외부 행사 방문객은 행사 시작 전이면 건물에도 출입할 수 있다고 기대하는 경우가 많다.
- Memory 위치: campus-wiki/event-relocations/27-visitor-hours-question
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-173

- 본문: 장비를 가져오는 행사 운영자는 반입구와 무대까지의 동선이 예약 확인서에 명확히 적혀 있기를 기대한다.
- Memory 위치: campus-wiki/event-relocations/28-organizer-loading-needs
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-174

- 본문: 행사 접근 지원이 필요한 참석자는 필요한 지원이 별도 요청 없이 준비되어 있으리라 기대해 사전 연락 요건을 놓치기 쉽다.
- Memory 위치: campus-wiki/event-relocations/29-access-request
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-175

- 본문: 본관의 소규모 세미나실은 독립동 대강당보다 수용 인원이 적다.
- Memory 위치: campus-wiki/event-relocations/30-relative-capacity
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-176

- 본문: 본관 10층 전시 관람시간은 예약 행사 이용시간과 별도로 게시된다.
- Memory 위치: campus-wiki/event-relocations/31-gallery-hours
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-177

- 본문: 본관 1층 회의공간에는 고정 좌석이 없는 가변형 구역이 있다.
- Memory 위치: campus-wiki/event-relocations/32-flexible-meeting-area
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-178

- 본문: 독립동 대강당에는 본관과 별개의 행사 안내 데스크가 있다.
- Memory 위치: campus-wiki/event-relocations/33-auditorium-desk
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-179

- 본문: 외부 행사 업체는 교내 주관 부서가 반입 시각과 동선을 확정해 주기를 기대한다.
- Memory 위치: campus-wiki/event-relocations/34-vendor-coordination
- 열람 대상: 방문자·교직원
- 기준선 상태: 비영향

### T1-W-180

- 본문: 취소된 공개 행사는 공식 행사 일정에 취소 상태로 표시된다.
- Memory 위치: campus-wiki/event-relocations/35-public-cancellation
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-181

- 본문: 공휴일에는 평일에 예약 가능한 공간도 운영하지 않을 수 있다.
- Memory 위치: campus-wiki/event-relocations/36-holiday-availability
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-182

- 본문: 안전상 긴급 조치는 승인된 공간 예약보다 우선한다.
- Memory 위치: campus-wiki/event-relocations/37-emergency-priority
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-183

- 본문: 공간 이름이 같아 보이면 건물명과 층을 함께 확인하라.
- Memory 위치: campus-wiki/event-relocations/38-confirm-building-floor
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-184

- 본문: 행사장에서 발견한 물품은 해당 건물의 안내 데스크에 맡긴다.
- Memory 위치: campus-wiki/event-relocations/39-event-lost-property
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-185

- 본문: 행사 주최자는 촬영 허용 범위가 참석자에게 사전에 명확히 전달되기를 기대한다.
- Memory 위치: campus-wiki/event-relocations/40-event-photography
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-186

- 본문: 공개 행사 정보와 비공개 참가자 정보를 구분해 안내하라.
- Memory 위치: campus-wiki/event-relocations/41-separate-public-private
- 열람 대상: 전체
- 기준선 상태: 비영향

## 주차 · 50개

### T1-W-018

- 본문: 본관 왼쪽의 A 야외주차장은 경사 진입로를 통해 본관 지하주차장과 연결된다.
- Memory 위치: campus-wiki/temporary-parking/01
- 열람 대상: 전체
- 기준선 상태: 수정 대상

### T1-W-019

- 본문: 본관 지하주차장은 운영시간 동안 일반 차량이 진입해 주차할 수 있다.
- Memory 위치: campus-wiki/temporary-parking/02
- 열람 대상: 전체
- 기준선 상태: 수정 대상

### T1-W-020

- 본문: 지하주차장 보행자 출입문은 운영시간 동안 일반 보행자에게 열린다.
- Memory 위치: campus-wiki/temporary-parking/03
- 열람 대상: 전체
- 기준선 상태: 수정 대상

### T1-W-021

- 본문: 본관 로비에서 지하주차장으로 내려가는 내부 계단은 운영시간 동안 이용할 수 있다.
- Memory 위치: campus-wiki/temporary-parking/04
- 열람 대상: 전체
- 기준선 상태: 수정 대상

### T1-W-022

- 본문: C 야외주차장은 본관 지하주차장과 별개의 진입로를 사용한다.
- Memory 위치: campus-wiki/temporary-parking/05-separate-access-road
- 열람 대상: 전체
- 기준선 상태: 영향 판정 지원

### T1-W-110

- 본문: C 야외주차장은 본관 공사구역 밖에 있다.
- Memory 위치: campus-wiki/temporary-parking/05-outside-work-zone
- 열람 대상: 전체
- 기준선 상태: 영향 판정 지원

### T1-W-023

- 본문: A 야외주차장–본관–중앙도서관 경로는 평상시 주차 뒤 도서관으로 가는 가장 짧은 동선 중 하나다.
- Memory 위치: campus-wiki/temporary-parking/06
- 열람 대상: 전체
- 기준선 상태: 영향 판정 지원

### T1-W-024

- 본문: 한 주차구역의 폐쇄를 캠퍼스 전체 주차 금지로 확대 해석하지 마라.
- Memory 위치: campus-wiki/temporary-parking/07-no-campuswide-generalization
- 열람 대상: 전체
- 기준선 상태: 영향 판정 지원

### T1-W-111

- 본문: 이용 가능한 대체 주차구역을 별도로 확인하라.
- Memory 위치: campus-wiki/temporary-parking/07-check-alternatives
- 열람 대상: 전체
- 기준선 상태: 영향 판정 지원

### T1-W-025

- 본문: 처음 방문하는 운전자는 본관과 가장 가까운 주차장에 일반 주차 공간이 있을 것으로 기대하는 경우가 많다.
- Memory 위치: campus-wiki/temporary-parking/08
- 열람 대상: 방문자
- 기준선 상태: 수정 대상

### T1-W-141

- 본문: 이동 지원이 필요한 방문객은 accessible entrance 가까이에 안전한 승하차 지점이 있기를 기대한다.
- Memory 위치: campus-wiki/temporary-parking/08-visitor-accessible-dropoff
- 열람 대상: 방문자
- 기준선 상태: 비영향

### T1-W-142

- 본문: 짐이 있는 방문객은 본관 입구 가까이에서 잠시 하역할 수 있기를 기대한다.
- Memory 위치: campus-wiki/temporary-parking/08-visitor-loading
- 열람 대상: 방문자
- 기준선 상태: 비영향

### T1-W-143

- 본문: 교직원은 소속 출입 자격이 있으면 본관 인접 주차장도 이용할 수 있다고 기대하는 경우가 많다.
- Memory 위치: campus-wiki/temporary-parking/08-staff-parking
- 열람 대상: 교직원
- 기준선 상태: 비영향

### T1-W-144

- 본문: 이동 지원이 필요한 교직원은 accessible entrance 가까운 승하차 지점을 우선 선호한다.
- Memory 위치: campus-wiki/temporary-parking/08-staff-accessible-dropoff
- 열람 대상: 교직원
- 기준선 상태: 비영향

### T1-W-145

- 본문: 장비를 운반하는 교직원은 목적 공간과 가까운 하역 지점을 선호한다.
- Memory 위치: campus-wiki/temporary-parking/08-staff-loading
- 열람 대상: 교직원
- 기준선 상태: 비영향
### T1-W-026

- 본문: 주차 안내 에이전트는 게시된 개방 상태를 설명할 수 있다.
- Memory 위치: campus-wiki/temporary-parking/09-explain-status-connections
- 열람 대상: 전체
- 기준선 상태: 수정 대상

### T1-W-146

- 본문: 주차 안내 에이전트는 게시된 연결 동선을 설명할 수 있다.
- Memory 위치: campus-wiki/temporary-parking/09-explain-connections
- 열람 대상: 전체
- 기준선 상태: 비영향
### T1-W-112

- 본문: 주차 안내 에이전트는 실시간 빈자리를 확인할 수 없다.
- Memory 위치: campus-wiki/temporary-parking/09-no-live-vacancy
- 열람 대상: 전체
- 기준선 상태: 수정 대상

### T1-W-113

- 본문: 주차 안내 에이전트는 현장 통제 해제 시각을 보장할 수 없다.
- Memory 위치: campus-wiki/temporary-parking/09-no-release-guarantee
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-132

- 본문: 배송 기사와 외부 유지보수 업체는 A 야외주차장 가장자리에서 짧게 하역할 수 있을 것으로 기대하는 경우가 있다.
- Memory 위치: campus-wiki/temporary-parking/10
- 열람 대상: 방문자·공사·건물 관계자
- 기준선 상태: 수정 대상

### T1-W-187

- 본문: C 야외주차장은 게시된 운영시간에 방문 차량을 받는다.
- Memory 위치: campus-wiki/temporary-parking/11-c-lot-visitors
- 열람 대상: 전체
- 기준선 상태: 수정 대상

### T1-W-188

- 본문: 방문 차량의 주차 등록 방법은 주차구역 입구 안내판에 게시된다.
- Memory 위치: campus-wiki/temporary-parking/12-visitor-registration
- 열람 대상: 방문자
- 기준선 상태: 비영향

### T1-W-189

- 본문: accessible parking 구역을 이용하려면 유효한 주차 표지가 필요하다.
- Memory 위치: campus-wiki/temporary-parking/13-accessible-permit
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-190

- 본문: C 야외주차장의 accessible parking 구역은 학생센터 방향 보행로 가까이에 있다.
- Memory 위치: campus-wiki/temporary-parking/14-c-accessible-location
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-191

- 본문: 본관 정문 앞 승하차 구역은 장시간 주차 공간이 아니다.
- Memory 위치: campus-wiki/temporary-parking/15-dropoff-not-parking
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-192

- 본문: 단기 하역 공간의 최대 이용시간은 현장 표지에 표시된다.
- Memory 위치: campus-wiki/temporary-parking/16-loading-time-limit
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-193

- 본문: 이륜차는 캠퍼스 지도에 표시된 이륜차 구역에 주차한다.
- Memory 위치: campus-wiki/temporary-parking/17-motorcycle-area
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-194

- 본문: 자전거는 차량 주차면이 아니라 지정된 자전거 거치대에 세운다.
- Memory 위치: campus-wiki/temporary-parking/18-bicycle-racks
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-195

- 본문: C 야외주차장에는 전기차 충전 주차면이 있다.
- Memory 위치: campus-wiki/temporary-parking/19-ev-charging
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-196

- 본문: 전기차 충전 주차면은 충전 중인 차량을 위한 공간이다.
- Memory 위치: campus-wiki/temporary-parking/20-ev-use
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-197

- 본문: 방문 주차 요금은 주차 등록 화면에 표시된다.
- Memory 위치: campus-wiki/temporary-parking/21-posted-fees
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-198

- 본문: 주차 안내 에이전트는 게시되지 않은 할인 요금을 추정할 수 없다.
- Memory 위치: campus-wiki/temporary-parking/22-no-unlisted-discount
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-199

- 본문: 공휴일의 주차 운영시간은 평일 운영시간과 다를 수 있다.
- Memory 위치: campus-wiki/temporary-parking/23-holiday-hours
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-200

- 본문: 폭설이나 결빙이 있으면 야외주차장 일부가 일시 통제될 수 있다.
- Memory 위치: campus-wiki/temporary-parking/24-winter-control
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-201

- 본문: 대규모 공개 행사가 있는 날에는 행사장 인근 주차 수요가 늘어난다.
- Memory 위치: campus-wiki/temporary-parking/25-event-demand
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-202

- 본문: 이동 지원이 필요한 운전자는 주차면에서 목적지까지 계단 없는 accessible route가 이어지기를 기대한다.
- Memory 위치: campus-wiki/temporary-parking/26-accessible-route-demand
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-203

- 본문: 처음 방문하는 운전자는 A 야외주차장과 C 야외주차장을 혼동하는 경우가 있다.
- Memory 위치: campus-wiki/temporary-parking/27-lot-confusion
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-204

- 본문: 주차 안내 에이전트는 현장 통제 표지의 설치 여부를 실시간으로 확인할 수 없고, 게시된 주차면 상태만으로 이용 가능 여부를 판단한다.
- Memory 위치: campus-wiki/temporary-parking/28-no-live-closure-sign-state
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-205

- 본문: 서문 정류장은 C 야외주차장 바깥쪽 보행로에 있다.
- Memory 위치: campus-wiki/temporary-parking/29-west-gate-stop
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-206

- 본문: 캠퍼스 순환차는 학생센터 앞 순환차 정류장에 선다.
- Memory 위치: campus-wiki/temporary-parking/30-campus-shuttle-stop
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-207

- 본문: 캠퍼스 순환차의 운행시간은 학기와 방학에 따라 달라진다.
- Memory 위치: campus-wiki/temporary-parking/31-shuttle-calendar
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-208

- 본문: 주차 안내 에이전트는 공개 지도에 있는 주차장 진입로를 설명할 수 있다.
- Memory 위치: campus-wiki/temporary-parking/32-explain-entrances
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-209

- 본문: 주차 안내 에이전트는 방문 차량을 대신 등록할 수 없다.
- Memory 위치: campus-wiki/temporary-parking/33-no-registration
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-210

- 본문: 주차 안내 에이전트는 주차 요금을 면제할 수 없다.
- Memory 위치: campus-wiki/temporary-parking/34-no-fee-waiver
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-211

- 본문: 날씨로 인한 주차 통제는 공식 주차 공지에서 확인하라.
- Memory 위치: campus-wiki/temporary-parking/35-check-weather-notice
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-212

- 본문: 한 주차장의 만차 상태를 다른 주차장의 만차로 확대 해석하지 마라.
- Memory 위치: campus-wiki/temporary-parking/36-no-fullness-generalization
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-213

- 본문: 유효한 주차 자격은 특정 주차면의 확보를 보장하지 않는다.
- Memory 위치: campus-wiki/temporary-parking/37-permit-no-space-guarantee
- 열람 대상: 학생·교직원
- 기준선 상태: 비영향

### T1-W-214

- 본문: 본관 정문 앞에는 accessible 승하차 구역이 표시되어 있다.
- Memory 위치: campus-wiki/temporary-parking/38-accessible-dropoff
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-215

- 본문: C 야외주차장의 공유차량 전용면은 표지로 구분되어 있다.
- Memory 위치: campus-wiki/temporary-parking/39-shared-vehicle-spaces
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-216

- 본문: 통행로나 accessible parking 구역을 막은 차량은 주차 관리 창구에 신고하라.
- Memory 위치: campus-wiki/temporary-parking/40-report-obstruction
- 열람 대상: 전체
- 기준선 상태: 비영향

## 상점·식음·서비스 · 50개

### T1-W-027

- 본문: 본관 1층 캠퍼스스토어는 방학 중에도 오전 7시부터 오후 11시까지 운영한다.
- Memory 위치: campus-wiki/shop-updates/01
- 열람 대상: 전체
- 기준선 상태: 수정 대상

### T1-W-028

- 본문: 공학관 캠퍼스스토어의 방학 중 통상 운영시간은 오전 9시부터 오후 6시까지다.
- Memory 위치: campus-wiki/shop-updates/02
- 열람 대상: 전체
- 기준선 상태: 수정 대상

### T1-W-029

- 본문: 본관 1층 카페는 여름방학에도 운영한다.
- Memory 위치: campus-wiki/shop-updates/03
- 열람 대상: 전체
- 기준선 상태: 수정 대상

### T1-W-147

- 본문: 본관 1층 식사 공간은 여름방학에도 운영한다.
- Memory 위치: campus-wiki/shop-updates/03-dining
- 열람 대상: 전체
- 기준선 상태: 수정 대상
### T1-W-030

- 본문: 본관 1층 이노베이션 허브 안에는 커피머신이 있다.
- Memory 위치: campus-wiki/shop-updates/04-location
- 열람 대상: 교직원
- 기준선 상태: 누락 보완

### T1-W-114

- 본문: 본관 1층 이노베이션 허브 안의 커피머신은 교직원만 사용할 수 있다.
- Memory 위치: campus-wiki/shop-updates/04-staff-only
- 열람 대상: 교직원
- 기준선 상태: 누락 보완

### T1-W-031

- 본문: 서편 복합관의 ATM은 본관 안의 ATM과 별개다.
- Memory 위치: campus-wiki/shop-updates/05-distinct-atm
- 열람 대상: 전체
- 기준선 상태: 영향 판정 지원

### T1-W-115

- 본문: 서편 복합관의 ATM은 A 야외주차장 옆 건물에 있다.
- Memory 위치: campus-wiki/shop-updates/05-by-a-lot
- 열람 대상: 전체
- 기준선 상태: 영향 판정 지원

### T1-W-032

- 본문: 저녁에 현금이 필요한 학생은 본관 ATM을 언제든 이용할 수 있으리라 기대하는 경우가 많다.
- Memory 위치: campus-wiki/shop-updates/06
- 열람 대상: 전체
- 기준선 상태: 수정 대상

### T1-W-148

- 본문: 늦은 시간에 간단한 물품이 필요한 학생은 본관 24시간 매장이 열려 있으리라 기대한다.
- Memory 위치: campus-wiki/shop-updates/06-24-hour-store
- 열람 대상: 전체
- 기준선 상태: 영향 판정 지원
### T1-W-033

- 본문: 폐쇄 시설과 같은 종류의 대체 장소를 확인해 안내하라.
- Memory 위치: campus-wiki/shop-updates/07-same-type-replacement
- 열람 대상: 전체
- 기준선 상태: 영향 판정 지원

### T1-W-116

- 본문: 서편 복합관 시설과 본관 시설을 같은 곳으로 취급하지 마라.
- Memory 위치: campus-wiki/shop-updates/07-no-facility-conflation
- 열람 대상: 전체
- 기준선 상태: 영향 판정 지원

### T1-W-034

- 본문: 편의시설 안내 에이전트는 게시된 위치를 답할 수 있다.
- Memory 위치: campus-wiki/shop-updates/08-answer-location-hours
- 열람 대상: 전체
- 기준선 상태: 수정 대상

### T1-W-149

- 본문: 편의시설 안내 에이전트는 게시된 운영시간을 답할 수 있다.
- Memory 위치: campus-wiki/shop-updates/08-answer-hours
- 열람 대상: 전체
- 기준선 상태: 비영향
### T1-W-117

- 본문: 편의시설 안내 에이전트는 상품 재고를 확인할 수 없다.
- Memory 위치: campus-wiki/shop-updates/08-no-stock
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-118

- 본문: 편의시설 안내 에이전트는 결제 가능 여부를 확인할 수 없다.
- Memory 위치: campus-wiki/shop-updates/08-no-payment-status
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-119

- 본문: 편의시설 안내 에이전트는 당일의 돌발 휴점을 확인할 수 없다.
- Memory 위치: campus-wiki/shop-updates/08-no-surprise-closure
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-133

- 본문: 캠퍼스스토어 위탁 운영업체는 저녁 시간 학생들이 본관 ATM과 24시간 매장을 함께 이용하는 경향을 수요 계획에 반영한다.
- Memory 위치: campus-wiki/shop-updates/09
- 열람 대상: 전체
- 기준선 상태: 수정 대상

### T1-W-217

- 본문: 공학관 캠퍼스스토어는 학용품과 기본 생활용품을 판매한다.
- Memory 위치: campus-wiki/shop-updates/10-engineering-store-goods
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-218

- 본문: 본관 캠퍼스스토어의 반품 조건은 매장 영수증 안내에 게시된다.
- Memory 위치: campus-wiki/shop-updates/11-return-policy
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-219

- 본문: 캠퍼스스토어에서 판매하는 상품의 가격은 각 매장이 정한다.
- Memory 위치: campus-wiki/shop-updates/12-store-pricing
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-220

- 본문: 본관 식사 공간의 당일 메뉴는 입구의 메뉴판에 게시된다.
- Memory 위치: campus-wiki/shop-updates/13-daily-menu
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-221

- 본문: 식사 메뉴의 주요 알레르기 유발 성분 표시는 메뉴판에서 확인할 수 있다.
- Memory 위치: campus-wiki/shop-updates/14-allergen-labels
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-222

- 본문: 식음 안내 에이전트는 조리 공간의 교차접촉이 없다고 보장할 수 없다.
- Memory 위치: campus-wiki/shop-updates/15-no-cross-contact-guarantee
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-223

- 본문: 채식 선택지는 당일 메뉴판의 식단 기호로 표시된다.
- Memory 위치: campus-wiki/shop-updates/16-vegetarian-label
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-224

- 본문: 본관 1층에는 개인 물병을 채울 수 있는 음수대가 있다.
- Memory 위치: campus-wiki/shop-updates/17-bottle-filling
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-225

- 본문: 본관 카페의 일반 좌석은 개별 예약을 받지 않는다.
- Memory 위치: campus-wiki/shop-updates/18-cafe-seating
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-226

- 본문: 학생센터 공용 라운지에는 이용자가 쓸 수 있는 전자레인지가 있다.
- Memory 위치: campus-wiki/shop-updates/19-student-centre-microwave
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-227

- 본문: 본관 2층에는 음료 자동판매기가 있다.
- Memory 위치: campus-wiki/shop-updates/20-floor-2-vending
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-228

- 본문: 본관 5층에는 간식 자동판매기가 있다.
- Memory 위치: campus-wiki/shop-updates/21-floor-5-vending
- 열람 대상: 학생·교직원
- 기준선 상태: 비영향

### T1-W-229

- 본문: 본관과 서편 복합관의 ATM은 서로 다른 운영기관이 관리한다.
- Memory 위치: campus-wiki/shop-updates/22-atm-operators
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-230

- 본문: 편의시설 안내 에이전트는 ATM 거래 내역을 열람하거나 거래 오류의 원인을 확인할 수 없다.
- Memory 위치: campus-wiki/shop-updates/23-no-atm-transactions
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-231

- 본문: ATM 카드 회수나 거래 오류는 해당 ATM 운영기관에 문의하라.
- Memory 위치: campus-wiki/shop-updates/24-atm-provider-support
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-232

- 본문: 방문자 서비스 창구의 운영시간은 본관 안내 페이지에 게시된다.
- Memory 위치: campus-wiki/shop-updates/25-visitor-services-hours
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-233

- 본문: 방문자 서비스 창구는 캠퍼스 지도와 공개 시설 안내를 제공한다.
- Memory 위치: campus-wiki/shop-updates/26-visitor-services-scope
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-234

- 본문: 일반 시설 문의는 공개 온라인 문의 양식으로 제출할 수 있다.
- Memory 위치: campus-wiki/shop-updates/27-online-inquiry-form
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-235

- 본문: 학생지원 업무 중 개인 기록을 다루는 서비스는 본인 확인이 필요하다.
- Memory 위치: campus-wiki/shop-updates/28-student-service-verification
- 열람 대상: 학생
- 기준선 상태: 비영향

### T1-W-236

- 본문: 방문자는 캠퍼스의 공개 게스트 네트워크를 이용할 수 있다.
- Memory 위치: campus-wiki/shop-updates/29-guest-network
- 열람 대상: 방문자
- 기준선 상태: 비영향

### T1-W-237

- 본문: 게스트 네트워크의 접속 방법은 방문자 서비스 안내에 게시된다.
- Memory 위치: campus-wiki/shop-updates/30-guest-network-instructions
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-238

- 본문: 공학관 캠퍼스스토어는 본관과 별도 건물에 있고 본관을 통과하지 않는 공개 보행로로 갈 수 있다.
- Memory 위치: campus-wiki/shop-updates/31-engineering-store-separate-route
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-239

- 본문: 편의시설 안내 에이전트는 이용자의 구매 내역을 열람할 수 없다.
- Memory 위치: campus-wiki/shop-updates/32-no-purchase-history
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-240

- 본문: 식음 안내 에이전트는 메뉴에 없는 재료 구성을 추정하지 마라.
- Memory 위치: campus-wiki/shop-updates/33-no-ingredient-guess
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-241

- 본문: 공휴일에는 캠퍼스 상점과 식음시설의 운영시간이 각각 달라질 수 있다.
- Memory 위치: campus-wiki/shop-updates/34-holiday-hours-vary
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-242

- 본문: 시험기간의 연장 운영은 해당 매장의 공식 공지에서 확인하라.
- Memory 위치: campus-wiki/shop-updates/35-exam-hours
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-243

- 본문: 매장 운영자는 상품 재고와 판매 가능 여부를 결정한다.
- Memory 위치: campus-wiki/shop-updates/36-store-operator-control
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-244

- 본문: 수업 사이 시간이 긴 학생은 본관 1층 식사 공간을 편하게 기다릴 수 있는 장소로 선호한다.
- Memory 위치: campus-wiki/shop-updates/37-student-waiting-use
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-245

- 본문: 외부 방문객은 공개 행사와 같은 건물 안에서 카페를 이용할 수 있으리라 기대하는 경우가 많다.
- Memory 위치: campus-wiki/shop-updates/38-event-visitor-cafe
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-246

- 본문: 다회용 용기 반납함은 본관 1층 식사 공간 출구 옆에 있다.
- Memory 위치: campus-wiki/shop-updates/39-reusable-return-bin
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-247

- 본문: 본관 식사 공간에는 휠체어가 접근할 수 있는 좌석이 있다.
- Memory 위치: campus-wiki/shop-updates/40-accessible-dining-seating
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-248

- 본문: 서비스 이용 문제는 해당 시설의 게시된 문의 창구에 전달하도록 안내하라.
- Memory 위치: campus-wiki/shop-updates/41-service-feedback
- 열람 대상: 전체
- 기준선 상태: 비영향

## 시설·층별 구성 · 50개

### T1-W-035

- 본문: 처음 방문하는 이용자는 1층 방문자 서비스 창구에서 목적지를 바로 안내받을 수 있으리라 기대한다.
- Memory 위치: campus-wiki/facility-updates/01
- 열람 대상: 전체
- 기준선 상태: 수정 대상

### T1-W-036

- 본문: 본관 2층에는 학생지원 행정실이 있다.
- Memory 위치: campus-wiki/facility-updates/02
- 열람 대상: 전체
- 기준선 상태: 수정 대상

### T1-W-150

- 본문: 본관 2층에는 공용 상담실이 있다.
- Memory 위치: campus-wiki/facility-updates/02-counseling-room
- 열람 대상: 전체
- 기준선 상태: 수정 대상

### T1-W-151

- 본문: 본관 2층에는 일반 화장실이 있다.
- Memory 위치: campus-wiki/facility-updates/02-general-restroom
- 열람 대상: 전체
- 기준선 상태: 수정 대상

### T1-W-152

- 본문: 본관 2층에는 accessible restroom이 있다.
- Memory 위치: campus-wiki/facility-updates/02-accessible-restroom
- 열람 대상: 전체
- 기준선 상태: 수정 대상
### T1-W-037

- 본문: 본관 3층에는 후문이 있다.
- Memory 위치: campus-wiki/facility-updates/03
- 열람 대상: 전체
- 기준선 상태: 수정 대상

### T1-W-153

- 본문: 본관 3층에는 중앙도서관 방향 연결 통로가 있다.
- Memory 위치: campus-wiki/facility-updates/03-library-corridor
- 열람 대상: 전체
- 기준선 상태: 수정 대상

### T1-W-154

- 본문: 본관 3층에는 세미나실이 있다.
- Memory 위치: campus-wiki/facility-updates/03-seminar-room
- 열람 대상: 전체
- 기준선 상태: 수정 대상

### T1-W-155

- 본문: 본관 3층에는 일반 화장실이 있다.
- Memory 위치: campus-wiki/facility-updates/03-general-restroom
- 열람 대상: 전체
- 기준선 상태: 수정 대상

### T1-W-156

- 본문: 본관 3층에는 accessible restroom이 있다.
- Memory 위치: campus-wiki/facility-updates/03-accessible-restroom
- 열람 대상: 전체
- 기준선 상태: 수정 대상
### T1-W-038

- 본문: 본관 4층에는 학과 사무실이 있다.
- Memory 위치: campus-wiki/facility-updates/04
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-157

- 본문: 본관 4층에는 공용 회의실이 있다.
- Memory 위치: campus-wiki/facility-updates/04-meeting-room
- 열람 대상: 전체
- 기준선 상태: 비영향
### T1-W-039

- 본문: 본관 5층에는 연구실이 있다.
- Memory 위치: campus-wiki/facility-updates/05
- 열람 대상: 학생·교직원
- 기준선 상태: 영향 판정 지원

### T1-W-158

- 본문: 본관 5층에는 세미나실이 있다.
- Memory 위치: campus-wiki/facility-updates/05-seminar-room
- 열람 대상: 학생·교직원
- 기준선 상태: 영향 판정 지원

### T1-W-159

- 본문: 본관 5층 일부 세미나실은 수업에도 사용된다.
- Memory 위치: campus-wiki/facility-updates/05-seminar-class-use
- 열람 대상: 학생·교직원
- 기준선 상태: 영향 판정 지원
### T1-W-040

- 본문: 본관 6층에는 공동연구실이 있다.
- Memory 위치: campus-wiki/facility-updates/06
- 열람 대상: 학생·교직원
- 기준선 상태: 영향 판정 지원

### T1-W-160

- 본문: 본관 6층에는 세미나실이 있다.
- Memory 위치: campus-wiki/facility-updates/06-seminar-room
- 열람 대상: 학생·교직원
- 기준선 상태: 영향 판정 지원

### T1-W-161

- 본문: 본관 6층 일부 세미나실은 수업에도 사용된다.
- Memory 위치: campus-wiki/facility-updates/06-seminar-class-use
- 열람 대상: 학생·교직원
- 기준선 상태: 영향 판정 지원
### T1-W-041

- 본문: 본관 7층에는 연구지원실이 있다.
- Memory 위치: campus-wiki/facility-updates/07
- 열람 대상: 교직원
- 기준선 상태: 비영향

### T1-W-162

- 본문: 본관 7층에는 연구자 공용 업무공간이 있다.
- Memory 위치: campus-wiki/facility-updates/07-shared-workspace
- 열람 대상: 교직원
- 기준선 상태: 비영향
### T1-W-042

- 본문: 본관 8층에는 교직원 사무실이 있다.
- Memory 위치: campus-wiki/facility-updates/08
- 열람 대상: 교직원
- 기준선 상태: 비영향

### T1-W-163

- 본문: 본관 8층에는 소규모 회의실이 있다.
- Memory 위치: campus-wiki/facility-updates/08-small-meeting-room
- 열람 대상: 교직원
- 기준선 상태: 비영향
### T1-W-043

- 본문: 본관 9층에는 행정 사무실이 있다.
- Memory 위치: campus-wiki/facility-updates/09
- 열람 대상: 교직원
- 기준선 상태: 비영향

### T1-W-164

- 본문: 본관 9층에는 10층 행사 지원실이 있다.
- Memory 위치: campus-wiki/facility-updates/09-event-support-room
- 열람 대상: 교직원
- 기준선 상태: 비영향
### T1-W-044

- 본문: 본관 10층에는 전시·행사홀이 있다.
- Memory 위치: campus-wiki/facility-updates/10
- 열람 대상: 전체
- 기준선 상태: 수정 대상

### T1-W-165

- 본문: 본관 10층에는 행사 준비실이 있다.
- Memory 위치: campus-wiki/facility-updates/10-event-prep-room
- 열람 대상: 전체
- 기준선 상태: 수정 대상
### T1-W-045

- 본문: 공개된 층별 시설과 임시 운영 공지를 함께 확인해 안내하라.
- Memory 위치: campus-wiki/facility-updates/11-check-public-notices
- 열람 대상: 전체
- 기준선 상태: 영향 판정 지원

### T1-W-120

- 본문: 비공개 공사 범위를 추정하지 마라.
- Memory 위치: campus-wiki/facility-updates/11-no-private-inference
- 열람 대상: 전체
- 기준선 상태: 영향 판정 지원

### T1-W-166

- 본문: 현장 점검 결과를 추정하지 마라.
- Memory 위치: campus-wiki/facility-updates/11-no-inspection-inference
- 열람 대상: 전체
- 기준선 상태: 영향 판정 지원
### T1-W-134

- 본문: 청소·보안 용역 직원은 교대 때 일반 이용자와 분리된 서비스 동선을 선호한다.
- Memory 위치: campus-wiki/facility-updates/12
- 열람 대상: 교직원·공사·건물 관계자
- 기준선 상태: 수정 대상

### T1-W-249

- 본문: 본관 1층에는 정문 로비가 있다.
- Memory 위치: campus-wiki/facility-updates/13-floor-1-lobby
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-250

- 본문: 본관 1층에는 방문자 서비스 창구가 있다.
- Memory 위치: campus-wiki/facility-updates/14-floor-1-visitor-services
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-251

- 본문: 본관 1층에는 이노베이션 허브가 있다.
- Memory 위치: campus-wiki/facility-updates/15-floor-1-innovation-hub
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-252

- 본문: 본관 1층에는 일반 화장실이 있다.
- Memory 위치: campus-wiki/facility-updates/16-floor-1-restroom
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-253

- 본문: 본관 1층에는 accessible restroom이 있다.
- Memory 위치: campus-wiki/facility-updates/17-floor-1-accessible-restroom
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-254

- 본문: 본관 2층 엘리베이터 로비는 학생지원 행정실 가까이에 있다.
- Memory 위치: campus-wiki/facility-updates/18-floor-2-elevator-lobby
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-255

- 본문: 본관 3층 엘리베이터 로비는 중앙도서관 방향 통로 가까이에 있다.
- Memory 위치: campus-wiki/facility-updates/19-floor-3-elevator-lobby
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-256

- 본문: 본관 4층 학과 사무실의 이름은 층별 안내판에 표시된다.
- Memory 위치: campus-wiki/facility-updates/20-floor-4-directory
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-257

- 본문: 본관 4층에는 학생이 이용할 수 있는 공용 인쇄 지점이 있다.
- Memory 위치: campus-wiki/facility-updates/21-floor-4-printing
- 열람 대상: 학생
- 기준선 상태: 비영향

### T1-W-258

- 본문: 본관 5층 연구실은 일반 공개 공간이 아니다.
- Memory 위치: campus-wiki/facility-updates/22-floor-5-restricted-labs
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-259

- 본문: 본관 6층 공동연구실은 승인된 연구 구성원이 이용한다.
- Memory 위치: campus-wiki/facility-updates/23-floor-6-research-access
- 열람 대상: 학생·교직원
- 기준선 상태: 비영향

### T1-W-260

- 본문: 본관 7층 연구지원실의 상담은 게시된 예약 방식에 따른다.
- Memory 위치: campus-wiki/facility-updates/24-floor-7-appointments
- 열람 대상: 학생·교직원
- 기준선 상태: 비영향

### T1-W-261

- 본문: 본관 8층 교직원 사무실 방문자는 약속한 담당자가 예정 시각에 사무실에 있을 것으로 기대한다.
- Memory 위치: campus-wiki/facility-updates/25-floor-8-visitor-appointment
- 열람 대상: 방문자·교직원
- 기준선 상태: 비영향

### T1-W-262

- 본문: 본관 9층의 공개 행정 서비스는 부서별 운영시간에 제공된다.
- Memory 위치: campus-wiki/facility-updates/26-floor-9-service-hours
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-263

- 본문: 본관 엘리베이터는 지하주차장 층부터 10층까지 연결한다.
- Memory 위치: campus-wiki/facility-updates/27-elevator-floor-range
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-264

- 본문: 층별 안내 에이전트는 공개된 시설의 층과 공간 이름을 설명할 수 있다.
- Memory 위치: campus-wiki/facility-updates/28-agent-floor-directory
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-265

- 본문: 층별 안내 에이전트는 회의실의 현재 점유 상태를 확인할 수 없다.
- Memory 위치: campus-wiki/facility-updates/29-no-live-room-occupancy
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-266

- 본문: 처음 방문하는 이용자는 층 번호보다 부서 이름에 더 익숙해 부서명 중심 안내를 이해하기 쉽다.
- Memory 위치: campus-wiki/facility-updates/30-users-ask-department
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-267

- 본문: 공휴일에는 본관이 열려 있어도 일부 행정 사무실이 운영하지 않을 수 있다.
- Memory 위치: campus-wiki/facility-updates/31-office-holiday-closure
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-268

- 본문: 층별 안내 에이전트는 공개 층별 정보가 실제 배치와 일치하는지 문의 시점에 실시간으로 검증할 수 없다.
- Memory 위치: campus-wiki/facility-updates/32-no-live-layout-verification
- 열람 대상: 전체
- 기준선 상태: 비영향

## 동선·접근성 · 50개

### T1-W-046

- 본문: 본관 3층 후문은 중앙도서관으로 이어지는 보행 동선과 직접 연결된다.
- Memory 위치: campus-wiki/route-changes/01
- 열람 대상: 전체
- 기준선 상태: 수정 대상

### T1-W-047

- 본문: 정문을 등지고 보면 A 야외주차장은 왼쪽에 있다.
- Memory 위치: campus-wiki/route-changes/02-a-lot-left
- 열람 대상: 전체
- 기준선 상태: 영향 판정 지원

### T1-W-121

- 본문: 정문을 등지고 보면 서편 복합관은 왼쪽에 있다.
- Memory 위치: campus-wiki/route-changes/02-west-complex-left
- 열람 대상: 전체
- 기준선 상태: 영향 판정 지원

### T1-W-122

- 본문: 정문을 등지고 보면 인문관은 오른쪽에 있다.
- Memory 위치: campus-wiki/route-changes/02-humanities-right
- 열람 대상: 전체
- 기준선 상태: 영향 판정 지원

### T1-W-123

- 본문: 학생센터는 중앙도서관 뒤편에 있다.
- Memory 위치: campus-wiki/route-changes/02-student-centre-behind-library
- 열람 대상: 전체
- 기준선 상태: 영향 판정 지원

### T1-W-048

- 본문: A 야외주차장–본관–중앙도서관 경로는 평상시 짧다.
- Memory 위치: campus-wiki/route-changes/03-short
- 열람 대상: 전체
- 기준선 상태: 수정 대상

### T1-W-124

- 본문: A 야외주차장–본관–중앙도서관 경로는 실내 구간이 길다.
- Memory 위치: campus-wiki/route-changes/03-long-indoor
- 열람 대상: 전체
- 기준선 상태: 수정 대상

### T1-W-049

- 본문: C 야외주차장–학생센터 accessible entrance–중앙도서관 서측 출입구 경로는 본관을 통과하지 않는다.
- Memory 위치: campus-wiki/route-changes/04
- 열람 대상: 전체
- 기준선 상태: 영향 판정 지원

### T1-W-050

- 본문: 학생들은 여름에 냉방되는 본관 1층부터 3층까지의 실내 경로를 야외 경로보다 선호한다.
- Memory 위치: campus-wiki/route-changes/05
- 열람 대상: 전체
- 기준선 상태: 수정 대상

### T1-W-051

- 본문: 현재 개방이 확인된 경로만 추천하라.
- Memory 위치: campus-wiki/route-changes/06-confirm-open
- 열람 대상: 전체
- 기준선 상태: 영향 판정 지원

### T1-W-125

- 본문: 일반 최단경로와 accessible route를 구분해 설명하라.
- Memory 위치: campus-wiki/route-changes/06-distinguish-route-types
- 열람 대상: 전체
- 기준선 상태: 영향 판정 지원

### T1-W-052

- 본문: 동선 안내 에이전트는 저장된 지형정보로 경로를 비교할 수 있다.
- Memory 위치: campus-wiki/route-changes/07-compare-stored-routes
- 열람 대상: 전체
- 기준선 상태: 수정 대상

### T1-W-126

- 본문: 동선 안내 에이전트는 실시간 혼잡을 확인할 수 없다.
- Memory 위치: campus-wiki/route-changes/07-no-live-congestion
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-127

- 본문: 동선 안내 에이전트는 이동식 장애물을 확인할 수 없다.
- Memory 위치: campus-wiki/route-changes/07-no-movable-obstacles
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-128

- 본문: 동선 안내 에이전트는 문의 시점에 새로 설치된 임시 표지나 이동식 통제선을 실시간으로 확인할 수 없다.
- Memory 위치: campus-wiki/route-changes/07-no-live-site-changes
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-053

- 본문: 본관 오른쪽 계단 방향에는 휠체어가 지날 수 있는 연속된 accessible route가 부족하다.
- Memory 위치: campus-wiki/route-changes/08-no-continuous-accessible-route
- 열람 대상: 전체
- 기준선 상태: 누락 보완

### T1-W-129

- 본문: 본관 오른쪽 계단 방향에서 학생센터까지의 우회 거리는 길다.
- Memory 위치: campus-wiki/route-changes/08-long-detour
- 열람 대상: 전체
- 기준선 상태: 누락 보완

### T1-W-135

- 본문: 이동 지원 동행인은 본관 실내 경로를 중앙도서관까지 날씨 영향을 덜 받는 동선으로 선호한다.
- Memory 위치: campus-wiki/route-changes/09
- 열람 대상: 전체
- 기준선 상태: 수정 대상

### T1-W-269

- 본문: 공개 캠퍼스 지도에는 건물 출입구와 건물 사이의 보행로가 표시된다.
- Memory 위치: campus-wiki/route-changes/10-public-campus-map
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-270

- 본문: 공개 캠퍼스 지도에는 계단 없는 accessible route가 별도로 표시된다.
- Memory 위치: campus-wiki/route-changes/11-map-accessible-routes
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-271

- 본문: 본관 정문 앞 보행로에는 accessible ramp 방향을 알리는 표지가 있다.
- Memory 위치: campus-wiki/route-changes/12-ramp-signage
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-272

- 본문: C 야외주차장에서 학생센터 accessible entrance까지 계단 없는 보행로가 이어진다.
- Memory 위치: campus-wiki/route-changes/13-c-lot-student-centre
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-273

- 본문: 학생센터에서 중앙도서관 서측 출입구까지 accessible route가 이어진다.
- Memory 위치: campus-wiki/route-changes/14-student-centre-library
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-274

- 본문: 서편 복합관에서 본관 정문까지 가는 지상 보행로가 있다.
- Memory 위치: campus-wiki/route-changes/15-west-complex-main
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-275

- 본문: 인문관에서 본관 정문까지 가는 보행로는 본관 오른쪽 계단 앞을 지난다.
- Memory 위치: campus-wiki/route-changes/16-humanities-main
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-276

- 본문: 본관 1층 로비에서 엘리베이터를 이용하면 3층 후문 높이까지 계단 없이 이동할 수 있다.
- Memory 위치: campus-wiki/route-changes/17-lobby-to-floor-3
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-277

- 본문: 본관 에스컬레이터 경로에는 계단을 피할 수 없는 구간이 있다.
- Memory 위치: campus-wiki/route-changes/18-escalator-not-step-free
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-278

- 본문: 계단 없는 이동이 필요한 경우 에스컬레이터가 아니라 엘리베이터 경로를 안내하라.
- Memory 위치: campus-wiki/route-changes/19-use-elevator-route
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-279

- 본문: 본관 정문에서 가장 가까운 엘리베이터는 1층 로비 안쪽에 있다.
- Memory 위치: campus-wiki/route-changes/20-nearest-elevator
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-280

- 본문: 본관과 중앙도서관 사이의 지상 경로에는 중간 휴식 벤치가 있다.
- Memory 위치: campus-wiki/route-changes/21-rest-bench
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-281

- 본문: 솔빛광장은 본관 정문과 서편 복합관 사이에 있다.
- Memory 위치: campus-wiki/route-changes/22-solbit-plaza
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-282

- 본문: 비나 눈이 오면 야외 경사 보행로의 이동 시간이 평소보다 길어질 수 있다.
- Memory 위치: campus-wiki/route-changes/23-weather-travel-time
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-283

- 본문: 제설 담당자는 눈이 오면 주요 accessible route를 다른 보행로보다 먼저 확보해야 한다고 판단한다.
- Memory 위치: campus-wiki/route-changes/24-snow-clearing-priority
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-284

- 본문: 주차 뒤 도서관으로 가는 학생은 익숙하고 짧은 A 야외주차장–본관–중앙도서관 동선을 선호한다.
- Memory 위치: campus-wiki/route-changes/25-a-lot-library-frequent-route
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-285

- 본문: 수업 교체 시간에는 본관 3층과 중앙도서관 사이 보행량이 늘어난다.
- Memory 위치: campus-wiki/route-changes/26-class-change-crowding
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-286

- 본문: 처음 방문하는 사람은 건물 번호보다 눈에 보이는 시설을 기준으로 한 길 안내를 이해하기 쉽다.
- Memory 위치: campus-wiki/route-changes/27-landmark-questions
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-287

- 본문: 경사진 대지 때문에 처음 방문하는 사람은 본관 1층 정문과 3층 후문의 높이를 혼동하는 경우가 있다.
- Memory 위치: campus-wiki/route-changes/28-elevation-confusion
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-288

- 본문: 배송 기사는 보행자와 섞이지 않는 지정 서비스 동선을 더 예측 가능하고 안전하다고 여긴다.
- Memory 위치: campus-wiki/route-changes/29-delivery-route
- 열람 대상: 방문자·공사·건물 관계자
- 기준선 상태: 비영향

### T1-W-289

- 본문: 동선 안내 에이전트는 현장 혼잡을 실시간으로 확인할 수 없고, 게시된 우회로 중 분기 수가 적은 경로를 비교할 수 있다.
- Memory 위치: campus-wiki/route-changes/30-agent-detour-observation-limit
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-290

- 본문: 동선 안내 에이전트는 공개 지도에서 계단과 엘리베이터 경로를 구분할 수 있다.
- Memory 위치: campus-wiki/route-changes/31-agent-route-types
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-291

- 본문: 동선 안내 에이전트는 문의 시점의 현장 보행량을 측정할 수 없다.
- Memory 위치: campus-wiki/route-changes/32-no-live-footfall
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-292

- 본문: 동선 안내 에이전트는 이용자 개인의 이동 시간을 보장할 수 없다.
- Memory 위치: campus-wiki/route-changes/33-no-time-guarantee
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-293

- 본문: 경로를 안내하기 전에 목적지 출입구의 현재 공지를 확인하라.
- Memory 위치: campus-wiki/route-changes/34-check-destination-notice
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-294

- 본문: 일반 이용자에게 교직원 전용 통로를 우회로로 추천하지 마라.
- Memory 위치: campus-wiki/route-changes/35-no-staff-only-route
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-295

- 본문: 최단경로에 계단이 있으면 이용 가능한 accessible route도 함께 제시하라.
- Memory 위치: campus-wiki/route-changes/36-offer-accessible-option
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-296

- 본문: 비상 상황에는 일반 길안내보다 현장 대피 표지와 안전요원의 지시를 따르도록 안내하라.
- Memory 위치: campus-wiki/route-changes/37-emergency-directions
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-297

- 본문: 서문 정류장에서 본관 정문까지는 솔빛광장을 지나는 보행로가 이어진다.
- Memory 위치: campus-wiki/route-changes/38-west-stop-main
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-298

- 본문: 학생센터 앞 순환차 정류장에서 중앙도서관 서측 출입구까지 계단 없는 경로가 있다.
- Memory 위치: campus-wiki/route-changes/39-shuttle-library-route
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-299

- 본문: 자전거 이용자는 솔빛광장 가장자리의 지정 거치대에서 내려 보행한다.
- Memory 위치: campus-wiki/route-changes/40-bicycle-dismount
- 열람 대상: 전체
- 기준선 상태: 비영향

### T1-W-300

- 본문: 공개 지도에 없는 비공식 지름길을 기본 경로로 제안하지 마라.
- Memory 위치: campus-wiki/route-changes/41-no-unmapped-shortcut
- 열람 대상: 전체
- 기준선 상태: 비영향
