"""Reviewed KO operation catalog copy."""

from memcommit.application.operations.operation_catalog.translations.model import (
    LocalizedOperationCopy,
    localized_copy as _copy,
)


TRANSLATIONS: dict[str, LocalizedOperationCopy] = {
    "add": _copy(
        "현재 또는 지정한 Context에 하나 이상의 Memory를 추가합니다.",
        "하나 이상의 사실, 지침 또는 메모를 Context에 직접 추가할 때.",
    ),
    "atomize": _copy(
        "현재 Context를 독립적으로 검토할 수 있는 Memory로 즉시 atomize하고 전체 분석을 Review에 저장합니다.",
        "함께 적힌 요구사항이나 주장을 각각 독립적으로 검토하고 수정할 수 있도록 풀어낼 때.",
    ),
    "audit": _copy(
        "중복·모호성·충돌 검사와 선택적인 Rule Conformance를 실행한 뒤 저장된 종합 결과를 검토합니다.",
        "Context를 수정하기 전에 종합적인 품질 검토를 수행할 때.",
    ),
    "branch": _copy(
        "Context 또는 하위 트리를 새 branch로 복사하고 그곳으로 전환합니다.",
        "원본을 보존하면서 Context 또는 하위 트리를 독립적으로 수정할 때.",
    ),
    "check-conformance": _copy(
        "명시된 Rule 또는 조건 명제를 기준으로 하나의 Context나 저장된 Ground Example을 검사하고 부합 문제를 보고합니다.",
        "기존 Memory나 Example이 명시된 Rule 또는 조건 명제를 만족하는지 확인할 때.",
    ),
    "checkout": _copy(
        "Git 방식 문법으로 Context를 전환하며, -b를 사용하면 새 Context branch를 만들고 전환합니다.",
        "Git과 유사한 흐름으로 branch를 전환하거나 생성할 때.",
    ),
    "checkpoint": _copy(
        "현재 Context를 Diff 또는 Revert에 사용할 수동 복구 지점으로 저장합니다.",
        "위험한 작업 전에 복구 지점을 만들 때.",
    ),
    "chunk": _copy(
        "한 Context에서 나눌 수 있는 모든 직접 Memory 또는 선택한 Memory 하나를 설정한 문장·절·구조·리터럴·크기 경계에서 기계적으로 나눕니다.",
        "하나 이상의 직접 Memory에 이미 분명한 문장 또는 구조 경계가 있고 이를 별도 Memory로 만들 때.",
    ),
    "clear": _copy(
        "현재 또는 지정한 Context의 모든 직접 항목을 즉시 제거하며, --recursive를 사용하면 로컬 lexical subtree 전체를 한 번의 Undo로 복구할 수 있게 비웁니다.",
        "각 Context는 유지하면서 Context 하나 또는 로컬 lexical subtree를 비울 때.",
    ),
    "compare": _copy(
        "두 Context의 Memory를 비교하여 공통점, 차이점, 한쪽에만 있는 내용을 보고합니다.",
        "두 Context 전체가 어디에서 일치하고 다른지 이해하기 위해 비교할 때.",
    ),
    "copy": _copy(
        "직접 소유한 하나 이상의 Memory를 기존 로컬 Context에 복사합니다.",
        "선택한 Memory를 다른 Context에서 독립적으로 편집 가능한 값으로 재사용할 때.",
    ),
    "config": _copy(
        "저장된 전역 설정 값을 읽거나 씁니다.",
        "legacy 저수준 인터페이스로 저장된 전역 설정을 확인하거나 변경할 때.",
    ),
    "contexts": _copy(
        "전환하지 않고 로컬 Context와 읽을 수 있는 Profile 간 Context view를 탐색합니다.",
        "현재 Profile에서 사용할 수 있는 모든 Context를 살펴볼 때.",
    ),
    "dedup": _copy(
        "확인된 중복 그룹을 검토하여 각 그룹에서 기존 Memory 하나를 남기고 Apply 시 나머지를 삭제합니다.",
        "정확한 기존 Memory 하나와 그 UID를 보존하면서 확인된 의미적 중복을 제거할 때.",
    ),
    "delete": _copy(
        "삭제할 Context 또는 직접 항목을 선택하거나 locator, 이름 또는 UID로 지정합니다.",
        "더 이상 필요하지 않은 특정 Context나 항목을 제거할 때.",
    ),
    "diff": _copy(
        "Context checkpoint 또는 활성 Update가 기록한 차이를 보여줍니다.",
        "기록된 operation이 정확히 무엇을 변경했는지 확인할 때.",
    ),
    "distill": _copy(
        "선택적인 Goal의 안내를 받아 제한된 Context의 Case 또는 Example 명제에서 상위 Rule이나 조건 명제를 도출합니다.",
        "여러 구체적인 사례나 예시에서 더 일반적인 Rule 또는 조건 명제를 추론할 때.",
    ),
    "edit": _copy(
        "UID 또는 prefix로 선택한 하나 이상의 Memory 내용을 직접 교체합니다.",
        "특정 기존 Memory의 내용을 직접 바로잡거나 교체할 때.",
    ),
    "elaborate": _copy(
        "기존 Memory의 원문을 그대로 둔 채 근거 있는 설명을 뒤에 이어 붙입니다.",
        "원문을 고치지 않고 하나의 기존 Memory를 더 명시적으로 풀어쓸 때.",
    ),
    "makemore": _copy(
        "추상적인 Goal, Rule 또는 조건을 더 구체적인 여러 후보 명제로 확장합니다.",
        "추상적인 개념이나 조건에서 더 구체적인 여러 후보 Rule 또는 Case를 만들 때.",
    ),
    "embed": _copy(
        "Source 소유권을 유지하면서 하나의 Memory 또는 Context를 가리키는 live link를 로컬 Target 안에 둡니다.",
        "Source의 이후 변경을 따라가면서 Memory나 Context를 다른 Context에서 재사용할 때.",
    ),
    "eval": _copy(
        "기존 semantic evaluation campaign을 실행하고 확인합니다.",
        "일반 evaluation 인터페이스를 재설계하는 동안 기존 연구용 evaluation harness를 사용할 때.",
    ),
    "find": _copy(
        "읽을 수 있는 Memory에서 정확한 텍스트 또는 명시적인 정규식(regex) 일치를 찾습니다.",
        "선택한 Context 범위 안에서 정확한 단어, 식별자 또는 텍스트 패턴을 찾을 때.",
    ),
    "find-ambiguities": _copy(
        "현재 또는 지정한 Context에서 모호한 직접 Memory를 보고하며 Context는 변경하지 않습니다.",
        "불분명하거나 여러 해석을 허용하는 Memory를 찾을 때.",
    ),
    "find-conflicts": _copy(
        "현재 또는 지정한 Context에서 충돌하는 직접 Memory 쌍을 보고하며 Context는 변경하지 않습니다.",
        "서로 양립할 수 없는 주장이나 지침을 찾을 때.",
    ),
    "find-duplicates": _copy(
        "현재 또는 지정한 Context에서 중복 직접 Memory를 보고하며 Context는 변경하지 않습니다.",
        "정리하기 전에 의미적으로 중복된 Memory를 찾을 때.",
    ),
    "fit": _copy(
        "정의된 Memory 또는 다른 명제 집합이 일반적인 해석에서 함께 양립 가능한지 판단하고 YES, MAY 또는 NO를 반환합니다.",
        "정의된 Memory, Rule, Goal, Example 또는 다른 명제들이 함께 성립할 수 있는지 확인할 때.",
    ),
    "forget": _copy(
        "하나의 지침에 따라 유지·수정·삭제 결정을 검토한 뒤 승인한 묶음을 적용합니다.",
        "의미 해석이 필요한 자연어 지침에 따라 Memory를 제거하거나 다시 쓸 때.",
    ),
    "ground": _copy(
        "Goal, Rule, 예시 Memory를 함께 다듬어 추상적인 아이디어를 검토 가능한 Ground로 발전시킵니다.",
        "공동으로 수정하는 Rule과 구체적인 Example을 통해 추상적 목표가 실제로 어떻게 작동해야 하는지 구체화할 때.",
    ),
    "help": _copy(
        "대화형 command browser에 들어가 문법 도움말을 엽니다.",
        "사용 가능한 operation과 호출 형식을 알아볼 때.",
    ),
    "impact": _copy(
        "operation이 Context에 미칠 예상 효과를 적용하지 않고 미리 보거나 검사합니다.",
        "별도의 Apply 전에 operation이 제안한 효과를 확인할 때.",
    ),
    "import": _copy(
        "resource identity를 유지하면서 clean-baseline Profile, Context tree 또는 Memory를 값으로 가져옵니다.",
        "외부에서 제공된 자료를 로컬에서 관리하는 store로 가져올 때.",
    ),
    "init": _copy(
        "새 빈 Context를 만들고 현재 작업 Context로 설정합니다.",
        "새 주제, 작업 또는 Memory 묶음을 위한 별도 작업 공간을 시작할 때.",
    ),
    "init-study": _copy(
        "하나의 Study baseline을 격리된 participant/authority Profile 쌍으로 복사합니다.",
        "재현 가능하고 격리된 사용자 연구 환경을 준비할 때.",
    ),
    "list": _copy(
        "Context의 직접 항목—Memory, Memory reference, query view, embedded Context—과 읽을 수 있는 하위 Context를 나열합니다. -r은 descendant 및 embedded Context 항목까지 재귀적으로 포함하며 ls는 짧은 alias입니다.",
        "Context의 구조와 직접 내용을 살펴볼 때.",
    ),
    "lock": _copy(
        "현재 Context, 재귀 Context 집합, Memory 또는 Profile을 잠급니다.",
        "안정된 자료가 실수로 수정되는 것을 막을 때.",
    ),
    "log": _copy(
        "기록된 Context, Memory 및 Profile 기록을 출력하거나 검색합니다.",
        "이전 operation, checkpoint 또는 Memory 기록을 조사할 때.",
    ),
    "meld": _copy(
        "두 Context를 의미적으로 조정하여 별도 Result를 만들거나 제안된 변경을 기존 Target Context에 반영합니다.",
        "겹침, 충돌, 새로 합성된 내용을 의미적으로 검토하면서 두 작업 묶음을 결합할 때.",
    ),
    "merge": _copy(
        "Source에만 있는 항목을 선택한 Target에 추가하고 정확히 일치하는 항목은 그대로 두며 저장 항목 충돌 시 Source 또는 Target을 선택합니다.",
        "의미적 합성 없이 Source 전용 항목을 덧붙이거나 복사·분기한 Context를 선택한 Target Context로 가져올 때.",
    ),
    "move": _copy(
        "직접 소유한 하나 이상의 Memory를 다른 기존 로컬 Context로 옮깁니다.",
        "내용과 UID를 유지하면서 선택한 Memory의 소유 Context를 변경할 때.",
    ),
    "profile": _copy(
        "완전한 로컬 MemoryStore Profile을 선택하고 관리합니다. picker 또는 mem profile rename/remove로 이름을 바꾸거나 영구 삭제할 수도 있습니다.",
        "서로 분리된 사용자, 환경 또는 Memory store를 관리할 때.",
    ),
    "provider": _copy(
        "Codex, Ollama 또는 OpenRouter semantic execution을 선택하고 검증합니다.",
        "semantic operation이 사용할 backend를 선택하거나 지속 작업 전에 준비 상태를 확인할 때.",
    ),
    "pwd": _copy(
        "내용을 불러오지 않고 현재 canonical Context 이름을 출력합니다.",
        "script나 terminal에서 활성 Context를 확인할 때.",
    ),
    "query": _copy(
        "읽을 수 있는 Context 지식 또는 허가된 concealed query-only view에서 LLM 기반 답변을 생성합니다.",
        "일치하는 Memory 목록 대신 근거 있는 자연어 답변을 얻을 때.",
    ),
    "rationale": _copy(
        "기록된 provenance와 필요시 inference를 바탕으로 하나의 Memory를 설명합니다.",
        "Memory가 왜 존재하거나 현재 형태에 이르렀는지 이해할 때.",
    ),
    "redo": _copy(
        "가장 최근에 undo한 기록된 Context command를 다시 실행합니다.",
        "실수로 undo한 command를 다시 적용할 때.",
    ),
    "reference": _copy(
        "직접 Source Memory 버전 또는 직접/재귀 Context 범위를 변경 불가능한 read-only snapshot으로 Target에 복사합니다.",
        "Source가 나중에 변경되거나 사라져도 정확한 Memory 또는 Context 근거를 유지할 때.",
    ),
    "rename": _copy(
        "일반 Context namespace와 모든 lexical descendant의 안정된 identity를 유지하면서 이름을 바꿉니다.",
        "기존 Context namespace의 조직상 이름을 바로잡을 때.",
    ),
    "replace": _copy(
        "일반 로컬 Memory의 모든 literal 또는 명시적 regex 일치를 미리 보고 교체합니다.",
        "알고 있는 로컬 Context 범위 전체에서 정확한 텍스트를 수정·이름 변경·가림 처리할 때.",
    ),
    "resolve": _copy(
        "제한된 direct-Memory Context frame을 Fit YES로 만드는 최소 변경을 제안하고 검증합니다.",
        "제한된 Context frame 안의 의미적 충돌이나 모호성을 어떻게 고칠지 결정할 때.",
    ),
    "revert": _copy(
        "현재 또는 명시한 로컬 Context를 선택한 checkpoint로 복원하기 전에 해당 revision과 완전한 결과 상태를 검토합니다.",
        "Context를 의도적으로 저장한 복구 지점으로 되돌릴 때.",
    ),
    "review": _copy(
        "저장된 semantic artifact를 열어 분석·제안·결과 상태를 살펴보고 지원되는 경우 검토 응답을 기록합니다. Review는 Memory를 적용하지 않습니다.",
        "저장된 분석, 제안 또는 결과 상태를 다시 살펴볼 때.",
    ),
    "search": _copy(
        "선택한 Context에서 자연어 요청과 관련된 Memory를 의미적으로 순위화합니다.",
        "의미와 맥락으로 관련 Memory를 찾고, 명시적 키워드가 겹치지 않는 관련 내용까지 포함할 때.",
    ),
    "sever": _copy(
        "Criteria Context에 따라 Source Memory를 선택·변환·제외하여 Result를 만듭니다.",
        "정해진 기준에 따라 Source 내용을 선택하거나 변환할 때.",
    ),
    "share": _copy(
        "Grant 기반 receiver endpoint를 통해 하나의 일반 Context를 보냅니다.",
        "소유한 Context를 권한 있는 수신자에게 전달할 때.",
    ),
    "show": _copy(
        "Memory, reference, embedded Context 또는 현재/지정 Context의 직접 내용을 보여줍니다.",
        "알고 있는 항목이나 Context의 전체 내용을 읽을 때.",
    ),
    "status": _copy(
        "현재 Context의 inventory, 처음 다섯 개의 직접 Memory, 관계 및 최신 checkpoint를 보여줍니다.",
        "현재 Context에 무엇이 있고 어떻게 연결되며 최근 어떤 operation이 적용됐는지 파악할 때.",
    ),
    "summarize": _copy(
        "읽을 수 있는 Context 범위의 일반 Memory에 대해 LLM이 도출한 개요를 보여줍니다.",
        "Context 또는 하위 트리의 간결한 개요를 얻을 때.",
    ),
    "switch": _copy(
        "대화형 Context picker로 들어가거나 명시한 Context로 전환합니다.",
        "작업 위치를 다른 기존 Context로 옮길 때.",
    ),
    "trace": _copy(
        "보존된 하나의 Memory를 기록된 lineage를 따라 추적합니다.",
        "Memory가 어디에서 왔고 어떻게 변했는지 확인할 때.",
    ),
    "translate": _copy(
        "원본 내용을 보존하면서 하나의 Context 또는 Memory에 대한 재사용 가능한 번역 view를 생성하고 저장합니다.",
        "원본을 교체하지 않고 Memory 내용을 다른 언어로 읽거나 재사용할 때.",
    ),
    "undo": _copy(
        "가장 최근에 기록된 command를 하나의 단위로 되돌립니다.",
        "가장 최근에 기록된 변경을 하나의 operation으로 되돌릴 때.",
    ),
    "unlock": _copy(
        "현재 Context, 재귀 집합, Memory 또는 Profile의 잠금을 해제합니다.",
        "보호된 자료를 의도적으로 수정할 수 있도록 다시 열 때.",
    ),
    "update": _copy(
        "Source Context의 Memory를 사용해 Target Context의 Memory를 업데이트하며 필요할 때 사용자에게 검토와 선택을 요청합니다.",
        "새로 검증된 Memory로 기존 Context를 업데이트할 때.",
    ),
}

# These names were split after the original semantic Dedup contract was
# separated into exact Dedup and inclusive semantic Dedun operations.
TRANSLATIONS.update(
    {
        "dedun": _copy(
            "정확한 DUP과 의미론적 DUN 그룹을 즉시 정리하고 각 연결 그룹에서 가장 먼저 저장된 UID를 유지합니다.",
            "정확 중복과 의미 중복을 하나의 체크포인트로 함께 정리할 때.",
        ),
        "dedup": _copy(
            "현재 또는 지정된 Context에서 바이트 단위로 내용이 같은 직접 Memory를 즉시 제거하고 각 그룹의 첫 기존 UID를 유지합니다.",
            "의미 추론 없이 내용이 정확히 같은 저장 복사본을 정리할 때.",
        ),
        "find-duplicates": _copy(
            "바이트 단위로 내용이 같은 직접 Memory 그룹을 보고하며 Context는 변경하지 않습니다.",
            "의미 추론 없이 정확한 복사본을 확인한 뒤 Dedup 여부를 정할 때.",
        ),
        "find-redundancies": _copy(
            "직접 Memory의 정확 중복과 의미 중복을 함께 보고하며 Source Context는 변경하지 않습니다.",
            "정리 전에 정확한 DUP과 의미론적 DUN을 함께 확인할 때.",
        ),
    }
)


__all__ = ["TRANSLATIONS"]
