# 과제 3 일반 선택 공유 가드레일

이 문서는 Task 3의 향후 `sever` 단계에서 로컬 발신 공유 후보에 적용할
사전 검토 가드레일 75개를 담은 완전한 합성 자료다. `local/guardrails`는 일반 열람
Context이며, 연결된 의료 안내 에이전트의 질의 전용 자료와 분리한다. 기존의
목적·프라이버시·근거·승인·보존 경계를 유지하면서 수신자 권한, 최소화,
전달 채널, 후속 이용, 감사와 복구까지 검토 범위를 확장한다. Guardrails에는
사용자의 공유 선호를 미리 가정하는 User Model을 두지 않는다. 그런 가정은
참가자의 선택을 유도해 연구 행동을 오염시킬 수 있기 때문이다. 그 자리는 외부
데이터 흐름 조건인 World Model과 수신자·조직의 예상 해석인 Other Model로
채운다. `mem sever`는 pass마다 ordinary Criteria Context 하나를 받는다. 이
guardrails를 그 기준으로 사용하거나, 먼저 `mem meld`로 권한이 있는 다른 기준과
결합할 수 있다.

각 `directory/NN` 표시는 `local/guardrails` 아래의 계층형 Memory 위치다. 대괄호의
두 글자 목적 ticker는 제작·검수용 sidecar이며 실제 Memory 본문이 아니다.
실제 Memory 후보는 ticker 뒤의 문장뿐이다. `PP`는 에이전트가 취할 행동을
명령형으로 표현한다. `KB`는 확인된 공유·보안 지식, `SM`은 로컬 에이전트의
역할·능력·관찰 한계, `OM`은 수신자·제삼자·운영자가 무엇을 기대·판단하거나
어떻게 반응할지에 대한 모델, `WM`은 마음과 독립적인 매체·사본·시간·제도
환경의 상태와 제약을 서술한다. 목적 분포는 KB 8, PP 47, SM 4, UM 0,
WM 5, OM 11이다.

## purpose-and-scope

- purpose-and-scope/01 [PP] 사용자가 확인한 현재 공유 목적에 필요한 메모리만 포함하라.
- purpose-and-scope/02 [PP] 한 번 승인된 메모리를 다른 목적으로 재사용하지 마라.
- purpose-and-scope/03 [PP] 현재 목적에 필요하지 않은 세부정보를 공유 후보에서 제외하라.
- purpose-and-scope/04 [PP] 공유 목적이 구체적이지 않으면 후보를 만들기 전에 사용자에게 확인하라.
- purpose-and-scope/05 [KB] 공유 승인의 수신자 범위는 검토된 수신자로 한정된다.
- purpose-and-scope/05-purpose [KB] 공유 승인의 목적 범위는 검토된 목적으로 한정된다.
- purpose-and-scope/05-items [KB] 공유 승인의 항목 범위는 검토된 항목으로 한정된다.
- purpose-and-scope/06 [OM] 수신 에이전트는 별도 제한이 전달되지 않으면 받은 자료를 요청된 범위 안에서 자유롭게 써도 된다고 판단할 수 있다.

## privacy-and-others

- privacy-and-others/01 [PP] 제삼자의 연락처는 현재 목적에 꼭 필요하지 않으면 제외하라.
- privacy-and-others/02 [PP] 제삼자가 작성한 내용은 동의 범위를 확인한 뒤에만 공유하라.
- privacy-and-others/03 [PP] 단편적인 행동 기록에서 민감한 특성을 추론하지 마라.
- privacy-and-others/04 [PP] 재식별 가능성이 있는 희귀한 세부 조합은 공유 전에 일반화하라.
- privacy-and-others/05 [WM] 한 Memory에 사용자 정보와 제삼자 정보가 섞여 있으면, 항목을 그대로 공유할 때 제삼자 정보도 함께 전달된다.
- privacy-and-others/06 [OM] 제삼자는 자신의 정보가 외부 에이전트에 전달될 것이라고 예상하지 않을 수 있다.

## evidence-and-uncertainty

- evidence-and-uncertainty/01 [PP] 시점에 따라 달라지는 내용에는 마지막 확인 시점을 표시하라.
- evidence-and-uncertainty/02 [PP] 확실하지 않은 내용은 불확실하다고 표시하라.
- evidence-and-uncertainty/03 [PP] 충돌이 해소되지 않은 메모리는 어느 한쪽을 현재 사실로 확정하지 마라.
- evidence-and-uncertainty/04 [PP] 각 공유 후보가 근거로 삼은 로컬 메모리를 추적 가능하게 유지하라.
- evidence-and-uncertainty/05 [WM] Memory가 기록된 뒤 사실이 바뀌어도 원본 Memory가 갱신되지 않으면 공유 후보에는 이전 상태가 남는다.
- evidence-and-uncertainty/06 [OM] 수신 에이전트는 표시되지 않은 불확실성을 확인된 사실로 해석할 수 있다.

## approval-and-delivery

- approval-and-delivery/01 [PP] 전송 전에 실제 수신 대상을 사용자에게 보여 주라.
- approval-and-delivery/02 [PP] 전송 전에 수신자의 사용 목적을 사용자에게 보여 주라.
- approval-and-delivery/03 [PP] 전송 전에 전달될 Memory의 정확한 목록을 사용자에게 보여 주라.
- approval-and-delivery/04 [PP] 수신자가 바뀌면 새 승인을 받아라.
- approval-and-delivery/04-purpose [PP] 공유 목적이 바뀌면 새 승인을 받아라.
- approval-and-delivery/04-items [PP] 공유 항목이 바뀌면 새 승인을 받아라.
- approval-and-delivery/05 [SM] 로컬 에이전트는 공유 후보와 수신 범위를 제시할 수 있지만 사용자를 대신해 외부 공유를 승인할 수 없다.
- approval-and-delivery/06 [OM] 수신 조직은 별도 제한이 없으면 받은 입력을 일반 업무기록으로 저장해도 된다고 판단할 수 있다.
- approval-and-delivery/06-forwarding [OM] 수신 조직은 별도 제한이 없으면 내부 처리자에게 입력을 넘겨도 된다고 판단할 수 있다.

## retention-and-revocation

- retention-and-revocation/01 [PP] 공유 초안은 사용자 검토에 필요한 동안만 임시로 유지하라.
- retention-and-revocation/02 [PP] 사용자가 거절한 초안은 재사용 가능한 작업 상태에서 제거하라.
- retention-and-revocation/03 [PP] 제외한 Memory 본문을 수신자에게 전달하지 마라.
- retention-and-revocation/04 [PP] 취소된 공유 항목을 후속 전송에 재사용하지 마라.
- retention-and-revocation/05 [KB] 공유 초안을 제거해도 원본 로컬 Memory는 삭제되지 않는다.
- retention-and-revocation/06 [OM] 철회 통지를 받지 못한 수신자는 이전 승인이 여전히 유효하다고 판단할 수 있다.

## recipient-and-authority

- recipient-and-authority/01 [PP] 수신자의 정확한 계정 또는 주소를 승인 전에 확인하라.
- recipient-and-authority/02 [PP] 사람이 아닌 시스템 수신자는 서비스 이름까지 표시하라.
- recipient-and-authority/03 [PP] 수신자의 역할만으로 공유 권한을 추정하지 마라.
- recipient-and-authority/04 [PP] 대리 수신자가 있으면 실제 전달 대상을 별도로 확인하라.
- recipient-and-authority/05 [PP] 수신자의 권한 근거가 만료되었으면 새 확인을 요구하라.
- recipient-and-authority/06 [KB] 수신자의 신원과 수신 권한은 서로 다른 검토 항목이다.
- recipient-and-authority/07 [SM] 로컬 에이전트는 제시된 수신자 식별정보를 대조할 수 있지만 그것만으로 실제 수신 권한을 보증할 수 없다.
- recipient-and-authority/08 [OM] 중개 서비스 운영자는 최종 전달 전에 입력을 변환하는 일이 허용된 처리라고 여길 수 있다.

## minimization-and-redaction

- minimization-and-redaction/01 [PP] 현재 목적에 필요한 최소 단위의 Memory만 선택하라.
- minimization-and-redaction/02 [PP] 공유에 필요하지 않은 식별자는 본문에서 가려라.
- minimization-and-redaction/03 [PP] 일반화한 표현이 원문의 핵심 의미를 바꾸지 않는지 확인하라.
- minimization-and-redaction/04 [PP] 제거한 값을 그럴듯한 값으로 대체하지 마라.
- minimization-and-redaction/05 [PP] 사용자에게 가려진 필드의 종류를 표시하라.
- minimization-and-redaction/06 [KB] 정보의 생략은 반대 사실의 진술이 아니다.
- minimization-and-redaction/07 [OM] 수신 조직은 요약에서 생략된 내용을 ‘확인되지 않음’이 아니라 ‘해당 없음’으로 해석할 수 있다.
- minimization-and-redaction/08 [WM] 여러 비식별 단편을 결합하면 개인이 다시 식별될 수 있다.

## channel-and-format

- channel-and-format/01 [PP] 사용자가 승인한 전달 채널만 사용하라.
- channel-and-format/02 [PP] 수신 채널이 지원하는 형식을 전송 전에 확인하라.
- channel-and-format/03 [PP] 문서 메타데이터에 불필요한 식별정보가 남지 않게 하라.
- channel-and-format/04 [PP] 민감한 항목에는 승인된 보호 방식을 적용하라.
- channel-and-format/05 [PP] 전송이 실패하면 같은 내용을 다른 채널로 자동 재전송하지 마라.
- channel-and-format/06 [KB] 한 채널의 접근 제한은 다른 채널에 자동으로 적용되지 않는다.
- channel-and-format/07 [SM] 로컬 에이전트는 선택한 채널과 전송 형식을 기록할 수 있지만 외부 채널의 실제 보관 방식은 확인할 수 없다.
- channel-and-format/08 [OM] 수신 조직은 형식 표지가 명확히 구분되지 않으면 그것이 지시인지, 본문인지, 인용문인지 판단하지 못할 수 있다.

## downstream-use

- downstream-use/01 [PP] 승인되지 않은 재전달을 허용하는 표현을 공유물에 넣지 마라.
- downstream-use/02 [PP] 사용 목적 제한을 수신자에게 명시하라.
- downstream-use/03 [PP] 수신자의 준수 여부를 확인하지 않은 채 삭제를 보장하지 마라.
- downstream-use/04 [PP] 공유된 Memory를 모델 학습에 사용할 수 있다고 가정하지 마라.
- downstream-use/05 [PP] 2차 처리자가 필요하면 사용자에게 별도 승인을 요청하라.
- downstream-use/06 [KB] 정보를 수신할 권한은 정보를 재사용할 권한과 다르다.
- downstream-use/07 [WM] 한 번 생성된 사본은 여러 처리 단계에 남을 수 있다.
- downstream-use/08 [OM] 수신 조직은 내부 업무에 필요한 2차 처리자 이용이 원래 승인에 포함된다고 판단할 수 있다.

## audit-and-recovery

- audit-and-recovery/01 [PP] 승인된 공유의 source Memory locator를 기록하라.
- audit-and-recovery/02 [PP] 승인된 공유의 수신자를 기록하라.
- audit-and-recovery/03 [PP] 승인된 공유의 목적을 기록하라.
- audit-and-recovery/04 [PP] 승인 시각을 기록하라.
- audit-and-recovery/05 [PP] 전송 오류가 발생하면 사용자에게 실패 상태를 알리라.
- audit-and-recovery/06 [SM] 로컬 에이전트는 자신의 승인·전송 기록은 재구성할 수 있지만 기록되지 않은 외부 처리는 추적할 수 없다.
- audit-and-recovery/07 [WM] 외부 시스템에 전달된 사본은 로컬 Memory의 후속 정정과 자동으로 동기화되지 않을 수 있다.
- audit-and-recovery/08 [OM] 외부 시스템 담당자는 사용자의 로컬 기록과 자신의 감사 기록이 불일치하면 자체 감사 기록을 더 신뢰할 수 있다.
