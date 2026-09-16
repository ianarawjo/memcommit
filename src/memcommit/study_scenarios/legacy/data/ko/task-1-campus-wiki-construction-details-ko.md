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

Memory 본문은 아래 Context JSON 파일에서 관리한다. 이 문서는 데이터 계약과 탐색용 인덱스다.

- [`campus-wiki/construction-details/work-bundles`](../native/task-1/task-1-campus-authority/ko/campus-wiki/construction-details/work-bundles/context.json)
- [`campus-wiki/construction-details/dependencies`](../native/task-1/task-1-campus-authority/ko/campus-wiki/construction-details/dependencies/context.json)
- [`campus-wiki/construction-details/report-status`](../native/task-1/task-1-campus-authority/ko/campus-wiki/construction-details/report-status/context.json)
- [`campus-wiki/construction-details/material-control`](../native/task-1/task-1-campus-authority/ko/campus-wiki/construction-details/material-control/context.json)
- [`campus-wiki/construction-details/verification`](../native/task-1/task-1-campus-authority/ko/campus-wiki/construction-details/verification/context.json)
- [`campus-wiki/construction-details/query-policy`](../native/task-1/task-1-campus-authority/ko/campus-wiki/construction-details/query-policy/context.json)
