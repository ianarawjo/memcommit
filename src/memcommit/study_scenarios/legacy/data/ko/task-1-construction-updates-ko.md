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
- 모든 후보 `본문`은 공개 대상 Context, 명시적인 수정·추가 액션, 반영할
  내용을 함께 담은 짧은 업데이트 지시다. 안정적인 대상 Memory ID와 정확한
  before/after 본문은 `task-1-update-actions-ko.tsv`에 검증 sidecar로 남기며,
  update planner가 이를 새로 추론해야 하는 정보로 취급하지 않는다. 항목 안의
  `기준선 관계`는 초기 작성 맥락을 보존한다. 기존 사실을 그대로 유지하거나
  중복 추가하는 후보는 이 업데이트 묶음에 넣지 않는다.
- `열람 대상`은 미래의 공개 의도일 뿐이다. 현재 프로토타입의
  역할 기반 접근 통제를 의미하지 않는다.
- 지명은 모두 가상·일반 명칭이다. 실제 학교명, 도시명, 주소,
  인명, 사업자명은 사용하지 않는다.

Memory 본문은 아래 Context JSON 파일에서 관리한다. 이 문서는 데이터 계약과 탐색용 인덱스다.

- [`participant/construction-updates/building-access`](../native/task-1/task-1/ko/participant/construction-updates/building-access/context.json)
- [`participant/construction-updates/event-relocations`](../native/task-1/task-1/ko/participant/construction-updates/event-relocations/context.json)
- [`participant/construction-updates/temporary-parking`](../native/task-1/task-1/ko/participant/construction-updates/temporary-parking/context.json)
- [`participant/construction-updates/shop-updates`](../native/task-1/task-1/ko/participant/construction-updates/shop-updates/context.json)
- [`participant/construction-updates/facility-updates`](../native/task-1/task-1/ko/participant/construction-updates/facility-updates/context.json)
- [`participant/construction-updates/route-changes`](../native/task-1/task-1/ko/participant/construction-updates/route-changes/context.json)
