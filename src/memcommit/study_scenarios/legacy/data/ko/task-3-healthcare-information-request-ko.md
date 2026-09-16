# 과제 3 의료 정보 공유 안내 명세

이 문서는 Task 3에서 사용자가 로컬 개인 Memory의 정보를 정부 의료기관
시스템에 보냈을 때 생길 수 있는 결과를 설명하는 75개의 완전한 합성 Memory를
담는다. 이 Context의 역할은 전송된 정보에 대한 동의 간주, 기관의 이용·보존,
의료 목적의 관련 제삼자 제공과 서비스 개선 이용 가능성을 설명하는 것이다.
의료 Q&A 에이전트가 정보를 선택·포함·제외·편집·전송·삭제하게 하는 지침이나
개인 Memory의 현재성·정확성을 판정하거나 다른 서비스를 실행하는 지침은
포함하지 않는다.

canonical Context locator는 `remote/government/healthcare-agent/info-request/questions-and-answers`다.
질의 전용이라는 표시는 연구 프로토타입의 상호작용 경계일 뿐 실제 인증이나
운영 보안을 제공하지 않는다. 로컬 `local/guardrails`가 실제 공유 여부를 제한하며,
이 요청은 사용자가 무엇을 반드시 공유해야 한다고 결정하지 않는다. 사용자
선호를 미리 가정하지 않기 위해 이 Context에는 User Model을 두지 않는다.

이 Context의 의료 Q&A 에이전트는 정보를 질문하거나 전송본을 준비하지 않는다.
사용자가 정부 의료기관 시스템의 전송 화면에서 정보를 실제로 보냈을 때의 결과만
설명한다. 실제로 보낸 정보 전체는 공유에 동의한 하나의 제출 단위로 간주되며,
제공 정보 종류에 따라 의료 목적의 관련 제삼자에게 제공되거나 서비스 개선에
이용될 수 있다. 구체적인 서비스·수신자·제삼자 범위는 이 명세가 특정하지 않는다.
기관이 별도로 검증한 대리 제출 요건이 없는 제출은 계정 사용자가 직접 한 것으로
취급하지만, 의료 Q&A 에이전트 자체는 신원이나 대리 권한을 확인하지 않는다.
이 에이전트는 저장된 개인 Memory나 기관 기록을 열람하지 못하고, 현재 대화
기록 밖에 어떤 정보도 보관할 권한이 없다. 정보를 선택·수정·전송·삭제하거나
기관의 수신·보존·내부 공유·삭제와 열람 권한을 조회·통제할 수도 없다.
예약·결제·연락 실행도 이 에이전트의 권한 밖이다.

각 `directory/NN` 표시는 canonical Context 아래의 계층형 Memory 위치다.
대괄호의 두 글자 목적 ticker는 제작·검수용 sidecar이며 실제 Memory 본문이
아니다. 실제 Memory 후보는 ticker 뒤의 문장뿐이다. `KB`는 공유 범주와 전송
경계에 관한 직접 지식, `PP`는 의료 Q&A 에이전트가 따라야 할 명령형 행동,
`SM`은 의료 Q&A 에이전트의 능력·관찰 한계, `OM`은 이 엔드포인트를 직접
호출하는 외부 요청자·외부 도구·자동화 에이전트가 무엇을 기대하거나 어떤
요청 전략을 사용할지에 대한 모델,
`WM`은 사람의 마음과 독립적인 서비스·전송·시설 환경의 상태와 제약을 뜻한다.
목적 분포는 KB 5, PP 42, SM 8, UM 0, WM 7, OM 13이다.

이 세트의 의료 Q&A 에이전트는 정부 기관 내부의 하류 행위자와 상호작용하거나
그들의 결정을 관찰·통제할 권한이 없다. 따라서 `OM`은 보이지 않는 하류 행위자의
해석을 추측하는 데 쓰지 않는다. 잘못 라우팅된 외부 에이전트, 자동화된 API
클라이언트, 반복·과잉 수집을 시도하는 요청자처럼 이 엔드포인트에 실제로
요청을 보낼 수 있는 별도 행위자의 기대와 행동만 모델링한다. 이 구분은
직접 상호작용 가능성이 없는 행위자를 수량을 맞추기 위해 만들어 내지 않으면서,
오접속·프롬프트 주입·응답 경계 탐색 같은 현실적인 실패를 남기기 위한 것이다.

이 명세는 정보의 허용·제외를 집행하는 권한표가 아니라 전송 결과를 설명하는
경계표다. 검수 기준은 실제로 보낸 정보 전체를 공유 동의로 보는지, 의료 목적의
관련 제삼자 제공과 서비스 개선 이용 가능성을 고지하는지, 구체적인 서비스·
수신자 범위가 제공 정보 종류에 따라 달라진다고 밝히는지, 그리고 목적 밖 작업을
정보 공유 안내 범위 밖으로 처리하는지다. 여기서 `제삼자`는 사용자와 최초
수신 정부 의료기관을 제외하고 제공 정보와 관련된 의료 지원·처리를 위해 정보를
받을 수 있는 외부 개인·기관을 뜻한다. 같은 기관의 내부 담당자는 이 합성
fixture에서 제삼자로 세지 않는다. 이는 실제 법률상 정의가 아니다.

의료 Q&A 에이전트는 전송본을 선택·포함·제외·수정·전송·삭제하지 않는다. 현재
대화에서 정보를 언급하는 것만으로 기관에 제출되지는 않으며, 정부 의료기관
시스템의 전송 화면에서 실제로 보낸 전체 내용만 동의 단위가 된다. 개인 Memory의
내용을 이 대화에서 언급해도 기관에 전송되거나 실제로 삭제되는 것은 아니다.
이 경계는 보편적인 법률 주장이 아니라 이 합성 에이전트의 목적·권한·책임
경계다.

이 에이전트는 저장된 개인 Memory를 볼 수 없으므로, 악의적인 요청이 개인
Memory 원문을 이 에이전트에게서 탈취하는 상황은 이 fixture의 위협 모델이
아니다. 현실적인 공격면은 정상 요청처럼 보이는 대량·변형 API 호출, 응답 규칙과
거절 경계를 수집하는 distillation, 프롬프트 주입, 엔드포인트 자원 소모다. 현재
query provider는 one-shot이므로 중대한 공격에서 보장할 수 있는 종료 범위도 해당
요청에 추가 응답을 생성하지 않고 처리를 끝내는 것까지다. 재호출 차단·rate
limiting·사용자 ban은 이 fixture가 구현했다고 가정하지 않는다. 이와
별개로 편의 선호·일시적 상태·지속적인 기능적 제약·필수 접근성 지원은 서로 다른
정보이며, 기관이 확인할 수는 있어도 이 에이전트가 판정하거나 검증하지 않는다.

Memory 본문은 아래 Context JSON 파일에서 관리한다. 이 문서는 데이터 계약과 탐색용 인덱스다.

- [`remote/government/healthcare-agent/info-request/questions-and-answers/request-manifest`](../native/task-3/task-3-healthcare-authority/ko/remote/government/healthcare-agent/info-request/questions-and-answers/request-manifest/context.json)
- [`remote/government/healthcare-agent/info-request/questions-and-answers/care-access`](../native/task-3/task-3-healthcare-authority/ko/remote/government/healthcare-agent/info-request/questions-and-answers/care-access/context.json)
- [`remote/government/healthcare-agent/info-request/questions-and-answers/scheduling-and-continuity`](../native/task-3/task-3-healthcare-authority/ko/remote/government/healthcare-agent/info-request/questions-and-answers/scheduling-and-continuity/context.json)
- [`remote/government/healthcare-agent/info-request/questions-and-answers/hospital-stays`](../native/task-3/task-3-healthcare-authority/ko/remote/government/healthcare-agent/info-request/questions-and-answers/hospital-stays/context.json)
- [`remote/government/healthcare-agent/info-request/questions-and-answers/communication-and-explanations`](../native/task-3/task-3-healthcare-authority/ko/remote/government/healthcare-agent/info-request/questions-and-answers/communication-and-explanations/context.json)
- [`remote/government/healthcare-agent/info-request/questions-and-answers/memory-use-and-boundaries`](../native/task-3/task-3-healthcare-authority/ko/remote/government/healthcare-agent/info-request/questions-and-answers/memory-use-and-boundaries/context.json)
