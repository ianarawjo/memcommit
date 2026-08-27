"""The version-pinned continuous Coffee Study scenario.

English is the canonical durable Memory text.  Korean is retained as a
same-UID imported translation catalog so changing the display language never
creates a second occurrence or changes the scenario fingerprint.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import uuid

from memcommit.context import Context, Memory
from memcommit.application.operations.translate.view import (
    TRANSLATION_ORIGIN_IMPORTED,
    TranslationCatalog,
)


COFFEE_V1_SCENARIO_ID = "coffee-v1"
_SCENARIO_NAMESPACE = uuid.uuid5(
    uuid.NAMESPACE_URL,
    "memcommit:study-scenario:coffee-v1",
)
COFFEE_V1_BASELINE_UID = str(uuid.uuid5(_SCENARIO_NAMESPACE, "baseline"))
_CATALOG_TIMESTAMP = "2026-08-25T00:00:00+00:00"


@dataclass(frozen=True)
class BilingualMemorySpec:
    """One canonical English Memory and its same-UID Korean rendering."""

    purpose: str
    en: str
    ko: str


@dataclass(frozen=True)
class ContextSpec:
    """One ordinary Context declared by the Coffee scenario."""

    name: str
    memories: tuple[BilingualMemorySpec, ...] = ()


@dataclass(frozen=True)
class ScenarioGrantSpec:
    """One public authority view or delivery endpoint."""

    key: str
    authority_context: str
    attachment_context: str
    public_name: str
    permissions: tuple[str, ...]
    recursive: bool


@dataclass(frozen=True)
class StudyScenarioTask:
    """One Task's already-public participant and authority namespaces."""

    task: int
    participant_current: str
    authority_current: str
    participant_contexts: tuple[Context, ...]
    authority_contexts: tuple[Context, ...]
    participant_catalogs: tuple[TranslationCatalog, ...]
    authority_catalogs: tuple[TranslationCatalog, ...]
    grants: tuple[ScenarioGrantSpec, ...]


@dataclass(frozen=True)
class StudyScenario:
    """One complete immutable Study input topology."""

    scenario_id: str
    baseline_uid: str
    digest: str
    tasks: tuple[StudyScenarioTask, ...]


_PRACTICE = (
    ContextSpec("practice"),
    ContextSpec("practice/coffee"),
    ContextSpec(
        "practice/coffee/chunk-atomize-summarize",
        (
            BilingualMemorySpec(
                "PRACTICE_TRANSCRIPT",
                "In summer, because the espresso is hot, the ice in an iced coffee, an iced Americano, melts really quickly, so you need a lot of ice from the start. The reason you need a lot of ice is because if you only put in a little, it melts right away, so then the drink gets warm. The ice gets warm, and because the ice gets warm, you should use cold water instead of room-temperature filtered water, the water needs to be cold too, and you also need to clean the buildup properly. Because if you look inside the ice machine and only clean the parts you can see, it can start to smell, and whatever is left inside comes through in the taste of the water, so you need to clean that too.",
                "여름에는 에스프레소가 뜨거워서 아이스커피, 그러니까 아이스 아메리카노의 얼음이 정말 빨리 녹기 때문에 처음부터 얼음이 많이 필요하다. 얼음이 많이 필요한 이유는 조금만 넣으면 바로 녹아버리고 그러면 음료가 따뜻해지기 때문이다. 얼음이 따뜻해지고, 얼음이 따뜻해지기 때문에 상온의 정수 대신 냉수를 사용해야 하고, 물도 차가워야 하며, 물때도 제대로 청소해야 한다. 제빙기 내부를 보았을 때 눈에 보이는 부분만 청소하면 냄새가 날 수 있고, 안에 남은 것이 물맛에 그대로 드러나므로 그것도 청소해야 한다.",
            ),
        ),
    ),
    ContextSpec("practice/coffee/compare-merge-meld-update"),
    ContextSpec(
        "practice/coffee/compare-merge-meld-update/a",
        (
            BilingualMemorySpec(
                "PP",
                "I avoid cafés where several conversations overlap loudly.",
                "대화 소리가 크게 겹치는 카페에는 가지 않는다.",
            ),
            BilingualMemorySpec(
                "PP",
                "I avoid cafés where the tables are so low that using plates or a laptop becomes uncomfortable.",
                "테이블이 너무 낮아 식기나 노트북을 사용하기 불편하면 피한다.",
            ),
            BilingualMemorySpec(
                "PP",
                "When flavor notes are too sparse, it is difficult to choose a coffee.",
                "향미 설명이 너무 빈약하면 원두를 선택하기 어렵다.",
            ),
            BilingualMemorySpec(
                "PP",
                "If the menu is too limited, there may not be enough options when ordering with a companion.",
                "메뉴가 지나치게 적으면 동행인과 함께 주문할 선택지가 부족하다.",
            ),
        ),
    ),
    ContextSpec(
        "practice/coffee/compare-merge-meld-update/b",
        (
            BilingualMemorySpec(
                "PP",
                "A café where nobody talks and the atmosphere is excessively quiet feels uncomfortable for a gathering.",
                "아무도 대화하지 않는 지나치게 조용한 카페는 모임을 가지기에 불편하다.",
            ),
            BilingualMemorySpec(
                "PP",
                "Tables that are unusually high and uniform make a café feel more like a home or an office, which I do not prefer.",
                "테이블이 지나치게 높고 획일적이면 카페보다 집이나 사무실처럼 느껴져 선호하지 않는다.",
            ),
            BilingualMemorySpec(
                "PP",
                "Flavor descriptions that are too abstract or exaggerated can make ordering more difficult.",
                "지나치게 추상적이거나 과장된 향미 표현은 주문을 오히려 어렵게 만든다.",
            ),
            BilingualMemorySpec(
                "PP",
                "A menu with too many options makes it difficult to choose.",
                "선택지가 너무 많으면 고르기 어렵다.",
            ),
        ),
    ),
    ContextSpec(
        "practice/coffee/search-find-sever-forget",
        (
            BilingualMemorySpec(
                "KB",
                "After finishing an errand at a nearby government office, I had some time left and stopped by with my family.",
                "근처 관공서에서 업무를 마치고 시간이 남아 가족과 함께 들렀다.",
            ),
            BilingualMemorySpec(
                "KB",
                "The dessert display showed only prices, so I did not know what the desserts were called, but the one I chose was delicious.",
                "디저트 진열대에는 가격만 표시되어 있어 이름은 알 수 없었지만, 고른 디저트는 맛있었다.",
            ),
            BilingualMemorySpec(
                "KB",
                "The coffee was also really delicious.",
                "커피도 굉장히 맛있었다.",
            ),
            BilingualMemorySpec(
                "KB",
                "I had to get a key to use the restroom, and it smelled a little, but the building was old, so it seemed unavoidable.",
                "화장실은 키를 받아서 가야 했고 냄새가 조금 났지만 오래된 건물이라 어쩔 수 없어 보였다.",
            ),
            BilingualMemorySpec(
                "KB",
                "The takeaway cup was pretty and felt really good to hold.",
                "테이크아웃 잔이 예쁘고 그립감이 매우 좋았다.",
            ),
        ),
    ),
)


_TASK_1_AUTHORITY = (
    ContextSpec("task-1/customer-perspectives"),
    ContextSpec(
        "task-1/customer-perspectives/woohooovertime",
        (
            BilingualMemorySpec(
                "KB",
                "Over the past month, the user made six café visits on weekday afternoons and brought a laptop on five of those visits.",
                "이 사용자는 지난 한 달 동안 평일 오후에 카페를 여섯 차례 방문했고, 그중 다섯 차례에는 노트북을 가져왔다.",
            ),
            BilingualMemorySpec(
                "PP",
                "When recommending a café to the user for a stay of two hours or longer, check table height, power outlets, and closing time together.",
                "사용자에게 카페를 추천할 때 두 시간 이상 머물 계획이면 테이블 높이, 콘센트, 폐점 시간을 함께 확인한다.",
            ),
            BilingualMemorySpec(
                "SM",
                "This agent can retrieve and compare the user's café visit history, but it does not make reservations or make the final choice of where to visit on the user's behalf.",
                "이 에이전트는 사용자의 카페 방문 기록을 조회하고 비교할 수 있지만, 사용자를 대신해 예약하거나 방문 장소를 최종 결정하지 않는다.",
            ),
            BilingualMemorySpec(
                "UM",
                "The user avoids visiting near closing time because even a short stay can feel rushed.",
                "사용자는 폐점 시간이 가까우면 실제 체류 시간이 짧아도 재촉받는다고 느껴 방문을 꺼린다.",
            ),
            BilingualMemorySpec(
                "WM",
                "Low tables and limited power outlets concentrate laptop users in a small number of seats, increasing competition for seats during busy periods.",
                "낮은 테이블과 부족한 콘센트는 노트북 이용자를 일부 좌석에 집중시켜 혼잡 시간대의 좌석 경쟁을 높인다.",
            ),
            BilingualMemorySpec(
                "WM",
                "Desk-height tables, ample seating, plentiful power outlets, and comfortable chairs signal that long work and study visits are welcome.",
                "책상과 비슷한 높이의 테이블, 넉넉한 좌석, 많은 콘센트와 편안한 의자는 장시간 작업과 공부를 환영한다는 신호가 된다.",
            ),
            BilingualMemorySpec(
                "OM",
                "The user expects that an owner may see long laptop use as reducing table turnover when other customers are waiting.",
                "사용자는 대기 손님이 있을 때 사장이 장시간 노트북 이용을 테이블 회전율 저하로 볼 수 있다고 예상한다.",
            ),
            BilingualMemorySpec(
                "OM",
                "The user expects that staff may welcome laptop customers who remain quiet after ordering because they require little additional attention.",
                "사용자는 노트북 손님이 주문 후 조용히 머무는 경우가 많아 직원들이 장시간 이용을 오히려 반길 수 있다고 예상한다.",
            ),
        ),
    ),
    ContextSpec(
        "task-1/customer-perspectives/saycheesecake",
        (
            BilingualMemorySpec(
                "KB",
                "The user's saved café photos repeatedly show window-seat selfies and desserts ordered with a companion.",
                "사용자가 저장한 카페 사진에는 창가 좌석에서 찍은 셀피와 동행인과 함께 주문한 디저트가 반복해서 나타난다.",
            ),
            BilingualMemorySpec(
                "PP",
                "When the user will visit with a companion, first reflect both people's essential conditions and present the remaining preferences as differences among the options.",
                "함께 방문할 동행인이 있다면 사용자와 동행인의 필수 조건을 먼저 반영하고, 나머지 선호는 선택지별 차이로 제시한다.",
            ),
            BilingualMemorySpec(
                "SM",
                "This agent can account for both the user's preferences and a companion's shared preferences about food, seating, and noise.",
                "이 에이전트는 사용자의 선호뿐 아니라 동행인이 공유한 음식, 좌석과 소음 선호도도 함께 반영할 수 있다.",
            ),
            BilingualMemorySpec(
                "SM",
                "This agent respects a companion's explicit dealbreakers first, but prioritizes its own user's preferences if the other agent also assumes that its user should not compromise.",
                "이 에이전트는 동행인의 명확한 기피 조건을 먼저 존중하지만, 상대 에이전트도 자기 사용자의 양보를 전제로 하면 이 사용자의 선호를 우선한다.",
            ),
            BilingualMemorySpec(
                "UM",
                "The user prefers sofas or wide bench seats that make it easy to turn toward a companion over desk-style seating.",
                "사용자는 책상형 좌석보다 몸을 돌려 앉기 쉬운 소파나 넓은 벤치 좌석을 선호한다.",
            ),
            BilingualMemorySpec(
                "WM",
                "Design-forward tables and sofas may be uncomfortable to use, but they can strengthen a café's visual distinctiveness.",
                "디자인이 강조된 테이블과 소파는 사용하기 불편할 수 있지만 카페의 시각적 독창성을 강화한다.",
            ),
            BilingualMemorySpec(
                "OM",
                "The user expects that a companion may feel burdened when no decaffeinated or non-coffee drink is available.",
                "사용자는 동행인이 디카페인이나 비커피 음료를 고를 수 없으면 주문에 부담을 느낄 수 있다고 예상한다.",
            ),
            BilingualMemorySpec(
                "OM",
                "The user expects that an owner may view a long stay more positively when companions order both drinks and dessert.",
                "사용자는 사장이 동행인들이 음료와 디저트를 함께 주문하면 긴 체류 시간을 비교적 긍정적으로 볼 수 있다고 예상한다.",
            ),
        ),
    ),
    ContextSpec(
        "task-1/customer-perspectives/strollersnackpack",
        (
            BilingualMemorySpec(
                "KB",
                "The café gathering that the user regularly organizes includes four adults and four to six young children.",
                "사용자가 정기적으로 준비하는 카페 모임에는 성인 네 명과 유아 네 명에서 여섯 명이 참여한다.",
            ),
            BilingualMemorySpec(
                "KB",
                "Every café the user marked for a return visit had a step-free entrance and an easy route for a stroller to reach the tables.",
                "사용자가 다시 가겠다고 표시한 카페들은 모두 출입구에 계단이 없고 유모차로 테이블까지 이동하기 쉬웠다.",
            ),
            BilingualMemorySpec(
                "PP",
                "When suggesting a gathering place for visits with children, lower the priority of cafés that strongly expect customers to maintain a quiet atmosphere.",
                "아이들과 함께하는 모임 장소를 제안할 때 조용한 분위기 유지를 손님에게 강하게 기대하는 카페는 우선순위를 낮춘다.",
            ),
            BilingualMemorySpec(
                "SM",
                "In addition to organizing visit records, this agent helps the user coordinate companions' arrival times and the children's nap and meal times.",
                "이 에이전트는 방문 기록을 정리하는 것뿐 아니라 사용자와 함께 동행인들의 도착 시간과 아이들의 낮잠·식사 시간을 조정하는 역할도 담당한다.",
            ),
            BilingualMemorySpec(
                "UM",
                "The user prefers one large table where the group can sit together without dispersing, even if the interior is less distinctive.",
                "사용자는 인테리어가 덜 특별하더라도 일행이 흩어지지 않고 함께 앉을 수 있는 큰 테이블을 선호한다.",
            ),
            BilingualMemorySpec(
                "UM",
                "Because the user has experienced people staring when a child cried, the user cannot relax in an atmosphere where even a small sound draws scrutiny.",
                "사용자는 아이가 울었을 때 주변의 시선이 모였던 경험 때문에, 작은 소리에도 눈치를 보게 되는 분위기에서는 편하게 머물지 못한다.",
            ),
            BilingualMemorySpec(
                "WM",
                "Hard table corners or breakable decorations at a young child's height can turn small movements into collisions or damage.",
                "아이의 키와 비슷한 높이에 단단한 테이블 모서리나 깨지기 쉬운 장식물이 있으면 작은 움직임도 부딪힘이나 파손으로 이어질 수 있다.",
            ),
            BilingualMemorySpec(
                "OM",
                "The user expects that customers working or studying alone may experience a baby's crying and a large group's conversation as disruptive.",
                "사용자는 혼자 일하거나 공부하는 손님들이 아기 울음과 여러 사람의 대화를 방해로 느낄 수 있다고 예상한다.",
            ),
        ),
    ),
)


_TASK_2_AUTHORITY = (
    ContextSpec("task-2/operational-perspectives"),
    ContextSpec(
        "task-2/operational-perspectives/coffeewithtaylor",
        (
            BilingualMemorySpec(
                "KB",
                "Last Friday's closing shift left a handoff note saying, '12-drink pickup order at 9:00 a.m.,' and the next day's opening shift reviewed it.",
                "지난 금요일 마감조는 인계 메모에 ‘오전 9시 픽업 주문 12잔’이라고 남겼고, 다음 날 오픈조가 이를 확인했다.",
            ),
            BilingualMemorySpec(
                "KB",
                "Taylor's recent work notes repeatedly record questions near closing about the last order time and how long customers may continue using the seats.",
                "Taylor가 남긴 최근 근무 메모에는 폐점이 가까워질수록 마지막 주문 시간과 좌석을 언제까지 이용할 수 있는지 묻는 질문이 반복해서 기록되어 있었다.",
            ),
            BilingualMemorySpec(
                "PP",
                "When preparing a work schedule, protect Taylor's personal commitment every Wednesday and do not suggest a replacement shift during that time unless Taylor asks first.",
                "근무 일정안을 만들 때 매주 수요일에 있는 Taylor의 개인 일정을 보호하고, Taylor가 먼저 요청하지 않는 한 그 시간의 대체 근무를 제안하지 않는다.",
            ),
            BilingualMemorySpec(
                "PP",
                "When showing Taylor a replacement-shift request, present the date, time, and position together and do not reply without Taylor's confirmation.",
                "대체 근무 요청을 Taylor에게 보여줄 때 날짜, 시간, 맡아야 할 포지션을 한 번에 정리하고, Taylor의 확인 없이 답장을 보내지 않는다.",
            ),
            BilingualMemorySpec(
                "SM",
                "This agent can compare Taylor's work schedule with personal commitments and travel time to flag conflicts, but it does not accept replacement shifts or reply to coworkers.",
                "이 에이전트는 Taylor의 근무표를 개인 일정 및 이동시간과 대조하여 충돌을 알려줄 수 있지만, 대체 근무를 수락하거나 다른 직원에게 답장을 보내지는 않는다.",
            ),
            BilingualMemorySpec(
                "UM",
                "Taylor experiences laptop customers who remain quiet for a long time after ordering as relatively easy customers who require little additional attention.",
                "Taylor는 주문 후 조용히 오래 머무는 노트북 손님을 추가 응대가 거의 필요하지 않은, 비교적 수월한 손님으로 느낀다.",
            ),
            BilingualMemorySpec(
                "WM",
                "A pickup order may be accepted and collected across different shifts, so without a written handoff the next worker must verify the order details again.",
                "픽업 주문은 접수와 수령이 서로 다른 근무조에 걸칠 수 있으므로, 기록으로 인계되지 않으면 다음 근무자가 주문 내용을 다시 확인해야 한다.",
            ),
            BilingualMemorySpec(
                "OM",
                "The owner of Morrow Coffee evaluates the whole experience from a customer's entry through ordering, staying, and leaving rather than focusing only on one task's efficiency.",
                "Morrow Coffee의 사장은 한 업무의 효율만 보기보다 손님이 입장하고 주문하고 머물다 나갈 때까지의 전체 경험을 중요하게 평가한다.",
            ),
        ),
    ),
    ContextSpec(
        "task-2/operational-perspectives/morrowcoffee-official",
        (
            BilingualMemorySpec(
                "KB",
                "Past operating records showed higher evening sales on days with a later closing time, but profit did not always rise after additional labor and closing costs were deducted.",
                "예전 영업기록에서는 폐점 시간을 늦춘 날 저녁 매출이 늘었지만, 추가 인건비와 마감 비용을 제외한 이익이 항상 증가한 것은 아니었다.",
            ),
            BilingualMemorySpec(
                "PP",
                "When curating the Instagram feed, prioritize photographs that match the menu, space, and atmosphere actually offered, and do not publish posts that suggest a different concept without the owner's approval.",
                "인스타그램 피드를 구성할 때 매장에서 실제로 제공하는 메뉴, 공간, 분위기와 어울리는 사진을 우선하고, 현재 컨셉과 다른 인상을 주는 게시물은 사장의 확인 없이 올리지 않는다.",
            ),
            BilingualMemorySpec(
                "SM",
                "This agent can advise from Morrow Coffee's operating records and the owner's experience, but when sharing that advice with another café it states that source and discloses that it has not directly verified the other café's circumstances.",
                "이 에이전트는 Morrow Coffee의 운영기록과 사장이 경험한 사례를 바탕으로 조언할 수 있지만, 다른 카페에 전달할 때는 그 근거가 Morrow Coffee의 경험임을 명시하고 상대 카페의 사정을 직접 확인하지 못했다는 한계를 함께 알린다.",
            ),
            BilingualMemorySpec(
                "WM",
                "Information important to families with young children—such as entry routes, group seating, and noise tolerance—can spread through recommendations from people with firsthand experience, so a satisfying visit may lead to a return visit by the same family or a visit by another family.",
                "유아 동반 가족에게 중요한 출입 동선, 단체 좌석, 소음 수용 정도 같은 정보는 실제 방문 경험이 있는 손님들의 추천을 통해 공유될 수 있어, 만족스러운 경험이 같은 가족의 재방문이나 다른 가족의 방문으로 이어질 수 있다.",
            ),
            BilingualMemorySpec(
                "PP",
                "When helping introduce a new recipe, do not treat outside consulting results as a finished answer; the owner should confirm and continuously improve the final version through repeated preparation and blind comparisons with other products.",
                "새 레시피 도입을 도울 때 외부 컨설팅 결과를 완성본으로 취급하지 않고, 사장의 반복 제작과 다른 제품과의 블라인드 비교를 거쳐 최종안을 확인하고 지속적으로 개선해 나간다.",
            ),
            BilingualMemorySpec(
                "UM",
                "The owner of Morrow Coffee has worked with Taylor for many years and wants to help Taylor become independent after gaining sufficient experience.",
                "Morrow Coffee의 사장은 Taylor와 오랫동안 함께 일해 왔으며, Taylor가 충분한 경험을 쌓은 뒤 독립하는 것도 도와주고 싶어 한다.",
            ),
            BilingualMemorySpec(
                "OM",
                "Customers treat employees' expressions and the way employees speak with one another as part of the café experience, and may evaluate the café differently when the staff atmosphere feels tense even if the space is appealing.",
                "손님들은 직원들의 표정과 서로 대화하는 분위기도 카페 경험의 일부로 받아들이며, 공간이 좋아도 직원들의 분위기가 경직되어 있으면 매장을 다르게 평가할 수 있다.",
            ),
            BilingualMemorySpec(
                "UM",
                "The owner of Morrow Coffee believes that one café cannot satisfy every customer type equally, and values defining the experience to prioritize without forcing in elements that conflict with that concept.",
                "Morrow Coffee의 사장은 모든 고객 유형을 한 매장에서 동일하게 만족시키기는 어렵다고 생각하며, 우선할 이용 경험을 분명히 정하고 그 컨셉과 충돌하는 요소를 무리하게 늘리지 않는 것을 중요하게 여긴다.",
            ),
        ),
    ),
    ContextSpec(
        "task-2/operational-perspectives/consulting-newwavecafeculture",
        (
            BilingualMemorySpec(
                "WM",
                "A café experience connects online information, the entrance, ordering, seating, and staff service, so designing even one element in a different direction makes the visit feel inconsistent from one stage to the next.",
                "카페 경험은 온라인 정보, 입구, 주문, 좌석, 직원 응대가 연결된 구조이므로, 한 요소라도 다른 방향으로 설계되면 방문 과정의 앞뒤가 일관되지 않게 된다.",
            ),
            BilingualMemorySpec(
                "PP",
                "When proposing operational improvements, prioritize methods that can be carried out with the current furniture and staff.",
                "운영 개선안을 제안할 때 현재 가구와 인력으로 실행할 수 있는 방법을 우선한다.",
            ),
            BilingualMemorySpec(
                "SM",
                "This agent can create proposals from consulting records and store operating data, but without an in-person site visit it cannot verify the actual taste of the drinks, the internal condition of equipment, or the atmosphere of staff service.",
                "이 에이전트는 컨설팅 기록과 매장 운영자료를 토대로 한 제안을 만들 수 있지만, 사람이 직접 현장을 확인하지 않는 한 실제 음료 맛, 장비 내부 상태, 직원들의 응대 분위기를 검증할 수는 없다.",
            ),
            BilingualMemorySpec(
                "OM",
                "When café owners describe conditions as impossible to change, they sometimes combine physically difficult conditions such as the location and building structure with conditions they have chosen to retain for now, such as the budget, staff composition, and store philosophy.",
                "컨설팅을 받는 카페 사장들이 ‘바꿀 수 없는 조건’이라고 부르는 것에는 상권과 건물 구조처럼 물리적으로 변경하기 어려운 조건과, 예산·직원 구성·매장 철학처럼 선택에 따라 조정할 수 있지만 당장은 유지하기로 한 조건이 함께 포함되는 경우가 있다.",
            ),
            BilingualMemorySpec(
                "UM",
                "The head of New Wave Cafe Culture believes that a consultant can provide a good starting point, but continually testing and developing recipes and operating methods is ultimately the café owner's responsibility.",
                "New Wave Cafe Culture의 대표는 자신이 좋은 출발점을 제공할 수는 있지만, 레시피와 운영 방식을 계속 시험하고 발전시키는 일은 결국 카페 사장의 몫이라고 생각한다.",
            ),
            BilingualMemorySpec(
                "PP",
                "When transferring a recipe, do not present it as a finished correct answer; include repeated preparation, blind comparison with other products, and regular subsequent revision in the process.",
                "레시피를 전수할 때 이를 완성된 정답으로 제시하지 않고, 반복 제작, 다른 제품과의 블라인드 비교, 이후의 정기적인 수정을 과정에 포함한다.",
            ),
            BilingualMemorySpec(
                "KB",
                "Because hot espresso quickly melts the ice in an iced Americano, use chilled water rather than water near room temperature and fill the cup with enough ice to account for the time before it is served.",
                "아이스 아메리카노는 뜨거운 에스프레소로 얼음이 빠르게 녹으므로 상온에 가까운 물보다 냉수를 사용하고, 제공 시점까지 고려하여 컵에 얼음을 충분히 채운다.",
            ),
            BilingualMemorySpec(
                "KB",
                "Residue inside an ice machine can leave an unpleasant taste in iced drinks even when the visible surfaces look clean, so clean the interior as well as the visible parts on a regular basis.",
                "제빙기 내부에 물때가 쌓이면 겉으로는 깨끗해 보여도 아이스 음료에 좋지 않은 맛이 남을 수 있으므로, 보이는 부분뿐 아니라 내부까지 정기적으로 관리한다.",
            ),
        ),
    ),
)


_TASK_3_AUTHORITY = (
    ContextSpec("task-3/friend-cafe"),
    ContextSpec(
        "task-3/friend-cafe/conditions",
        (
            BilingualMemorySpec(
                "KB",
                "The friend's café is located where a district of embassies, consulates, and business facilities overlaps with a university area, so both professionals and university students use it.",
                "친구의 카페는 대사관·영사관과 업무 시설이 모인 지역과 대학 상권이 겹치는 곳에 있어, 직장인과 대학생의 이용이 함께 나타난다.",
            ),
            BilingualMemorySpec(
                "PP",
                "Rather than expanding the number of recommended menu items, the friend prioritizes serving core coffees and signature items at consistent quality on every visit.",
                "친구는 추천 메뉴의 가짓수를 넓히기보다, 핵심 커피와 대표 메뉴를 방문할 때마다 일관된 품질로 제공하는 것을 우선한다.",
            ),
            BilingualMemorySpec(
                "KB",
                "The friend maintains the café's social media feed consistently but does not feel that many customers say they visited because of it. The friend instead believes that direct recommendations through nearby professionals, university students, and local networks have a greater effect on actual visits.",
                "친구는 카페의 소셜미디어 피드를 꾸준히 운영하고 있지만, 이를 보고 방문했다고 말하는 손님이 많다는 느낌은 받지 못하고 있다. 오히려 인근 직장인·대학생과 지역 네트워크를 통한 직접적인 추천이 실제 방문에 더 큰 영향을 준다고 생각한다.",
            ),
            BilingualMemorySpec(
                "UM",
                "The friend wants an atmosphere that allows natural conversation rather than complete silence while still feeling credible for business meetings. Studying and small university-student gatherings are welcome, but the friend does not want groups to make the entire space noisy.",
                "친구는 완전히 조용한 공간보다는 자연스러운 대화가 가능하면서도 업무 미팅에 신뢰감을 줄 수 있는 분위기를 원한다. 대학생의 공부와 소규모 모임은 괜찮지만, 단체 손님이 몰려 공간 전체가 시끄러워지는 분위기는 원하지 않는다.",
            ),
            BilingualMemorySpec(
                "UM",
                "The friend wants to hear, from a customer's perspective, which aspects of using a café feel important and what influences satisfaction or willingness to return.",
                "친구는 참가자에게 손님의 입장에서 카페를 이용할 때 어떤 점이 중요하게 느껴지는지, 무엇이 만족이나 재방문 의사에 영향을 주는지 듣고 싶어 한다.",
            ),
            BilingualMemorySpec(
                "KB",
                "The café is midsized, slightly larger than a small independent café, and is organized mainly around seating suitable for conversations or meetings of two to four people. The furniture and interior have already been selected to fit the café's atmosphere, so there is no plan for major changes to the interior or seating arrangement this time.",
                "매장은 소형 개인 카페보다 조금 큰 중형 규모이며, 2–4명이 대화하거나 미팅하기 좋은 좌석을 중심으로 구성되어 있다. 가구와 인테리어는 이미 매장의 분위기에 맞게 선택되어 있어, 이번에는 인테리어나 좌석 배치를 크게 변경할 계획이 없다.",
            ),
            BilingualMemorySpec(
                "KB",
                "The friend previously tested longer business hours, but the results after additional costs were not clear, so the friend plans to keep the current hours. Instead, the friend feels the current staff cannot provide reliably stable service when professional and university-student traffic overlaps and believes additional staff need to be hired.",
                "친구는 이전에 영업시간 연장을 시험했지만 추가 비용을 고려한 성과가 뚜렷하지 않아 현재 영업시간을 유지하려 한다. 대신 직장인과 대학생의 이용이 겹치는 시간대에는 현재 인력만으로 안정적인 응대가 어렵다고 느껴, 직원을 추가로 채용할 필요가 있다고 생각한다.",
            ),
            BilingualMemorySpec(
                "OM",
                "Large family groups rarely visit this area, and large family gatherings are not a core use scenario that the café prioritizes.",
                "이 상권에서는 가족 단위 손님이 단체로 방문하는 경우가 드물며, 가족 단위의 대규모 모임은 카페가 우선적으로 고려하는 핵심 이용 시나리오가 아니다.",
            ),
        ),
    ),
)


_SOURCE_PERMISSIONS = (
    "READ",
    "EMBED",
    "DERIVE",
    "COMBINE",
    "EXPORT",
    "SAVE_BOUND_ANALYSIS",
    "SAVE_ANALYSIS",
)


_TASK_CONTEXT_SPECS = {
    1: (
        (*_PRACTICE, ContextSpec("task-1")),
        _TASK_1_AUTHORITY,
        (
            ScenarioGrantSpec(
                key="coffee-v1-task-1-customer-perspectives",
                authority_context="task-1/customer-perspectives",
                attachment_context="task-1",
                public_name="task-1/customer-perspectives",
                permissions=_SOURCE_PERMISSIONS,
                recursive=True,
            ),
        ),
    ),
    2: (
        (ContextSpec("task-2"),),
        _TASK_2_AUTHORITY,
        (
            ScenarioGrantSpec(
                key="coffee-v1-task-2-operational-perspectives",
                authority_context="task-2/operational-perspectives",
                attachment_context="task-2",
                public_name="task-2/operational-perspectives",
                permissions=_SOURCE_PERMISSIONS,
                recursive=True,
            ),
        ),
    ),
    3: (
        (ContextSpec("task-3"),),
        _TASK_3_AUTHORITY,
        (
            ScenarioGrantSpec(
                key="coffee-v1-task-3-friend-conditions",
                authority_context="task-3/friend-cafe/conditions",
                attachment_context="task-3",
                public_name="task-3/friend-cafe/conditions",
                permissions=_SOURCE_PERMISSIONS,
                recursive=False,
            ),
            ScenarioGrantSpec(
                key="coffee-v1-task-3-friend-share-endpoint",
                authority_context="task-3/friend-cafe",
                attachment_context="task-3",
                public_name="task-3/friend-cafe",
                permissions=("SHARE",),
                recursive=False,
            ),
        ),
    ),
}


def _stable_uid(kind: str, *parts: object) -> str:
    return str(
        uuid.uuid5(
            _SCENARIO_NAMESPACE,
            "\0".join((kind, *(str(part) for part in parts))),
        )
    )


def _build_contexts(
    role: str,
    specs: tuple[ContextSpec, ...],
) -> tuple[tuple[Context, ...], tuple[TranslationCatalog, ...]]:
    contexts: list[Context] = []
    catalogs: list[TranslationCatalog] = []
    for spec in specs:
        context = Context(
            uid=_stable_uid("context", role, spec.name),
            name=spec.name,
        )
        translations: list[tuple[Memory, BilingualMemorySpec]] = []
        for index, memory_spec in enumerate(spec.memories, start=1):
            memory = Memory(
                uid=_stable_uid(
                    "memory",
                    role,
                    spec.name,
                    index,
                    memory_spec.purpose,
                ),
                content=memory_spec.en,
            )
            context.add(memory)
            translations.append((memory, memory_spec))
        contexts.append(context)
        if translations:
            catalog = TranslationCatalog.empty(
                context,
                "ko",
                created_at=_CATALOG_TIMESTAMP,
            )
            for memory, memory_spec in translations:
                evidence = hashlib.sha256(
                    (memory_spec.en + "\0" + memory_spec.ko).encode("utf-8")
                ).hexdigest()
                catalog = catalog.with_curated(
                    context,
                    memory.uid,
                    memory_spec.ko,
                    origin=TRANSLATION_ORIGIN_IMPORTED,
                    evidence_sha256=evidence,
                    updated_at=_CATALOG_TIMESTAMP,
                )
            catalogs.append(catalog)
    return tuple(contexts), tuple(catalogs)


def _scenario_digest() -> str:
    payload: dict[str, object] = {
        "scenario_id": COFFEE_V1_SCENARIO_ID,
        "canonical_language": "en",
        "translation_languages": ["ko"],
        "tasks": [],
    }
    raw_tasks = payload["tasks"]
    assert isinstance(raw_tasks, list)
    for task in (1, 2, 3):
        participant_specs, authority_specs, grants = _TASK_CONTEXT_SPECS[task]
        raw_tasks.append(
            {
                "task": task,
                "participant": [
                    {
                        "name": spec.name,
                        "memories": [
                            {
                                "purpose": item.purpose,
                                "en": item.en,
                                "ko": item.ko,
                            }
                            for item in spec.memories
                        ],
                    }
                    for spec in participant_specs
                ],
                "authority": [
                    {
                        "name": spec.name,
                        "memories": [
                            {
                                "purpose": item.purpose,
                                "en": item.en,
                                "ko": item.ko,
                            }
                            for item in spec.memories
                        ],
                    }
                    for spec in authority_specs
                ],
                "grants": [grant.__dict__ for grant in grants],
            }
        )
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


COFFEE_V1_DIGEST = "fdfd2fd1f788723c0eb56b2a2f3838e16e9b073e3e9719c72800a0c920f5ffce"
if _scenario_digest() != COFFEE_V1_DIGEST:
    # A versioned Study command must never keep its name while its experiment
    # changes. Bump the scenario identifier and pin a new digest deliberately.
    raise RuntimeError("coffee-v1 data changed without a scenario version bump.")


def build_coffee_v1_scenario() -> StudyScenario:
    """Return fresh mutable Context objects for one Coffee Study run."""

    tasks: list[StudyScenarioTask] = []
    for task in (1, 2, 3):
        participant_specs, authority_specs, grants = _TASK_CONTEXT_SPECS[task]
        participant_contexts, participant_catalogs = _build_contexts(
            f"task-{task}:participant",
            participant_specs,
        )
        authority_contexts, authority_catalogs = _build_contexts(
            f"task-{task}:authority",
            authority_specs,
        )
        tasks.append(
            StudyScenarioTask(
                task=task,
                participant_current=("practice" if task == 1 else f"task-{task}"),
                authority_current=authority_specs[0].name,
                participant_contexts=participant_contexts,
                authority_contexts=authority_contexts,
                participant_catalogs=participant_catalogs,
                authority_catalogs=authority_catalogs,
                grants=grants,
            )
        )
    return StudyScenario(
        scenario_id=COFFEE_V1_SCENARIO_ID,
        baseline_uid=COFFEE_V1_BASELINE_UID,
        digest=COFFEE_V1_DIGEST,
        tasks=tuple(tasks),
    )
