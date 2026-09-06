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

Memory 본문은 아래 Context JSON 파일에서 관리한다. 이 문서는 데이터 계약과 탐색용 인덱스다.

- [`campus-wiki/building-access`](../native/task-1/task-1-campus-authority/ko/campus-wiki/building-access/context.json)
- [`campus-wiki/event-relocations`](../native/task-1/task-1-campus-authority/ko/campus-wiki/event-relocations/context.json)
- [`campus-wiki/temporary-parking`](../native/task-1/task-1-campus-authority/ko/campus-wiki/temporary-parking/context.json)
- [`campus-wiki/shop-updates`](../native/task-1/task-1-campus-authority/ko/campus-wiki/shop-updates/context.json)
- [`campus-wiki/facility-updates`](../native/task-1/task-1-campus-authority/ko/campus-wiki/facility-updates/context.json)
- [`campus-wiki/route-changes`](../native/task-1/task-1-campus-authority/ko/campus-wiki/route-changes/context.json)
